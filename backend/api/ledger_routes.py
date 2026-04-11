"""
Ledger Explorer API — Browse contracts, templates, parties, and packages on Canton.

Provides endpoints for verifying deployed contracts and inspecting ledger state,
similar to Daml Navigator but native to the Ginie platform.
"""

import os
import json as _json
import pathlib as _pathlib
import tempfile
import structlog
import httpx
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from config import get_settings
from canton.canton_client_v2 import make_sandbox_jwt


class ContractQueryRequest(BaseModel):
    template_ids: list[str] | None = None
    party: str | None = None


class ContractFetchRequest(BaseModel):
    contract_id: str
    template_id: str | None = None

logger = structlog.get_logger()

ledger_router = APIRouter(prefix="/ledger", tags=["ledger-explorer"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _canton_url() -> str:
    return get_settings().get_canton_url()


def _canton_env() -> str:
    return get_settings().canton_environment


async def _fetch_all_party_ids() -> list[str]:
    """Fetch all party identifiers from Canton (used for sandbox JWT)."""
    base = _canton_url()
    bootstrap_token = make_sandbox_jwt(["sandbox"])
    headers = {"Authorization": f"Bearer {bootstrap_token}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{base}/v1/parties", headers=headers)
        if resp.status_code == 200:
            result = resp.json().get("result", [])
            return [p["identifier"] for p in result if p.get("identifier")]
    except Exception:
        pass
    return []


async def _auth_header(act_as: list[str] | None = None) -> dict:
    """Build auth header for Canton JSON API."""
    env = _canton_env()
    if env == "sandbox":
        parties = act_as
        if not parties:
            parties = await _fetch_all_party_ids()
        if not parties:
            parties = ["sandbox"]
        token = make_sandbox_jwt(parties)
        return {"Authorization": f"Bearer {token}"}
    token = get_settings().canton_token
    if not token:
        raise HTTPException(status_code=500, detail="CANTON_TOKEN not set for non-sandbox environment. Set it in backend/.env.ginie")
    return {"Authorization": f"Bearer {token}"}


async def _json_api_request(method: str, path: str, body: dict | None = None, params: dict | None = None) -> dict:
    """Make a request to the Canton JSON API."""
    url = f"{_canton_url()}{path}"
    headers = {**await _auth_header(), "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            if method == "GET":
                resp = await client.get(url, headers=headers, params=params)
            else:
                resp = await client.post(url, headers=headers, json=body or {})
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail=f"Canton JSON API not reachable at {_canton_url()}. Is it running?"
        )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Canton JSON API request timed out")

    if resp.status_code >= 400:
        detail = resp.text[:500]
        try:
            detail = resp.json().get("errors", [resp.text[:500]])
        except Exception:
            pass
        raise HTTPException(status_code=resp.status_code, detail=f"Canton API error: {detail}")

    return resp.json()


# ---------------------------------------------------------------------------
# 1. List Parties
# ---------------------------------------------------------------------------

@ledger_router.get("/parties")
async def list_parties():
    """List all parties known to the ledger.

    Returns party identifiers, display names, and whether they are local.
    Similar to `daml ledger list-parties`.
    """
    data = await _json_api_request("GET", "/v1/parties")
    result = data.get("result", [])

    parties = []
    for p in result:
        parties.append({
            "identifier": p.get("identifier", ""),
            "displayName": p.get("displayName", ""),
            "isLocal": p.get("isLocal", False),
        })

    return {
        "parties": parties,
        "count": len(parties),
        "ledger_url": _canton_url(),
        "environment": _canton_env(),
    }


# ---------------------------------------------------------------------------
# 2. List Contracts (query)
# ---------------------------------------------------------------------------

_TEMPLATE_CACHE_PATH = _pathlib.Path(tempfile.gettempdir()) / "ginie_template_cache.json"


def _load_cached_template_ids() -> set[str]:
    """Load previously discovered template IDs from disk cache."""
    try:
        if _TEMPLATE_CACHE_PATH.exists():
            data = _json.loads(_TEMPLATE_CACHE_PATH.read_text())
            return set(data) if isinstance(data, list) else set()
    except Exception:
        pass
    return set()


def _save_cached_template_ids(tids: set[str]):
    """Persist template IDs to disk so they survive backend restarts."""
    try:
        _TEMPLATE_CACHE_PATH.write_text(_json.dumps(sorted(tids)))
    except Exception:
        pass


def _discover_template_ids() -> list[str]:
    """Discover template IDs from deployed jobs + persistent cache.

    Canton 2.x /v1/query requires at least one templateId.
    Canton 2.x /v1/packages/{id} returns binary DAR data (not JSON),
    so we cannot discover templates from packages.

    Strategy:
      1. Read template IDs from the in-memory job store (current session)
      2. Merge with IDs persisted on disk (previous sessions)
      3. Save merged set back to disk
    """
    from api.routes import _in_memory_jobs

    template_ids: set[str] = _load_cached_template_ids()

    for job_data in _in_memory_jobs.values():
        tid = job_data.get("template_id", "")
        if tid and ":" in tid:
            template_ids.add(tid)

    if template_ids:
        _save_cached_template_ids(template_ids)

    return list(template_ids)


@ledger_router.post("/contracts")
async def list_contracts(req: ContractQueryRequest = ContractQueryRequest()):
    """Query active contracts on the ledger.

    Args:
        req.template_ids: Optional list of fully qualified template IDs to filter by.
        req.party: Optional party to act as for the query.

    Returns list of active contracts with their details.
    Canton 2.x /v1/query requires templateIds — when none are provided
    we auto-discover them from uploaded packages.
    """
    template_ids = req.template_ids
    party = req.party
    act_as = [party] if party else None

    # Canton /v1/query requires templateIds — discover if not provided
    if not template_ids:
        template_ids = _discover_template_ids()
        if not template_ids:
            return {"contracts": [], "count": 0, "environment": _canton_env()}

    url = f"{_canton_url()}/v1/query"
    headers = {**await _auth_header(act_as=act_as), "Content-Type": "application/json"}

    # Query in batches to avoid overloading (max 20 templates per request)
    all_contracts = []
    batch_size = 20
    for i in range(0, len(template_ids), batch_size):
        batch = template_ids[i:i + batch_size]
        body = {"templateIds": batch}

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, headers=headers, json=body)
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Canton JSON API not reachable")
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Request timed out")

        if resp.status_code >= 400:
            # Some template batches may fail (e.g. stdlib templates) — skip them
            logger.warning("Contract query batch failed", status=resp.status_code, batch_start=i)
            continue

        data = resp.json()
        result = data.get("result", [])

        for c in result:
            all_contracts.append({
                "contractId": c.get("contractId", ""),
                "templateId": c.get("templateId", ""),
                "payload": c.get("payload", {}),
                "signatories": c.get("signatories", []),
                "observers": c.get("observers", []),
                "agreementText": c.get("agreementText", ""),
            })

    return {
        "contracts": all_contracts,
        "count": len(all_contracts),
        "environment": _canton_env(),
    }


# ---------------------------------------------------------------------------
# 3. Fetch Single Contract
# ---------------------------------------------------------------------------

@ledger_router.post("/contracts/fetch")
async def fetch_contract(req: ContractFetchRequest):
    """Fetch a specific contract by its ID.

    Args:
        req.contract_id: The contract ID to fetch.
        req.template_id: Optional template ID for faster lookup.
    """
    contract_id = req.contract_id
    template_id = req.template_id
    body = {"contractId": contract_id}
    if template_id:
        body["templateId"] = template_id

    data = await _json_api_request("POST", "/v1/fetch", body=body)
    result = data.get("result", {})

    if not result:
        raise HTTPException(status_code=404, detail=f"Contract {contract_id} not found on ledger")

    return {
        "contract": {
            "contractId": result.get("contractId", contract_id),
            "templateId": result.get("templateId", ""),
            "payload": result.get("payload", {}),
            "signatories": result.get("signatories", []),
            "observers": result.get("observers", []),
            "agreementText": result.get("agreementText", ""),
        },
        "found": True,
        "environment": _canton_env(),
    }


# ---------------------------------------------------------------------------
# 4. List Packages (uploaded DARs)
# ---------------------------------------------------------------------------

@ledger_router.get("/packages")
async def list_packages():
    """List all uploaded DAR packages on the ledger.

    Returns package IDs that have been uploaded to Canton.
    """
    data = await _json_api_request("GET", "/v1/packages")
    result = data.get("result", [])

    return {
        "packages": result,
        "count": len(result),
        "environment": _canton_env(),
    }


# ---------------------------------------------------------------------------
# 5. Get Package Details
# ---------------------------------------------------------------------------

@ledger_router.get("/packages/{package_id}")
async def get_package_detail(package_id: str):
    """Get details/status of a specific uploaded package."""
    try:
        data = await _json_api_request("GET", f"/v1/packages/{package_id}")
        return {
            "package_id": package_id,
            "found": True,
            "details": data,
            "environment": _canton_env(),
        }
    except HTTPException as e:
        if e.status_code == 404:
            return {"package_id": package_id, "found": False, "environment": _canton_env()}
        raise


# ---------------------------------------------------------------------------
# 6. Allocate Party
# ---------------------------------------------------------------------------

@ledger_router.post("/parties/allocate")
async def allocate_party(display_name: str, identifier_hint: str | None = None):
    """Allocate a new party on the ledger.

    Args:
        display_name: Human-readable name for the party.
        identifier_hint: Optional hint for the party identifier.
    """
    body = {"displayName": display_name}
    if identifier_hint:
        body["identifierHint"] = identifier_hint

    data = await _json_api_request("POST", "/v1/parties/allocate", body=body)
    result = data.get("result", {})

    return {
        "identifier": result.get("identifier", ""),
        "displayName": result.get("displayName", display_name),
        "isLocal": result.get("isLocal", True),
        "environment": _canton_env(),
    }


# ---------------------------------------------------------------------------
# 7. Ledger Health / Status
# ---------------------------------------------------------------------------

@ledger_router.get("/status")
async def ledger_status():
    """Check Canton ledger connectivity and basic stats."""
    canton_url = _canton_url()
    env = _canton_env()

    # Check reachability
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{canton_url}/v1/query",
                content=b'{"templateIds":[]}',
                headers={**await _auth_header(), "Content-Type": "application/json"},
            )
            reachable = resp.status_code < 500
    except Exception:
        reachable = False

    if not reachable:
        return {
            "status": "offline",
            "canton_url": canton_url,
            "environment": env,
            "error": "Canton JSON API is not reachable",
        }

    # Get party count
    try:
        party_data = await _json_api_request("GET", "/v1/parties")
        party_count = len(party_data.get("result", []))
    except Exception:
        party_count = -1

    # Get package count
    try:
        pkg_data = await _json_api_request("GET", "/v1/packages")
        package_count = len(pkg_data.get("result", []))
    except Exception:
        package_count = -1

    return {
        "status": "online",
        "canton_url": canton_url,
        "environment": env,
        "parties": party_count,
        "packages": package_count,
    }


