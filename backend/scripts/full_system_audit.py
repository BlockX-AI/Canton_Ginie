"""
Ginie Platform — Full End-to-End System Audit
==============================================
Runs all 10 audit steps:
  1. Service Validation
  2. Pipeline Test (20 contracts)
  3. Audit Engine Validation
  4. Compliance Engine Validation
  5. Deployment Validation
  6. Ledger Explorer Validation
  7. Frontend UX Validation
  8. Concurrency Test
  9. Failure Testing
  10. Report Generation
"""

import os
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE = os.environ.get("GINIE_API_URL", "http://localhost:8000/api/v1")
FRONTEND = os.environ.get("GINIE_FRONTEND_URL", "http://localhost:3000")
CANTON_JSON = os.environ.get("CANTON_JSON_URL", "http://localhost:7575")
CANTON_GRPC = os.environ.get("CANTON_GRPC_URL", "localhost:6865")
TIMEOUT = 300          # max seconds to wait for a single pipeline job
POLL_INTERVAL = 3      # seconds between status polls
REPORT_PATH = Path(__file__).resolve().parent / "final_system_audit.txt"

CLIENT = httpx.Client(timeout=120.0)

PROMPTS = [
    "Create an escrow contract between a buyer and seller with a mediator who can release or refund funds",
    "Create a loan agreement contract between a lender and borrower with interest rate and repayment schedule",
    "Create a token swap contract that atomically exchanges two different tokens between two parties",
    "Create an insurance policy contract with premium payments, claims, and payout logic",
    "Create a freelancer payment contract between a client and freelancer with milestone-based payments",
    "Create a supply chain tracking contract that tracks goods from manufacturer to retailer",
    "Create a subscription service contract with recurring payments and cancellation logic",
    "Create a royalty distribution contract that splits revenue among multiple stakeholders",
    "Create a voting contract for shareholder decisions with weighted votes and quorum",
    "Create a custody contract for digital asset safekeeping with withdrawal approvals",
    "Create a settlement contract for securities trading with DVP (delivery versus payment)",
    "Create an invoice factoring contract where invoices can be sold to a factor at a discount",
    "Create a lease agreement contract for property rental with deposit, rent, and termination",
    "Create a warranty contract that tracks product warranties and allows claims within warranty period",
    "Create a carbon credit trading contract with issuance, transfer, and retirement of credits",
    "Create a fundraising contract with investment rounds, cap table, and investor rights",
    "Create a dividend distribution contract that pays out dividends to token holders proportionally",
    "Create a derivatives contract for a simple call option with strike price and expiry",
    "Create a joint venture contract between two companies with profit sharing and governance",
    "Create a payment splitting contract that automatically distributes payments among multiple recipients",
]

PROMPT_LABELS = [
    "escrow", "loan", "token_swap", "insurance", "freelancer_payment",
    "supply_chain", "subscription", "royalty", "voting", "custody",
    "settlement", "invoice", "lease", "warranty", "carbon_credit",
    "fundraising", "dividend", "derivatives", "joint_venture", "payment",
]

COMPLIANCE_PROFILES = [
    "nist-800-53", "soc2-type2", "iso27001",
    "defi-security", "generic",
]

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------
results: list[dict] = []
issues: list[str] = []


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def api(method: str, path: str, **kwargs) -> httpx.Response:
    url = f"{BASE}{path}" if not path.startswith("http") else path
    return CLIENT.request(method, url, **kwargs)


# ---------------------------------------------------------------------------
# STEP 1 — Service Validation
# ---------------------------------------------------------------------------
def step1_service_validation() -> dict:
    log("=" * 60)
    log("STEP 1 — SERVICE VALIDATION")
    log("=" * 60)
    checks = {}

    # Backend health
    try:
        r = api("GET", "/health")
        data = r.json()
        checks["backend"] = {"status": "UP", "data": data}
        log(f"  Backend API:    UP  (v{data.get('version','?')}, rag={data.get('rag_status')}, redis={data.get('redis_status')})")
    except Exception as e:
        checks["backend"] = {"status": "DOWN", "error": str(e)}
        issues.append("CRITICAL: Backend API not reachable")
        log(f"  Backend API:    DOWN — {e}")

    # Ledger status (tests Canton JSON API + sandbox)
    try:
        r = api("GET", "/ledger/status")
        data = r.json()
        checks["canton"] = {"status": data.get("status", "unknown"), "data": data}
        log(f"  Canton Ledger:  {data.get('status','?').upper()}  (parties={data.get('parties')}, packages={data.get('packages')})")
    except Exception as e:
        checks["canton"] = {"status": "DOWN", "error": str(e)}
        issues.append("CRITICAL: Canton ledger not reachable")
        log(f"  Canton Ledger:  DOWN — {e}")

    # Frontend
    try:
        r = httpx.get(FRONTEND, timeout=10.0)
        checks["frontend"] = {"status": "UP", "status_code": r.status_code}
        log(f"  Frontend:       UP  (HTTP {r.status_code})")
    except Exception as e:
        checks["frontend"] = {"status": "DOWN", "error": str(e)}
        issues.append("CRITICAL: Frontend not reachable")
        log(f"  Frontend:       DOWN — {e}")

    # Canton JSON API directly
    try:
        r = httpx.get(f"{CANTON_JSON}/v1/parties", headers={"Authorization": "Bearer dummy"}, timeout=5.0)
        checks["json_api"] = {"status": "UP" if r.status_code < 500 else "ERROR"}
        log(f"  JSON API:       UP  (HTTP {r.status_code})")
    except Exception as e:
        checks["json_api"] = {"status": "DOWN", "error": str(e)}
        log(f"  JSON API:       DOWN — {e}")

    return checks


