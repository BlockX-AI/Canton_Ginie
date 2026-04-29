"""Deterministic static checks on Daml source.

These checks run *unconditionally* alongside the LLM-based audit \u2014
they are cheap regex/line scans, so they always produce findings even
when the LLM phase times out, returns malformed JSON, or simply misses
a structural bug.

Why not rely on the LLM alone?
------------------------------
The audit LLM is great at semantic vulnerabilities ("this controller
can drain funds") but flaky at *structural* bugs that look fine line
by line. The canonical example is a no-op state-transition choice:

    choice ApproveInvoice : ContractId Invoice
      controller client
      do
        assertMsg "Invoice already approved" (vendor /= client)
        create this           -- re-creates with NO field changes

The LLM happily reads this as "an Approve choice exists" and gives the
contract a passing security score. But the choice has no effect on
ledger state \u2014 there's no `status` flag, no field mutation, just
``archive self`` (implicit, consuming) followed by ``create this``
which rebuilds an identical row. Any subsequent ``PayInvoice`` works
on either the original or the "approved" copy with no enforcement of
ordering. This is a real, deployable bug that the LLM missed.

A regex over the choice body catches this in milliseconds and
contributes a HIGH-severity finding to the combined audit result.

Each check returns zero or more *finding* dicts shaped to merge
cleanly with the LLM audit's ``findings`` list (same keys, same
``severity`` values).
"""

from __future__ import annotations

import re
from typing import Iterable

import structlog

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# A *choice block* is everything from `choice <Name>` (or
# `nonconsuming choice <Name>`) up to the next top-level `choice`,
# `template`, or end-of-file. We don't try to parse Daml \u2014 we just
# slice on these anchors. False-positives are filtered later by the
# specific checks.
_CHOICE_ANCHOR = re.compile(
    r"^\s*(?:nonconsuming\s+|preconsuming\s+|postconsuming\s+)?choice\s+(\w+)\b",
    re.MULTILINE,
)
_TEMPLATE_ANCHOR = re.compile(r"^\s*template\s+(\w+)\b", re.MULTILINE)


def _iter_choice_blocks(source: str) -> Iterable[tuple[str, str, int]]:
    """Yield ``(choice_name, body_text, start_line)`` for every choice.

    The ``body_text`` includes everything from the ``choice`` keyword
    up to (but not including) the next ``choice`` / ``template`` / EOF
    so it captures the ``with``, ``controller``, and ``do`` blocks.
    """
    anchors: list[tuple[int, str]] = []
    for m in _CHOICE_ANCHOR.finditer(source):
        anchors.append((m.start(), m.group(1)))
    for m in _TEMPLATE_ANCHOR.finditer(source):
        anchors.append((m.start(), "__TEMPLATE__"))

    anchors.sort(key=lambda x: x[0])

    for i, (start, name) in enumerate(anchors):
        if name == "__TEMPLATE__":
            continue
        end = anchors[i + 1][0] if i + 1 < len(anchors) else len(source)
        body = source[start:end]
        line_no = source[:start].count("\n") + 1
        yield name, body, line_no


def _strip_comments(text: str) -> str:
    """Drop ``--`` line comments so they don't trigger the regex."""
    return re.sub(r"--[^\n]*", "", text)


# ---------------------------------------------------------------------------
# Check 1: no-op state transition (``create this`` with no mutation)
# ---------------------------------------------------------------------------

# Match ``create this`` that is NOT followed by ``with`` on the same or
# next line. ``create this with field = ...`` mutates the row, which
# is a legitimate state transition and must be allowed.
_CREATE_THIS_RE = re.compile(
    r"\bcreate\s+this\b(?!\s*with\b)",
    re.IGNORECASE,
)