# ---------------------------------------------------------------------------
# 8. Verify Contract (convenience — checks if contract exists on ledger)
# ---------------------------------------------------------------------------

@ledger_router.get("/verify/{contract_id}")
async def verify_contract(contract_id: str):
    """Verify that a contract exists on the Canton ledger.

    Returns verification status and contract details if found.
    Useful for confirming successful deployments.

    Strategy:
      1. Query with each discovered templateId (Canton 2.x requires templateIds)
      2. Search the results for the matching contractId
      Falls back to /v1/fetch with templateId when found via job store.
    """
    canton_url = _canton_url()
    headers = {**await _auth_header(), "Content-Type": "application/json"}

    try:
        # Strategy 1: Look up the template_id for this contract from job store
        from api.routes import _in_memory_jobs
        job_template_id = None
        for job_data in _in_memory_jobs.values():
            if job_data.get("contract_id") == contract_id:
                job_template_id = job_data.get("template_id", "")
                break

        async with httpx.AsyncClient(timeout=15.0) as client:
            # If we know the template, try /v1/fetch directly (fast path)
            if job_template_id:
                resp = await client.post(
                    f"{canton_url}/v1/fetch",
                    headers=headers,
                    json={"contractId": contract_id, "templateId": job_template_id},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    result = data.get("result")
                    if result:
                        return {
                            "verified": True,
                            "contract_id": contract_id,
                            "templateId": result.get("templateId", ""),
                            "signatories": result.get("signatories", []),
                            "observers": result.get("observers", []),
                            "payload": result.get("payload", {}),
                            "environment": _canton_env(),
                        }

            # Strategy 2: Query with all known template IDs and search for contract
            template_ids = _discover_template_ids()
            for tid in template_ids:
                try:
                    resp = await client.post(
                        f"{canton_url}/v1/query",
                        headers=headers,
                        json={"templateIds": [tid]},
                    )
                    if resp.status_code == 200:
                        for entry in resp.json().get("result", []):
                            if entry.get("contractId") == contract_id:
                                return {
                                    "verified": True,
                                    "contract_id": contract_id,
                                    "templateId": entry.get("templateId", ""),
                                    "signatories": entry.get("signatories", []),
                                    "observers": entry.get("observers", []),
                                    "payload": entry.get("payload", {}),
                                    "environment": _canton_env(),
                                }
                except Exception:
                    continue

        return {
            "verified": False,
            "contract_id": contract_id,
            "error": "Contract not found on ledger",
            "environment": _canton_env(),
        }

    except Exception as e:
        return {
            "verified": False,
            "contract_id": contract_id,
            "error": str(e),
            "environment": _canton_env(),
        }
