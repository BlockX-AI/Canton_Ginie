import sys
import os
import asyncio
import argparse
import httpx

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from config import get_settings
from canton.canton_client_v2 import make_sandbox_jwt

settings = get_settings()


async def query_active_contracts(
    base_url: str = "http://localhost:7575",
    token: str = None,
    template_id: str = None,
) -> list:
    """Query Canton JSON API for active contracts.

    Args:
        base_url: Canton JSON API URL.
        token: Bearer token (JWT). If None, uses settings.canton_token.
        template_id: Fully-qualified template ID to filter by (required by v1 API).
    """
    if not token:
        token = settings.canton_token

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    if template_id:
        request_body = {"templateIds": [template_id]}
    else:
        request_body = {"templateIds": []}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{base_url}/v1/query",
                json=request_body,
                headers=headers,
            )

        if response.status_code != 200:
            print(f"Error: HTTP {response.status_code}")
            print(response.text)
            return []

        data = response.json()
        contracts = data.get("result", [])

        if not contracts:
            print("No active contracts found on the ledger")
            return []

        print(f"\n=== Found {len(contracts)} active contract(s) ===\n")

        for contract in contracts:
            contract_id = contract.get("contractId", "N/A")
            tid = contract.get("templateId", "N/A")
            payload = contract.get("payload", contract.get("argument", {}))
            signatories = contract.get("signatories", [])
            observers = contract.get("observers", [])

            print("-------------------------------------")
            print(f"Contract ID:\n{contract_id}\n")
            print(f"Template:\n{tid}\n")

            if payload:
                print("Arguments:")
                if isinstance(payload, dict):
                    for key, value in payload.items():
                        print(f"  {key}: {value}")
                else:
                    print(f"  {payload}")
                print()

            if signatories:
                print(f"Signatories: {', '.join(signatories)}")

            if observers:
                print(f"Observers:   {', '.join(observers)}")

            print("-------------------------------------\n")

        return contracts

    except Exception as exc:
        print(f"Error querying ledger: {exc}")
        return []


def main():
    parser = argparse.ArgumentParser(description="Query active contracts on Canton ledger")
    parser.add_argument("--template-id", "-t", help="Fully-qualified template ID (packageId:Module:Template)")
    parser.add_argument("--party", "-p", action="append", help="Party ID to include in JWT actAs (repeatable)")
    parser.add_argument("--url", default="http://localhost:7575", help="Canton JSON API URL")
    args = parser.parse_args()

    token = None
    if args.party:
        token = make_sandbox_jwt(act_as=args.party)

    asyncio.run(query_active_contracts(
        base_url=args.url,
        token=token,
        template_id=args.template_id,
    ))


if __name__ == "__main__":
    main()
