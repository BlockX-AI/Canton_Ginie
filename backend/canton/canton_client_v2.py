import base64
import json
import time
from typing import Optional

import httpx
import structlog


def make_sandbox_jwt(act_as: list[str], read_as: list[str] | None = None) -> str:
    """Generate an unsigned JWT accepted by the Canton wildcard auth service.

    WARNING: This produces an `alg=none` token and must ONLY be used in sandbox mode.
    For devnet/mainnet, use a real signed token via CANTON_TOKEN env var.
    """
    from config import get_settings
    settings = get_settings()
    if settings.canton_environment != "sandbox":
        raise RuntimeError(
            "make_sandbox_jwt() called in non-sandbox environment "
            f"({settings.canton_environment}). Use CANTON_TOKEN env var instead."
        )

    def _b64url(s: str) -> str:
        return base64.urlsafe_b64encode(s.encode()).rstrip(b"=").decode()

    header = _b64url(json.dumps({"alg": "none", "typ": "JWT"}, separators=(",", ":")))
    payload = _b64url(json.dumps({
        "sub": "ginie-sandbox",
        "ledgerId": "sandbox",
        "applicationId": "ginie-daml",
        "actAs": act_as,
        "readAs": read_as or act_as,
        "admin": True,
        "exp": int(time.time()) + 3600,
    }, separators=(",", ":")))

    _log = structlog.get_logger()
    _log.warning("Using unsigned JWT (alg=none) — sandbox mode only", act_as=act_as)
    return f"{header}.{payload}."

logger = structlog.get_logger()


class CantonClientV2:
    """
    Canton / DAML JSON API client.

    Targets the DAML SDK 2.x HTTP JSON API (v1 endpoints).
    Maintains the same interface as the planned v2 client so callers
    need no changes when upgrading to Canton 3.x.
    """

    def __init__(self, base_url: str, auth_token: Optional[str] = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = auth_token or "sandbox-token"

    def _headers(self, content_type: str = "application/json") -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": content_type,
        }

    # ------------------------------------------------------------------
    # DAR upload  →  POST /v1/packages
    # ------------------------------------------------------------------

    async def upload_dar(self, dar_path: str) -> tuple[bool, str]:
        try:
            with open(dar_path, "rb") as f:
                dar_bytes = f.read()

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/v1/packages",
                    content=dar_bytes,
                    headers=self._headers("application/octet-stream"),
                )

            if response.status_code in (200, 201):
                logger.info("DAR uploaded", path=dar_path, status=response.status_code)
                return True, ""

            return False, f"HTTP {response.status_code}: {response.text[:400]}"

        except FileNotFoundError:
            return False, f"DAR file not found: {dar_path}"
        except Exception as exc:
            return False, str(exc)

    async def get_packages(self) -> list[str]:
        """Return the list of loaded package IDs from the ledger."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/v1/packages",
                    headers=self._headers(),
                )
            if response.status_code == 200:
                data = response.json()
                return data.get("result", [])
        except Exception:
            pass
        return []

    # ------------------------------------------------------------------
    # Party allocation  →  POST /v1/parties/allocate
    # ------------------------------------------------------------------

    async def allocate_party(self, party_hint: str) -> tuple[bool, str, str]:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{self.base_url}/v1/parties/allocate",
                    json={
                        "displayName": party_hint,
                        "identifierHint": party_hint.lower().replace(" ", "-"),
                    },
                    headers=self._headers(),
                )

            if response.status_code in (200, 201):
                data = response.json()
                result = data.get("result", data)
                party_id = result.get("identifier") or result.get("party")
                if not party_id:
                    raise RuntimeError(
                        f"Party allocation for '{party_hint}' succeeded (HTTP {response.status_code}) "
                        "but Canton returned no identifier. Check Canton node logs."
                    )
                logger.info("Party allocated", hint=party_hint, party_id=party_id)
                return True, party_id, ""

            # Party already exists — fetch it from GET /v1/parties
            if response.status_code == 400 and "already exists" in response.text.lower():
                existing_id = await self._lookup_party(party_hint)
                if existing_id:
                    logger.info("Party already exists, reusing", hint=party_hint, party_id=existing_id)
                    return True, existing_id, ""

            return False, "", f"HTTP {response.status_code}: {response.text[:400]}"

        except Exception as exc:
            return False, "", str(exc)

    async def _lookup_party(self, party_hint: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/v1/parties",
                    headers=self._headers(),
                )
            if response.status_code == 200:
                data = response.json()
                parties = data.get("result", [])
                hint_lower = party_hint.lower().replace(" ", "-")
                for p in parties:
                    identifier = p.get("identifier", "")
                    display = p.get("displayName", "").lower()
                    if identifier.startswith(hint_lower + "::") or display == party_hint.lower():
                        return identifier
        except Exception:
            pass
        return ""

    # ------------------------------------------------------------------
    # Contract creation  →  POST /v1/create
    # ------------------------------------------------------------------

    def set_token(self, token: str) -> None:
        self.token = token

    async def create_contract(
        self,
        template_id: str,
        payload: dict,
        acting_party: str,
        command_id: Optional[str] = None,
    ) -> tuple[bool, str, str]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/v1/create",
                    json={
                        "templateId": template_id,
                        "payload": payload,
                    },
                    headers=self._headers(),
                )

            if response.status_code in (200, 201):
                data = response.json()
                result = data.get("result", data)
                contract_id = result.get("contractId") or result.get("contract_id")
                if contract_id:
                    logger.info("Contract created", contract_id=contract_id)
                    return True, contract_id, ""
                return False, "", f"No contractId in response: {response.text[:300]}"

            return False, "", f"HTTP {response.status_code}: {response.text[:400]}"

        except Exception as exc:
            return False, "", str(exc)

    # ------------------------------------------------------------------
    # Contract verification  →  POST /v1/query
    # ------------------------------------------------------------------

    async def verify_contract(
        self,
        contract_id: str,
        template_id: str | None = None,
    ) -> tuple[bool, str]:
        try:
            body: dict = {}
            if template_id:
                body["templateIds"] = [template_id]

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{self.base_url}/v1/query",
                    json=body,
                    headers=self._headers(),
                )

            if response.status_code != 200:
                return False, f"Query failed: HTTP {response.status_code}"

            data = response.json()
            results = data.get("result", [])
            for entry in results:
                if entry.get("contractId") == contract_id:
                    return True, ""

            return False, "Contract not found in active contracts"

        except Exception as exc:
            return False, str(exc)

    # ------------------------------------------------------------------
    # Health check  →  GET /livez
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{self.base_url}/livez",
                    headers=self._headers(),
                )
            return response.status_code == 200
        except Exception:
            return False
