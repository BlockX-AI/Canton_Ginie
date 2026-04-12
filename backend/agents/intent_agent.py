import json
import structlog

from utils.llm_client import call_llm

logger = structlog.get_logger()

INTENT_SYSTEM_PROMPT = """You are an expert at understanding financial contract requirements for the Canton Network (a privacy-first blockchain platform that uses Daml smart contracts).

Your job is to parse a user's plain-English description of a smart contract and extract structured requirements.

Canton/Daml key concepts you must understand:
- Templates: contract blueprints (like classes in OOP)
- Choices: actions parties can take (like methods)
- Parties: named authorized participants (NOT wallet addresses)
- Signatories: parties who must authorize the contract creation
- Observers: parties who can see the contract but don't sign
- DAR file: compiled Daml archive uploaded to the ledger

Supported contract types:
- bond_tokenization: Fixed-income bonds with coupon payments
- equity_token: Fractional ownership / share tokenization
- asset_transfer: Generic asset transfer between parties
- escrow: Three-party escrow with conditional release
- trade_settlement: DvP (Delivery vs Payment) settlement
- option_contract: Call/put options on underlying assets
- cash_payment: Payment instructions and receipts
- nft_ownership: Non-fungible token ownership and marketplace
- generic: Custom contracts that don't fit above categories

Privacy features available in Canton:
- party_based_privacy: Only parties on a contract see its data
- divulgence: Selectively share contract data with observers
- sub_transaction_privacy: Hide intermediate steps

Output ONLY valid JSON. No explanation, no markdown, just raw JSON.

Multi-signatory contracts (Propose-Accept pattern):
- If 2+ parties must AGREE to create a contract (both are signatories), set "needs_proposal": true
- The initiator proposes, the other party accepts — this is the Canton Propose-Accept workflow
- Keywords: "agreement", "both parties sign", "mutual consent", "bilateral", "multi-signatory"
- If only one party creates the contract and others just observe, set "needs_proposal": false

Project mode (multi-template output):
- Set "project_mode": true when the request is complex enough to need multiple DAML templates
- Triggers: complexity "high", 3+ features, 3+ templates needed, OR contract type involving
  multiple lifecycle stages (bond issuance + coupon + redemption, trade + settlement, etc.)
- When project_mode is true, list each template in "templates" with name, role, and parties:
  roles: "core" (main business object), "lifecycle" (coupon, redemption), "transfer", "utility"
- Simple single-template requests keep "project_mode": false

Example output format:
{
  "contract_type": "bond_tokenization",
  "parties": ["issuer", "investor", "regulator"],
  "features": ["coupon_payment", "redemption", "transfer"],
  "privacy_features": ["party_based_privacy"],
  "canton_specific": ["atomic_settlement", "party_model"],
  "complexity": "high",
  "daml_templates_needed": ["Bond", "CouponPayment", "Redemption"],
  "business_constraints": ["coupon_rate must be between 0 and 1", "face_value must be positive"],
  "suggested_choices": ["PayCoupon", "Redeem", "Transfer"],
  "description": "A bond tokenization contract where Goldman Sachs issues bonds to investors",
  "needs_proposal": true,
  "project_mode": true,
  "templates": [
    {"name": "Bond", "role": "core", "parties": ["issuer", "investor"]},
    {"name": "CouponPayment", "role": "lifecycle", "parties": ["issuer", "investor"]},
    {"name": "Redemption", "role": "lifecycle", "parties": ["issuer", "investor"]}
  ]
}"""


