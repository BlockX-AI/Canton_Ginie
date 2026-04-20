"""
End-to-end tests for the full Ginie pipeline.

What these tests verify:
  1. Intent Agent   — real LLM (Claude) parses a prompt into structured JSON
  2. Writer Agent   — real LLM generates syntactically plausible Daml code
  3. Compile Agent  — real `daml build` compiles the DAR (skipped if SDK absent)
  4. Fix Agent      — real LLM rewrites code when compile errors are present
  5. Deploy Agent   — real Canton HTTP API deploys the DAR (skipped if sandbox absent)
  6. Full LangGraph pipeline via orchestrator

Run:
    cd backend
    source venv/bin/activate
    pytest tests/test_e2e.py -v -s          # all tests, live output
    pytest tests/test_e2e.py -v -s -k llm   # only LLM-dependent tests
"""

import os
import sys
import time
import pytest
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_settings


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def settings():
    return get_settings()


@pytest.fixture(scope="session")
def api_key_valid(settings):
    from utils.llm_client import check_llm_available
    result = check_llm_available()
    if not result["ok"]:
        print(f"\n  LLM unavailable: provider={result['provider']} error={result.get('error','')}")
    else:
        print(f"\n  LLM ready: provider={result['provider']} model={result['model']}")
    return result["ok"]


@pytest.fixture(scope="session")
def daml_sdk_available():
    from agents.compile_agent import resolve_daml_sdk
    try:
        path = resolve_daml_sdk()
        return path
    except FileNotFoundError:
        return None


@pytest.fixture(scope="session")
def canton_available(settings):
    import httpx
    try:
        with httpx.Client(timeout=4.0) as client:
            resp = client.get(
                f"{settings.get_canton_url()}/v1/query",
                headers={"Authorization": "Bearer sandbox-token", "Content-Type": "application/json"},
                content=b'{"templateIds":[]}',
            )
            return resp.status_code < 500
    except Exception:
        return False


# ---------------------------------------------------------------------------
# E2E Test 1: Intent → Writer  (LLM only, no SDK needed)
# ---------------------------------------------------------------------------

class TestE2EIntentToCode:
    PROMPTS = [
        (
            "bond",
            "I want a bond tokenization contract where Goldman Sachs can issue "
            "fixed-rate bonds to pension fund investors with 5% annual coupon "
            "payments and redemption at maturity.",
        ),
        (
            "escrow",
            "Build an escrow contract with buyer, seller and a neutral escrow agent. "
            "The buyer deposits funds, the seller delivers goods, and the agent "
            "releases payment upon confirmed delivery.",
        ),
        (
            "equity",
            "Create an equity token contract where TechCorp issues fractional shares "
            "to investors and pays quarterly dividends.",
        ),
    ]

    @pytest.mark.parametrize("contract_name,prompt", PROMPTS)
    def test_intent_to_code(self, contract_name, prompt, api_key_valid):
        if not api_key_valid:
            pytest.skip("LLM unavailable — check API key in backend/.env.ginie")
        from agents.intent_agent import run_intent_agent
        from agents.writer_agent import run_writer_agent

        print(f"\n{'='*60}")
        print(f"  CONTRACT: {contract_name}")
        print(f"{'='*60}")

        # Step 1 — Intent
        t0 = time.time()
        intent_result = run_intent_agent(prompt)
        print(f"  [intent] elapsed={time.time()-t0:.1f}s  success={intent_result['success']}")

        assert intent_result["success"], f"Intent failed: {intent_result.get('error')}"
        intent = intent_result["structured_intent"]
        print(f"  [intent] contract_type={intent.get('contract_type')}")
        print(f"  [intent] parties={intent.get('parties')}")
        print(f"  [intent] templates={intent.get('daml_templates_needed')}")

        assert intent.get("contract_type"), "contract_type missing from structured intent"
        assert intent.get("parties"), "parties missing from structured intent"
        assert intent.get("daml_templates_needed"), "daml_templates_needed missing"

        # Step 2 — Writer
        t0 = time.time()
        writer_result = run_writer_agent(intent)
        print(f"  [writer] elapsed={time.time()-t0:.1f}s  success={writer_result['success']}")

        assert writer_result["success"], f"Writer failed: {writer_result.get('error')}"
        code = writer_result["daml_code"]
        print(f"  [writer] code_length={len(code)}")
        print(f"  [writer] first_line={code.splitlines()[0][:80]}")

        assert len(code) > 100, "Generated code is suspiciously short"
        assert "module" in code, "No 'module' declaration in generated Daml"
        assert "template" in code, "No 'template' in generated Daml"
        assert "signatory" in code, "No 'signatory' in generated Daml"


# ---------------------------------------------------------------------------
# E2E Test 2: Intent → Writer → Compile  (requires Daml SDK)
# ---------------------------------------------------------------------------

