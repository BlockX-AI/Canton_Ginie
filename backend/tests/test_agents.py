"""
Unit tests for each agent.
Run: cd backend && source venv/bin/activate && pytest tests/ -v
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_settings


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def api_key_valid():
    from utils.llm_client import check_llm_available
    result = check_llm_available()
    if not result["ok"]:
        print(f"\n  LLM check failed: provider={result['provider']} error={result.get('error','')}")
    return result["ok"]


# ---------------------------------------------------------------------------
# Intent Agent
# ---------------------------------------------------------------------------

class TestIntentAgent:
    def test_parses_bond_contract(self, api_key_valid):
        if not api_key_valid:
            from config import get_settings
            provider = get_settings().llm_provider
            pytest.skip(f"LLM unavailable — check {provider.upper()}_API_KEY in backend/.env.ginie")
        from agents.intent_agent import run_intent_agent
        result = run_intent_agent(
            "I want a bond tokenization contract where Goldman Sachs issues "
            "fixed-rate bonds to pension fund investors with 5% coupon payments."
        )
        assert result["success"], f"Intent failed: {result.get('error')}"
        intent = result["structured_intent"]
        assert "contract_type" in intent
        assert "parties" in intent
        assert len(intent["parties"]) >= 2
        print(f"\n  contract_type : {intent['contract_type']}")
        print(f"  parties       : {intent['parties']}")
        print(f"  key_features  : {intent.get('key_features', [])}")

    def test_parses_escrow_contract(self, api_key_valid):
        if not api_key_valid:
            pytest.skip("LLM unavailable — check API key in backend/.env.ginie")
        from agents.intent_agent import run_intent_agent
        result = run_intent_agent(
            "Build an escrow contract with buyer, seller and escrow agent. "
            "Buyer deposits funds, seller delivers goods, agent releases on confirmation."
        )
        assert result["success"]
        intent = result["structured_intent"]
        assert "escrow" in str(intent).lower() or "buyer" in str(intent["parties"]).lower()

    def test_parses_nft_contract(self, api_key_valid):
        if not api_key_valid:
            pytest.skip("LLM unavailable — check API key in backend/.env.ginie")
        from agents.intent_agent import run_intent_agent
        result = run_intent_agent("Create an NFT marketplace where artists mint tokens and collectors trade them.")
        assert result["success"]
        intent = result["structured_intent"]
        assert intent.get("contract_type")

    def test_returns_daml_templates(self, api_key_valid):
        if not api_key_valid:
            pytest.skip("LLM unavailable — check API key in backend/.env.ginie")
        from agents.intent_agent import run_intent_agent
        result = run_intent_agent("Simple asset transfer between two parties.")
        assert result["success"]
        assert "daml_templates_needed" in result["structured_intent"]
        assert len(result["structured_intent"]["daml_templates_needed"]) >= 1


# ---------------------------------------------------------------------------
# RAG / Writer Agent
# ---------------------------------------------------------------------------

class TestWriterAgent:
    def test_generates_valid_daml(self, api_key_valid):
        if not api_key_valid:
            pytest.skip("LLM unavailable — check API key in backend/.env.ginie")
        from agents.writer_agent import run_writer_agent
        intent = {
            "contract_type": "bond_tokenization",
            "parties": ["issuer", "investor"],
            "key_features": ["coupon payment", "maturity redemption"],
            "daml_templates_needed": ["Bond"],
            "privacy_requirements": "party-based",
            "asset_type": "bond",
        }
        result = run_writer_agent(intent)
        assert result["success"], f"Writer failed: {result.get('error')}"
        code = result["daml_code"]
        assert "module" in code.lower()
        assert "template" in code.lower()
        assert "signatory" in code.lower()
        print(f"\n  code_length   : {len(code)} chars")
        print(f"  first_80_chars: {code[:80].strip()}")

    def test_generates_valid_daml_escrow(self, api_key_valid):
        if not api_key_valid:
            pytest.skip("LLM unavailable — check API key in backend/.env.ginie")
        from agents.writer_agent import run_writer_agent
        intent = {
            "contract_type": "escrow",
            "parties": ["buyer", "seller", "escrowAgent"],
            "key_features": ["fund deposit", "delivery confirmation", "dispute resolution"],
            "daml_templates_needed": ["Escrow"],
            "privacy_requirements": "multi-party visibility",
            "asset_type": "currency",
        }
        result = run_writer_agent(intent)
        assert result["success"]
        code = result["daml_code"]
        assert "template" in code.lower()
        assert "signatory" in code.lower()

    def test_has_module_declaration(self, api_key_valid):
        if not api_key_valid:
            pytest.skip("LLM unavailable — check API key in backend/.env.ginie")
        from agents.writer_agent import run_writer_agent
        intent = {
            "contract_type": "equity_token",
            "parties": ["company", "shareholder"],
            "key_features": ["dividend payment", "voting"],
            "daml_templates_needed": ["EquityToken"],
            "privacy_requirements": "standard",
            "asset_type": "equity",
        }
        result = run_writer_agent(intent)
        assert result["success"]
        assert result["daml_code"].startswith("module") or "module Main" in result["daml_code"]


# ---------------------------------------------------------------------------
# Compile Agent
# ---------------------------------------------------------------------------

class TestCompileAgent:
    SIMPLE_DAML = """\
module Main where

import Daml.Script

