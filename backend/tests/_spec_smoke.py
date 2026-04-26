"""Smoke check for spec_synth parsing + formatting helpers.

Run from repo root:
    backend/venv/Scripts/python.exe backend/tests/_spec_smoke.py

This is intentionally NOT pytest-discovered (filename starts with _) so it
doesn't run in CI by default.
"""
import sys
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from pipeline.spec_synth import (  # noqa: E402
    _parse_json_loose,
    _normalise_spec,
    derive_hard_rules,
    format_hard_rules_for_prompt,
    format_spec_for_prompt,
    validate_spec,
)

RAW = """```json
{
  "domain": "credential",
  "pattern": "soulbound-credential",
  "title": "Achievement Badge",
  "summary": "Issuer awards a non-transferable badge to a recipient.",
  "rationale": "User said the badge stays forever and nobody can take it; that is the soulbound credential pattern.",
  "parties": [
    {"name": "issuer",    "role": "the company awarding the badge", "is_signatory": true, "is_observer": false},
    {"name": "recipient", "role": "the person receiving the badge", "is_signatory": false, "is_observer": true}
  ],
  "fields": [
    {"name": "badgeName",    "type": "Text", "required": true,  "purpose": "human-readable badge title"},
    {"name": "description",  "type": "Text", "required": true,  "purpose": "what the badge recognises"},
    {"name": "issuedAt",     "type": "Time", "required": true,  "purpose": "issuance timestamp"},
    {"name": "metadataUri",  "type": "Optional Text", "required": false, "purpose": "off-chain metadata"}
  ],
  "behaviours": [
    {"name": "Award",  "controller": "issuer",    "effect": "create",  "description": "issuer mints the badge"},
    {"name": "Accept", "controller": "recipient", "effect": "co-sign", "description": "recipient acknowledges the badge"},
    {"name": "Revoke", "controller": "issuer",    "effect": "archive", "description": "issuer revokes the badge"}
  ],
  "non_behaviours": [
    {"name": "Transfer", "reason": "soulbound \u2014 non-transferable by design"}
  ],
  "invariants": [
    "issuer /= recipient",
    "badgeName is non-empty"
  ],
  "test_scenarios": [
    "issuer awards -> recipient accepts -> contract live",
    "issuer revokes -> contract archived",
    "recipient cannot transfer (no Transfer choice exists)"
  ]
}
```
"""

def main() -> None:
    parsed = _parse_json_loose(RAW)
    assert parsed is not None, "JSON parse failed"
    spec = _normalise_spec(parsed)
    assert spec["pattern"] == "soulbound-credential"
    assert len(spec["behaviours"]) == 3
    assert len(spec["non_behaviours"]) == 1
    out = format_spec_for_prompt(spec)
    assert "Non-behaviours" in out
    assert "Transfer" in out
    assert "Award" in out

    # ---- P1: validator should accept this clean credential spec ---------
    issues = validate_spec(spec)
    assert issues == [], f"clean spec should validate, got: {issues}"

    # ---- P1: validator should reject a credential with a Transfer behaviour
    bad_credential = {
        **spec,
        "behaviours": [
            *spec["behaviours"],
            {"name": "Transfer", "controller": "issuer", "effect": "create", "description": "x"},
        ],
        "fields": [
            *spec["fields"],
            {"name": "amount", "type": "Decimal", "required": True, "purpose": "x"},
        ],
    }
    issues = validate_spec(bad_credential)
    assert any("Transfer" in i for i in issues), f"missing transfer complaint: {issues}"
    assert any("amount" in i.lower() for i in issues), f"missing amount complaint: {issues}"

    # ---- P1: validator should reject a voting spec with only 2 parties ---
    bad_voting = {
        "domain": "governance",
        "pattern": "voting-dao",
        "title": "Vote",
        "summary": "",
        "rationale": "",
        "parties": [
            {"name": "voter1", "role": "voter", "is_signatory": True, "is_observer": False},
            {"name": "voter2", "role": "voter", "is_signatory": True, "is_observer": False},
        ],
        "fields": [],
        "behaviours": [
            {"name": "VoteVoter1", "controller": "voter1", "effect": "create", "description": ""},
            {"name": "VoteVoter2", "controller": "voter2", "effect": "create", "description": ""},
        ],
        "non_behaviours": [],
        "invariants": [],
        "test_scenarios": [],
    }
    issues = validate_spec(bad_voting)
    assert any("3 parties" in i for i in issues), f"voting party-count check missing: {issues}"
    assert any("Finalize" in i or "Tally" in i for i in issues), f"finalize check missing: {issues}"

    # ---- P1: derive_hard_rules for a voting spec ------------------------
    voting_spec = {
        "domain": "governance",
        "pattern": "voting-dao",
        "parties": [
            {"name": "proposer"}, {"name": "voter1"}, {"name": "voter2"},
            {"name": "voter3"}, {"name": "voter4"},
        ],
        "fields": [],
        "behaviours": [{"name": "CastVote"}, {"name": "Finalize"}],
        "non_behaviours": [{"name": "Bribe", "reason": "no off-ledger payments"}],
        "invariants": ["votedYes intersect votedNo == []"],
    }
    rules = derive_hard_rules(voting_spec)
    rules_text = " ".join(rules)
    assert "[Party]" in rules_text, "list-of-party rule missing"
    assert "CastVote" in rules_text, "single-CastVote rule missing"
    assert "votedYes" in rules_text or "double-vot" in rules_text.lower(), "double-vote rule missing"
    assert "Bribe" in rules_text, "non-behaviour rule missing"
    assert "assertMsg" in rules_text, "assertMsg rule missing"

    block = format_hard_rules_for_prompt(rules)
    assert "HARD RULES" in block
    assert "non-negotiable" in block
    assert "VoteVoter1" in block, "explicit anti-pattern callout missing"

    # ---- P1: empty spec -> no rules ------------------------------------
    assert derive_hard_rules(None) == []
    assert derive_hard_rules({}) == []
    assert format_hard_rules_for_prompt([]) == ""

    print("spec_synth smoke OK (incl. P1 validator + hard-rules)")
    print("---")
    print(out)
    print("---")
    print(block)


if __name__ == "__main__":
    main()
