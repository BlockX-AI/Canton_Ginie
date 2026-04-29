"""Spec Synthesis stage \u2014 derives a structured contract specification.

This sits between intent extraction and code generation. It produces a
machine-readable plan ("Spec") that:

1. Drives the writer agent \u2014 the spec is appended to the generation prompt
   as an explicit checklist, forcing the LLM to address every behaviour,
   every field, every invariant. It also lists *non-behaviours* (things
   the contract must NOT do) so the writer doesn't silently add them.

2. Drives the auditor (future stage) \u2014 the spec is the ground-truth
   checklist the audit can mechanically verify the code against.

3. Is surfaced in the UI ("Plan" panel on /sandbox/[jobId]) so users see
   the reasoning before the code is written and can spot problems early.

Failure mode is best-effort: if the LLM call or JSON parse fails, this
stage returns ``None`` and the pipeline continues with the original
intent only. It must never block code generation.
"""

from __future__ import annotations

import json
import re
import structlog
from typing import Any, Optional

from utils.llm_client import call_llm

logger = structlog.get_logger()


_SPEC_SYSTEM_PROMPT = """You are a senior smart-contract architect. Given a user's
plain-English description and a coarse intent extraction, produce a precise,
machine-readable specification for a Daml contract on Canton Network.

Your output is a contract *plan* \u2014 not the code itself. The plan will be used
as a strict checklist by the code generator and auditor downstream, so it
must be correct, exhaustive, and self-consistent.

Domain mapping rules (most important):
- "badge", "award", "credential", "certificate", "diploma", "membership",
  "attestation", "soulbound" -> domain="credential", pattern="soulbound-credential"
  (non-transferable). Required fields typically include name, description,
  issuedAt, criteria, optional metadataUri.
- "bond", "note", "coupon" -> domain="finance",
  pattern="bond-tokenization".
- "loan", "borrow", "lend", "repay", "interest", "principal repayment",
  "lender tracks payments" -> domain="finance",
  pattern="loan-agreement". Required fields: ``principal : Decimal``,
  ``interestRate : Decimal``, ``maturity : Time``, ``issuedAt : Time``.
  Required behaviours: ``MakePayment`` (controller=borrower, reduces
  principal), ``TrackPayment`` (controller=lender, **nonconsuming**),
  ``FullRepay`` (controller=borrower, **archives by creating
  RepaidLoan**), plus a propose-accept proposal template with
  ``Reject`` / ``Cancel`` / ``Expire`` choices that each create a
  matching ``RejectedLoanProposal`` / ``CancelledLoanProposal`` /
  ``ExpiredLoanProposal`` audit record. Add ``expiresAt : Time`` to the
  proposal.
- "share", "equity", "stock", "dividend" -> domain="finance", pattern="equity-token".
- "escrow", "hold", "release on condition" -> domain="payments", pattern="escrow".
- "auction", "bid" -> domain="finance", pattern="auction".
- "vote", "proposal", "ballot", "governance" -> domain="governance".
- "supply chain", "shipment", "provenance" -> domain="supply-chain".
- "nft", "collectible", "art piece" -> domain="rights", pattern="nft".

Behaviour expansion rules:
- "stays forever / nobody can take / cannot be transferred" ->
  add a Transfer entry to **non_behaviours** (NOT to behaviours). The
  contract MUST NOT contain any choice that creates a copy with a different
  signatory/observer.
- "issuer can revoke / take back / cancel" -> add a Revoke choice with
  controller=issuer, effect=archive.
- "recipient must accept / consent / opt in" -> add an Accept choice with
  controller=recipient, effect=co-sign (Propose-Accept pattern).
- "anyone can verify / read" -> add the recipient as observer; do not add
  a query choice (templates are already publicly readable to observers).
- If the prompt is ambiguous, default to the SAFER behaviour (e.g. require
  Accept, omit Transfer).

Non-behaviour rules:
- ALWAYS state explicitly what the contract MUST NOT do, including the
  Daml choices that should NOT exist. This is critical \u2014 soulbound
  credentials must omit Transfer, etc.

Field rules:
- Do NOT invent a numeric `amount` field for non-financial contracts.
  Credentials, badges, memberships, NFTs do not need an `amount`.
- Always include `issuedAt : Time` for credentials/certificates.
- Always include a human-readable `name` or `title` field.

Output ONLY a single JSON object that matches this schema. No prose, no
markdown fences:

{
  "domain": "credential | finance | governance | supply-chain | rights | payments | identity | other",
  "pattern": "<short kebab-case identifier, e.g. soulbound-credential>",
  "title": "<3-6 word human title for the contract>",
  "summary": "<1-2 sentence plain-English summary of what is being built>",
  "rationale": "<2-4 sentences explaining the inferred design \u2014 why this pattern, why these behaviours, why these non-behaviours>",
  "parties": [
    {"name": "issuer", "role": "<one-line role description>", "is_signatory": true, "is_observer": false}
  ],
  "fields": [
    {"name": "badgeName", "type": "Text", "required": true, "purpose": "<one-line>"}
  ],
  "behaviours": [
    {"name": "Award", "controller": "issuer", "effect": "create", "description": "<one-line>"}
  ],
  "non_behaviours": [
    {"name": "Transfer", "reason": "<why this is intentionally absent>"}
  ],
  "invariants": [
    "issuer /= recipient",
    "badgeName is non-empty"
  ],
  "test_scenarios": [
    "issuer awards badge -> recipient accepts -> contract live",
    "issuer revokes -> contract archived",
    "recipient cannot transfer (no Transfer choice exists)"
  ]
}

Hard rules:
- Output is a SINGLE JSON object. Use double quotes only. No trailing commas.
- "fields" excludes party fields (those are in "parties").
- Use Daml types: Text, Decimal, Int, Time, Date, Bool, Optional Text, Party.
- Every behaviour controller must be a party listed in "parties".
- behaviours.length >= 1.
- Prefer 3-8 fields, 2-5 behaviours, 1-3 non_behaviours, 2-4 invariants,
  3-5 test_scenarios.
- Be concise: descriptions are one line each.
"""


