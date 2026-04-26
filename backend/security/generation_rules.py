"""
Pre-audit security rules injected into the writer agent's system prompt.

These rules are enforced at generation time so the LLM produces code that
passes the post-generation audit on the first attempt.  Each rule maps to
a common audit finding; generating code that already satisfies the rule
eliminates an entire fix-loop iteration.
"""

from __future__ import annotations

GENERATION_SECURITY_RULES: list[dict] = [
    {
        "id": "SEC-GEN-001",
        "rule": "All Party fields used as signatory and observer must be validated as distinct in the ensure clause",
        "example": "ensure issuer /= investor",
        "severity": "high",
    },
    {
        "id": "SEC-GEN-002",
        "rule": "All Decimal fields for financial amounts must have positive-value AND upper-bound constraints in the ensure clause",
        "example": "ensure amount > 0.0 && amount <= 1000000000.0",
        "severity": "high",
    },
    {
        "id": "SEC-GEN-003",
        "rule": "Consuming choices that transfer ownership must create a new contract (never just archive without replacement)",
        "example": "choice Transfer : ContractId Bond ... do create this with owner = newOwner",
        "severity": "critical",
    },
    {
        "id": "SEC-GEN-004",
        "rule": "Observer fields must never overlap with signatory fields unless explicitly required",
        "example": "observer investor  -- where investor /= issuer is enforced in ensure",
        "severity": "medium",
    },
    {
        "id": "SEC-GEN-005",
        "rule": "Every choice must have an explicit controller authorization — never leave controller unspecified",
        "example": "controller investor",
        "severity": "high",
    },
    {
        "id": "SEC-GEN-006",
        "rule": "Nonconsuming choices must never create contracts that could lead to unbounded growth — add guards or limits",
        "example": "nonconsuming choice GetInfo : Text ... do return description  -- read-only, no create",
        "severity": "medium",
    },
    {
        "id": "SEC-GEN-007",
        "rule": "Date fields used for deadlines or expiry must be validated against current time in choices that depend on them",
        "example": "do now <- getTime; assertMsg \"expired\" (expiryDate > toDateUTC now)",
        "severity": "high",
    },
    {
        "id": "SEC-GEN-008",
        "rule": "Contract keys must include at least one signatory party in the key tuple",
        "example": "key (issuer, bondId) : (Party, Text)",
        "severity": "high",
    },
    {
        "id": "SEC-GEN-009",
        "rule": "List and Optional fields must have size constraints in ensure clauses to prevent unbounded payload",
        "example": "ensure DA.List.length items <= 100",
        "severity": "medium",
    },
    {
        "id": "SEC-GEN-010",
        "rule": "Every template must have at least one consuming choice besides Archive to allow state transitions",
        "example": "choice Execute : () ... do archive self; return ()",
        "severity": "medium",
    },
    {
        "id": "SEC-GEN-011",
        "rule": (
            "A consuming choice that calls `create this` MUST mutate at "
            "least one field via `with` \u2014 a bare `create this` re-"
            "creates a byte-identical contract (no-op state transition) "
            "and gives the impression of a state change while changing "
            "nothing observable on-ledger. If the choice has no field "
            "to mutate, either add a `status` field to the template or "
            "drop the choice entirely."
        ),
        "example": (
            "choice Approve : ContractId Invoice ... do "
            "create this with status = Approved  -- NEVER bare `create this`"
        ),
        "severity": "high",
    },
    {
        "id": "SEC-GEN-012",
        "rule": (
            "Terminal-state choices (Pay, Settle, Complete, Finalize, "
            "MarkPaid, etc.) MUST `create` a successor template "
            "(`PaidInvoice`, `SettledTrade`, ...) instead of bare "
            "`archive self`. A bare archive collapses every terminal "
            "outcome into a single ledger event and breaks audit-trail "
            "queries. Reject / Cancel / Withdraw choices may bare-archive "
            "because the business meaning is genuinely \u2018discard\u2019."
        ),
        "example": (
            "choice MarkPaid : ContractId PaidInvoice ... do "
            "archive self; create PaidInvoice with vendor; client; amount"
        ),
        "severity": "medium",
    },
    {
        "id": "SEC-GEN-013",
        "rule": (
            "Every `assertMsg` message MUST accurately describe the "
            "boolean condition it guards. A message like \u201cInvoice "
            "already approved\u201d on a condition `vendor /= client` "
            "is a lie at runtime \u2014 when the assertion fails the "
            "user sees a misleading reason. Either rewrite the message "
            "to match the condition, or rewrite the condition to match "
            "the message."
        ),
        "example": (
            "assertMsg \"Vendor and client must differ\" (vendor /= client)"
        ),
        "severity": "medium",
    },
]


def format_rules_for_prompt() -> str:
    """Format the security rules as a numbered block for the writer system prompt."""
    lines = [
        "",
        "MANDATORY SECURITY REQUIREMENTS (violations will fail the post-generation audit):",
    ]
    for rule in GENERATION_SECURITY_RULES:
        lines.append(
            f"  {rule['id']} [{rule['severity'].upper()}]: {rule['rule']}"
        )
        lines.append(f"    Example: {rule['example']}")
    return "\n".join(lines)