def _check_no_op_state_transition(
    daml_code: str,
) -> list[dict]:
    findings: list[dict] = []
    for choice_name, body, line_no in _iter_choice_blocks(daml_code):
        body_clean = _strip_comments(body)
        if not _CREATE_THIS_RE.search(body_clean):
            continue
        # Filter false positives: if the body has ANY ``create this with``
        # it's a real state transition; we only flag bare ``create this``.
        if re.search(r"\bcreate\s+this\s+with\b", body_clean, re.IGNORECASE):
            continue
        findings.append({
            "id": f"DSV-016::{choice_name}",
            "severity": "HIGH",
            "category": "DAML-Specific Security Vector",
            "title": f"No-op state transition in choice `{choice_name}`",
            "description": (
                f"The consuming choice `{choice_name}` archives the current "
                "contract (consuming default) and then immediately calls "
                "`create this` with no field changes. The resulting row is "
                "byte-identical to the one just archived, so the choice has "
                "no observable effect on ledger state \u2014 it's a no-op "
                "state transition. This typically indicates a missing "
                "`status` field or a forgotten `with` clause that should "
                "set the new state (e.g. `create this with status = Approved`)."
            ),
            "location": {
                "template": None,
                "choice": choice_name,
                "lineNumbers": [line_no, line_no],
            },
            "impact": (
                "The choice cannot enforce any subsequent precondition "
                "(e.g. \u201cmust be approved before payment\u201d) because "
                "there is no state to check. Downstream choices that should "
                "depend on this transition will silently accept un-approved "
                "contracts."
            ),
            "exploitScenario": (
                "A controller exercises a downstream choice (e.g. `Pay`) "
                "directly on the freshly-created contract, skipping the "
                "intended `Approve` gate \u2014 the contract has no field "
                "to record that approval ever happened, so the gate is "
                "unenforceable."
            ),
            "recommendation": (
                "Either (a) add a state field (`status : InvoiceStatus`, "
                "`approved : Bool`, etc.) and write `create this with "
                "status = ...` to record the transition, or (b) remove "
                "the no-op choice entirely if the transition was meant "
                "to be a tag in the transaction stream only."
            ),
            "references": ["DSV-016", "CWE-754", "SC10"],
            "codeSnippet": "create this  -- bare; no `with` clause",
            "fixedCode": "create this with status = Approved",
            "source": "static",
        })
    return findings


# ---------------------------------------------------------------------------
# Check 2: archive-only consuming choice (state-machine flattening)
# ---------------------------------------------------------------------------

# Choice body that does ``archive self`` followed by nothing meaningful
# (return (), pure (), or just whitespace). Such a body collapses every
# distinct outcome (paid / rejected / cancelled) into a single archive
# event, destroying the audit trail.
_ARCHIVE_ONLY_RE = re.compile(
    r"\barchive\s+self\b",
    re.IGNORECASE,
)
_CREATE_ANY_RE = re.compile(r"\bcreate\b\s+(?!this\b)\w+", re.IGNORECASE)


def _check_archive_without_replacement(
    daml_code: str,
) -> list[dict]:
    findings: list[dict] = []
    for choice_name, body, line_no in _iter_choice_blocks(daml_code):
        body_clean = _strip_comments(body)
        if not _ARCHIVE_ONLY_RE.search(body_clean):
            continue
        # If the body also creates *some other* contract type (the typical
        # state-machine pattern: ``archive self; create PaidInvoice ...``),
        # this is a healthy transition.
        if _CREATE_ANY_RE.search(body_clean):
            continue
        # If the body re-creates ``this`` with mutations, that's also fine.
        if re.search(r"\bcreate\s+this\s+with\b", body_clean, re.IGNORECASE):
            continue
        # Skip choices whose business meaning is genuinely "delete and stop"
        # (Reject / Cancel / Withdraw). A heuristic on the choice name is
        # imperfect but sharply reduces noise; the LLM audit can still flag
        # them via business-logic reasoning.
        if re.match(
            r"^(Reject|Cancel|Withdraw|Revoke|Expire|Abort|Decline)",
            choice_name,
            re.IGNORECASE,
        ):
            continue
        findings.append({
            "id": f"DSV-017::{choice_name}",
            "severity": "MEDIUM",
            "category": "DAML-Specific Security Vector",
            "title": f"Archive-only choice `{choice_name}` flattens state machine",
            "description": (
                f"The choice `{choice_name}` ends with `archive self` and "
                "does not create a successor contract. This destroys the "
                "audit trail: a query against the ledger can no longer "
                "distinguish *why* the contract closed (paid? settled? "
                "cancelled?) without scanning the transaction stream for "
                "the choice name."
            ),
            "location": {
                "template": None,
                "choice": choice_name,
                "lineNumbers": [line_no, line_no],
            },
            "impact": (
                "Compliance reporting and downstream analytics cannot "
                "reconstruct the contract's terminal state from active "
                "ledger queries alone. Auditors must replay history."
            ),
            "exploitScenario": (
                "A regulator requests a list of all paid invoices for a "
                "quarter. With archive-only terminal choices the answer "
                "must be derived from the transaction stream rather than "
                "a live `PaidInvoice` template, increasing the chance of "
                "missed records during reconciliation."
            ),
            "recommendation": (
                "Replace `archive self; return ()` with "
                "`archive self; create <SuccessorTemplate> with ...` so "
                "the terminal state is queryable. Reserve bare archive "
                "for genuine \u2018cancel and discard\u2019 choices "
                "(Reject, Cancel, Withdraw, etc.)."
            ),
            "references": ["DSV-017", "DSV-015", "AU-2"],
            "codeSnippet": "archive self; return ()",
            "fixedCode": "archive self; create PaidInvoice with ...",
            "source": "static",
        })
    return findings


