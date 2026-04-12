"""
Pipeline integration tests — verifiable evidence that the system works.

These tests exercise the real pipeline against live services. They are
designed to run with `pytest -v -s` and produce structured output that
a reviewer can inspect.

Requires:
  - At least one LLM API key set in backend/.env.ginie
  - Canton sandbox running for deploy tests (optional — skipped if absent)
  - Daml SDK installed for compile tests (optional — skipped if absent)

Run:
    cd backend
    pytest tests/test_pipeline.py -v -s
    pytest tests/test_pipeline.py -v -s -k "compile"   # subset
"""

import os
import sys
import time
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_settings


# -- Fixtures ----------------------------------------------------------------

@pytest.fixture(scope="session")
def settings():
    return get_settings()


@pytest.fixture(scope="session")
def llm_available():
    from utils.llm_client import check_llm_available
    result = check_llm_available()
    return result["ok"]


@pytest.fixture(scope="session")
def daml_sdk():
    from agents.compile_agent import resolve_daml_sdk
    try:
        return resolve_daml_sdk()
    except FileNotFoundError:
        return None


@pytest.fixture(scope="session")
def canton_up(settings):
    import httpx
    try:
        r = httpx.get(
            f"{settings.get_canton_url()}/v1/query",
            headers={"Authorization": "Bearer sandbox-token", "Content-Type": "application/json"},
            content=b'{"templateIds":[]}',
            timeout=4.0,
        )
        return r.status_code < 500
    except Exception:
        return False


# -- Test prompts ------------------------------------------------------------

PROMPTS = [
    ("bond", "Bond contract between issuer and investor with 5% coupon and maturity date."),
    ("escrow", "Escrow payment between buyer, seller, and escrow agent who releases on delivery."),
    ("token_swap", "Token swap contract between partyA and partyB exchanging two different assets."),
    ("iou", "Simple IOU between lender and borrower with repayment choice."),
    ("custody", "Digital asset custody contract between custodian and asset owner."),
]


# -- 1. Intent + Writer (LLM only) ------------------------------------------

class TestIntentWriter:
    @pytest.mark.parametrize("name,prompt", PROMPTS[:3])
    def test_generates_daml(self, name, prompt, llm_available):
        if not llm_available:
            pytest.skip("No LLM API key configured")

        from agents.intent_agent import run_intent_agent
        from agents.writer_agent import run_writer_agent

        t0 = time.time()
        intent_result = run_intent_agent(prompt)
        assert intent_result["success"], f"Intent failed: {intent_result.get('error')}"
        intent = intent_result["structured_intent"]
        assert intent.get("contract_type")
        assert intent.get("parties")

        writer_result = run_writer_agent(intent)
        elapsed = time.time() - t0
        assert writer_result["success"], f"Writer failed: {writer_result.get('error')}"

        code = writer_result["daml_code"]
        assert len(code) > 100
        assert "module" in code
        assert "template" in code
        assert "signatory" in code
        print(f"  [{name}] OK  {elapsed:.1f}s  {len(code)} chars")


# -- 2. Compile (requires Daml SDK) -----------------------------------------

class TestCompile:
    def test_bond_compiles(self, llm_available, daml_sdk):
        if not llm_available:
            pytest.skip("No LLM API key")
        if not daml_sdk:
            pytest.skip("Daml SDK not installed")

        from agents.intent_agent import run_intent_agent
        from agents.writer_agent import run_writer_agent
        from agents.compile_agent import run_compile_agent

        intent = run_intent_agent(PROMPTS[0][1])
        assert intent["success"]
        writer = run_writer_agent(intent["structured_intent"])
        assert writer["success"]

        t0 = time.time()
        result = run_compile_agent(writer["daml_code"], "test-bond-compile")
        elapsed = time.time() - t0

        assert result["success"], f"Compile failed: {result.get('error_summary','')}"
        assert result["dar_path"]
        assert os.path.exists(result["dar_path"])
        print(f"  [compile] OK  {elapsed:.1f}s  DAR={result['dar_path']}")


# -- 3. Fix loop (compile + fix retry) --------------------------------------

class TestFixLoop:
    def test_fix_recovers(self, llm_available, daml_sdk):
        if not llm_available:
            pytest.skip("No LLM API key")
        if not daml_sdk:
            pytest.skip("Daml SDK not installed")

        from agents.intent_agent import run_intent_agent
        from agents.writer_agent import run_writer_agent
        from agents.compile_agent import run_compile_agent
        from agents.fix_agent import run_fix_agent

        settings = get_settings()

        intent = run_intent_agent(PROMPTS[3][1])
        assert intent["success"]
        writer = run_writer_agent(intent["structured_intent"])
        assert writer["success"]

        code = writer["daml_code"]
        result = run_compile_agent(code, "test-fix-0")
        if result["success"]:
            print("  [fix-loop] First compile succeeded, no fix needed")
            return

        for attempt in range(1, settings.max_fix_attempts + 1):
            fix = run_fix_agent(code, result["errors"], attempt_number=attempt)
            assert fix["success"], f"Fix agent failed on attempt {attempt}"
            code = fix["fixed_code"]
            result = run_compile_agent(code, f"test-fix-{attempt}")
            if result["success"]:
                print(f"  [fix-loop] Fixed after {attempt} attempt(s)")
                return

        pytest.fail(f"Still failing after {settings.max_fix_attempts} fix attempts")


