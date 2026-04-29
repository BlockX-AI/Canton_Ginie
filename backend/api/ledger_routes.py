"""
Ledger Explorer API — Browse contracts, templates, parties, and packages on Canton.

Provides endpoints for verifying deployed contracts and inspecting ledger state,
similar to Daml Navigator but native to the Ginie platform.
"""

import json as _json
import pathlib as _pathlib
import tempfile
import structlog
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import get_settings
from canton.canton_client_v2 import make_sandbox_jwt


class ContractQueryRequest(BaseModel):
    template_ids: list[str] | None = None
    party: str | None = None


class ContractFetchRequest(BaseModel):
    contract_id: str
    template_id: str | None = None

logger = structlog.get_logger()


def _parse_acs_response(resp: httpx.Response) -> list[dict]:
    """Tolerant parser for Canton ACS query responses.

    Across Canton 3.4.x patch versions ``/v1/query`` /
    ``/v2/state/active-contracts`` can return ANY of three shapes:

    1. Envelope-wrapped JSON  : ``{"result": [{...}, ...]}``  (Canton 2.x default)
    2. Plain JSON array       : ``[{...}, {...}]``            (some 3.4 patches)
    3. Newline-delimited JSON : ``{...}\\n{...}\\n``           (other 3.4 patches)

    Production code that hard-codes shape #1 has been observed to break
    on patch upgrades (see "The Complete Guide" \u00a72.12). This helper
    accepts all three so the explorer survives Canton minor-version
    drift without manual intervention.

    Returns an empty list if the body is unparseable. Never raises.
    """
    text = (resp.text or "").strip()
    if not text:
        return []

    # Shape 1 / 2 : standard JSON.
    try:
        parsed = _json.loads(text)
    except _json.JSONDecodeError:
        parsed = None

    if isinstance(parsed, dict):
        # Envelope-wrapped (most common). Some implementations nest
        # under ``result``, others under ``contracts`` or ``activeContracts``.
        for key in ("result", "contracts", "activeContracts"):
            inner = parsed.get(key)
            if isinstance(inner, list):
                return [c for c in inner if isinstance(c, dict)]
        # Single-row dict response (rare, but treat it as a list of one).
        return [parsed] if parsed.get("contractId") else []

    if isinstance(parsed, list):
        return [c for c in parsed if isinstance(c, dict)]

    # Shape 3 : NDJSON. Parse line-by-line; ignore garbage lines.
    rows: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            obj = _json.loads(line)
        except _json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows

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
    Similar to ``daml ledger list-parties``.

    Soft-fails: if the Canton JSON API is unreachable or rejects the
    request (which happens when the bootstrap JWT scope grows past Canton's
    accepted size on a long-lived shared sandbox), we return an empty list
    with a ``ledger_error`` field rather than 500-ing. The Explorer UI then
    renders an empty state instead of a red error box, and authenticated
    users still see their own parties via ``/me/parties``.
    """
    try:
        data = await _json_api_request("GET", "/v1/parties")
    except HTTPException as e:
        logger.warning(
            "/ledger/parties soft-failing: Canton call failed",
            status=e.status_code,
            detail=str(e.detail)[:200],
        )
        return {
            "parties": [],
            "count": 0,
            "ledger_url": _canton_url(),
            "environment": _canton_env(),
            "ledger_error": f"Canton {e.status_code}: {str(e.detail)[:200]}",
        }
    except Exception as e:
        logger.warning("/ledger/parties soft-failing: unexpected error", error=str(e))
        return {
            "parties": [],
            "count": 0,
            "ledger_url": _canton_url(),
            "environment": _canton_env(),
            "ledger_error": f"Unexpected: {str(e)[:200]}",
        }

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

        # Tolerant parsing: handle envelope-wrapped, plain-array, and
        # NDJSON shapes that Canton 3.4.x patches have been observed to
        # use interchangeably. See ``_parse_acs_response``.
        for c in _parse_acs_response(resp):
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

    Soft-fails on Canton errors with the same shape as ``/ledger/parties``:
    a 200 response carrying an empty list and a ``ledger_error`` field
    rather than propagating Canton's 500. Authenticated users keep their
    own listing via ``/me/packages``; unauthenticated visitors see the
    Explorer's empty state instead of a red error box.
    """
    try:
        data = await _json_api_request("GET", "/v1/packages")
    except HTTPException as e:
        logger.warning(
            "/ledger/packages soft-failing: Canton call failed",
            status=e.status_code,
            detail=str(e.detail)[:200],
        )
        return {
            "packages": [],
            "count": 0,
            "environment": _canton_env(),
            "ledger_error": f"Canton {e.status_code}: {str(e.detail)[:200]}",
        }
    except Exception as e:
        logger.warning("/ledger/packages soft-failing: unexpected error", error=str(e))
        return {
            "packages": [],
            "count": 0,
            "environment": _canton_env(),
            "ledger_error": f"Unexpected: {str(e)[:200]}",
        }

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