def synthesize_spec(user_input: str, structured_intent: dict | None) -> Optional[dict[str, Any]]:
    """Best-effort: returns a spec dict, or None on failure.

    Strategy: synthesize once, run a structural validator on the spec
    (pattern-aware checks for things like "voting must have 3+ parties",
    "credentials must NOT have a Transfer behaviour", etc.). If the
    validator complains, regenerate ONCE feeding the complaints back as
    explicit feedback. The second attempt's output is accepted whether
    or not it satisfies the validator \u2014 partial-but-useful is better
    than none, and downstream hard-rules in the writer prompt act as a
    second line of defence.

    The pipeline must keep working even if this returns None \u2014 the writer
    agent falls back to the legacy intent-only prompt in that case.
    """
    intent_summary = _intent_summary(structured_intent)

    spec = _call_synth(user_input, intent_summary, feedback="")
    if spec is None:
        return None

    issues = validate_spec(spec)
    if issues:
        logger.warning(
            "Spec validation found issues, regenerating with feedback",
            issues=issues,
            pattern=spec.get("pattern"),
        )
        feedback = (
            "Your previous attempt had these structural problems. Fix ALL of them:\n"
            + "\n".join(f"  - {i}" for i in issues)
        )
        retried = _call_synth(user_input, intent_summary, feedback=feedback)
        if retried is not None:
            spec = retried
            remaining = validate_spec(spec)
            if remaining:
                logger.warning(
                    "Spec still has issues after retry; accepting best-effort",
                    issues=remaining,
                )

    logger.info(
        "Spec synthesised",
        domain=spec.get("domain"),
        pattern=spec.get("pattern"),
        n_parties=len(spec.get("parties") or []),
        n_fields=len(spec.get("fields") or []),
        n_behaviours=len(spec.get("behaviours") or []),
        n_non_behaviours=len(spec.get("non_behaviours") or []),
    )
    return spec


def _intent_summary(structured_intent: dict | None) -> str:
    if not isinstance(structured_intent, dict):
        return ""
    return json.dumps({
        "contract_type":  structured_intent.get("contract_type"),
        "parties":        structured_intent.get("parties"),
        "features":       structured_intent.get("features"),
        "description":    structured_intent.get("description"),
        "needs_proposal": structured_intent.get("needs_proposal"),
    })


