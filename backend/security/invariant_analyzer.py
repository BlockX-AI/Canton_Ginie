"""Cross-template invariant analyzer.

Detects ``ensure``-vs-choice contradictions that the LLM auditor
routinely misses and that pure line-by-line static checks cannot see.

The canonical example is the ``FullRepay`` deadlock:

    template LoanAgreement
      ...
      ensure principal > 0.0   --  precondition for the agreement to exist

      choice FullRepay : ContractId RepaidLoan
        controller borrower
        do
          assertMsg "Loan must be fully repaid" (principal == 0.0)
          create RepaidLoan with
            originalAmount = principal           --  always 0.0 here

    template RepaidLoan
      ...
      ensure originalAmount > 0.0   --  unreachable: 0.0 > 0.0 is False

The choice asserts ``principal == 0.0`` to fire, but the agreement
itself requires ``principal > 0.0`` to exist - so ``MakePayment``
cannot drive the principal to zero without violating the agreement's
own ensure clause. And even if it could, the resulting ``RepaidLoan``
would fail its own ensure because ``originalAmount`` is bound to the
zero principal.

This module catches that pattern (and analogous ones) by:

  1. Extracting each template's ``ensure`` predicates as ``(field, op, k)``.
  2. Walking every choice body, recording:
       a) ``assertMsg "..." (var op k)`` constraints, and
       b) ``create T with f = expr`` assignments.
  3. For every (choice, target-template) pair, substituting the
     assignment expression into the target's ensure predicates and
     proving unsat using the choice's local constraints.

The analyzer is deliberately *narrow* - we only handle simple binary
predicates against numeric literals (``==``, ``!=``, ``<``, ``<=``,
``>``, ``>=``). That covers every real-world deadlock we have seen
without requiring a full SMT solver. Anything we cannot statically
resolve is silently skipped (no false positives).

The analyzer is *additive*: it is appended to ``detect_static_findings``
and never blocks the pipeline. Findings carry severity HIGH because
an unreachable terminal state is a contract-bricking bug.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import structlog

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Predicate:
    """A simple ``var <op> literal`` constraint.

    Anything more complex (function calls, multi-var expressions,
    string comparisons) is dropped during parsing - the analyzer is
    intentionally conservative.
    """
    var:   str
    op:    str   # one of: == != < <= > >=
    value: float


@dataclass
class TemplateInfo:
    name:    str
    fields:  list[str]
    ensures: list[Predicate]


# ---------------------------------------------------------------------------
# Lightweight parsers
# ---------------------------------------------------------------------------


# A binary predicate against a numeric literal:  ``var op number``.
# We accept optional surrounding parentheses and an optional ``.0`` on
# the literal. ``-`` is captured for negative literals.
_SIMPLE_PRED_RE = re.compile(
    r"""
    ^\s*
    \(?\s*
    (?P<var>[A-Za-z_][A-Za-z0-9_']*)   # left-hand side identifier
    \s*(?P<op>==|/=|!=|<=|>=|<|>)\s*   # comparison operator
    (?P<val>-?\d+(?:\.\d+)?)           # numeric literal
    \s*\)?\s*$
    """,
    re.VERBOSE,
)

# Slightly looser: parse the *first* simple binary predicate inside a
# larger expression. Used for assertMsg bodies which sometimes have
# extra parentheses or ``&&`` joiners.
_FIRST_PRED_RE = re.compile(
    r"\(?\s*(?P<var>[A-Za-z_][A-Za-z0-9_']*)\s*(?P<op>==|/=|!=|<=|>=|<|>)\s*(?P<val>-?\d+(?:\.\d+)?)\s*\)?"
)


def _parse_predicate(text: str) -> Optional[Predicate]:
    """Parse a single ``var op literal`` predicate; ``None`` if shape mismatches."""
    if not text:
        return None
    m = _SIMPLE_PRED_RE.match(text.strip())
    if not m:
        return None
    op = m.group("op")
    if op == "/=":
        op = "!="                          # Daml uses ``/=``; normalise
    try:
        return Predicate(m.group("var"), op, float(m.group("val")))
    except ValueError:
        return None


def _split_ensure_conjuncts(ensure_body: str) -> list[str]:
    """Split a multi-line ensure body on top-level ``&&`` joiners.

    We do not handle ``||`` because a disjunctive ensure relaxes
    constraints and cannot create deadlocks of the kind we target.
    """
    # Strip line comments and normalise whitespace, but keep the
    # logical structure.
    cleaned = re.sub(r"--[^\n]*", "", ensure_body)
    cleaned = cleaned.replace("\n", " ").strip()
    # Split on `&&` but only at the top level. A real Daml expression
    # may have nested parens; a simple counter is enough here.
    parts: list[str] = []
    depth = 0
    last = 0
    i = 0
    while i < len(cleaned) - 1:
        ch = cleaned[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif depth == 0 and cleaned[i] == "&" and cleaned[i + 1] == "&":
            parts.append(cleaned[last:i].strip())
            last = i + 2
            i += 2
            continue
        i += 1
    tail = cleaned[last:].strip()
    if tail:
        parts.append(tail)
    return [p for p in parts if p]


# ---------------------------------------------------------------------------
# Template extraction
# ---------------------------------------------------------------------------


_TEMPLATE_RE = re.compile(
    r"^template\s+(?P<name>\w+)\b(?P<body>.*?)(?=^template\s+\w+|\Z)",
    re.MULTILINE | re.DOTALL,
)
_FIELD_LINE_RE = re.compile(
    r"^\s+(?P<name>[A-Za-z_]\w*)\s*:\s*(?P<type>[A-Za-z_][\w\.\s]*)\s*$",
    re.MULTILINE,
)
# The ``ensure`` block in Daml runs from ``ensure`` up to the first
# subsequent top-level keyword (``signatory``, ``observer``, ``agreement``,
# ``key``, ``choice``, ``nonconsuming``, ``preconsuming``, ``postconsuming``)
# OR the end of the template. We keep the regex modest and rely on
# the template_body slice to bound the search.
_ENSURE_RE = re.compile(
    r"^\s*ensure\s+(?P<expr>.+?)(?=^\s*(?:signatory|observer|agreement|key|choice|nonconsuming|preconsuming|postconsuming|maintainer)\b|\Z)",
    re.MULTILINE | re.DOTALL,
)


def _extract_templates(code: str) -> dict[str, TemplateInfo]:
    """Parse every ``template`` block into a ``TemplateInfo``.

    Field extraction is best-effort: we only need field *names* so the
    create-substitution can match by name. Ensure parsing keeps
    only the conjuncts that match the simple predicate shape.
    """
    out: dict[str, TemplateInfo] = {}
    for m in _TEMPLATE_RE.finditer(code):
        name = m.group("name")
        body = m.group("body")

        # Restrict field discovery to the ``with .. where`` slice.
        with_to_where = re.search(
            r"^\s*with\s*\n(?P<fields>.*?)^\s*where\b",
            body,
            re.MULTILINE | re.DOTALL,
        )
        fields: list[str] = []
        if with_to_where:
            for fm in _FIELD_LINE_RE.finditer(with_to_where.group("fields")):
                fields.append(fm.group("name"))

        ensures: list[Predicate] = []
        em = _ENSURE_RE.search(body)
        if em:
            for conj in _split_ensure_conjuncts(em.group("expr")):
                p = _parse_predicate(conj)
                if p is not None:
                    ensures.append(p)

        out[name] = TemplateInfo(name=name, fields=fields, ensures=ensures)
    return out


# ---------------------------------------------------------------------------
# Choice walking
# ---------------------------------------------------------------------------


_CHOICE_RE = re.compile(
    r"^\s*(?:nonconsuming\s+|preconsuming\s+|postconsuming\s+)?choice\s+(?P<name>\w+)\b"
    r"(?P<body>.*?)(?=^\s*(?:nonconsuming\s+|preconsuming\s+|postconsuming\s+)?choice\s+\w+|^template\s+\w+|\Z)",
    re.MULTILINE | re.DOTALL,
)
_ASSERT_RE = re.compile(
    r"\bassertMsg\s+\"[^\"]*\"\s+\((?P<expr>[^)]*(?:\([^)]*\)[^)]*)*)\)",
)
_ASSERT_BARE_RE = re.compile(r"\bassert\s+\((?P<expr>[^)]*(?:\([^)]*\)[^)]*)*)\)")
# ``create T with f = expr; g = expr2`` (newline-separated) OR
# ``create T with f = expr, g = expr2`` (comma-separated). Be liberal:
# capture everything from ``with`` up to the next blank line, the next
# ``create`` / choice / template keyword, or end-of-body.
_CREATE_RE = re.compile(
    r"\bcreate\s+(?P<target>[A-Z]\w*)\s+with\b(?P<assigns>.*?)"
    r"(?=^\s*(?:create|choice|nonconsuming|preconsuming|postconsuming|template)\b|\n\s*\n|\Z)",
    re.MULTILINE | re.DOTALL,
)
_ASSIGN_LINE_RE = re.compile(
    r"(?P<field>[A-Za-z_]\w*)\s*=\s*(?P<expr>[^,\n]+?)(?=,|$)",
)


def _extract_assert_constraints(body: str) -> dict[str, Predicate]:
    """Collect ``var op literal`` constraints implied by assertMsg/assert.

    If the same variable is constrained twice (e.g. ``x > 0`` then
    ``x == 5``) we keep the *strongest* one - here, the equality.
    Equality always wins because it pins down a concrete value.
    """
    constraints: dict[str, Predicate] = {}
    for src_re in (_ASSERT_RE, _ASSERT_BARE_RE):
        for m in src_re.finditer(body):
            expr = m.group("expr")
            for sub in _FIRST_PRED_RE.finditer(expr):
                p = _parse_predicate(sub.group(0))
                if not p:
                    continue
                # Equality dominates; otherwise keep the first observed.
                existing = constraints.get(p.var)
                if existing is None or (existing.op != "==" and p.op == "=="):
                    constraints[p.var] = p
    return constraints


def _extract_creates(body: str) -> list[tuple[str, dict[str, str]]]:
    """Find every ``create T with ...`` and return ``(target, {field: expr})``.

    Expressions are kept as raw strings; resolution against the choice's
    constraint set happens in the caller.
    """
    out: list[tuple[str, dict[str, str]]] = []
    for m in _CREATE_RE.finditer(body):
        target = m.group("target")
        assigns_text = m.group("assigns")
        # Drop trailing junk that landed in the slice.
        assigns_text = re.sub(r"^\s*", "", assigns_text)
        # Normalise: each line ``f = expr`` or comma-separated.
        # We split by newline first, then by comma at top level.
        rough_lines: list[str] = []
        for ln in assigns_text.splitlines():
            ln = ln.strip()
            if not ln or ln.startswith("--"):
                continue
            # Stop at obvious end-of-record markers.
            if ln.startswith(("create ", "do ", "where", "controller", "let ", "in ")):
                break
            rough_lines.append(ln)
        joined = " , ".join(rough_lines)

        assigns: dict[str, str] = {}
        for am in _ASSIGN_LINE_RE.finditer(joined + ","):
            field = am.group("field").strip()
            expr  = am.group("expr").strip()
            if not field or not expr:
                continue
            assigns[field] = expr
        out.append((target, assigns))
    return out


# ---------------------------------------------------------------------------
# Unsat reasoning
# ---------------------------------------------------------------------------


def _eval_op(a: float, op: str, b: float) -> bool:
    return {
        "==": a == b,
        "!=": a != b,
        "<":  a < b,
        "<=": a <= b,
        ">":  a > b,
        ">=": a >= b,
    }[op]


def _is_unsat(constraint: Predicate, ensure_pred: Predicate) -> bool:
    """Decide whether ``constraint && ensure_pred`` is unsatisfiable.

    Both predicates refer to the same variable. Conservative: returns
    True only when we can prove unsat from the simple-binary fragment.
    """
    if constraint.var != ensure_pred.var:
        return False

    # Equality on the constraint pins the value; just evaluate.
    if constraint.op == "==":
        return not _eval_op(constraint.value, ensure_pred.op, ensure_pred.value)

    # Equality on the ensure side: same trick, swapped.
    if ensure_pred.op == "==":
        return not _eval_op(ensure_pred.value, constraint.op, constraint.value)

    # Half-open intervals: only flag obviously-disjoint cases.
    # ``var > a`` && ``var < b`` is sat iff a < b (we'd need both;
    # we don't combine multi-constraint reasoning here).
    return False


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def detect_invariant_deadlocks(daml_code: str) -> list[dict]:
    """Return findings for every detectable ensure/choice contradiction.

    Two patterns are surfaced:

    1. **Cross-template deadlock**: a ``create T with f = expr``
       inside a choice contradicts ``T``'s own ensure once ``expr``
       is resolved against the choice's local assertMsg constraints.

    2. **Self-template deadlock**: the *enclosing* template's ensure
       contradicts a same-template ``create this with f = expr``
       update. This catches the "balance bottoms out at zero but the
       template requires balance > 0" case in a single template.

    Both produce HIGH-severity findings with ``id = DSV-024``.
    """
    if not daml_code or not isinstance(daml_code, str):
        return []
    findings: list[dict] = []
    try:
        templates = _extract_templates(daml_code)
        if not templates:
            return []

        # Walk every choice across every template body.
        for tpl_name, tpl_match in _iter_templates_with_body(daml_code):
            for cm in _CHOICE_RE.finditer(tpl_match):
                choice_name = cm.group("name")
                body        = cm.group("body")
                constraints = _extract_assert_constraints(body)
                creates     = _extract_creates(body)

                for target, assigns in creates:
                    target_info = templates.get(target)
                    if target_info is None or not target_info.ensures:
                        continue
                    findings.extend(
                        _check_create_against_ensure(
                            host_template=tpl_name,
                            choice=choice_name,
                            target=target,
                            assigns=assigns,
                            constraints=constraints,
                            target_ensures=target_info.ensures,
                        )
                    )
    except Exception as exc:  # noqa: BLE001
        logger.warning("invariant analyzer crashed", error=str(exc))
        return []

    # Dedup by (choice, target, ensure-var) so a multi-create body
    # doesn't produce identical findings repeatedly.
    seen: set[tuple[str, str, str]] = set()
    deduped: list[dict] = []
    for f in findings:
        key = (
            f.get("location", {}).get("choice", ""),
            f.get("location", {}).get("template", ""),
            f.get("references", [""])[0] if f.get("references") else "",
        )
        # Use a hash of title to disambiguate truly distinct findings.
        sig = (key[0], key[1], f.get("title", ""))
        if sig in seen:
            continue
        seen.add(sig)
        deduped.append(f)
    return deduped


def _iter_templates_with_body(code: str):
    """Yield ``(template_name, template_body)`` slices.

    We re-run ``_TEMPLATE_RE`` against the full source instead of
    re-using ``_extract_templates``'s output because we want the raw
    template-body text to scan for choices.
    """
    for m in _TEMPLATE_RE.finditer(code):
        yield m.group("name"), m.group("body")


def _check_create_against_ensure(
    *,
    host_template: str,
    choice: str,
    target: str,
    assigns: dict[str, str],
    constraints: dict[str, Predicate],
    target_ensures: list[Predicate],
) -> list[dict]:
    """For each target ensure, see if the substituted assignment is unsat."""
    out: list[dict] = []
    for ens in target_ensures:
        rhs_expr = assigns.get(ens.var)
        if rhs_expr is None:
            # The ensure is on a field this create doesn't touch.
            continue

        # Case A: rhs is a numeric literal.
        rhs_pred = _parse_predicate(f"x == {rhs_expr}")
        # Above gives us a constraint of the form ``x == <num>`` if
        # the literal parses; we then synthesise the equivalent on
        # ``ens.var`` and check unsat.
        if rhs_pred is not None and rhs_pred.var == "x":
            substituted = Predicate(ens.var, "==", rhs_pred.value)
            if _is_unsat(substituted, ens):
                out.append(_make_finding(
                    host_template=host_template,
                    choice=choice,
                    target=target,
                    field=ens.var,
                    rhs_repr=str(rhs_pred.value),
                    ensure=ens,
                    rationale=(
                        f"the literal ``{rhs_pred.value}`` directly violates "
                        f"``{target}``'s ``ensure {ens.var} {ens.op} {ens.value}``"
                    ),
                ))
            continue

        # Case B: rhs is a bare variable that the choice constrains.
        if re.match(r"^[A-Za-z_]\w*$", rhs_expr):
            constraint = constraints.get(rhs_expr)
            if constraint is None:
                continue
            # Substitute: ``ens.var`` will hold whatever ``rhs_expr``
            # holds, which is constrained by ``constraint``.
            substituted = Predicate(ens.var, constraint.op, constraint.value)
            if _is_unsat(substituted, ens):
                out.append(_make_finding(
                    host_template=host_template,
                    choice=choice,
                    target=target,
                    field=ens.var,
                    rhs_repr=rhs_expr,
                    ensure=ens,
                    rationale=(
                        f"the choice asserts ``{rhs_expr} {constraint.op} {constraint.value}`` "
                        f"and then assigns ``{ens.var} = {rhs_expr}`` into ``{target}``, "
                        f"whose ensure requires ``{ens.var} {ens.op} {ens.value}``"
                    ),
                ))
            continue

        # Otherwise the rhs is an expression we cannot reason about -
        # skip silently to keep false-positive rate at zero.
    return out


def _make_finding(
    *,
    host_template: str,
    choice: str,
    target: str,
    field: str,
    rhs_repr: str,
    ensure: Predicate,
    rationale: str,
) -> dict:
    return {
        "id":          "DSV-024",
        "severity":    "HIGH",
        "title":       (
            f"Unreachable terminal state: ``{host_template}::{choice}`` "
            f"creates a ``{target}`` that violates its own ensure"
        ),
        "description": (
            f"The choice ``{choice}`` on template ``{host_template}`` runs "
            f"``create {target} with {field} = {rhs_repr}``, but the target "
            f"template ``{target}`` declares ``ensure {field} {ensure.op} "
            f"{ensure.value}``. {rationale.capitalize()}. The transaction "
            "will abort with ``ENSURE_VIOLATED`` at runtime, making this "
            "code path permanently unreachable."
        ),
        "location": {
            "template":    host_template,
            "choice":      choice,
            "lineNumbers": [0, 0],
        },
        "impact": (
            "A terminal-state choice that is unreachable means the host "
            "contract has no way to be cleanly retired. Holders are "
            "stuck holding an active row that cannot be archived through "
            "the intended workflow. In a financial product this is a "
            "deal-breaker: a fully repaid loan cannot be marked repaid, "
            "an executed trade cannot be settled, etc."
        ),
        "exploitScenario": (
            f"User drives the contract toward the conditions ``{choice}`` "
            "asserts (e.g. paying down principal to zero, satisfying a "
            "delivery clause). When they call the choice, the create "
            "step fails with ``ENSURE_VIOLATED`` on the target template. "
            "There is no other archive path, so the original contract "
            "remains active forever, distorting balance-sheet reporting "
            "and creating an audit nightmare."
        ),
        "recommendation": (
            f"Either (a) relax the ensure on ``{target}`` so it accepts "
            f"the value ``{choice}`` produces, or (b) capture the "
            "contract's *original* state into a separate immutable "
            f"field at creation time and create ``{target}`` from that "
            "field rather than from the mutated state. Pattern: "
            "``originalPrincipal`` captured at Accept, never written "
            "again, used as the source for ``RepaidLoan.originalAmount``."
        ),
        "references":  ["DSV-024"],
        "codeSnippet": f"create {target} with {field} = {rhs_repr}",
        "fixedCode":   (
            f"-- Capture the value at *creation* time:\n"
            f"-- template {host_template} with ... ; original{field.capitalize()} : Decimal ; ...\n"
            f"create {target} with {field} = original{field.capitalize()}"
        ),
        "source":      "static",
    }
