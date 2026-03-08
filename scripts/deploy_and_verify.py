import sys
import os
import asyncio
import uuid
import httpx

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from pipeline.orchestrator import run_mvp_pipeline
from canton.canton_client_v2 import make_sandbox_jwt
from config import get_settings

settings = get_settings()


async def query_active_contracts(
    base_url: str = "http://localhost:7575",
    token: str = None,
    template_id: str = None,
) -> list:
    """Query Canton JSON API for active contracts."""
    if not token:
        token = settings.canton_token

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # /v1/query requires templateIds
    if template_id:
        request_body = {"templateIds": [template_id]}
    else:
        # Try to fetch packages and build a wildcard query
        request_body = {"templateIds": []}

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{base_url}/v1/query",
            json=request_body,
            headers=headers,
        )

    if response.status_code != 200:
        print(f"Error querying ledger: HTTP {response.status_code}")
        print(response.text)
        return []

    data = response.json()
    return data.get("result", [])


async def main():
    canton_url = "http://localhost:7575"

    # ------------------------------------------------------------------
    # Step 1: Deploy contract via pipeline
    # ------------------------------------------------------------------
    print("Deploying contract via pipeline...")

    job_id = f"demo-{uuid.uuid4()}"
    result = await run_mvp_pipeline(
        job_id=job_id,
        user_input="Create a bond contract between issuer and investor",
        canton_url=canton_url,
        auth_token=settings.canton_token,
        max_fix_attempts=5,
    )

    if not result.get("success"):
        print(f"\nPipeline failed at stage: {result.get('stage')}")
        print(f"Error: {result.get('error')}")
        sys.exit(1)

    deployed_contract_id = result["contract_id"]
    deployed_package_id = result.get("package_id", "")
    deployed_template_id = result.get("template_id", "")

    print(f"\nContract deployed: {deployed_contract_id}")
    print(f"Package ID:        {deployed_package_id}")

    # ------------------------------------------------------------------
    # Step 2: Query Canton ledger
    # ------------------------------------------------------------------
    # Regenerate JWT with the allocated party IDs so the query can see the contracts
    parties = result.get("parties", {})
    party_ids = list(parties.values()) if parties else []
    query_token = make_sandbox_jwt(act_as=party_ids) if party_ids else settings.canton_token

    print("\nQuerying Canton ledger...")

    contracts = await query_active_contracts(
        base_url=canton_url,
        token=query_token,
        template_id=deployed_template_id,
    )

    if not contracts:
        print("No active contracts found on the ledger")
        sys.exit(1)

    print(f"Found {len(contracts)} active contract(s)")

    # ------------------------------------------------------------------
    # Step 3: Verify deployed contract exists
    # ------------------------------------------------------------------
    found = None
    for contract in contracts:
        if contract.get("contractId") == deployed_contract_id:
            found = contract
            break

    if found:
        template_id = found.get("templateId", "N/A")
        arguments = found.get("payload", found.get("argument", {}))
        signatories = found.get("signatories", [])
        observers = found.get("observers", [])

        print()
        print("---------------------------------")
        print("CONTRACT VERIFIED ON LEDGER")
        print("---------------------------------")
        print(f"Contract ID: {found['contractId']}")
        print(f"Template:    {template_id}")
        print()
        if isinstance(arguments, dict):
            for key, value in arguments.items():
                print(f"  {key}: {value}")
        print()
        if signatories:
            print(f"Signatories: {', '.join(signatories)}")
        if observers:
            print(f"Observers:   {', '.join(observers)}")
        print("---------------------------------")
        sys.exit(0)
    else:
        print(f"\nContract not found on ledger: {deployed_contract_id}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