def _call_synth(user_input: str, intent_summary: str, feedback: str) -> Optional[dict[str, Any]]:
    """Single LLM round-trip. Returns a normalised spec dict or None."""
    user_msg = (
        f"User prompt:\n{user_input}\n\n"
        f"Coarse intent:\n{intent_summary or '(none)'}\n\n"
    )
    if feedback:
        user_msg += f"VALIDATOR FEEDBACK (mandatory to address):\n{feedback}\n\n"
    user_msg += "Produce the contract Spec JSON now."

    try:
        raw = call_llm(
            system_prompt=_SPEC_SYSTEM_PROMPT,
            user_message=user_msg,
            max_tokens=2048,
        )
    except Exception as e:
        logger.warning("Spec synthesis LLM call failed", error=str(e))
        return None

    parsed = _parse_json_loose(raw)
    if not parsed:
        logger.warning("Spec synthesis produced unparseable output", preview=(raw or "")[:200])
        return None

    spec = _normalise_spec(parsed)
    if not spec.get("behaviours"):
        # An empty behaviours list means the model gave us nothing usable \u2014
        # fall back rather than feed an empty checklist to the writer.
        logger.warning("Spec synthesis produced no behaviours, discarding")
        return None
    return spec


def _parse_json_loose(raw: str) -> Optional[dict[str, Any]]:
    if not raw:
        return None
    text = raw.strip()
    # Strip markdown fences if present
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
    # Find the first balanced {...} block
    first = text.find("{")
    last = text.rfind("}")
    if first == -1 or last == -1 or last <= first:
        return None
    candidate = text[first:last + 1]
    try:
        data = json.loads(candidate)
        if isinstance(data, dict):
            return data
    except Exception:
        return None
    return None


def _normalise_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """Coerce values to expected shapes & strip junk so the rest of the
    pipeline can rely on simple key lookups."""
    out: dict[str, Any] = {}
    out["domain"] = str(spec.get("domain") or "other").strip()[:64]
    out["pattern"] = str(spec.get("pattern") or "generic").strip()[:64]
    out["title"] = str(spec.get("title") or "").strip()[:120]
    out["summary"] = str(spec.get("summary") or "").strip()[:600]
    out["rationale"] = str(spec.get("rationale") or "").strip()[:1500]
    out["parties"] = _list_of_dicts(
        spec.get("parties"),
        keys={"name", "role", "is_signatory", "is_observer"},
    )
    out["fields"] = _list_of_dicts(
        spec.get("fields"),
        keys={"name", "type", "required", "purpose"},
    )
    out["behaviours"] = _list_of_dicts(
        spec.get("behaviours"),
        keys={"name", "controller", "effect", "description"},
    )
    out["non_behaviours"] = _list_of_dicts(
        spec.get("non_behaviours"),
        keys={"name", "reason"},
    )
    out["invariants"] = [
        str(s).strip() for s in (spec.get("invariants") or []) if isinstance(s, str)
    ][:8]
    out["test_scenarios"] = [
        str(s).strip() for s in (spec.get("test_scenarios") or []) if isinstance(s, str)
    ][:8]
    return out


def _list_of_dicts(raw: Any, keys: set[str]) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        clean: dict[str, Any] = {}
        for k in keys:
            if k in item:
                clean[k] = item[k]
        if clean:
            out.append(clean)
    return out


