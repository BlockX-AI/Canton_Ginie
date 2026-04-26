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
    except Exception as e:
        logger.warning("Static checks crashed", error=str(e))
    return findings