def _db_derived_counts() -> tuple[int, int]:
    """Best-effort counts derived from our own Postgres tables.

    Used as a fallback (and floor) for ``/ledger/status`` when Canton's
    JSON API rejects the bootstrap JWT or is otherwise unreachable. The
    DB rows are what the Explorer's Parties / Packages tabs already
    render, so anchoring the stat cards to the same source guarantees
    the numbers and the lists agree.
    """
    try:
        from db.session import get_db_session
        from db.models import RegisteredParty, DeployedContract
        from sqlalchemy import func, distinct
        with get_db_session() as session:
            party_count = (
                session.query(func.count(distinct(RegisteredParty.party_id))).scalar()
                or 0
            )
            package_count = (
                session.query(func.count(distinct(DeployedContract.package_id)))
                .filter(
                    DeployedContract.package_id.isnot(None),
                    DeployedContract.package_id != "",
                )
                .scalar()
                or 0
            )
            return int(party_count), int(package_count)
    except Exception as exc:
        logger.warning("DB-derived counts unavailable", error=str(exc))
        return 0, 0


@ledger_router.get("/status")
async def ledger_status():
    """Check Canton ledger connectivity and basic stats.

    Counts are reported as ``max(canton_side, db_side)``: the DB knows
    everything we ourselves deployed, so even when Canton's listing
    endpoints reject our bootstrap JWT we never show ``-1`` / "—" to
    the user.
    """
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

    db_party_count, db_package_count = _db_derived_counts()

    if not reachable:
        # Even when Canton is unreachable we surface DB-known counts so
        # the dashboard never collapses to dashes after a transient
        # network blip or sandbox restart.
        return {
            "status": "offline",
            "canton_url": canton_url,
            "environment": env,
            "parties": db_party_count,
            "packages": db_package_count,
            "error": "Canton JSON API is not reachable",
        }

    # Canton-side counts (best-effort).
    party_count = -1
    package_count = -1
    try:
        party_data = await _json_api_request("GET", "/v1/parties")
        party_count = len(party_data.get("result", []))
    except Exception as exc:
        logger.info("Canton /v1/parties unavailable, falling back to DB count", error=str(exc))
    try:
        pkg_data = await _json_api_request("GET", "/v1/packages")
        package_count = len(pkg_data.get("result", []))
    except Exception as exc:
        logger.info("Canton /v1/packages unavailable, falling back to DB count", error=str(exc))

    # Take the max so we never under-report what we know exists. Negative
    # placeholders from a failed Canton call are dropped here.
    final_parties = max(party_count, db_party_count) if party_count >= 0 else db_party_count
    final_packages = max(package_count, db_package_count) if package_count >= 0 else db_package_count

    return {
        "status": "online",
        "canton_url": canton_url,
        "environment": env,
        "parties": final_parties,
        "packages": final_packages,
    }


# ---------------------------------------------------------------------------
# 8. Verify Contract (convenience — checks if contract exists on ledger)
# ---------------------------------------------------------------------------

def _lookup_deployed_contract(contract_id: str) -> dict | None:
    """Return persisted {template_id, package_id, party_id, deployed_at} for a
    contract from our ``deployed_contracts`` table, or None if unknown.

    This is the authoritative local source of truth for what we ourselves
    deployed — survives backend restarts, unlike the in-memory job dict.
    """
    try:
        from db.session import get_db_session
        from db.models import DeployedContract
        with get_db_session() as session:
            row = (
                session.query(DeployedContract)
                .filter(DeployedContract.contract_id == contract_id)
                .order_by(DeployedContract.id.desc())
                .first()
            )
            if not row:
                return None
            return {
                "template_id": row.template_id or "",
                "package_id": row.package_id or "",
                "party_id": row.party_id or "",
                "deployed_at": row.deployed_at.isoformat() if getattr(row, "deployed_at", None) else "",
                "canton_env": row.canton_env or "",
            }
    except Exception as exc:
        logger.warning("DeployedContract lookup failed", error=str(exc))
        return None


async def _reader_auth_header(act_as_party: str | None) -> dict:
    """Auth header scoped to a specific reader party when possible.

    Using a JWT that names the contract's signatory as ``actAs``/``readAs``
    is the *only* way ``/v1/query`` and ``/v1/fetch`` will return that
    contract; the generic bootstrap JWT is a reader of the ``sandbox``
    party which sees nothing.
    """
    env = _canton_env()
    if env == "sandbox" and act_as_party:
        token = make_sandbox_jwt([act_as_party])
        return {"Authorization": f"Bearer {token}"}
    return await _auth_header()