template SimpleContract
  with
    owner : Party
    counterparty : Party
    description : Text
  where
    signatory owner
    observer counterparty

    choice Accept : ()
      controller counterparty
      do
        return ()

    choice Reject : ()
      controller counterparty
      do
        return ()

setup : Script ()
setup = script do
  alice <- allocateParty "Alice"
  bob   <- allocateParty "Bob"
  submitMulti [alice] [] do
    createCmd SimpleContract with
      owner = alice
      counterparty = bob
      description = "Test"
  return ()
"""

    def test_sdk_discovery(self):
        from agents.compile_agent import resolve_daml_sdk
        try:
            path = resolve_daml_sdk()
            assert os.path.isfile(path)
            print(f"\n  sdk_path: {path}")
        except FileNotFoundError as exc:
            pytest.skip(f"Daml SDK not installed: {exc}")

    def test_compiles_valid_daml(self):
        from agents.compile_agent import run_compile_agent, resolve_daml_sdk
        try:
            resolve_daml_sdk()
        except FileNotFoundError:
            pytest.skip("Daml SDK not installed — skipping real compile test")

        result = run_compile_agent(self.SIMPLE_DAML, "test-compile-valid")
        assert result["success"], (
            f"Compile failed:\n{result.get('raw_error', '')}\n"
            f"Errors: {result.get('errors', [])}"
        )
        assert result["dar_path"]
        assert os.path.exists(result["dar_path"])
        print(f"\n  dar_path: {result['dar_path']}")

    def test_reports_errors_on_invalid_daml(self):
        from agents.compile_agent import run_compile_agent, resolve_daml_sdk
        try:
            resolve_daml_sdk()
        except FileNotFoundError:
            pytest.skip("Daml SDK not installed")

        bad_daml = "module Main where\n\ntemplate Broken\n  with\n    owner : Party\n  where\n    -- missing signatory\n    choice Foo : () controller owner do return ()\n"
        result = run_compile_agent(bad_daml, "test-compile-bad")
        assert not result["success"]
        assert len(result["errors"]) > 0
        print(f"\n  errors: {result['errors'][0]['message'][:80]}")

    def test_sdk_not_found_returns_structured_error(self, monkeypatch):
        from agents import compile_agent
        monkeypatch.setattr(compile_agent, "resolve_daml_sdk", lambda: (_ for _ in ()).throw(FileNotFoundError("SDK not found")))
        result = compile_agent.run_compile_agent("module Main where", "test-no-sdk")
        assert not result["success"]
        assert result["errors"][0]["error_type"] == "sdk_not_installed"


# ---------------------------------------------------------------------------
# Fix Agent
# ---------------------------------------------------------------------------

class TestFixAgent:
    def test_fix_improves_code(self, api_key_valid):
        if not api_key_valid:
            pytest.skip("LLM unavailable — check API key in backend/.env.ginie")
        from agents.fix_agent import run_fix_agent

        bad_code = "module Main where\n\ntemplate Broken\n  with\n    owner : Party\n  where\n    choice Foo : () controller owner do return ()\n"
        errors = [{"message": "No signatory found", "error_type": "missing_signatory", "line": 7, "fixable": True, "raw": ""}]

        result = run_fix_agent(bad_code, errors, attempt_number=1)
        assert result["success"], f"Fix agent failed: {result.get('error')}"
        fixed = result["fixed_code"]
        assert "signatory" in fixed.lower(), "Fix agent did not add signatory"
        print(f"\n  fixed snippet: {fixed[:120]}")

    def test_fix_regenerates_on_many_errors(self, api_key_valid):
        if not api_key_valid:
            pytest.skip("LLM unavailable — check API key in backend/.env.ginie")
        from agents.fix_agent import run_fix_agent

        bad_code = "this is not valid daml at all\n"
        errors = [{"message": f"error {i}", "error_type": "parse_error", "line": i, "fixable": True, "raw": ""} for i in range(6)]

        result = run_fix_agent(bad_code, errors, attempt_number=1)
        assert result["success"]
        assert "module" in result["fixed_code"].lower()


# ---------------------------------------------------------------------------
# Full pipeline (no deploy — requires SDK)
# ---------------------------------------------------------------------------

class TestPipelineCompile:
    def test_intent_to_compile(self, api_key_valid):
        if not api_key_valid:
            pytest.skip("Anthropic API key invalid")
        from agents.intent_agent import run_intent_agent
        from agents.writer_agent import run_writer_agent
        from agents.compile_agent import run_compile_agent, resolve_daml_sdk

        try:
            resolve_daml_sdk()
        except FileNotFoundError:
            pytest.skip("Daml SDK not installed")

        intent_result = run_intent_agent("Simple IOU contract between lender and borrower.")
        assert intent_result["success"]

        writer_result = run_writer_agent(intent_result["structured_intent"])
        assert writer_result["success"]

        compile_result = run_compile_agent(writer_result["daml_code"], "test-pipeline-compile")
        print(f"\n  compile_success: {compile_result['success']}")
        if not compile_result["success"]:
            print(f"  errors: {compile_result.get('error_summary', '')[:200]}")

        assert "success" in compile_result, "Compile agent must return a result dict with 'success' key"
        if not compile_result["success"]:
            errors = compile_result.get("errors", compile_result.get("compile_errors", []))
            assert len(errors) > 0, (
                "Compile agent returned success=False but provided no error details — "
                "caller cannot diagnose the failure"
            )