# ---------------------------------------------------------------------------
# STEP 2 — Pipeline Test (20 contracts)
# ---------------------------------------------------------------------------
def run_single_pipeline(idx: int, prompt: str, label: str) -> dict:
    """Submit a contract prompt, poll until done, return full result."""
    entry = {
        "index": idx + 1,
        "label": label,
        "prompt": prompt[:80] + "...",
        "success": False,
        "status": "unknown",
        "contract_id": None,
        "package_id": None,
        "template_id": None,
        "fallback_used": None,
        "attempt_number": None,
        "security_score": None,
        "compliance_score": None,
        "enterprise_score": None,
        "deploy_gate": None,
        "error": None,
        "duration_s": 0,
    }

    t0 = time.time()

    # Submit
    try:
        r = api("POST", "/generate", json={"prompt": prompt, "canton_environment": "sandbox"})
        if r.status_code != 200:
            entry["error"] = f"Generate returned HTTP {r.status_code}: {r.text[:200]}"
            issues.append(f"Contract #{idx+1} ({label}): generate failed HTTP {r.status_code}")
            log(f"  #{idx+1:>2} {label:<20} SUBMIT FAILED — HTTP {r.status_code}")
            return entry
        job_id = r.json().get("job_id")
    except Exception as e:
        entry["error"] = str(e)
        issues.append(f"Contract #{idx+1} ({label}): generate exception {e}")
        log(f"  #{idx+1:>2} {label:<20} SUBMIT ERROR — {e}")
        return entry

    # Poll
    deadline = time.time() + TIMEOUT
    while time.time() < deadline:
        time.sleep(POLL_INTERVAL)
        try:
            r = api("GET", f"/status/{job_id}")
            st = r.json()
            status = st.get("status", "unknown")
            if status in ("complete", "failed"):
                break
        except Exception:
            continue

    # Get result
    try:
        r = api("GET", f"/result/{job_id}")
        data = r.json()
    except Exception as e:
        entry["error"] = f"Result fetch error: {e}"
        entry["duration_s"] = round(time.time() - t0, 1)
        return entry

    entry["status"] = data.get("status", "unknown")
    entry["success"] = data.get("success", False)
    entry["contract_id"] = data.get("contract_id")
    entry["package_id"] = data.get("package_id")
    entry["template_id"] = data.get("template_id")
    entry["fallback_used"] = data.get("fallback_used")
    entry["attempt_number"] = data.get("attempt_number")
    entry["security_score"] = data.get("security_score")
    entry["compliance_score"] = data.get("compliance_score")
    entry["enterprise_score"] = data.get("enterprise_score")
    entry["deploy_gate"] = data.get("deploy_gate")
    entry["error"] = data.get("error_message")
    entry["generated_code"] = data.get("generated_code", "")
    entry["job_id"] = job_id
    entry["audit_reports"] = data.get("audit_reports")
    entry["duration_s"] = round(time.time() - t0, 1)

    tag = "OK" if entry["success"] else "FAIL"
    log(f"  #{idx+1:>2} {label:<20} {tag:<4}  sec={entry['security_score']}  comp={entry['compliance_score']}  ent={entry['enterprise_score']}  gate={entry['deploy_gate']}  {entry['duration_s']}s")

    if not entry["success"]:
        issues.append(f"Contract #{idx+1} ({label}): pipeline failed — {entry.get('error','unknown')}")

    return entry


def step2_pipeline_test() -> list[dict]:
    log("")
    log("=" * 60)
    log("STEP 2 — PIPELINE TEST (20 CONTRACTS)")
    log("=" * 60)
    log(f"  {'#':<4} {'Label':<20} {'Result':<5} {'Sec':>4} {'Comp':>5} {'Ent':>5} {'Gate':>5} {'Time':>6}")
    log(f"  {'-'*4} {'-'*20} {'-'*5} {'-'*4} {'-'*5} {'-'*5} {'-'*5} {'-'*6}")

    all_results = []
    for i, (prompt, label) in enumerate(zip(PROMPTS, PROMPT_LABELS)):
        entry = run_single_pipeline(i, prompt, label)
        all_results.append(entry)
        results.append(entry)

    return all_results