def run_intent_agent(user_input: str) -> dict:
    logger.info("Running intent agent", input_length=len(user_input))

    try:
        raw_output = call_llm(
            system_prompt=INTENT_SYSTEM_PROMPT,
            user_message=f"Parse this contract description and return structured JSON:\n\n{user_input}",
            max_tokens=1024,
        )

        if raw_output.startswith("```"):
            lines = raw_output.split("\n")
            raw_output = "\n".join(lines[1:-1])

        intent = json.loads(raw_output)

        required_fields = ["contract_type", "parties", "features", "daml_templates_needed"]
        for field in required_fields:
            if field not in intent:
                intent[field] = _get_default(field)

        # Post-process: ensure needs_proposal and project_mode are set
        intent["needs_proposal"] = _detect_needs_proposal(intent)
        intent["project_mode"] = _detect_project_mode(intent)

        logger.info("Intent parsed",
                    contract_type=intent.get("contract_type"),
                    parties=intent.get("parties"),
                    needs_proposal=intent.get("needs_proposal"),
                    project_mode=intent.get("project_mode"))
        return {"success": True, "structured_intent": intent}

    except json.JSONDecodeError as e:
        logger.error("Failed to parse intent JSON", error=str(e))
        fallback = _fallback_intent(user_input)
        return {"success": True, "structured_intent": fallback}
    except Exception as e:
        logger.error("Intent agent failed", error=str(e))
        return {"success": False, "error": str(e), "structured_intent": _fallback_intent(user_input)}


def _get_default(field: str):
    defaults = {
        "contract_type":        "generic",
        "parties":              ["party1", "party2"],
        "features":             ["basic_transfer"],
        "daml_templates_needed": ["Main"],
        "privacy_features":     ["party_based_privacy"],
        "canton_specific":      ["party_model"],
        "complexity":           "medium",
        "business_constraints": [],
        "suggested_choices":    [],
        "description":          "Custom Canton contract",
    }
    return defaults.get(field, None)


def _fallback_intent(user_input: str) -> dict:
    return {
        "contract_type":        "generic",
        "parties":              ["owner", "counterparty"],
        "features":             ["basic_transfer"],
        "privacy_features":     ["party_based_privacy"],
        "canton_specific":      ["party_model"],
        "complexity":           "simple",
        "daml_templates_needed": ["Main"],
        "business_constraints": [],
        "suggested_choices":    ["Transfer", "Archive"],
        "description":          user_input[:200],
        "needs_proposal":       False,
        "project_mode":         False,
        "templates":            [],
    }


_PROPOSAL_KEYWORDS = {
    "agreement", "both parties", "mutual", "bilateral",
    "multi-signatory", "co-sign", "jointly", "both sign",
    "propose-accept", "propose accept", "proposal",
    "counter-sign", "consent", "both agree",
}


def _detect_needs_proposal(intent: dict) -> bool:
    """Determine if the contract needs a Propose-Accept workflow.

    Uses the LLM's own assessment if present, otherwise falls back to
    heuristic detection based on party count and description keywords.
    """
    # Trust the LLM if it explicitly set the field
    if isinstance(intent.get("needs_proposal"), bool):
        return intent["needs_proposal"]

    # Heuristic: check description for multi-signatory keywords
    desc = (intent.get("description") or "").lower()
    for kw in _PROPOSAL_KEYWORDS:
        if kw in desc:
            return True

    # Heuristic: 2+ parties that are both likely signatories
    # (e.g., both named in features like "agreement")
    parties = intent.get("parties", [])
    features = " ".join(intent.get("features", [])).lower()
    if len(parties) >= 2 and ("agreement" in features or "bilateral" in features):
        return True

    return False


_PROJECT_MODE_TYPES = {
    "bond_tokenization", "trade_settlement", "escrow",
    "option_contract", "equity_token",
}


def _detect_project_mode(intent: dict) -> bool:
    """Determine if the request warrants multi-template project generation."""
    # Trust the LLM if it explicitly set the field
    if isinstance(intent.get("project_mode"), bool):
        return intent["project_mode"]

    # Heuristic: high complexity
    if intent.get("complexity") == "high":
        return True

    # Heuristic: 3+ templates requested
    templates = intent.get("daml_templates_needed", [])
    if len(templates) >= 3:
        return True

    # Heuristic: 3+ features
    features = intent.get("features", [])
    if len(features) >= 3:
        return True

    # Heuristic: known complex contract types
    if intent.get("contract_type") in _PROJECT_MODE_TYPES:
        return True

    return False