def format_spec_for_prompt(spec: dict[str, Any] | None) -> str:
    """Render the spec as a plain-text checklist to inject into the writer
    agent's user message. Goal: every line maps to a concrete code element
    the model must produce (or, in the case of non-behaviours, a thing it
    must NOT produce).
    """
    if not spec:
        return ""
    lines: list[str] = []
    lines.append("CONTRACT PLAN (machine-derived spec \u2014 your code MUST honour every line):")
    if spec.get("title"):
        lines.append(f"Title: {spec['title']}")
    if spec.get("summary"):
        lines.append(f"Summary: {spec['summary']}")
    if spec.get("pattern"):
        lines.append(f"Pattern: {spec['pattern']} (domain={spec.get('domain', 'other')})")

    parties = spec.get("parties") or []
    if parties:
        lines.append("\nParties:")
        for p in parties:
            tags: list[str] = []
            if p.get("is_signatory"):
                tags.append("signatory")
            if p.get("is_observer"):
                tags.append("observer")
            tag_str = f" [{', '.join(tags)}]" if tags else ""
            lines.append(f"  - {p.get('name', '?')}{tag_str}: {p.get('role', '')}")

    fields = spec.get("fields") or []
    if fields:
        lines.append("\nFields (must appear in `with` block):")
        for f in fields:
            req = "" if f.get("required") is False else " (required)"
            lines.append(
                f"  - {f.get('name', '?')} : {f.get('type', 'Text')}{req} \u2014 {f.get('purpose', '')}"
            )

    behaviours = spec.get("behaviours") or []
    if behaviours:
        lines.append("\nBehaviours (must appear as `choice`s):")
        for b in behaviours:
            lines.append(
                f"  - {b.get('name', '?')} (controller={b.get('controller', '?')}, "
                f"effect={b.get('effect', '?')}): {b.get('description', '')}"
            )

    non_behaviours = spec.get("non_behaviours") or []
    if non_behaviours:
        lines.append("\nNon-behaviours (must NOT appear \u2014 do not generate these choices):")
        for nb in non_behaviours:
            lines.append(f"  - {nb.get('name', '?')} \u2014 {nb.get('reason', 'intentionally absent')}")

    invariants = spec.get("invariants") or []
    if invariants:
        lines.append("\nInvariants (combine with && in the single `ensure` clause):")
        for inv in invariants:
            lines.append(f"  - {inv}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Validator + hard-rule derivation (P1)
# ---------------------------------------------------------------------------
#
# These helpers add a second line of defence between the planner and the
# writer:
#
#   * ``validate_spec`` runs pattern-aware structural checks on the
#     synthesised spec; the planner re-runs once if any check fails,
#     feeding the complaints back as explicit feedback.
#
#   * ``derive_hard_rules`` produces a list of MUST / MUST-NOT prose
#     rules computed from the spec's actual content (party count,
#     party names, behaviour names, invariants, etc). The writer
#     receives these as a separate "HARD RULES" block in its prompt
#     so structural rules survive even when the LLM skims the Plan.
#
# Both are pure functions of the spec dict \u2014 no I/O, no side effects.


_TRANSFER_LIKE = (
    "transfer", "reassign", "changeowner", "give", "send",
    "passon", "pass-on", "pass_on", "delegate",
)
_PLURAL_PARTY_NAMES = {
    "voters", "members", "signers", "participants",
    "investors", "holders", "shareholders", "delegates",
    "validators", "witnesses",
}


def validate_spec(spec: dict[str, Any] | None) -> list[str]:
    """Pattern-aware structural validation.

    Returns a list of human-readable complaints; an empty list means
    the spec is structurally sound for its declared pattern. Complaints
    are written to be actionable feedback for a re-prompt.
    """
    issues: list[str] = []
    if not isinstance(spec, dict):
        return ["Spec is not a dict"]

    pattern = (spec.get("pattern") or "").lower()
    domain = (spec.get("domain") or "").lower()
    parties = spec.get("parties") or []
    fields = spec.get("fields") or []
    behaviours = spec.get("behaviours") or []
    invariants = spec.get("invariants") or []

    # ----- Universal sanity ------------------------------------------------
    if not behaviours:
        issues.append(
            "No behaviours defined. The contract must expose at least one choice."
        )
    if not parties:
        issues.append("No parties defined.")

    behaviour_names = " ".join((b.get("name") or "").lower() for b in behaviours)
    field_names = " ".join((f.get("name") or "").lower() for f in fields)

    # ----- Voting / DAO ----------------------------------------------------
    is_voting = (
        "voting" in pattern or "dao" in pattern
        or "vote" in pattern or "ballot" in pattern
        or domain in {"governance", "voting"}
    )
    if is_voting:
        if len(parties) < 3:
            issues.append(
                "Voting/DAO patterns require at least 3 parties. "
                "Replace numbered party fields with a single collective party "
                "named `voters` (renderer will emit `voters : [Party]`)."
            )
        if "vote" not in behaviour_names and "cast" not in behaviour_names:
            issues.append(
                "Voting pattern must include a single `Vote` (or `CastVote`) "
                "behaviour parameterised by the voter; do NOT enumerate one "
                "behaviour per voter."
            )
        if all(
            kw not in behaviour_names
            for kw in ("finalize", "tally", "resolve", "close")
        ):
            issues.append(
                "Voting pattern must include a `Finalize` (or `Tally`) "
                "behaviour that closes the vote."
            )

    # ----- Soulbound credential -------------------------------------------
    is_credential = (
        "soulbound" in pattern or "credential" in pattern
        or "badge" in pattern or "certificate" in pattern
        or domain == "credential"
    )
    if is_credential:
        for b in behaviours:
            bname = (b.get("name") or "").lower()
            if any(kw in bname for kw in _TRANSFER_LIKE):
                issues.append(
                    f"Credential/badge pattern must NOT have a transfer-like "
                    f"behaviour `{b.get('name')}` \u2014 move it to non_behaviours."
                )
        for f in fields:
            ftype = (f.get("type") or "").lower()
            fname = (f.get("name") or "").lower()
            if "decimal" in ftype and any(
                kw in fname for kw in ("amount", "value", "price", "cost")
            ):
                issues.append(
                    f"Credential pattern should not carry a financial field "
                    f"`{f.get('name')} : {f.get('type')}`. Remove it."
                )

    # ----- NFT (transferable) ---------------------------------------------
    is_nft = (
        "nft" in pattern or "collectible" in pattern
        or domain == "rights"
    )
    if is_nft:
        if "transfer" not in behaviour_names:
            issues.append(
                "NFT pattern must include a `Transfer` behaviour "
                "(controller=owner, effect=create-with-new-owner)."
            )

    # ----- Bond / fixed income --------------------------------------------
    # Detect bonds *only* by explicit pattern / coupon-field signals, NOT
    # by domain==finance + principal. The latter heuristic was too eager
    # and mis-flagged loan-agreement / lending specs (which legitimately
    # have ``principal`` but no ``maturity``), forcing the synth into a
    # bond retry that lost loan-specific behaviours like ``FullRepay``.
    is_bond = (
        "bond" in pattern
        or pattern == "note"
        or "coupon" in field_names
    )
    is_loan = "loan" in pattern or any(
        kw in field_names for kw in ("loanamount", "interestrate")
    )
    if is_bond and not is_loan:
        if "principal" not in field_names and "amount" not in field_names:
            issues.append(
                "Bond pattern must include a `principal` (or `amount`) field of type Decimal."
            )
        if not any(kw in field_names for kw in ("maturity", "matur", "expir")):
            issues.append("Bond pattern must include a `maturity` field of type Time.")

    # ----- Loan / lending -------------------------------------------------
    # Mirror Tier A's loan-pattern requirements at the spec level so we
    # never accept a lending plan that lacks the audit-trail termination
    # paths. Without these the writer downstream cannot safely emit
    # SEC-GEN-017 terminal-state choices.
    if is_loan:
        if not any(kw in field_names for kw in ("principal", "loanamount", "amount")):
            issues.append(
                "Loan pattern must include a `principal` / `loanAmount` field of type Decimal."
            )
        # Soft-warn (not hard-fail) on the audit-trail behaviours so a
        # short prompt that omits Reject is still accepted; the writer's
        # generation rules supply the missing pieces.
        # (No hard issues appended.)

    # ----- Escrow ---------------------------------------------------------
    is_escrow = "escrow" in pattern or domain == "payments"
    if is_escrow:
        if len(parties) < 3:
            issues.append(
                "Escrow pattern needs at least 3 parties (arbiter, buyer, seller)."
            )
        if not any(kw in behaviour_names for kw in ("confirm", "release")):
            issues.append("Escrow pattern needs a `Confirm` (or `Release`) behaviour.")
        if "refund" not in behaviour_names and "cancel" not in behaviour_names:
            issues.append("Escrow pattern needs a `Refund` (or `Cancel`) behaviour.")

    # ----- Cross-pattern: invariants must reference real fields/parties ---
    # If the model produced invariants but we have no parties or fields at
    # all, something is wrong.
    if invariants and not parties and not fields:
        issues.append(
            "Invariants reference fields/parties but the spec defines none."
        )

    return issues


def derive_hard_rules(spec: dict[str, Any] | None) -> list[str]:
    """Build a list of MUST/MUST-NOT prose rules from the spec content.

    These rules are computed from the *actual* fields, parties and
    behaviours the planner produced \u2014 not from the pattern label
    alone \u2014 so they remain accurate even when a less common pattern
    is selected.

    The writer agent injects the rendered list (see
    ``format_hard_rules_for_prompt``) into the user message so the
    LLM cannot skim past them the way it can skim past the Plan.
    """
    rules: list[str] = []
    if not isinstance(spec, dict):
        return rules

    parties = spec.get("parties") or []
    behaviours = spec.get("behaviours") or []
    non_behaviours = spec.get("non_behaviours") or []
    invariants = spec.get("invariants") or []
    pattern = (spec.get("pattern") or "").lower()
    domain = (spec.get("domain") or "").lower()

    # If the spec carries no usable content at all, return no rules \u2014
    # we don't want to inject baseline prose rules into a writer that's
    # operating without any plan context.
    if not parties and not behaviours and not pattern and not domain:
        return rules

    party_names_lc = [(p.get("name") or "").lower() for p in parties]
    plural_party = any(
        name in _PLURAL_PARTY_NAMES or (name.endswith("s") and len(name) > 3)
        for name in party_names_lc
    )
    is_voting = (
        "voting" in pattern or "dao" in pattern or "vote" in pattern
        or "ballot" in pattern or domain in {"governance", "voting"}
    )

    # ---- Rule: collective parties must be a `[Party]` list ---------------
    if len(parties) >= 3 or plural_party or is_voting:
        rules.append(
            "MUST represent the collective parties as a SINGLE field of "
            "type `[Party]` (e.g. `voters : [Party]`, `members : [Party]`). "
            "FORBIDDEN: numbered fields like `voter1 : Party, voter2 : Party, "
            "voter3 : Party`. The Daml runtime cannot generalise across "
            "numbered fields and the contract becomes brittle to the exact "
            "party count."
        )

    # ---- Rule: vote-like behaviours must be a single parameterised choice
    bnames = [(b.get("name") or "") for b in behaviours]
    vote_like = [n for n in bnames if "vote" in n.lower() or "cast" in n.lower()]
    if is_voting or vote_like:
        rules.append(
            "MUST implement voting via ONE single `CastVote` choice with "
            "`with voter : Party, inFavor : Bool` and `controller voter`, "
            "guarded by `assertMsg \"...\" (voter `elem` voters)`. "
            "FORBIDDEN: per-voter clones like `VoteVoter1`, `VoteVoter2`, "
            "`VoteVoter3` \u2014 these are 100% structurally identical and "
            "must be parameterised, not duplicated."
        )
        rules.append(
            "MUST prevent double-voting: track `votedYes : [Party]` and "
            "`votedNo : [Party]` and `assertMsg` that the voter has not "
            "already voted before recording the new vote."
        )

    # ---- Rule: non-behaviours are forbidden -----------------------------
    for nb in non_behaviours:
        nm = (nb.get("name") or "").strip()
        if nm:
            rules.append(
                f"FORBIDDEN choice: `{nm}`. The Plan explicitly excludes it "
                f"({(nb.get('reason') or 'see Plan').strip()})."
            )

    # ---- Rule: every invariant must surface as assertMsg ---------------
    if invariants:
        rules.append(
            "MUST express each Plan invariant as an `assertMsg \"<descriptive "
            "human-readable reason>\" <condition>` inside the `do` block of "
            "the choice that mutates the relevant state. Use `ensure` ONLY "
            "for invariants that hold for the entire lifetime of the "
            "contract (creation through archival)."
        )

    # ---- Rule: imports must be used --------------------------------------
    rules.append(
        "MUST NOT include unused imports. `import DA.Time` only if the "
        "contract has a `Time` field or calls `getTime`. `import DA.Date` "
        "only if it uses `Date`. `length`, `elem`, `notElem`, `head`, "
        "`tail`, `null`, `map`, `filter` are in the prelude \u2014 NEVER "
        "import `DA.List` for them."
    )

    # ---- Rule: descriptive assertMsg over bare ensure -------------------
    rules.append(
        "MUST favour `assertMsg \"<reason>\" <cond>` over a bare boolean "
        "in `ensure` chains. A failing `assertMsg` produces a useful error "
        "message; a failing `ensure` just says `precondition violated`."
    )

    return rules


def format_hard_rules_for_prompt(rules: list[str] | None) -> str:
    """Render derived hard rules as a clearly-delimited prompt block.

    Returns ``""`` if there are no rules; otherwise a block with a
    numbered list and clear delimiters that sits ABOVE the Plan and the
    curated reference, since these are the structural laws the writer
    must obey before anything else.
    """
    if not rules:
        return ""
    body = "\n".join(f"  {i+1}. {r}" for i, r in enumerate(rules))
    return (
        "\n--- HARD RULES (auto-derived from the Plan; non-negotiable) ---\n"
        "Each rule is mandatory. The post-compile auditor checks for "
        "every one of them, and violations cause your output to be "
        "rejected and regenerated.\n\n"
        f"{body}\n"
        "--- END HARD RULES ---\n"
    )