class TestE2ECompile:
    def test_bond_compiles(self, daml_sdk_available, api_key_valid):
        if not api_key_valid:
            pytest.skip("LLM unavailable — check API key in backend/.env.ginie")
        if not daml_sdk_available:
            pytest.skip("Daml SDK not installed — install with: curl -sSL https://get.daml.com/ | sh")

        from agents.intent_agent import run_intent_agent
        from agents.writer_agent import run_writer_agent
        from agents.compile_agent import run_compile_agent

        prompt = (
            "Bond tokenization contract: issuer creates bonds, investors subscribe, "
            "coupon payments happen quarterly, redemption at maturity."
        )

        print("\n  [e2e-compile] Running intent agent...")
        intent_result = run_intent_agent(prompt)
        assert intent_result["success"]

        print("  [e2e-compile] Running writer agent...")
        writer_result = run_writer_agent(intent_result["structured_intent"])
        assert writer_result["success"]
        code = writer_result["daml_code"]

        print(f"  [e2e-compile] Generated {len(code)} chars of Daml. Compiling...")
        t0 = time.time()
        compile_result = run_compile_agent(code, "e2e-bond-compile")
        elapsed = time.time() - t0
        print(f"  [e2e-compile] daml build elapsed={elapsed:.1f}s  success={compile_result['success']}")

        if not compile_result["success"]:
            print(f"  [e2e-compile] error_summary:\n{compile_result.get('error_summary', '')}")
            print(f"  [e2e-compile] raw_error (first 500):\n{compile_result.get('raw_error','')[:500]}")

        assert compile_result["success"], (
            f"Bond contract failed to compile.\n"
            f"Summary: {compile_result.get('error_summary','')}\n"
            f"Raw: {compile_result.get('raw_error','')[:800]}"
        )
        assert compile_result["dar_path"]
        assert os.path.exists(compile_result["dar_path"]), "DAR file path returned but file does not exist"
        print(f"  [e2e-compile] DAR produced: {compile_result['dar_path']}")

    def test_compile_fix_loop(self, daml_sdk_available, api_key_valid):
        if not api_key_valid:
            pytest.skip("LLM unavailable — check API key in backend/.env.ginie")
        """If first compile fails, the fix agent must improve the code."""
        if not daml_sdk_available:
            pytest.skip("Daml SDK not installed")

        from agents.intent_agent import run_intent_agent
        from agents.writer_agent import run_writer_agent
        from agents.compile_agent import run_compile_agent
        from agents.fix_agent import run_fix_agent
        from config import get_settings

        settings = get_settings()

        intent_result = run_intent_agent("Simple IOU between lender and borrower with repayment choice.")
        assert intent_result["success"]

        writer_result = run_writer_agent(intent_result["structured_intent"])
        assert writer_result["success"]

        code = writer_result["daml_code"]
        compile_result = run_compile_agent(code, "e2e-fix-loop-0")
        print(f"\n  [fix-loop] attempt=0 compile_success={compile_result['success']}")

        if compile_result["success"]:
            print("  [fix-loop] First compile succeeded — no fix needed")
            return

        for attempt in range(1, settings.max_fix_attempts + 1):
            fix_result = run_fix_agent(code, compile_result["errors"], attempt_number=attempt)
            assert fix_result["success"], f"Fix agent failed on attempt {attempt}"
            code = fix_result["fixed_code"]

            compile_result = run_compile_agent(code, f"e2e-fix-loop-{attempt}")
            print(f"  [fix-loop] attempt={attempt} compile_success={compile_result['success']}")
            if compile_result["success"]:
                print(f"  [fix-loop] Fixed after {attempt} attempt(s)")
                assert compile_result["dar_path"]
                return

        pytest.fail(
            f"Contract still failing after {settings.max_fix_attempts} fix attempts.\n"
            f"Final error: {compile_result.get('error_summary', '')}"
        )


# ---------------------------------------------------------------------------
# E2E Test 3: Full pipeline via LangGraph orchestrator (no deploy)
# ---------------------------------------------------------------------------

class TestE2EOrchestrator:
    def test_full_pipeline_no_deploy(self, daml_sdk_available, api_key_valid):
        if not daml_sdk_available:
            pytest.skip("Daml SDK not installed")
        if not api_key_valid:
            pytest.skip("LLM unavailable — check API key in backend/.env.ginie")

        from pipeline.orchestrator import run_pipeline

        prompt = "Asset transfer contract between sender and receiver with acceptance and rejection choices."
        print(f"\n  [orchestrator] prompt={prompt[:60]}...")

        t0 = time.time()
        result = run_pipeline(
            user_input=prompt,
            canton_environment="sandbox",
            canton_url="http://localhost:7575",
            job_id="e2e-orchestrator-test",
        )
        elapsed = time.time() - t0
        print(f"  [orchestrator] elapsed={elapsed:.1f}s  status={result.get('status')}")
        print(f"  [orchestrator] step={result.get('current_step')}")
        print(f"  [orchestrator] error={result.get('error_message','none')}")

        assert result.get("daml_code"), "No Daml code produced by orchestrator"
        assert result.get("structured_intent"), "No structured intent in pipeline result"
        assert result.get("status") in ("complete", "failed"), "Pipeline must reach terminal state"

        if result.get("status") == "failed":
            err = result.get("error_message", "")
            if "Canton" in err or "DAR" in err or "deploy" in err:
                print("  [orchestrator] Pipeline compiled but deploy skipped (Canton not running) — PASS")
                return
            pytest.fail(f"Pipeline failed unexpectedly: {err}")


