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
    {
        "id": "SEC-GEN-014",
        "rule": (
            "Every Proposal-style template (i.e. any template whose "
            "name ends in `Proposal` or that is part of a Propose-"
            "Accept lifecycle) MUST carry an `expiresAt : Time` field, "
            "and its `Accept` choice MUST guard against acceptance "
            "after expiry. Without this, a stale proposal can be "
            "accepted years later at terms the proposer no longer "
            "intends \u2014 a documented financial-loss vector. The "
            "template should also expose an `Expire` choice that "
            "produces an `ExpiredProposal` audit record once the "
            "deadline has passed."
        ),
        "example": (
            "do now <- getTime; "
            "assertMsg \"Proposal has expired\" (now <= expiresAt); "
            "create Agreement with ..."
        ),
        "severity": "high",
    },
    {
        "id": "SEC-GEN-015",
        "rule": (
            "Termination choices (Reject, Cancel, Expire, Terminate, "
            "Abort, etc.) MUST create a successor audit-record "
            "template that captures who terminated, when, and (where "
            "applicable) why. A bare `return ()` or `pure ()` archives "
            "the contract silently and discards the rejection reason "
            "\u2014 forensics years later cannot reconstruct the "
            "decision. Always: `create RejectedProposal with ...; "
            "rejectedAt = now`."
        ),
        "example": (
            "choice Reject : ContractId RejectedProposal "
            "with reason : Text controller counterparty "
            "do now <- getTime; "
            "create RejectedProposal with proposer; counterparty; "
            "reason; rejectedAt = now"
        ),
        "severity": "high",
    },
    {
        "id": "SEC-GEN-016",
        "rule": (
            "ANY choice whose body has no side effect on ledger state "
            "(no `create`, no `archive`, just `return ()` / `pure ()`) "
            "MUST be declared `nonconsuming`. Without this keyword Daml "
            "auto-archives the host contract on every exercise \u2014 a "
            "single call to a misnamed `TrackPayment` / `LogActivity` / "
            "`CheckBalance` choice silently destroys the live agreement. "
            "Heuristic: if the choice name starts with Track, Log, "
            "Observe, Check, View, Query, Inspect, Report, Get, Read, "
            "Show, Validate, or Verify, it is almost certainly meant to "
            "be `nonconsuming`. If the choice is meant to record an "
            "event, prefer `create <AuditRecord> with \u2026` over "
            "`return ()`."
        ),
        "example": (
            "nonconsuming choice TrackPayment : () "
            "with paymentAmount : Decimal "
            "controller lender "
            "do assertMsg \"Payment must be positive\" (paymentAmount > 0.0); "
            "return ()"
        ),
        "severity": "high",
    },
    {
        "id": "SEC-GEN-017",
        "rule": (
            "Any template whose `ensure` clause enforces "
            "`<balance> > 0` AND that exposes a choice subtracting "
            "from `<balance>` MUST also expose a terminal-state "
            "choice (`FullRepay`, `Close`, `Settle`, `Finalize`) that "
            "either archives the contract cleanly OR creates a "
            "`Settled<Template>` / `Repaid<Template>` audit-record "
            "successor. Without this path the final payment fails "
            "with `ENSURE_VIOLATED` because the resulting contract "
            "violates its own `> 0` invariant \u2014 the agreement "
            "becomes permanently un-closable. Inside the mutating "
            "choice (e.g. `MakePayment`), branch on "
            "`balance - param == 0.0` and route to the terminal "
            "path automatically."
        ),
        "example": (
            "choice FullRepay : ContractId RepaidLoan "
            "controller borrower "
            "do now <- getTime; "
            "create RepaidLoan with borrower; lender; "
            "originalAmount = loanAmount; repaidAt = now"
        ),
        "severity": "high",
    },
    {
        "id": "SEC-GEN-018",
        "rule": (
            "Any choice that subtracts a parameter from a template "
            "field MUST first assert "
            "`assertMsg \"<param> cannot exceed <field>\" "
            "(<param> <= <field>)`. Relying on a downstream `ensure` "
            "clause to reject negative balances produces an opaque "
            "`ENSURE_VIOLATED` error that hides the real cause. The "
            "fail-fast assertion gives the user a clear, actionable "
            "message and lets the transaction abort early."
        ),
        "example": (
            "do "
            "assertMsg \"Payment must be positive\" (paymentAmount > 0.0); "
            "assertMsg \"Payment cannot exceed loanAmount\" "
            "(paymentAmount <= loanAmount); "
            "create this with loanAmount = loanAmount - paymentAmount"
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
