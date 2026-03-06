import structlog
import httpx
from typing import Optional

logger = structlog.get_logger()


class CantonClient:
    def __init__(self, base_url: str, token: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.token    = token
        self.headers  = {
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {token}" if token else "Bearer sandbox-token",
        }

    def health_check(self) -> bool:
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.base_url}/v1/query", headers=self.headers)
                return response.status_code < 500
        except Exception:
            return False

    def upload_dar(self, dar_bytes: bytes) -> dict:
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    f"{self.base_url}/v1/packages",
                    content=dar_bytes,
                    headers={
                        **self.headers,
                        "Content-Type": "application/octet-stream",
                    },
                )
                if response.status_code in (200, 201):
                    return {"success": True, "data": response.json()}
                return {"success": False, "error": response.text, "status": response.status_code}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_packages(self) -> list[str]:
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(f"{self.base_url}/v1/packages", headers=self.headers)
                if response.status_code == 200:
                    data = response.json()
                    return data.get("result", [])
        except Exception as e:
            logger.warning("Failed to list packages", error=str(e))
        return []

    def create_contract(self, template_id: str, payload: dict) -> dict:
        try:
            with httpx.Client(timeout=30.0) as client:
                body = {"templateId": template_id, "payload": payload}
                response = client.post(
                    f"{self.base_url}/v1/create",
                    json=body,
                    headers=self.headers,
                )
                if response.status_code in (200, 201):
                    data = response.json()
                    return {"success": True, "contract_id": data.get("result", {}).get("contractId", "")}
                return {"success": False, "error": response.text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def query_contracts(self, template_id: str) -> list[dict]:
        try:
            with httpx.Client(timeout=10.0) as client:
                body = {"templateIds": [template_id]}
                response = client.post(
                    f"{self.base_url}/v1/query",
                    json=body,
                    headers=self.headers,
                )
                if response.status_code == 200:
                    data = response.json()
                    return data.get("result", [])
        except Exception as e:
            logger.warning("Failed to query contracts", error=str(e))
        return []

    def get_contract(self, contract_id: str) -> Optional[dict]:
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(
                    f"{self.base_url}/v1/contract/{contract_id}",
                    headers=self.headers,
                )
                if response.status_code == 200:
                    return response.json().get("result")
        except Exception as e:
            logger.warning("Failed to get contract", error=str(e))
        return None
