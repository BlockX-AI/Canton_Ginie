import json
import structlog

from config import get_settings
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

Example output format:
{
  "contract_type": "bond_tokenization",
  "parties": ["issuer", "investor", "regulator"],
  "features": ["coupon_payment", "redemption", "transfer"],
  "privacy_features": ["party_based_privacy"],
  "canton_specific": ["atomic_settlement", "party_model"],
  "complexity": "medium",
  "daml_templates_needed": ["Bond", "CouponPayment", "Redemption"],
  "business_constraints": ["coupon_rate must be between 0 and 1", "face_value must be positive"],
  "suggested_choices": ["PayCoupon", "Redeem", "Transfer"],
  "description": "A bond tokenization contract where Goldman Sachs issues bonds to investors"
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

        logger.info("Intent parsed", contract_type=intent.get("contract_type"), parties=intent.get("parties"))
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
    }