# -- 4. Full pipeline (orchestrator) ----------------------------------------

class TestFullPipeline:
    def test_orchestrator_no_deploy(self, llm_available, daml_sdk):
        if not llm_available:
            pytest.skip("No LLM API key")
        if not daml_sdk:
            pytest.skip("Daml SDK not installed")

        from pipeline.orchestrator import run_pipeline

        t0 = time.time()
        result = run_pipeline(
            user_input=PROMPTS[1][1],
            canton_environment="sandbox",
            canton_url="http://localhost:7575",
            job_id="test-pipeline-no-deploy",
        )
        elapsed = time.time() - t0

        assert result.get("daml_code"), "No Daml code produced"
        assert result.get("structured_intent"), "No structured intent"
        print(f"  [orchestrator] {elapsed:.1f}s  status={result.get('status')}")

    def test_full_deploy(self, llm_available, daml_sdk, canton_up):
        if not llm_available:
            pytest.skip("No LLM API key")
        if not daml_sdk:
            pytest.skip("Daml SDK not installed")
        if not canton_up:
            pytest.skip("Canton sandbox not running")

        from pipeline.orchestrator import run_pipeline

        t0 = time.time()
        result = run_pipeline(
            user_input=PROMPTS[0][1],
            canton_environment="sandbox",
            canton_url="http://localhost:7575",
            job_id="test-pipeline-deploy",
        )
        elapsed = time.time() - t0

        assert result.get("status") == "complete", f"Pipeline failed: {result.get('error_message','')}"
        assert result.get("contract_id"), "No contract_id"
        assert result.get("package_id"), "No package_id"
        print(f"  [deploy] {elapsed:.1f}s  contract_id={result['contract_id'][:16]}...")


# -- 5. Security audit on generated code ------------------------------------

class TestAudit:
    def test_audit_produces_scores(self, llm_available):
        if not llm_available:
            pytest.skip("No LLM API key")

        from security.hybrid_auditor import run_hybrid_audit

        sample_code = '''module Main where

template Bond
  with
    issuer : Party
    investor : Party
    principal : Decimal
    couponRate : Decimal
  where
    signatory issuer
    observer investor

    choice Accept : ContractId Bond
      controller investor
      do create this
'''

        result = run_hybrid_audit(daml_code=sample_code, contract_name="Bond")
        assert result.get("success"), f"Audit failed: {result.get('error')}"
        scores = result.get("combined_scores", {})
        assert scores.get("security_score") is not None
        assert scores.get("compliance_score") is not None
        assert isinstance(scores.get("deploy_gate"), bool)
        print(f"  [audit] sec={scores['security_score']} comp={scores['compliance_score']} gate={scores['deploy_gate']}")


# -- 6. API endpoints (integration, requires running server) -----------------

class TestAPI:
    BASE = "http://localhost:8000/api/v1"

    def _server_up(self):
        import httpx
        try:
            httpx.get(f"{self.BASE}/health", timeout=3.0)
            return True
        except Exception:
            return False

    def test_health(self):
        if not self._server_up():
            pytest.skip("Backend not running at localhost:8000")
        import httpx
        resp = httpx.get(f"{self.BASE}/health", timeout=5.0)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        print(f"  [health] daml_sdk={data.get('daml_sdk')} rag={data.get('rag_status')}")

    def test_generate_and_poll(self, llm_available):
        if not self._server_up():
            pytest.skip("Backend not running at localhost:8000")

        import httpx
        resp = httpx.post(
            f"{self.BASE}/generate",
            json={"prompt": "Simple IOU between Alice and Bob.", "canton_environment": "sandbox"},
            timeout=10.0,
        )
        assert resp.status_code == 200
        job_id = resp.json()["job_id"]
        print(f"  [generate] job_id={job_id}")

        deadline = time.time() + 180
        while time.time() < deadline:
            status = httpx.get(f"{self.BASE}/status/{job_id}", timeout=5.0).json()
            if status["status"] in ("complete", "failed"):
                break
            time.sleep(3.0)

        result = httpx.get(f"{self.BASE}/result/{job_id}", timeout=5.0).json()
        assert result["status"] in ("complete", "failed")
        print(f"  [result] status={result['status']} contract_id={result.get('contract_id','N/A')}")