# ---------------------------------------------------------------------------
# Check 3: unused imports (cheap nag, cheap to fix)
# ---------------------------------------------------------------------------

# Map import module -> a list of identifiers that, when used in the
# remainder of the source, justify the import. If none of the
# identifiers appear, the import is dead and triggers an OPT finding.
_IMPORT_USAGE: dict[str, list[str]] = {
    "DA.Date": ["addDays", "subDays", "fromGregorian", "toGregorian", "Month",
                "DayOfWeek", "isLeapYear", "subDate"],
    "DA.Time": ["getTime", "addRelTime", "subTime", "toDateUTC", "toTimeOfDay",
                "RelTime", "days", "hours", "minutes", "seconds"],
    "DA.List": ["sortBy", "groupBy", "intercalate", "transpose", "partition",
                "dedup", "dedupBy"],
    "DA.Optional": ["fromOptional", "fromOptionalEx", "catOptionals",
                    "mapOptional"],
    "DA.Text": ["isEmpty", "length", "toLower", "toUpper", "split", "splitOn",
                "intercalate", "replace"],
}


_IMPORT_RE = re.compile(r"^\s*import\s+(?:qualified\s+)?([A-Za-z][A-Za-z0-9_.]+)\b",
                        re.MULTILINE)


def _check_unused_imports(daml_code: str) -> list[dict]:
    findings: list[dict] = []
    src_no_comments = _strip_comments(daml_code)
    for m in _IMPORT_RE.finditer(daml_code):
        module = m.group(1)
        usage_idents = _IMPORT_USAGE.get(module)
        if not usage_idents:
            continue  # we don't have a usage map for this module \u2014 skip
        # Strip the import line itself before searching for usage so the
        # mere presence of the import doesn't mask its own absence.
        body_after_imports = _IMPORT_RE.sub("", src_no_comments)
        if any(re.search(rf"\b{re.escape(ident)}\b", body_after_imports)
               for ident in usage_idents):
            continue
        line_no = daml_code[:m.start()].count("\n") + 1
        findings.append({
            "id": f"DSV-018::{module}",
            "severity": "LOW",
            "category": "Code Quality",
            "title": f"Unused import `{module}`",
            "description": (
                f"`import {module}` is declared but none of its public "
                "identifiers appear in the rest of the module. Daml "
                "compiles fine but the import inflates the module "
                "graph and conflicts with the project's hard-rule that "
                "forbids dead imports."
            ),
            "location": {
                "template": None,
                "choice": None,
                "lineNumbers": [line_no, line_no],
            },
            "impact": (
                "Increases compile-time surface area and may shadow "
                "prelude identifiers when the module is later extended."
            ),
            "exploitScenario": "N/A \u2014 quality finding only.",
            "recommendation": f"Remove `import {module}`.",
            "references": ["DSV-018", "SWC-131"],
            "codeSnippet": m.group(0).strip(),
            "fixedCode": "",
            "source": "static",
        })
    return findings