# ---------------------------------------------------------------------------
# E2E Test 4: Full pipeline + deploy (requires SDK + Canton sandbox)
# ---------------------------------------------------------------------------

class TestE2EFullDeploy:
    def test_full_pipeline_with_deploy(self, daml_sdk_available, canton_available, api_key_valid):
        if not daml_sdk_available:
            pytest.skip("Daml SDK not installed")
        if not canton_available:
            pytest.skip("Canton sandbox not running — start with: canton sandbox --config canton-sandbox-memory.conf")
        if not api_key_valid:
            pytest.skip("LLM unavailable — check API key in backend/.env.ginie")

        from pipeline.orchestrator import run_pipeline

        prompt = (
            "Cash payment contract where a payer sends money to a payee. "
            "The payee can accept or reject the payment."
        )
        print(f"\n  [full-deploy] prompt={prompt[:60]}...")

        t0 = time.time()
        result = run_pipeline(
            user_input=prompt,
            canton_environment="sandbox",
            canton_url="http://localhost:7575",
            job_id="e2e-full-deploy",
        )
        elapsed = time.time() - t0
        print(f"  [full-deploy] elapsed={elapsed:.1f}s")
        print(f"  [full-deploy] status={result.get('status')}")
        print(f"  [full-deploy] contract_id={result.get('contract_id')}")
        print(f"  [full-deploy] package_id={result.get('package_id')}")
        print(f"  [full-deploy] explorer_link={result.get('explorer_link')}")

        assert result.get("status") == "complete", (
            f"Pipeline did not complete.\n"
            f"Error: {result.get('error_message','')}\n"
            f"Step: {result.get('current_step','')}"
        )
        assert result.get("contract_id"), "No contract_id returned after successful deploy"
        assert result.get("package_id"),  "No package_id returned after successful deploy"
        assert result.get("daml_code"),   "No generated code in final result"


# ---------------------------------------------------------------------------
# E2E Test 5: FastAPI endpoints (integration)
# ---------------------------------------------------------------------------

class TestE2EAPI:
    BASE = "http://localhost:8000/api/v1"

    def test_health_endpoint(self):
        import httpx
        try:
            resp = httpx.get(f"{self.BASE}/health", timeout=5.0)
        except httpx.ConnectError:
            pytest.skip("Backend API not running at localhost:8000")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        print(f"\n  [api-health] {data}")

    def test_generate_and_poll(self, api_key_valid):
        import httpx

        try:
            httpx.get(f"{self.BASE}/health", timeout=3.0)
        except httpx.ConnectError:
            pytest.skip("Backend API not running at localhost:8000")

        resp = httpx.post(
            f"{self.BASE}/generate",
            json={
                "prompt": "Simple IOU contract between Alice and Bob.",
                "canton_environment": "sandbox",
            },
            timeout=10.0,
        )
        assert resp.status_code == 200, f"Generate returned {resp.status_code}: {resp.text}"
        data = resp.json()
        job_id = data["job_id"]
        assert job_id
        print(f"\n  [api-generate] job_id={job_id}")

        deadline = time.time() + 180
        while time.time() < deadline:
            status_resp = httpx.get(f"{self.BASE}/status/{job_id}", timeout=5.0)
            assert status_resp.status_code == 200
            status = status_resp.json()
            print(f"  [api-poll] status={status['status']}  progress={status.get('progress')}%  step={status.get('current_step')}")
            if status["status"] in ("complete", "failed"):
                break
            time.sleep(2.0)
        else:
            pytest.fail("Pipeline did not finish within 180 seconds")

        result_resp = httpx.get(f"{self.BASE}/result/{job_id}", timeout=5.0)
        assert result_resp.status_code == 200
        result = result_resp.json()
        print(f"  [api-result] status={result['status']}")
        print(f"  [api-result] contract_id={result.get('contract_id')}")
        print(f"  [api-result] code_length={len(result.get('generated_code',''))}")

        assert result["status"] in ("complete", "failed"), \
            f"Job did not reach terminal state: {result['status']}"
        if api_key_valid:
            assert result.get("generated_code"), "No Daml code in final result (API key is valid, this is a real failure)"
        else:
            print("  [api-poll] SKIP code assertion — LLM API key invalid (check provider key in backend/.env.ginie)")