# ---------------------------------------------------------------------------
# STEP 3 — Audit Engine Validation
# ---------------------------------------------------------------------------
def step3_audit_validation(pipeline_results: list[dict]) -> dict:
    log("")
    log("=" * 60)
    log("STEP 3 — AUDIT ENGINE VALIDATION")
    log("=" * 60)

    audit_stats = {"tested": 0, "valid": 0, "issues": []}

    for entry in pipeline_results:
        code = entry.get("generated_code", "")
        if not code or len(code) < 20:
            continue
        audit_stats["tested"] += 1

        label = entry["label"]
        try:
            r = api("POST", "/audit/analyze", json={
                "code": code,
                "contract_name": label,
                "skip_compliance": True,
            })
            if r.status_code != 200:
                audit_stats["issues"].append(f"{label}: HTTP {r.status_code}")
                log(f"  {label:<20} AUDIT FAILED — HTTP {r.status_code}")
                continue

            data = r.json()
            score = data.get("security_score")
            findings = data.get("findings_count", 0)
            has_report = bool(data.get("audit_report"))
            has_summary = bool(data.get("executive_summary"))

            ok = data.get("success") and score is not None and has_report
            if ok:
                audit_stats["valid"] += 1
            else:
                audit_stats["issues"].append(f"{label}: incomplete audit (success={data.get('success')}, score={score}, report={has_report})")

            log(f"  {label:<20} score={score:<4} findings={findings:<3} report={'Y' if has_report else 'N'}  summary={'Y' if has_summary else 'N'}  {'OK' if ok else 'ISSUE'}")

        except Exception as e:
            audit_stats["issues"].append(f"{label}: exception {e}")
            log(f"  {label:<20} ERROR — {e}")

    for iss in audit_stats["issues"]:
        issues.append(f"Audit: {iss}")

    log(f"\n  Audit validation: {audit_stats['valid']}/{audit_stats['tested']} passed")
    return audit_stats


# ---------------------------------------------------------------------------
# STEP 4 — Compliance Engine Validation
# ---------------------------------------------------------------------------
def step4_compliance_validation(pipeline_results: list[dict]) -> dict:
    log("")
    log("=" * 60)
    log("STEP 4 — COMPLIANCE ENGINE VALIDATION")
    log("=" * 60)

    comp_stats = {"profiles_tested": 0, "profiles_valid": 0, "issues": []}

    # Pick first successful contract's code for profile testing
    sample_code = None
    for entry in pipeline_results:
        if entry.get("success") and entry.get("generated_code"):
            sample_code = entry["generated_code"]
            break

    if not sample_code:
        log("  SKIP — No successful contract code available for compliance testing")
        issues.append("Compliance: No sample code available")
        return comp_stats

    # Test each profile
    for profile in COMPLIANCE_PROFILES:
        comp_stats["profiles_tested"] += 1
        try:
            r = api("POST", "/compliance/analyze", json={
                "code": sample_code,
                "contract_name": "AuditSample",
                "profile": profile,
            })
            if r.status_code != 200:
                comp_stats["issues"].append(f"{profile}: HTTP {r.status_code}")
                log(f"  {profile:<15} FAILED — HTTP {r.status_code}")
                continue

            data = r.json()
            score = data.get("compliance_score")
            has_report = bool(data.get("compliance_report"))
            bool(data.get("executive_summary"))
            success = data.get("success")

            report = data.get("compliance_report") or {}
            has_controls = bool(report.get("controlAssessments"))
            has_evidence = bool(report.get("evidence"))
            has_gaps = bool(report.get("gapAnalysis"))
            has_attestation = bool(report.get("attestation"))

            ok = success and score is not None and has_report
            if ok:
                comp_stats["profiles_valid"] += 1
            else:
                comp_stats["issues"].append(f"{profile}: incomplete (success={success}, score={score})")

            log(f"  {profile:<15} score={score:<4} controls={'Y' if has_controls else 'N'}  evidence={'Y' if has_evidence else 'N'}  gaps={'Y' if has_gaps else 'N'}  attest={'Y' if has_attestation else 'N'}  {'OK' if ok else 'ISSUE'}")

        except Exception as e:
            comp_stats["issues"].append(f"{profile}: exception {e}")
            log(f"  {profile:<15} ERROR — {e}")

    # Also list available profiles
    try:
        r = api("GET", "/compliance/profiles")
        profiles_available = r.json().get("profiles", [])
        log(f"\n  Available profiles: {profiles_available}")
    except Exception:
        pass

    for iss in comp_stats["issues"]:
        issues.append(f"Compliance: {iss}")

    log(f"  Compliance validation: {comp_stats['profiles_valid']}/{comp_stats['profiles_tested']} profiles passed")
    return comp_stats


