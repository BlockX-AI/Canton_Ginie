import sys
import os
import time
import json

_BACKEND = os.path.join(os.path.dirname(__file__), "..", "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, os.path.abspath(_BACKEND))

import httpx

API_BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000")

PROMPTS = [
    "Simple payment contract between sender and receiver with amount and currency",
    "Bond contract between issuer and investor with faceValue, couponRate, and maturityDate",
    "Token swap contract between partyA and partyB exchanging tokenAmount at an agreed price",
    "Rental agreement between landlord and tenant with monthlyRent, deposit, and leaseEnd date",
    "Insurance policy between insurer and policyholder with premium, coverageAmount, and expiryDate",
    "Supply chain contract between manufacturer and distributor with quantity, unitPrice, and deliveryDate",
    "Escrow contract between buyer, seller, and escrowAgent with escrowAmount and releaseCondition",
    "Voting contract between organizer and voter with proposal text and deadline",
    "Loan agreement between lender and borrower with principal, interestRate, and repaymentDate",
    "NFT marketplace listing between seller and buyer with tokenId, askingPrice, and royaltyPercent",
]

POLL_INTERVAL = 15  # seconds between status checks
MAX_WAIT = 300      # max seconds to wait per contract


def submit_job(prompt: str) -> str:
    """Submit a generation job and return the job_id."""
    resp = httpx.post(
        f"{API_BASE}/api/v1/generate",
        json={"prompt": prompt},
        timeout=15.0,
    )
    resp.raise_for_status()
    return resp.json()["job_id"]


def poll_status(job_id: str) -> dict:
    """Poll until the job completes or fails."""
    start = time.time()
    while time.time() - start < MAX_WAIT:
        resp = httpx.get(f"{API_BASE}/api/v1/status/{job_id}", timeout=10.0)
        data = resp.json()
        status = data.get("status", "unknown")
        step = data.get("current_step", "")
        progress = data.get("progress", 0)
        print(f"    [{progress:3d}%] {step}")

        if status in ("complete", "failed", "error"):
            return data
        time.sleep(POLL_INTERVAL)

    return {"status": "timeout", "error_message": f"Timed out after {MAX_WAIT}s"}


def fetch_result(job_id: str) -> dict:
    """Fetch the final result for a completed job."""
    try:
        resp = httpx.get(f"{API_BASE}/api/v1/result/{job_id}", timeout=30.0)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        return {"error": str(e)}
    return {}


def main():
    print(f"=" * 70)
    print(f"  GINIE DAML — 10 Contract Generation Test")
    print(f"  API: {API_BASE}")
    print(f"=" * 70)

    # Quick health check
    try:
        health = httpx.get(f"{API_BASE}/api/v1/health", timeout=10.0)
        print(f"\n  Health check: {health.json().get('status', 'unknown')}\n")
    except Exception as e:
        print(f"\n  ERROR: Backend not reachable at {API_BASE}: {e}")
        sys.exit(1)

    results = []

    for i, prompt in enumerate(PROMPTS, 1):
        print(f"\n{'─' * 70}")
        print(f"  Contract {i}/10: {prompt[:60]}...")
        print(f"{'─' * 70}")

        try:
            job_id = submit_job(prompt)
            print(f"  Job ID: {job_id}")

            status_data = poll_status(job_id)
            status = status_data.get("status", "unknown")
            error = status_data.get("error_message", "")

            if status == "complete":
                result_data = fetch_result(job_id)
                contract_id = result_data.get("contract_id", "N/A")
                diagram_len = len(result_data.get("diagram_mermaid", ""))
                print(f"  ✓ SUCCESS — contract_id: {str(contract_id)[:40]}...")
                print(f"    Diagram: {diagram_len} chars")
                results.append({"index": i, "status": "SUCCESS", "prompt": prompt[:50], "contract_id": str(contract_id)[:40], "diagram_chars": diagram_len})
            else:
                print(f"  ✗ {status.upper()} — {error[:100]}")
                results.append({"index": i, "status": status.upper(), "prompt": prompt[:50], "error": error[:100]})

        except Exception as e:
            print(f"  ✗ EXCEPTION — {e}")
            results.append({"index": i, "status": "EXCEPTION", "prompt": prompt[:50], "error": str(e)[:100]})

    # Summary
    print(f"\n{'=' * 70}")
    print(f"  SUMMARY")
    print(f"{'=' * 70}")

    success = sum(1 for r in results if r["status"] == "SUCCESS")
    failed = len(results) - success

    for r in results:
        icon = "✓" if r["status"] == "SUCCESS" else "✗"
        print(f"  {icon} [{r['index']:2d}] {r['status']:<10} {r['prompt']}")

    print(f"\n  Total: {len(results)} | Success: {success} | Failed: {failed}")
    print(f"  Success Rate: {success}/{len(results)} ({100*success//max(len(results),1)}%)")
    print(f"{'=' * 70}\n")

    # Write results to file
    out_path = os.path.join(os.path.dirname(__file__), "test_10_results.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"  Results saved to: {out_path}")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
