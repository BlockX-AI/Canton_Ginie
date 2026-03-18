"""Example: Generate and deploy a DAML contract using the Ginie SDK.

Prerequisites:
    - Ginie backend running at http://localhost:8000
    - Canton sandbox running on port 6865
    - Canton JSON API running on port 7575

Usage:
    python -m sdk.examples.generate_and_deploy
"""

import sys
import os

# Allow running from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from sdk.client.ginie_client import GinieClient
from sdk.client.types import GinieAPIError, GinieTimeoutError


def main():
    client = GinieClient(
        base_url="http://localhost:8000/api/v1",
        timeout=60,
    )

    print("=" * 60)
    print("  Ginie SDK — Generate & Deploy Example")
    print("=" * 60)

    # Step 1: Check backend health
    print("\n[1] Checking backend health...")
    try:
        health = client.health()
        print(f"    DAML SDK: {health.get('daml_sdk', 'unknown')}")
        print(f"    RAG:      {health.get('rag_status', 'unknown')}")
        print(f"    Redis:    {health.get('redis_status', 'unknown')}")
    except GinieAPIError as e:
        print(f"    ERROR: Cannot reach Ginie backend — {e}")
        return

    # Step 2: Generate and deploy a contract
    prompt = "Create a bond contract between an issuer and investor with a face value, coupon rate, and maturity date"

    print(f"\n[2] Generating contract...")
    print(f"    Prompt: {prompt[:80]}...")

    def on_status(status):
        print(f"    [{status.progress:3d}%] {status.current_step}")

    try:
        result = client.full_pipeline(
            prompt=prompt,
            timeout=300,
            on_status=on_status,
        )
    except GinieTimeoutError as e:
        print(f"\n    TIMEOUT: {e}")
        return
    except GinieAPIError as e:
        print(f"\n    ERROR: {e}")
        return

    # Step 3: Display results
    print("\n" + "=" * 60)
    print("  RESULTS")
    print("=" * 60)

    if result.is_deployed:
        print(f"  Status:          ✅ Deployed")
        print(f"  Contract ID:     {result.contract_id}")
        print(f"  Package ID:      {result.package_id}")
        print(f"  Template ID:     {result.template_id}")
        print(f"  Explorer:        {result.explorer_link}")
        print(f"  Attempts:        {result.attempt_number}")

        if result.security_score is not None:
            print(f"\n  Security Score:  {result.security_score}/100")
        if result.compliance_score is not None:
            print(f"  Compliance:      {result.compliance_score}/100")
        if result.enterprise_score is not None:
            print(f"  Enterprise:      {result.enterprise_score}/100")
        if result.deploy_gate is not None:
            gate = "PASS" if result.deploy_gate else "FAIL"
            print(f"  Deploy Gate:     {gate}")

        if result.parties:
            print(f"\n  Parties:")
            for name, pid in result.parties.items():
                print(f"    {name}: {pid}")
    else:
        print(f"  Status:  ❌ Failed")
        print(f"  Error:   {result.error_message}")

    print("\n" + "=" * 60)
    client.close()


if __name__ == "__main__":
    main()