# ---------------------------------------------------------------------------
# Check 4: consuming no-op choice (the TrackPayment / observation bug)
# ---------------------------------------------------------------------------
#
# A choice that takes no action and is NOT prefixed by ``nonconsuming`` is
# Daml's most insidious footgun: it auto-archives the contract every time
# anyone exercises it. The canonical example is a "Track" or "Log" choice
# the LLM emits to satisfy a "lender can track payments" prompt:
#
#     choice TrackPayment : ()
#       controller lender
#       do
#         return ()        -- archives the loan agreement! \U0001F4A3
#
# This is HIGH severity: the choice destroys live state under a name that
# implies passive observation. Detection criterion: choice block is NOT
# declared ``nonconsuming``, body contains no ``create`` and no
# ``archive``, and the body either ends in ``return ()`` / ``pure ()``
# or is suspiciously short (one statement).

_NONCONSUMING_RE = re.compile(r"^\s*nonconsuming\s+choice\b", re.MULTILINE)
_RETURN_UNIT_RE  = re.compile(r"\b(?:return|pure)\s+\(\)\s*$", re.MULTILINE)
_OBSERVATION_NAME_RE = re.compile(
    r"^(Track|Log|Observe|Check|View|Query|Inspect|Report|Get|Read|Show|"
    r"Validate|Verify|Compute)",
    re.IGNORECASE,
)


def _check_consuming_no_op(daml_code: str) -> list[dict]:
    """Flag consuming choices whose body never creates or archives anything.

    Triggered by names like ``TrackPayment`` (HIGH if the name screams
    observation) or any short, ``return ()``\u2011terminated choice that
    forgets the ``nonconsuming`` keyword. False-positive rate is kept low
    by requiring BOTH no ``create`` AND a ``return ()`` / ``pure ()``
    sentinel.
    """
    findings: list[dict] = []
    for choice_name, body, line_no in _iter_choice_blocks(daml_code):
        body_clean = _strip_comments(body)

        # The choice anchor regex (``^\s*(?:nonconsuming\s+)?choice``)
        # consumes the leading newline due to ``\s*`` so the captured
        # body's first ``\n``-split chunk is empty. Walk forward until
        # we hit the actual ``choice`` declaration line and check that
        # for the ``nonconsuming`` keyword.
        first_nonempty = next(
            (ln for ln in body_clean.split("\n") if ln.strip()),
            "",
        )
        if "nonconsuming" in first_nonempty.lower():
            continue
        # Cross-check: also look at the original source line by line
        # number, in case the body slicing logic ever changes.
        all_lines = daml_code.split("\n")
        if 1 <= line_no <= len(all_lines) and "nonconsuming" in all_lines[line_no - 1].lower():
            continue

        # If the body creates or archives anything, it has a real effect
        # and is correctly consuming. Skip.
        if _CREATE_ANY_RE.search(body_clean) or re.search(r"\bcreate\s+this\b", body_clean):
            continue
        if re.search(r"\barchive\s+self\b", body_clean):
            continue

        # Now confirm the body really is a no-op: must end with ``return ()``
        # or ``pure ()``. Otherwise we may be looking at a complex but
        # legitimate consuming choice (e.g. delegating via ``exercise``).
        if not _RETURN_UNIT_RE.search(body_clean):
            continue

        # Severity escalation when the choice name screams "observation".
        # ``TrackPayment``, ``LogActivity``, ``CheckBalance``, etc. \u2014
        # the user reading this code expects no state change.
        looks_like_observation = bool(_OBSERVATION_NAME_RE.match(choice_name))
        sev = "HIGH" if looks_like_observation else "MEDIUM"

        findings.append({
            "id": f"DSV-019::{choice_name}",
            "severity": sev,
            "category": "DAML-Specific Security Vector",
            "title": (
                f"Consuming no-op choice `{choice_name}` silently archives the contract"
            ),
            "description": (
                f"The choice `{choice_name}` is declared without the "
                "``nonconsuming`` keyword, so Daml treats it as a "
                "consuming choice: every successful exercise auto-archives "
                "the host contract. The body, however, performs no "
                "state transition (no ``create``, no ``archive``, no "
                "successor template) \u2014 it just returns ``()``. The "
                "net effect is that any caller exercising this choice "
                "destroys the contract under a name that implies passive "
                "observation."
            ),
            "location": {
                "template": None,
                "choice": choice_name,
                "lineNumbers": [line_no, line_no],
            },
            "impact": (
                "Live business state is irrecoverably lost the first "
                "time the choice is exercised. For loan / escrow / "
                "subscription contracts this is a single-call denial of "
                "service against the entire agreement."
            ),
            "exploitScenario": (
                f"A counterparty exercises `{choice_name}` believing it "
                "is read-only (per the choice name and zero-effect body); "
                "the live contract is auto-archived and all subsequent "
                "state-mutating choices fail with `CONTRACT_NOT_FOUND`. "
                "Recovery requires re-creating the contract from scratch, "
                "losing the on-ledger history."
            ),
            "recommendation": (
                f"Add the ``nonconsuming`` keyword: "
                f"``nonconsuming choice {choice_name} : ...``. If the "
                "choice is meant to record an event, replace ``return ()`` "
                "with ``create <AuditRecord> with ...`` so the exercise "
                "leaves a queryable trail."
            ),
            "references": ["DSV-019", "DSV-009", "SWC-115"],
            "codeSnippet": f"choice {choice_name} : ()\n  ... do\n    return ()",
            "fixedCode": (
                f"nonconsuming choice {choice_name} : ()\n  ... do\n    return ()"
            ),
            "source": "static",
        })
    return findings