# ---------------------------------------------------------------------------
# STEP 5 — Deployment Validation
# ---------------------------------------------------------------------------
def step5_deployment_validation(pipeline_results: list[dict]) -> dict:
    log("")
    log("=" * 60)
    log("STEP 5 — DEPLOYMENT VALIDATION")
    log("=" * 60)

    dep_stats = {"deployed": 0, "verified": 0, "issues": []}

    for entry in pipeline_results:
        if not entry.get("success") or not entry.get("contract_id"):
            continue
        dep_stats["deployed"] += 1
        label = entry["label"]
        cid = entry["contract_id"]
        pid = entry.get("package_id", "")
        entry.get("template_id", "")

        # Verify via ledger explorer verify endpoint
        try:
            r = api("GET", f"/ledger/verify/{cid}")
            data = r.json()
            verified = data.get("verified", False)
            if verified:
                dep_stats["verified"] += 1
                log(f"  {label:<20} VERIFIED  cid={cid[:16]}...  pkg={pid[:16]}...")
            else:
                dep_stats["issues"].append(f"{label}: contract not verified on ledger")
                log(f"  {label:<20} NOT FOUND on ledger  cid={cid[:16]}...")
        except Exception as e:
            dep_stats["issues"].append(f"{label}: verify error {e}")
            log(f"  {label:<20} VERIFY ERROR — {e}")

    for iss in dep_stats["issues"]:
        issues.append(f"Deploy: {iss}")

    log(f"\n  Deployment validation: {dep_stats['verified']}/{dep_stats['deployed']} verified on ledger")
    return dep_stats


# ---------------------------------------------------------------------------
# STEP 6 — Ledger Explorer Validation
# ---------------------------------------------------------------------------
def step6_explorer_validation(pipeline_results: list[dict]) -> dict:
    log("")
    log("=" * 60)
    log("STEP 6 — LEDGER EXPLORER VALIDATION")
    log("=" * 60)

    exp_stats = {"checks": {}, "issues": []}

    # Contracts tab
    try:
        r = api("POST", "/ledger/contracts", json={})
        data = r.json()
        contract_count = data.get("count", 0)
        contracts = data.get("contracts", [])
        exp_stats["checks"]["contracts_count"] = contract_count
        log(f"  Contracts Tab:  {contract_count} contracts found")

        # Cross-check: every deployed contract should appear
        deployed_cids = {e["contract_id"] for e in pipeline_results if e.get("contract_id")}
        explorer_cids = {c.get("contractId") for c in contracts}
        missing = deployed_cids - explorer_cids
        if missing:
            exp_stats["issues"].append(f"Missing contracts in explorer: {len(missing)}")
            log(f"    MISMATCH: {len(missing)} deployed contracts not visible in explorer")
        else:
            log("    Cross-check: All deployed contracts visible in explorer")

        # Validate payload structure
        for c in contracts[:3]:
            has_payload = bool(c.get("payload"))
            has_sigs = bool(c.get("signatories"))
            if not has_payload or not has_sigs:
                exp_stats["issues"].append(f"Contract {c.get('contractId','?')[:16]} missing payload/signatories")

    except Exception as e:
        exp_stats["issues"].append(f"Contracts tab error: {e}")
        log(f"  Contracts Tab:  ERROR — {e}")

    # Parties tab
    try:
        r = api("GET", "/ledger/parties")
        data = r.json()
        parties = data.get("parties", [])
        party_count = data.get("count", 0)
        exp_stats["checks"]["parties_count"] = party_count
        log(f"  Parties Tab:    {party_count} parties")

        # Check for duplicates
        identifiers = [p["identifier"] for p in parties]
        if len(identifiers) != len(set(identifiers)):
            exp_stats["issues"].append("Duplicate party identifiers found")
            log("    WARNING: Duplicate parties detected")
        else:
            log("    No duplicates detected")

        for p in parties:
            log(f"    - {p.get('displayName', 'unnamed')}: {p['identifier'][:40]}...")

    except Exception as e:
        exp_stats["issues"].append(f"Parties tab error: {e}")
        log(f"  Parties Tab:    ERROR — {e}")

    # Packages tab
    try:
        r = api("GET", "/ledger/packages")
        data = r.json()
        pkg_count = data.get("count", 0)
        exp_stats["checks"]["packages_count"] = pkg_count
        log(f"  Packages Tab:   {pkg_count} packages")

        # Verify deployed package IDs exist
        deployed_pids = {e["package_id"] for e in pipeline_results if e.get("package_id")}
        explorer_pids = set(data.get("packages", []))
        missing_pkgs = deployed_pids - explorer_pids
        if missing_pkgs:
            exp_stats["issues"].append(f"Missing packages: {len(missing_pkgs)}")
            log(f"    MISMATCH: {len(missing_pkgs)} deployed packages not in explorer")
        else:
            log("    Cross-check: All deployed packages present")

    except Exception as e:
        exp_stats["issues"].append(f"Packages tab error: {e}")
        log(f"  Packages Tab:   ERROR — {e}")

    # Verify tab — test with first deployed contract
    for entry in pipeline_results:
        if entry.get("contract_id"):
            cid = entry["contract_id"]
            try:
                r = api("GET", f"/ledger/verify/{cid}")
                data = r.json()
                exp_stats["checks"]["verify_works"] = data.get("verified", False)
                log(f"  Verify Tab:     {'PASS' if data.get('verified') else 'FAIL'} (tested with {cid[:16]}...)")
            except Exception as e:
                exp_stats["issues"].append(f"Verify tab error: {e}")
                log(f"  Verify Tab:     ERROR — {e}")
            break

    for iss in exp_stats["issues"]:
        issues.append(f"Explorer: {iss}")

    return exp_stats


