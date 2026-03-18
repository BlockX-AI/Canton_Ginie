"""Example: Full end-to-end pipeline — generate, audit, comply, deploy.

Demonstrates:
  1. Generate contract via AI
  2. Wait for pipeline completion
  3. Run standalone audit on generated code
  4. Run compliance against multiple profiles
  5. Fetch formatted audit reports

Usage:
    python -m sdk.examples.full_pipeline
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from sdk.client.ginie_client import GinieClient
from sdk.client.types import GinieAPIError, GinieTimeoutError


def main():
    client = GinieClient(
        base_url="http://localhost:8000/api/v1",
        timeout=60,
    )

    print("=" * 60)
    print("  Ginie SDK — Full Pipeline Example")
    print("=" * 60)

    # ── Step 1: Generate and deploy ──────────────────────────────
    prompt = "Create an escrow contract where a buyer deposits funds, a seller delivers goods, and an arbiter can resolve disputes"

    print(f"\n[1] Generating contract...")
    print(f"    Prompt: {prompt[:70]}...")

    def on_status(s):
        print(f"    [{s.progress:3d}%] {s.current_step}")

    try:
        result = client.full_pipeline(prompt=prompt, timeout=300, on_status=on_status)
    except GinieTimeoutError as e:
        print(f"    TIMEOUT: {e}")
        return
    except GinieAPIError as e:
        print(f"    ERROR: {e}")
        return

    print(f"\n    Status:      {result.status}")
    print(f"    Contract ID: {result.contract_id or 'N/A'}")
    print(f"    Security:    {result.security_score}/100" if result.security_score else "")
    print(f"    Compliance:  {result.compliance_score}/100" if result.compliance_score else "")

    if not result.generated_code:
        print("    No code generated — cannot run further analysis.")
        client.close()
        return

    code = result.generated_code

    # ── Step 2: Run standalone audit ─────────────────────────────
    print(f"\n[2] Running standalone security audit on generated code...")
    try:
        audit = client.run_audit(code=code, contract_name="EscrowContract")
        print(f"    Security Score:   {audit.security_score}/100")
        print(f"    Enterprise Score: {audit.enterprise_score}/100")
        print(f"    Deploy Gate:      {'PASS' if audit.deploy_gate else 'FAIL'}")
        print(f"    Findings:         {audit.findings_count}")
    except GinieAPIError as e:
        print(f"    Audit error: {e}")

    # ── Step 3: Run compliance against multiple profiles ─────────
    profiles = ["nist-800-53", "soc2-type2", "iso27001", "canton-dlt"]
    print(f"\n[3] Running compliance across {len(profiles)} profiles...")

    for profile in profiles:
        try:
            comp = client.run_compliance(code=code, profile=profile)
            score = comp.compliance_score or 0
            bar = "█" * (score // 5) + "░" * (20 - score // 5)
            print(f"    {profile:15s} [{bar}] {score}/100")
        except GinieAPIError as e:
            print(f"    {profile:15s} ERROR: {e}")

    # ── Step 4: Fetch formatted reports ──────────────────────────
    if result.job_id:
        print(f"\n[4] Fetching audit reports for job {result.job_id[:12]}...")
        try:
            reports = client.get_audit_report(result.job_id, format="all")
            available = reports.get("formats_available", [])
            print(f"    Available formats: {', '.join(available) if available else 'none'}")
            if reports.get("markdown_report"):
                md = reports["markdown_report"]
                print(f"    Markdown report: {len(md)} chars")
        except GinieAPIError as e:
            print(f"    Report error: {e}")

    # ── Step 5: Iterate on contract ──────────────────────────────
    print(f"\n[5] Iterating: adding penalty clause...")
    try:
        new_job_id = client.iterate_contract(
            job_id=result.job_id,
            feedback="Add a penalty clause that charges 5% fee if the seller misses the deadline",
        )
        print(f"    New job: {new_job_id}")
        print(f"    Waiting for iteration to complete...")
        iter_result = client.wait_for_completion(new_job_id, timeout=300, on_status=on_status)
        print(f"    Iteration status: {iter_result.status}")
        print(f"    Contract ID:      {iter_result.contract_id or 'N/A'}")
    except (GinieAPIError, GinieTimeoutError) as e:
        print(f"    Iteration error: {e}")

    print("\n" + "=" * 60)
    print("  Pipeline complete!")
    print("=" * 60)
    client.close()


if __name__ == "__main__":
    main()