# ---------------------------------------------------------------------------
# Check 5: balance-bearing template missing terminal-state choice
# ---------------------------------------------------------------------------
#
# Catches the loan-agreement deadlock: a template enforces ``loanAmount > 0.0``
# in its ``ensure`` clause and provides a payment choice that subtracts
# from ``loanAmount``, but no choice ever lets the balance reach zero
# cleanly. The final payment becomes un-submittable because the resulting
# contract violates its own invariant.
#
# Detection criterion:
#   1. Template has ``ensure`` containing ``<field> > 0`` (or ``>= 0`` with
#      a strict ``> 0`` guard pattern).
#   2. Some choice subtracts from ``<field>`` (``<field> - <param>``).
#   3. No choice in the template archives without replacement and no
#      choice creates a "Settled" / "Closed" / "Repaid" successor template.

# The ensure clause runs from ``ensure`` until the next blank line or a
# top-level keyword (``choice``, ``signatory``, etc.). We extract it
# first, then look for ``<field> > 0`` patterns INSIDE that block. Doing
# it in one regex is brittle because Daml's ``/=`` (not-equal) contains
# an ``=`` and confuses naive [^=]*? slicing.
_ENSURE_BLOCK_RE = re.compile(
    r"\bensure\b(.+?)(?=^\s*(?:choice|signatory|observer|key|maintainer|template|where)\b|\Z)",
    re.IGNORECASE | re.DOTALL | re.MULTILINE,
)
_FIELD_POS_RE = re.compile(r"\b(\w+)\s*>\s*0(?:\.0+)?\b")