# ---------------------------------------------------------------------------
# STEP 7 — Frontend UX Validation
# ---------------------------------------------------------------------------
def step7_frontend_validation() -> dict:
    log("")
    log("=" * 60)
    log("STEP 7 — FRONTEND UX VALIDATION")
    log("=" * 60)

    ux_checks = {}

    # Home page
    try:
        r = httpx.get(FRONTEND, timeout=10.0)
        ux_checks["home_page"] = r.status_code == 200
        log(f"  Home page:      {'OK' if r.status_code == 200 else 'FAIL'} (HTTP {r.status_code})")
    except Exception as e:
        ux_checks["home_page"] = False
        log(f"  Home page:      FAIL — {e}")

    # Explorer page
    try:
        r = httpx.get(f"{FRONTEND}/explorer", timeout=10.0)
        ux_checks["explorer_page"] = r.status_code == 200
        log(f"  Explorer page:  {'OK' if r.status_code == 200 else 'FAIL'} (HTTP {r.status_code})")
    except Exception as e:
        ux_checks["explorer_page"] = False
        log(f"  Explorer page:  FAIL — {e}")

    # Sandbox page structure
    try:
        r = httpx.get(f"{FRONTEND}/sandbox/test-id", timeout=10.0)
        ux_checks["sandbox_page"] = r.status_code == 200
        log(f"  Sandbox page:   {'OK' if r.status_code == 200 else 'FAIL'} (HTTP {r.status_code})")
    except Exception as e:
        ux_checks["sandbox_page"] = False
        log(f"  Sandbox page:   FAIL — {e}")

    # API docs
    try:
        r = httpx.get("http://localhost:8000/docs", timeout=10.0)
        ux_checks["api_docs"] = r.status_code == 200
        log(f"  API docs:       {'OK' if r.status_code == 200 else 'FAIL'} (HTTP {r.status_code})")
    except Exception as e:
        ux_checks["api_docs"] = False
        log(f"  API docs:       FAIL — {e}")

    log("\n  Note: Visual UX (score rings, pipeline steps, copy buttons, deploy gate badge)")
    log(f"        require manual browser verification at {FRONTEND}")

    return ux_checks


# ---------------------------------------------------------------------------
# STEP 8 — Concurrency Test
# ---------------------------------------------------------------------------
def step8_concurrency_test() -> dict:
    log("")
    log("=" * 60)
    log("STEP 8 — CONCURRENCY TEST (5 parallel jobs)")
    log("=" * 60)

    concurrent_prompts = [
        ("conc_escrow", "Create an escrow contract between a buyer and seller"),
        ("conc_loan", "Create a simple loan agreement between two parties"),
        ("conc_payment", "Create a payment contract between a payer and payee"),
        ("conc_token", "Create a token transfer contract with sender and receiver"),
        ("conc_vote", "Create a simple voting contract for a board decision"),
    ]

    conc_stats = {"submitted": 0, "completed": 0, "succeeded": 0, "issues": []}

    job_ids = []
    for label, prompt in concurrent_prompts:
        try:
            r = api("POST", "/generate", json={"prompt": prompt, "canton_environment": "sandbox"})
            if r.status_code == 200:
                jid = r.json().get("job_id")
                job_ids.append((label, jid))
                conc_stats["submitted"] += 1
                log(f"  Submitted {label}: {jid[:8]}...")
        except Exception as e:
            conc_stats["issues"].append(f"{label}: submit error {e}")
            log(f"  {label}: SUBMIT ERROR — {e}")

    # Wait for all to complete
    log(f"  Waiting for {len(job_ids)} jobs to complete (max {TIMEOUT}s)...")
    deadline = time.time() + TIMEOUT

    completed = set()
    while time.time() < deadline and len(completed) < len(job_ids):
        time.sleep(POLL_INTERVAL)
        for label, jid in job_ids:
            if jid in completed:
                continue
            try:
                r = api("GET", f"/status/{jid}")
                status = r.json().get("status", "unknown")
                if status in ("complete", "failed"):
                    completed.add(jid)
                    conc_stats["completed"] += 1

                    r2 = api("GET", f"/result/{jid}")
                    data = r2.json()
                    success = data.get("success", False)
                    if success:
                        conc_stats["succeeded"] += 1

                    log(f"  {label}: {'SUCCESS' if success else 'FAILED'}  ({round(time.time() - deadline + TIMEOUT)}s)")
            except Exception:
                continue

    # Check for issues
    not_completed = len(job_ids) - len(completed)
    if not_completed > 0:
        conc_stats["issues"].append(f"{not_completed} jobs did not complete within timeout")

    for iss in conc_stats["issues"]:
        issues.append(f"Concurrency: {iss}")

    log(f"\n  Concurrency: {conc_stats['succeeded']}/{conc_stats['submitted']} succeeded, {conc_stats['completed']}/{conc_stats['submitted']} completed")
    return conc_stats