@ledger_router.get("/verify/{contract_id}")
async def verify_contract(contract_id: str):
    """Verify that a contract exists on the Canton ledger.

    Strategy (in order — each step is independent so one broken path
    never starves the others):

      1. Look up ``template_id`` + signatory ``party_id`` from the
         persistent ``deployed_contracts`` table.
      2. ``/v1/fetch`` with a JWT scoped to that signatory (fast path).
      3. ``/v1/query`` with the same scoped JWT and known template.
      4. ``/v1/query`` with the bootstrap JWT over every discovered
         template (legacy fallback — covers contracts we didn't deploy
         ourselves, e.g. those created directly via Navigator).
      5. If all ledger paths fail but we have a DB row, report
         ``deployed_but_unreachable`` so the UI can distinguish
         "ledger wiped" from "unknown contract id".
    """
    canton_url = _canton_url()

    # Step 1: persistent lookup (survives backend restarts).
    db_row = _lookup_deployed_contract(contract_id)
    db_template_id = db_row.get("template_id") if db_row else ""
    db_party_id = db_row.get("party_id") if db_row else ""

    # Fallback to in-memory job cache for contracts that were deployed
    # after the DB row was somehow missed (should be rare).
    if not db_template_id:
        try:
            from api.routes import _in_memory_jobs
            for job_data in _in_memory_jobs.values():
                if job_data.get("contract_id") == contract_id:
                    db_template_id = job_data.get("template_id", "") or db_template_id
                    db_party_id = job_data.get("party_id", "") or db_party_id
                    break
        except Exception:
            pass

    scoped_headers = {
        **await _reader_auth_header(db_party_id),
        "Content-Type": "application/json",
    }
    generic_headers = {**await _auth_header(), "Content-Type": "application/json"}

    async def _render(result: dict) -> dict:
        return {
            "verified": True,
            "contract_id": contract_id,
            "templateId": result.get("templateId", ""),
            "signatories": result.get("signatories", []),
            "observers": result.get("observers", []),
            "payload": result.get("payload", {}),
            "environment": _canton_env(),
        }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Step 2: scoped /v1/fetch (exact, cheapest).
            if db_template_id:
                try:
                    resp = await client.post(
                        f"{canton_url}/v1/fetch",
                        headers=scoped_headers,
                        json={"contractId": contract_id, "templateId": db_template_id},
                    )
                    if resp.status_code == 200:
                        result = resp.json().get("result")
                        if result:
                            return await _render(result)
                except Exception as exc:
                    logger.info("Scoped /v1/fetch failed", error=str(exc))

            # Step 3: scoped /v1/query over the known template.
            if db_template_id:
                try:
                    resp = await client.post(
                        f"{canton_url}/v1/query",
                        headers=scoped_headers,
                        json={"templateIds": [db_template_id]},
                    )
                    if resp.status_code == 200:
                        for entry in resp.json().get("result", []):
                            if entry.get("contractId") == contract_id:
                                return await _render(entry)
                except Exception as exc:
                    logger.info("Scoped /v1/query failed", error=str(exc))

            # Step 4: generic fallback — sweep every discovered template
            # with the bootstrap JWT. Slow but covers the "imported a
            # contract ID we never deployed" case.
            template_ids = _discover_template_ids()
            # Ensure we also try the DB-known template even if discovery
            # missed it (common after Canton restart wipes packages).
            if db_template_id and db_template_id not in template_ids:
                template_ids = [db_template_id, *template_ids]
            for tid in template_ids:
                try:
                    resp = await client.post(
                        f"{canton_url}/v1/query",
                        headers=generic_headers,
                        json={"templateIds": [tid]},
                    )
                    if resp.status_code == 200:
                        for entry in resp.json().get("result", []):
                            if entry.get("contractId") == contract_id:
                                return await _render(entry)
                except Exception:
                    continue

        # Step 5: contract not visible on the live ledger. Differentiate.
        if db_row:
            return {
                "verified": False,
                "contract_id": contract_id,
                "status": "deployed_but_unreachable",
                "error": (
                    "Contract was deployed (see deployment history) but is "
                    "no longer visible on the ledger. The Canton sandbox "
                    "state may have been reset since this contract was "
                    "created — redeploy to restore."
                ),
                "template_id": db_template_id,
                "deployed_at": db_row.get("deployed_at"),
                "environment": _canton_env(),
            }
        return {
            "verified": False,
            "contract_id": contract_id,
            "status": "unknown",
            "error": "Contract not found on ledger and not in deployment history.",
            "environment": _canton_env(),
        }

    except Exception as e:
        return {
            "verified": False,
            "contract_id": contract_id,
            "error": str(e),
            "environment": _canton_env(),
        }
