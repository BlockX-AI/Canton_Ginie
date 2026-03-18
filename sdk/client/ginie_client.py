"""Ginie SDK — Core client for programmatic access to the Ginie platform.

Usage:
    from sdk import GinieClient

    client = GinieClient()
    result = client.full_pipeline("Create a bond contract between issuer and investor")
    print(result.contract_id, result.security_score)
"""

from __future__ import annotations

import time
import httpx

from sdk.client.config import GinieConfig
from sdk.client.types import (
    JobStatus,
    JobResult,
    AuditReport,
    ComplianceReport,
    GinieAPIError,
    GinieTimeoutError,
)


class GinieClient:
    """Python client for the Ginie DAML contract generation platform.

    Provides methods to generate contracts, run security audits,
    perform compliance checks, deploy to Canton, and fetch results.

    Args:
        base_url: Ginie backend API URL (default: http://localhost:8000/api/v1).
        timeout: Default HTTP request timeout in seconds.
        config: Optional GinieConfig instance for advanced configuration.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000/api/v1",
        timeout: int = 60,
        config: GinieConfig | None = None,
    ):
        if config:
            self._config = config
        else:
            self._config = GinieConfig(base_url=base_url, timeout=timeout)

        self._http = httpx.Client(
            base_url=self._config.base_url,
            timeout=self._config.timeout,
            headers=self._config.headers,
        )

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> "GinieClient":
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        """Close the underlying HTTP client."""
        self._http.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs) -> dict:
        """Execute an HTTP request and return parsed JSON."""
        try:
            resp = self._http.request(method, path, **kwargs)
        except httpx.TimeoutException as e:
            raise GinieAPIError(f"Request timed out: {e}", status_code=0)
        except httpx.ConnectError as e:
            raise GinieAPIError(
                f"Cannot connect to Ginie API at {self._config.base_url}: {e}",
                status_code=0,
            )

        if resp.status_code == 202:
            # Job still in progress — not an error, return status hint
            return {"status": "in_progress", "detail": resp.text}

        if resp.status_code >= 400:
            detail = ""
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text[:500]
            raise GinieAPIError(
                f"API error {resp.status_code}: {detail}",
                status_code=resp.status_code,
                detail=detail,
            )

        return resp.json()

    # ------------------------------------------------------------------
    # 1. Generate Contract
    # ------------------------------------------------------------------

    def generate_contract(
        self,
        prompt: str,
        canton_environment: str | None = None,
        canton_url: str | None = None,
    ) -> str:
        """Submit a contract generation request.

        Args:
            prompt: Natural language description of the desired contract.
            canton_environment: Target Canton environment (sandbox/devnet/mainnet).
            canton_url: Optional Canton JSON API URL override.

        Returns:
            job_id: Unique identifier for tracking the pipeline job.
        """
        payload: dict = {"prompt": prompt}
        if canton_environment:
            payload["canton_environment"] = canton_environment
        if canton_url:
            payload["canton_url"] = canton_url

        data = self._request("POST", "/generate", json=payload)
        job_id = data.get("job_id")
        if not job_id:
            raise GinieAPIError("No job_id returned from /generate")
        return job_id

    # ------------------------------------------------------------------
    # 2. Get Status
    # ------------------------------------------------------------------

    def get_status(self, job_id: str) -> JobStatus:
        """Get the current status of a pipeline job.

        Args:
            job_id: The job identifier returned by generate_contract().

        Returns:
            JobStatus with current pipeline progress.
        """
        data = self._request("GET", f"/status/{job_id}")
        return JobStatus.from_dict(data)

    # ------------------------------------------------------------------
    # 3. Get Result
    # ------------------------------------------------------------------

    def get_result(self, job_id: str) -> JobResult:
        """Get the full result of a completed job.

        Args:
            job_id: The job identifier.

        Returns:
            JobResult with contract details, audit scores, and deployment info.

        Raises:
            GinieAPIError: If the job is still in progress (HTTP 202) or not found.
        """
        data = self._request("GET", f"/result/{job_id}")
        if data.get("status") == "in_progress":
            raise GinieAPIError(
                "Job still in progress — use wait_for_completion() or poll get_status().",
                status_code=202,
            )
        return JobResult.from_dict(data)

    # ------------------------------------------------------------------
    # 4. Wait for Completion (Polling)
    # ------------------------------------------------------------------

    def wait_for_completion(
        self,
        job_id: str,
        poll_interval: float | None = None,
        timeout: float | None = None,
        on_status: callable | None = None,
    ) -> JobResult:
        """Poll until the job reaches a terminal state, then return the result.

        Args:
            job_id: The job identifier.
            poll_interval: Seconds between polls (default: config.poll_interval).
            timeout: Max seconds to wait (default: config.poll_timeout).
            on_status: Optional callback invoked with each JobStatus update.

        Returns:
            JobResult with the final pipeline output.

        Raises:
            GinieTimeoutError: If the job does not finish within the timeout.
            GinieAPIError: If the API is unreachable.
        """
        interval = poll_interval or self._config.poll_interval
        max_wait = timeout or self._config.poll_timeout
        start = time.time()

        while True:
            elapsed = time.time() - start
            if elapsed > max_wait:
                raise GinieTimeoutError(job_id, elapsed)

            status = self.get_status(job_id)
            if on_status:
                on_status(status)

            if status.is_terminal:
                return self.get_result(job_id)

            time.sleep(interval)

    # ------------------------------------------------------------------
    # 5. Run Security Audit
    # ------------------------------------------------------------------

    def run_audit(
        self,
        code: str,
        contract_name: str = "Contract",
        compliance_profile: str = "generic",
        skip_compliance: bool = False,
        skip_audit: bool = False,
    ) -> AuditReport:
        """Run a hybrid security + compliance audit on DAML source code.

        Args:
            code: DAML source code to audit.
            contract_name: Name of the contract being audited.
            compliance_profile: Compliance profile to evaluate against.
            skip_compliance: Skip the compliance analysis phase.
            skip_audit: Skip the security audit phase.

        Returns:
            AuditReport with scores, findings, and recommendations.
        """
        data = self._request("POST", "/audit/analyze", json={
            "code": code,
            "contract_name": contract_name,
            "compliance_profile": compliance_profile,
            "skip_compliance": skip_compliance,
            "skip_audit": skip_audit,
        })
        return AuditReport.from_dict(data)

    def run_audit_by_job(
        self,
        job_id: str,
        compliance_profile: str = "generic",
    ) -> AuditReport:
        """Run audit on a completed job's generated code.

        Args:
            job_id: The job identifier of a completed pipeline run.
            compliance_profile: Compliance profile to evaluate against.

        Returns:
            AuditReport with scores and findings.
        """
        data = self._request("POST", "/audit/byJob", json={
            "job_id": job_id,
            "compliance_profile": compliance_profile,
        })
        return AuditReport.from_dict(data)

    # ------------------------------------------------------------------
    # 6. Run Compliance Check
    # ------------------------------------------------------------------

    def run_compliance(
        self,
        code: str,
        contract_name: str = "Contract",
        profile: str = "nist-800-53",
    ) -> ComplianceReport:
        """Run compliance analysis on DAML source code.

        Args:
            code: DAML source code to analyze.
            contract_name: Name of the contract.
            profile: Compliance profile (nist-800-53, soc2-type2, iso27001,
                     defi-security, canton-dlt, generic).

        Returns:
            ComplianceReport with compliance score and assessment.
        """
        data = self._request("POST", "/compliance/analyze", json={
            "code": code,
            "contract_name": contract_name,
            "profile": profile,
        })
        return ComplianceReport.from_dict(data)

    def run_compliance_by_job(
        self,
        job_id: str,
        profile: str = "nist-800-53",
    ) -> ComplianceReport:
        """Run compliance check on a completed job's generated code.

        Args:
            job_id: The job identifier.
            profile: Compliance profile to evaluate against.

        Returns:
            ComplianceReport with compliance assessment.
        """
        data = self._request("POST", "/compliance/byJob", json={
            "job_id": job_id,
            "profile": profile,
        })
        return ComplianceReport.from_dict(data)

    # ------------------------------------------------------------------
    # 7. List Compliance Profiles
    # ------------------------------------------------------------------

    def list_compliance_profiles(self) -> dict:
        """List available compliance profiles and their descriptions.

        Returns:
            Dict with 'profiles' list and 'descriptions' mapping.
        """
        return self._request("GET", "/compliance/profiles")

    # ------------------------------------------------------------------
    # 8. Get Audit Report
    # ------------------------------------------------------------------

    def get_audit_report(self, job_id: str, format: str = "all") -> dict:
        """Get formatted audit reports for a completed job.

        Args:
            job_id: The job identifier.
            format: Report format — 'json', 'markdown', 'html', or 'all'.

        Returns:
            Dict with report content in requested format(s).
        """
        return self._request("GET", f"/audit/report/{job_id}", params={"format": format})

    # ------------------------------------------------------------------
    # 9. Full Pipeline (convenience)
    # ------------------------------------------------------------------

    def full_pipeline(
        self,
        prompt: str,
        canton_environment: str | None = None,
        canton_url: str | None = None,
        poll_interval: float | None = None,
        timeout: float | None = None,
        on_status: callable | None = None,
    ) -> JobResult:
        """Generate a contract and wait for full pipeline completion.

        This is a convenience method that combines generate_contract()
        and wait_for_completion() into a single call.

        Args:
            prompt: Natural language description of the desired contract.
            canton_environment: Target Canton environment.
            canton_url: Optional Canton JSON API URL.
            poll_interval: Seconds between status polls.
            timeout: Max seconds to wait for completion.
            on_status: Optional callback invoked with each status update.

        Returns:
            JobResult with the final pipeline output including contract ID,
            security scores, compliance scores, and deployment details.
        """
        job_id = self.generate_contract(
            prompt=prompt,
            canton_environment=canton_environment,
            canton_url=canton_url,
        )
        return self.wait_for_completion(
            job_id=job_id,
            poll_interval=poll_interval,
            timeout=timeout,
            on_status=on_status,
        )

    # ------------------------------------------------------------------
    # 10. Iterate on Contract
    # ------------------------------------------------------------------

    def iterate_contract(
        self,
        job_id: str,
        feedback: str,
        original_code: str | None = None,
    ) -> str:
        """Request modifications to an existing generated contract.

        Args:
            job_id: The original job identifier.
            feedback: Description of desired changes.
            original_code: Optional original code to modify.

        Returns:
            new_job_id: Job identifier for the iteration.
        """
        payload: dict = {"feedback": feedback}
        if original_code:
            payload["original_code"] = original_code

        data = self._request("POST", f"/iterate/{job_id}", json=payload)
        return data.get("job_id", "")

    # ------------------------------------------------------------------
    # 11. Health Check
    # ------------------------------------------------------------------

    def health(self) -> dict:
        """Check the health of the Ginie backend API.

        Returns:
            Dict with DAML SDK version, RAG status, and Redis status.
        """
        return self._request("GET", "/health")