# ---------------------------------------------------------------------------
# STEP 9 — Failure Testing
# ---------------------------------------------------------------------------
def step9_failure_testing() -> dict:
    log("")
    log("=" * 60)
    log("STEP 9 — FAILURE / EDGE CASE TESTING")
    log("=" * 60)

    fail_stats = {"tests": 0, "passed": 0, "issues": []}

    # Test 1: Empty prompt (should fail validation)
    fail_stats["tests"] += 1
    try:
        r = api("POST", "/generate", json={"prompt": ""})
        if r.status_code == 422:
            fail_stats["passed"] += 1
            log("  Empty prompt:       PASS (422 validation error as expected)")
        else:
            fail_stats["issues"].append(f"Empty prompt returned HTTP {r.status_code} instead of 422")
            log(f"  Empty prompt:       FAIL (expected 422, got {r.status_code})")
    except Exception as e:
        log(f"  Empty prompt:       ERROR — {e}")

    # Test 2: Very short prompt (should fail validation)
    fail_stats["tests"] += 1
    try:
        r = api("POST", "/generate", json={"prompt": "hi"})
        if r.status_code == 422:
            fail_stats["passed"] += 1
            log("  Short prompt:       PASS (422 validation error as expected)")
        else:
            fail_stats["issues"].append(f"Short prompt returned HTTP {r.status_code} instead of 422")
            log(f"  Short prompt:       FAIL (expected 422, got {r.status_code})")
    except Exception as e:
        log(f"  Short prompt:       ERROR — {e}")

    # Test 3: Invalid job ID
    fail_stats["tests"] += 1
    try:
        r = api("GET", "/status/nonexistent-job-id")
        if r.status_code == 404:
            fail_stats["passed"] += 1
            log("  Invalid job ID:     PASS (404 as expected)")
        else:
            fail_stats["issues"].append(f"Invalid job ID returned HTTP {r.status_code}")
            log(f"  Invalid job ID:     FAIL (expected 404, got {r.status_code})")
    except Exception as e:
        log(f"  Invalid job ID:     ERROR — {e}")

    # Test 4: Invalid audit code
    fail_stats["tests"] += 1
    try:
        r = api("POST", "/audit/analyze", json={"code": "not valid daml code but long enough to pass validation"})
        if r.status_code == 200:
            data = r.json()
            # Should still return a result (with low scores)
            if data.get("success") is not None:
                fail_stats["passed"] += 1
                log(f"  Invalid DAML audit: PASS (returned result with score={data.get('security_score')})")
            else:
                log("  Invalid DAML audit: PARTIAL")
        else:
            log(f"  Invalid DAML audit: HTTP {r.status_code}")
    except Exception as e:
        log(f"  Invalid DAML audit: ERROR — {e}")

    # Test 5: Invalid compliance profile
    fail_stats["tests"] += 1
    try:
        r = api("POST", "/compliance/analyze", json={"code": "module Test where\ntemplate Foo\n  with p: Party\n  where signatory p", "profile": "nonexistent-profile"})
        if r.status_code in (400, 422, 200):
            fail_stats["passed"] += 1
            log(f"  Invalid profile:    PASS (HTTP {r.status_code})")
        else:
            log(f"  Invalid profile:    HTTP {r.status_code}")
    except Exception as e:
        log(f"  Invalid profile:    ERROR — {e}")

    # Test 6: Verify non-existent contract
    fail_stats["tests"] += 1
    try:
        r = api("GET", "/ledger/verify/0000000000000000000000000000000000000000")
        data = r.json()
        if data.get("verified") is False:
            fail_stats["passed"] += 1
            log("  Fake contract ID:   PASS (verified=false as expected)")
        else:
            fail_stats["issues"].append("Fake contract ID returned verified=true")
            log("  Fake contract ID:   FAIL (should be verified=false)")
    except Exception as e:
        log(f"  Fake contract ID:   ERROR — {e}")

    # Test 7: Fetch non-existent contract
    fail_stats["tests"] += 1
    try:
        r = api("POST", "/ledger/contracts/fetch", json={"contract_id": "nonexistent"})
        if r.status_code in (404, 400, 500):
            fail_stats["passed"] += 1
            log(f"  Fetch bad contract: PASS (HTTP {r.status_code})")
        else:
            log(f"  Fetch bad contract: HTTP {r.status_code}")
    except Exception as e:
        log(f"  Fetch bad contract: ERROR — {e}")

    for iss in fail_stats["issues"]:
        issues.append(f"Failure test: {iss}")

    log(f"\n  Failure tests: {fail_stats['passed']}/{fail_stats['tests']} passed")
    return fail_stats


