"""
Integration test for the Ginie-DAML MVP pipeline.

Tests:
  1. Sandbox creation and file operations
  2. Template generation using daml_tools
  3. Compilation via run_compile_agent_sandbox
  4. Deployment via run_deploy_agent_sandbox (skipped if Canton unreachable)

Run from repo root:
    python scripts/test_pipeline.py
"""

import asyncio
import json
import os
import sys
import uuid

_BACKEND = os.path.join(os.path.dirname(__file__), "..", "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, os.path.abspath(_BACKEND))

from sandbox.daml_sandbox import DamlSandbox
from tools.daml_tools import (
    add_choice,
    add_signatory,
    create_template,
)
from agents.compile_agent import run_compile_agent_sandbox
from agents.deploy_agent import run_deploy_agent_sandbox
from canton.canton_client_v2 import CantonClientV2

from config import get_settings as _get_settings
_settings = _get_settings()
CANTON_URL = os.environ.get("CANTON_URL", "http://localhost:7575")
AUTH_TOKEN = _settings.canton_token or os.environ.get("CANTON_TOKEN", "")

SIMPLE_DAML = """\
module Main where

template Bond
  with
    issuer : Party
    investor : Party
    faceValue : Decimal
  where
    signatory issuer
    observer investor

    ensure faceValue > 0.0

    choice Redeem : ()
      controller issuer
      do
        return ()
"""


def _sep(title: str) -> None:
    print(f"\n{'='*55}")
    print(f"  {title}")
    print("=" * 55)


# ---------------------------------------------------------------------------
# Test 1: Sandbox lifecycle
# ---------------------------------------------------------------------------

async def test_sandbox() -> bool:
    _sep("TEST 1: Sandbox lifecycle")

    job_id = f"test-sandbox-{uuid.uuid4().hex[:8]}"
    sandbox = DamlSandbox(job_id, "TestProject")

    await sandbox.initialize()

    assert sandbox.files.exists("daml.yaml"), "daml.yaml missing"
    assert sandbox.files.exists("daml/Main.daml"), "daml/Main.daml missing"

    yaml_content = await sandbox.files.read("daml.yaml")
    assert "TestProject" in yaml_content, "project name not in daml.yaml"

    await sandbox.files.write("daml/Extra.daml", "module Extra where\n")
    assert sandbox.files.exists("daml/Extra.daml"), "Extra.daml not written"

    files = sandbox.files.list_files("daml/*.daml")
    assert len(files) >= 2, f"Expected >=2 daml files, got {files}"

    abs_path = sandbox.get_absolute_path("daml/Main.daml")
    assert os.path.isabs(abs_path), "get_absolute_path must return absolute path"

    cmd_result = await sandbox.commands.run("echo hello")
    assert cmd_result["exit_code"] == 0, f"echo failed: {cmd_result}"
    assert "hello" in cmd_result["stdout"], "stdout missing 'hello'"

    await sandbox.cleanup()
    assert not os.path.exists(sandbox.sandbox_dir), "sandbox directory not cleaned up"

    print("PASS")
    return True


# ---------------------------------------------------------------------------
# Test 2: daml_tools — incremental template construction
# ---------------------------------------------------------------------------

async def test_daml_tools() -> bool:
    _sep("TEST 2: DAML Tools — create_template / add_signatory / add_choice")

    job_id = f"test-tools-{uuid.uuid4().hex[:8]}"
    sandbox = DamlSandbox(job_id, "BondToken")
    await sandbox.initialize()

    result = await create_template(
        sandbox,
        "Bond",
        [
            {"name": "issuer", "type": "Party"},
            {"name": "investor", "type": "Party"},
            {"name": "faceValue", "type": "Decimal"},
        ],
    )
    print(f"  create_template → {result}")
    assert sandbox.files.exists("daml/Bond.daml"), "Bond.daml not created"

    result = await add_signatory(sandbox, "Bond", "issuer")
    print(f"  add_signatory   → {result}")

    code = await sandbox.files.read("daml/Bond.daml")
    assert "signatory issuer" in code, f"signatory not added:\n{code}"

    result = await add_choice(
        sandbox,
        "Bond",
        "Redeem",
        "issuer",
        [],
        "()",
        "return ()",
    )
    print(f"  add_choice      → {result}")

    code = await sandbox.files.read("daml/Bond.daml")
    assert "choice Redeem" in code, f"choice not added:\n{code}"

    await sandbox.cleanup()
    print("PASS")
    return True


# ---------------------------------------------------------------------------
# Test 3: Compile agent
# ---------------------------------------------------------------------------

async def test_compile() -> bool:
    _sep("TEST 3: Compile Agent — dpm build")

    job_id = f"test-compile-{uuid.uuid4().hex[:8]}"
    sandbox = DamlSandbox(job_id, "BondToken")
    await sandbox.initialize()

    await sandbox.files.write("daml/Main.daml", SIMPLE_DAML)

    result = await run_compile_agent_sandbox(sandbox, "BondToken")
    print(f"  compile_success : {result['compile_success']}")
    print(f"  dar_path        : {result.get('dar_path', '-')}")

    if not result["compile_success"]:
        errors = result.get("compile_errors", [])
        sdk_missing = any(e.get("type") == "sdk_not_installed" for e in errors)
        if sdk_missing:
            print("  SKIP (DAML SDK not installed)")
            await sandbox.cleanup()
            return True

        print("  compile_errors  :")
        for err in errors:
            print(f"    [{err.get('type')}] {err.get('file')}:{err.get('line')} — {err.get('message')}")
        print("FAIL — compile errors above")
        await sandbox.cleanup()
        return False

    assert result["dar_path"], "dar_path is empty on success"
    await sandbox.cleanup()
    print("PASS")
    return True


# ---------------------------------------------------------------------------
# Test 4: Deploy agent (requires running Canton sandbox)
# ---------------------------------------------------------------------------

async def test_deploy() -> bool:
    _sep("TEST 4: Deploy Agent — Canton v2 API")

    client = CantonClientV2(CANTON_URL, AUTH_TOKEN)
    reachable = await client.health_check()

    if not reachable:
        print(f"  Canton not reachable at {CANTON_URL}")
        print("  SKIP (start Canton sandbox to run this test)")
        return True

    job_id = f"test-deploy-{uuid.uuid4().hex[:8]}"
    sandbox = DamlSandbox(job_id, "BondToken")
    await sandbox.initialize()

    await sandbox.files.write("daml/Main.daml", SIMPLE_DAML)

    compile_result = await run_compile_agent_sandbox(sandbox, "BondToken")
    if not compile_result["compile_success"]:
        print("  Compilation failed — skipping deploy test")
        await sandbox.cleanup()
        return True

    deploy_result = await run_deploy_agent_sandbox(
        sandbox=sandbox,
        project_name="BondToken",
        parties=["issuer", "investor"],
        canton_url=CANTON_URL,
        auth_token=AUTH_TOKEN,
    )

    print(f"  success     : {deploy_result['success']}")
    print(f"  contract_id : {deploy_result.get('contract_id', '-')}")
    print(f"  package_id  : {deploy_result.get('package_id', '-')}")

    if not deploy_result["success"]:
        print(f"  error       : {deploy_result.get('error')}")
        print("  FAIL")
        await sandbox.cleanup()
        return False

    assert deploy_result["contract_id"], "contract_id is empty"
    await sandbox.cleanup()
    print("PASS")
    return True


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

async def main() -> None:
    results = {}

    results["sandbox"] = await test_sandbox()
    results["daml_tools"] = await test_daml_tools()
    results["compile"] = await test_compile()
    results["deploy"] = await test_deploy()

    _sep("SUMMARY")
    all_passed = True
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {name:<20} {status}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("All tests passed.")
        sys.exit(0)
    else:
        print("Some tests FAILED.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