def _check_missing_terminal_state(daml_code: str) -> list[dict]:
    """Flag balance-bearing templates with no closure path."""
    findings: list[dict] = []
    src_no_comments = _strip_comments(daml_code)

    # Slice into top-level template blocks.
    template_anchors = list(_TEMPLATE_ANCHOR.finditer(src_no_comments))
    for i, m in enumerate(template_anchors):
        tname = m.group(1)
        start = m.start()
        end = template_anchors[i + 1].start() if i + 1 < len(template_anchors) else len(src_no_comments)
        block = src_no_comments[start:end]
        line_no = src_no_comments[:start].count("\n") + 1

        ensure_m = _ENSURE_BLOCK_RE.search(block)
        if not ensure_m:
            continue
        ensure_text = ensure_m.group(1)
        # Pick the first ``<field> > 0`` candidate. Skip ``0`` and bare
        # numerals so we don't mis-attribute the field name.
        field = None
        for fm in _FIELD_POS_RE.finditer(ensure_text):
            cand = fm.group(1)
            if cand.isdigit() or cand.lower() in {"and", "or"}:
                continue
            field = cand
            break
        if not field:
            continue

        # Does any choice subtract from this field?
        subtract_re = re.compile(rf"\b{re.escape(field)}\s*-\s*\w+", re.IGNORECASE)
        if not subtract_re.search(block):
            continue

        # Is there a terminal pathway?
        # (a) bare ``archive self`` followed by ``return ()`` / end of choice.
        has_bare_archive = bool(
            re.search(r"\barchive\s+self\b[^\n]*\n[^\n]*?(?:return\s+\(\)|pure\s+\(\)|$)",
                      block, re.IGNORECASE | re.MULTILINE)
        )
        # (b) a choice that creates a ``Settled`` / ``Closed`` / ``Repaid`` /
        # ``Completed`` / ``Paid`` successor.
        has_settled_successor = bool(
            re.search(r"\bcreate\s+(?:Settled|Closed|Repaid|Completed|Paid|Finalised|Finalized)\w*",
                      block, re.IGNORECASE)
        )
        # (c) a choice named ``Close`` / ``Settle`` / ``Finalize`` / ``FullRepay``.
        has_terminal_choice = bool(
            re.search(r"^\s*choice\s+(?:Close|Settle|Finali[sz]e|FullRepay|Complete|Repay|Terminate)\w*",
                      block, re.MULTILINE | re.IGNORECASE)
        )

        if has_bare_archive or has_settled_successor or has_terminal_choice:
            continue

        findings.append({
            "id": f"DSV-020::{tname}",
            "severity": "HIGH",
            "category": "DAML-Specific Security Vector",
            "title": (
                f"Template `{tname}` has no terminal state \u2014 final payment "
                "violates `ensure` clause"
            ),
            "description": (
                f"`{tname}` enforces ``{field} > 0`` in its ``ensure`` clause "
                f"and provides a choice that decreases ``{field}``. There is "
                "no terminal choice (`Close`, `Settle`, `FullRepay`, etc.) "
                "and no successor template (`Settled<Template>`, "
                f"`Repaid<Template>`). Consequently the moment a payment "
                f"would bring ``{field}`` to zero, the resulting contract "
                "fails its own invariant and the transaction aborts with a "
                "cryptic ``ENSURE_VIOLATED`` error \u2014 stranding the "
                "contract permanently in a non-zero state."
            ),
            "location": {
                "template": tname,
                "choice": None,
                "lineNumbers": [line_no, line_no],
            },
            "impact": (
                "The contract enters an unresolvable terminal limbo: the "
                "final payment cannot be submitted, so the agreement can "
                "never be cleanly closed. On-ledger queries will forever "
                "show a tiny non-zero balance with no path to settlement."
            ),
            "exploitScenario": (
                f"Borrower attempts ``MakePayment`` for the exact "
                f"outstanding ``{field}``. Canton evaluates the choice, "
                f"computes ``{field} - paymentAmount = 0``, attempts to "
                "create the resulting contract, the ``ensure`` clause "
                "rejects it. The borrower is told the payment failed and "
                "can never close the loan."
            ),
            "recommendation": (
                f"Add a terminal choice such as ``choice FullRepay`` (or "
                f"``Close`` / ``Settle``) that does ONE of: "
                f"(a) ``archive self`` (clean discard, suitable for "
                "ephemeral agreements), or "
                f"(b) ``create Settled{tname} with ...`` to preserve the "
                "audit trail. Within ``MakePayment``, branch on "
                f"``{field} - paymentAmount == 0`` and call the terminal "
                "path automatically."
            ),
            "references": ["DSV-020", "DSV-015"],
            "codeSnippet": f"ensure {field} > 0.0\n... no terminal choice ...",
            "fixedCode": (
                f"choice FullRepay : ()\n"
                f"  controller borrower\n"
                f"  do\n"
                f"    create Settled{tname} with ...\n"
                f"    pure ()"
            ),
            "source": "static",
        })
    return findings


# ---------------------------------------------------------------------------
# Check 6: unchecked subtraction (overpayment / underflow)
# ---------------------------------------------------------------------------
#
# When a choice does ``balance - paymentAmount`` without first asserting
# ``paymentAmount <= balance``, the user gets an opaque ``ENSURE_VIOLATED``
# error from a downstream invariant rather than a clear "Overpayment not
# allowed" message. This is the V2 loan-agreement MEDIUM-severity finding.

_SUBTRACT_PATTERN = re.compile(
    r"(\w+)\s*-\s*(\w+)",
)