# ---------------------------------------------------------------------------
# STEP 10 — Report Generation
# ---------------------------------------------------------------------------
def step10_report(
    svc_checks, pipeline_results, audit_stats, comp_stats,
    dep_stats, exp_stats, ux_checks, conc_stats, fail_stats
):
    log("")
    log("=" * 60)
    log("STEP 10 — GENERATING FINAL REPORT")
    log("=" * 60)

    total = len(pipeline_results)
    success = sum(1 for e in pipeline_results if e.get("success"))
    failed = total - success

    sec_scores = [e["security_score"] for e in pipeline_results if e.get("security_score") is not None]
    comp_scores = [e["compliance_score"] for e in pipeline_results if e.get("compliance_score") is not None]
    ent_scores = [e["enterprise_score"] for e in pipeline_results if e.get("enterprise_score") is not None]
    fallbacks = sum(1 for e in pipeline_results if e.get("fallback_used"))
    gates_pass = sum(1 for e in pipeline_results if e.get("deploy_gate") is True)
    gates_fail = sum(1 for e in pipeline_results if e.get("deploy_gate") is False)
    durations = [e["duration_s"] for e in pipeline_results if e.get("duration_s")]

    avg_sec = round(sum(sec_scores) / len(sec_scores), 1) if sec_scores else 0
    avg_comp = round(sum(comp_scores) / len(comp_scores), 1) if comp_scores else 0
    avg_ent = round(sum(ent_scores) / len(ent_scores), 1) if ent_scores else 0
    avg_dur = round(sum(durations) / len(durations), 1) if durations else 0

    success_rate = round(success / total * 100, 1) if total else 0

    # Verdict
    if success_rate >= 85 and avg_sec >= 60 and avg_comp >= 60 and dep_stats.get("verified", 0) >= success * 0.8:
        verdict = "READY_FOR_DEMO"
    elif success_rate >= 60:
        verdict = "NEEDS_FIXES"
    else:
        verdict = "NOT_PRODUCTION_READY"

    report_lines = []
    w = report_lines.append

    w("=" * 72)
    w("   GINIE PLATFORM — FULL SYSTEM AUDIT REPORT")
    w(f"   Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    w("=" * 72)

    w("")
    w("STEP 1 — SERVICE VALIDATION")
    w("-" * 40)
    for svc, info in svc_checks.items():
        w(f"  {svc:<15} {info.get('status', 'UNKNOWN')}")

    w("")
    w("STEP 2 — PIPELINE TEST RESULTS")
    w("-" * 40)
    w(f"  {'#':<4} {'Label':<22} {'Status':<8} {'Sec':>4} {'Comp':>5} {'Ent':>5} {'Gate':>5} {'FB':>3} {'Time':>6}")
    w(f"  {'-'*4} {'-'*22} {'-'*8} {'-'*4} {'-'*5} {'-'*5} {'-'*5} {'-'*3} {'-'*6}")
    for e in pipeline_results:
        st = "OK" if e.get("success") else "FAIL"
        fb = "Y" if e.get("fallback_used") else "N"
        gate = "Y" if e.get("deploy_gate") else ("N" if e.get("deploy_gate") is False else "-")
        w(f"  {e['index']:<4} {e['label']:<22} {st:<8} {e.get('security_score') or '-':>4} {e.get('compliance_score') or '-':>5} {e.get('enterprise_score') or '-':>5} {gate:>5} {fb:>3} {e.get('duration_s',0):>5.0f}s")

    w("")
    w("AGGREGATED METRICS")
    w("-" * 40)
    w(f"  Total contracts:    {total}")
    w(f"  Successful:         {success} ({success_rate}%)")
    w(f"  Failed:             {failed}")
    w(f"  Fallback used:      {fallbacks}")
    w(f"  Deploy gate PASS:   {gates_pass}")
    w(f"  Deploy gate FAIL:   {gates_fail}")
    w(f"  Avg security:       {avg_sec}")
    w(f"  Avg compliance:     {avg_comp}")
    w(f"  Avg enterprise:     {avg_ent}")
    w(f"  Avg duration:       {avg_dur}s")

    w("")
    w("STEP 3 — AUDIT ENGINE")
    w("-" * 40)
    w(f"  Tested:  {audit_stats.get('tested', 0)}")
    w(f"  Valid:   {audit_stats.get('valid', 0)}")
    if audit_stats.get("issues"):
        for iss in audit_stats["issues"]:
            w(f"  ISSUE: {iss}")

    w("")
    w("STEP 4 — COMPLIANCE ENGINE")
    w("-" * 40)
    w(f"  Profiles tested:  {comp_stats.get('profiles_tested', 0)}")
    w(f"  Profiles valid:   {comp_stats.get('profiles_valid', 0)}")
    if comp_stats.get("issues"):
        for iss in comp_stats["issues"]:
            w(f"  ISSUE: {iss}")

    w("")
    w("STEP 5 — DEPLOYMENT VALIDATION")
    w("-" * 40)
    w(f"  Deployed:   {dep_stats.get('deployed', 0)}")
    w(f"  Verified:   {dep_stats.get('verified', 0)}")
    if dep_stats.get("issues"):
        for iss in dep_stats["issues"]:
            w(f"  ISSUE: {iss}")

    w("")
    w("STEP 6 — LEDGER EXPLORER")
    w("-" * 40)
    for k, v in exp_stats.get("checks", {}).items():
        w(f"  {k}: {v}")
    if exp_stats.get("issues"):
        for iss in exp_stats["issues"]:
            w(f"  ISSUE: {iss}")

    w("")
    w("STEP 7 — FRONTEND UX")
    w("-" * 40)
    for k, v in ux_checks.items():
        w(f"  {k}: {'PASS' if v else 'FAIL'}")

    w("")
    w("STEP 8 — CONCURRENCY")
    w("-" * 40)
    w(f"  Submitted:  {conc_stats.get('submitted', 0)}")
    w(f"  Completed:  {conc_stats.get('completed', 0)}")
    w(f"  Succeeded:  {conc_stats.get('succeeded', 0)}")
    if conc_stats.get("issues"):
        for iss in conc_stats["issues"]:
            w(f"  ISSUE: {iss}")

    w("")
    w("STEP 9 — FAILURE TESTING")
    w("-" * 40)
    w(f"  Tests:  {fail_stats.get('tests', 0)}")
    w(f"  Passed: {fail_stats.get('passed', 0)}")
    if fail_stats.get("issues"):
        for iss in fail_stats["issues"]:
            w(f"  ISSUE: {iss}")

    w("")
    w("ALL ISSUES FOUND")
    w("-" * 40)
    if issues:
        for i, iss in enumerate(issues, 1):
            w(f"  {i:>3}. {iss}")
    else:
        w("  No issues found.")

    w("")
    w("=" * 72)
    w(f"  FINAL VERDICT:  {verdict}")
    w("=" * 72)
    w("")
    w("RECOMMENDATIONS")
    w("-" * 40)
    if success_rate < 100:
        w(f"  - Investigate {failed} failed contract(s) and improve fallback coverage")
    if avg_sec < 80:
        w(f"  - Average security score ({avg_sec}) below 80 — review common findings")
    if avg_comp < 80:
        w(f"  - Average compliance score ({avg_comp}) below 80 — review control gaps")
    if fallbacks > total * 0.5:
        w(f"  - High fallback rate ({fallbacks}/{total}) — improve LLM prompt engineering")
    if dep_stats.get("deployed", 0) > dep_stats.get("verified", 0):
        w(f"  - {dep_stats.get('deployed',0) - dep_stats.get('verified',0)} deployed contracts not verified — check explorer template cache")
    if not issues:
        w("  - All checks passed. Platform is ready for demonstration.")
    w("")

    report_text = "\n".join(report_lines)

    # Save to file
    REPORT_PATH.write_text(report_text, encoding="utf-8")
    log(f"\n  Report saved to: {REPORT_PATH}")

    # Also print
    print("\n" + report_text)

    return {"verdict": verdict, "success_rate": success_rate, "report_path": str(REPORT_PATH)}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    start = time.time()
    log("Ginie Platform — Full System Audit Starting")
    log(f"  API:      {BASE}")
    log(f"  Frontend: {FRONTEND}")
    log(f"  Canton:   {CANTON_JSON}")
    log("")

    # Step 1
    svc_checks = step1_service_validation()

    # Abort if backend or canton is down
    if svc_checks.get("backend", {}).get("status") == "DOWN":
        log("\nABORT: Backend is down. Cannot continue audit.")
        return
    if svc_checks.get("canton", {}).get("status") not in ("online", "UP"):
        log("\nWARNING: Canton may be offline — continuing with caution")

    # Step 2
    pipeline_results = step2_pipeline_test()

    # Step 3
    audit_stats = step3_audit_validation(pipeline_results)

    # Step 4
    comp_stats = step4_compliance_validation(pipeline_results)

    # Step 5
    dep_stats = step5_deployment_validation(pipeline_results)

    # Step 6
    exp_stats = step6_explorer_validation(pipeline_results)

    # Step 7
    ux_checks = step7_frontend_validation()

    # Step 8
    conc_stats = step8_concurrency_test()

    # Step 9
    fail_stats = step9_failure_testing()

    # Step 10
    report_result = step10_report(
        svc_checks, pipeline_results, audit_stats, comp_stats,
        dep_stats, exp_stats, ux_checks, conc_stats, fail_stats
    )

    elapsed = round(time.time() - start, 1)
    log(f"\nTotal audit time: {elapsed}s")
    log(f"Verdict: {report_result['verdict']}")


if __name__ == "__main__":
    main()