def _check_unchecked_subtraction(daml_code: str) -> list[dict]:
    findings: list[dict] = []
    seen_choices: set[str] = set()
    for choice_name, body, line_no in _iter_choice_blocks(daml_code):
        if choice_name in seen_choices:
            continue
        body_clean = _strip_comments(body)

        # Look only at lines after ``do``; pre-``do`` matches like
        # ``with paymentAmount : Decimal`` would create false positives.
        do_idx = body_clean.find(" do")
        do_block = body_clean[do_idx:] if do_idx > 0 else body_clean

        # Find the FIRST subtraction in the do-block. This deliberately
        # avoids capturing every arithmetic op \u2014 the canonical
        # underflow bug is a single ``balance - param`` in the body.
        sub = _SUBTRACT_PATTERN.search(do_block)
        if not sub:
            continue
        field, param = sub.group(1), sub.group(2)
        # Skip syntactic noise that looks like subtraction but isn't:
        # numeric literals (``- 1.0``), ``with`` parameter signatures,
        # or hyphen-decorated identifiers.
        if field.isdigit() or param.isdigit():
            continue
        if field.lower() in {"with", "do", "where", "controller"}:
            continue

        # If the body already contains an ``assertMsg ... <= field`` or
        # ``assertMsg ... < field`` guard above the subtraction, we're fine.
        guard_re = re.compile(
            rf"assertMsg[^\n]*\b{re.escape(param)}\b[^\n]*<=?\s*\b{re.escape(field)}\b",
            re.IGNORECASE,
        )
        if guard_re.search(do_block):
            continue
        # Symmetric form: assertMsg ... field >= param
        guard_re2 = re.compile(
            rf"assertMsg[^\n]*\b{re.escape(field)}\b[^\n]*>=?\s*\b{re.escape(param)}\b",
            re.IGNORECASE,
        )
        if guard_re2.search(do_block):
            continue

        seen_choices.add(choice_name)
        findings.append({
            "id": f"DSV-021::{choice_name}",
            "severity": "MEDIUM",
            "category": "Logic / Arithmetic Safety",
            "title": (
                f"Choice `{choice_name}` subtracts `{param}` from `{field}` "
                "without bounds check"
            ),
            "description": (
                f"The body of `{choice_name}` computes ``{field} - {param}`` "
                "but no preceding ``assertMsg`` enforces "
                f"``{param} <= {field}``. If ``{param}`` exceeds "
                f"``{field}`` the result becomes negative and is "
                "subsequently rejected by a template-level ``ensure`` "
                "clause \u2014 producing an opaque ``ENSURE_VIOLATED`` "
                "error to the user instead of an explicit overpayment "
                "message."
            ),
            "location": {
                "template": None,
                "choice": choice_name,
                "lineNumbers": [line_no, line_no],
            },
            "impact": (
                "End users see a cryptic invariant-violation error and "
                "cannot tell whether they paid too much, too little, or "
                "violated some other rule. Support burden increases; "
                "audit trails record the failed transaction without a "
                "human-readable cause."
            ),
            "exploitScenario": (
                f"Borrower types the wrong number into a payment field "
                f"and submits ``{param} > {field}``. Canton executes the "
                "subtraction, the resulting contract violates "
                f"``ensure {field} > 0``, the transaction aborts with "
                "``ENSURE_VIOLATED``. The borrower has no idea whether "
                "they overpaid, the payment system is down, or the "
                "contract is bugged."
            ),
            "recommendation": (
                f"Add ``assertMsg \"{param} cannot exceed {field}\" "
                f"({param} <= {field})`` immediately above the subtraction. "
                "Provides a clear error and lets the call fail fast."
            ),
            "references": ["DSV-021", "SWC-101"],
            "codeSnippet": f"create this with {field} = {field} - {param}",
            "fixedCode": (
                f"assertMsg \"{param} cannot exceed {field}\" ({param} <= {field})\n"
                f"create this with {field} = {field} - {param}"
            ),
            "source": "static",
        })
    return findings


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def detect_static_findings(daml_code: str) -> list[dict]:
    """Run every static check and return the merged finding list."""
    if not daml_code or not isinstance(daml_code, str):
        return []
    findings: list[dict] = []
    try:
        findings.extend(_check_no_op_state_transition(daml_code))
        findings.extend(_check_archive_without_replacement(daml_code))
        findings.extend(_check_unused_imports(daml_code))
        findings.extend(_check_consuming_no_op(daml_code))
        findings.extend(_check_missing_terminal_state(daml_code))
        findings.extend(_check_unchecked_subtraction(daml_code))
    except Exception as e:
        logger.warning("Static checks crashed", error=str(e))
    return findings
