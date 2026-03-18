"""Ginie SDK — Unit tests.

Tests the SDK client against the live Ginie backend.
Requires backend, Canton sandbox, and JSON API to be running.

Usage:
    python -m pytest sdk/tests/test_sdk.py -v
    python -m sdk.tests.test_sdk
"""

import sys
import os
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from sdk.client.ginie_client import GinieClient
from sdk.client.config import GinieConfig
from sdk.client.types import (
    JobStatus,
    JobResult,
    AuditReport,
    ComplianceReport,
    GinieAPIError,
    GinieTimeoutError,
)

BASE_URL = os.environ.get("GINIE_API_URL", "http://localhost:8000/api/v1")

SAMPLE_DAML = """module Main where

template SimpleToken
  with
    owner : Party
    name : Text
    amount : Decimal
  where
    signatory owner
    ensure amount > 0.0

    choice Transfer : ContractId SimpleToken
      with
        newOwner : Party
      controller owner
      do
        create this with owner = newOwner
"""


class TestGinieConfig(unittest.TestCase):
    """Test configuration defaults and overrides."""

    def test_defaults(self):
        cfg = GinieConfig()
        self.assertEqual(cfg.base_url, "http://localhost:8000/api/v1")
        self.assertEqual(cfg.timeout, 60)
        self.assertEqual(cfg.poll_interval, 3.0)
        self.assertEqual(cfg.poll_timeout, 300.0)
        self.assertEqual(cfg.canton_environment, "sandbox")

    def test_override(self):
        cfg = GinieConfig(base_url="http://remote:9000/api/v1", timeout=120)
        self.assertEqual(cfg.base_url, "http://remote:9000/api/v1")
        self.assertEqual(cfg.timeout, 120)


class TestTypes(unittest.TestCase):
    """Test response type constructors and properties."""

    def test_job_status_from_dict(self):
        s = JobStatus.from_dict({
            "job_id": "abc-123",
            "status": "running",
            "current_step": "Compiling...",
            "progress": 50,
        })
        self.assertEqual(s.job_id, "abc-123")
        self.assertEqual(s.status, "running")
        self.assertFalse(s.is_complete)
        self.assertFalse(s.is_terminal)

    def test_job_status_terminal(self):
        s = JobStatus.from_dict({"job_id": "x", "status": "complete"})
        self.assertTrue(s.is_complete)
        self.assertTrue(s.is_terminal)

        f = JobStatus.from_dict({"job_id": "y", "status": "failed"})
        self.assertTrue(f.is_failed)
        self.assertTrue(f.is_terminal)

    def test_job_result_deployed(self):
        r = JobResult.from_dict({
            "job_id": "j1",
            "status": "complete",
            "contract_id": "cid-001",
            "security_score": 85,
        })
        self.assertTrue(r.is_deployed)
        self.assertEqual(r.security_score, 85)

    def test_job_result_not_deployed(self):
        r = JobResult.from_dict({"job_id": "j2", "status": "failed"})
        self.assertFalse(r.is_deployed)

    def test_audit_report_from_dict(self):
        a = AuditReport.from_dict({
            "success": True,
            "security_score": 78,
            "deploy_gate": True,
            "findings_count": 3,
        })
        self.assertTrue(a.success)
        self.assertEqual(a.security_score, 78)
        self.assertTrue(a.deploy_gate)

    def test_compliance_report_from_dict(self):
        c = ComplianceReport.from_dict({
            "success": True,
            "compliance_score": 92,
            "profile": "nist-800-53",
        })
        self.assertEqual(c.compliance_score, 92)
        self.assertEqual(c.profile, "nist-800-53")

    def test_exceptions(self):
        err = GinieAPIError("test", status_code=500, detail="Internal")
        self.assertEqual(err.status_code, 500)
        self.assertIn("test", str(err))

        terr = GinieTimeoutError("job-1", 120.5)
        self.assertEqual(terr.job_id, "job-1")
        self.assertIn("120.5", str(terr))


class TestClientHealth(unittest.TestCase):
    """Test health check — requires running backend."""

    def test_health(self):
        client = GinieClient(base_url=BASE_URL)
        try:
            h = client.health()
            self.assertIn("daml_sdk", h)
            self.assertIn("rag_status", h)
            print(f"  Health: DAML={h['daml_sdk']}, RAG={h['rag_status']}")
        except GinieAPIError:
            self.skipTest("Backend not running")
        finally:
            client.close()


class TestClientGeneration(unittest.TestCase):
    """Test contract generation — requires full stack running."""

    def test_generate_and_poll(self):
        client = GinieClient(base_url=BASE_URL)
        try:
            client.health()
        except GinieAPIError:
            self.skipTest("Backend not running")

        try:
            job_id = client.generate_contract("Create a simple token contract")
            self.assertTrue(len(job_id) > 10)
            print(f"  Job created: {job_id[:12]}...")

            status = client.get_status(job_id)
            self.assertIsInstance(status, JobStatus)
            self.assertIn(status.status, ("queued", "running", "complete", "failed"))
            print(f"  Status: {status.status} [{status.progress}%]")
        finally:
            client.close()

    def test_full_pipeline(self):
        client = GinieClient(base_url=BASE_URL)
        try:
            client.health()
        except GinieAPIError:
            self.skipTest("Backend not running")

        try:
            result = client.full_pipeline(
                prompt="Create a simple agreement between two parties",
                timeout=300,
            )
            self.assertIsInstance(result, JobResult)
            self.assertIn(result.status, ("complete", "failed"))
            print(f"  Pipeline result: {result.status}")
            if result.is_deployed:
                print(f"  Contract: {result.contract_id}")
                print(f"  Security: {result.security_score}")
        finally:
            client.close()


class TestClientAudit(unittest.TestCase):
    """Test audit endpoints — requires running backend."""

    def test_run_audit(self):
        client = GinieClient(base_url=BASE_URL)
        try:
            client.health()
        except GinieAPIError:
            self.skipTest("Backend not running")

        try:
            audit = client.run_audit(code=SAMPLE_DAML, contract_name="SimpleToken")
            self.assertIsInstance(audit, AuditReport)
            print(f"  Audit: success={audit.success}, score={audit.security_score}")
        finally:
            client.close()

    def test_run_compliance(self):
        client = GinieClient(base_url=BASE_URL)
        try:
            client.health()
        except GinieAPIError:
            self.skipTest("Backend not running")

        try:
            comp = client.run_compliance(
                code=SAMPLE_DAML,
                contract_name="SimpleToken",
                profile="generic",
            )
            self.assertIsInstance(comp, ComplianceReport)
            print(f"  Compliance: success={comp.success}, score={comp.compliance_score}")
        finally:
            client.close()

    def test_list_profiles(self):
        client = GinieClient(base_url=BASE_URL)
        try:
            client.health()
        except GinieAPIError:
            self.skipTest("Backend not running")

        try:
            profiles = client.list_compliance_profiles()
            self.assertIn("profiles", profiles)
            self.assertIn("generic", profiles["profiles"])
            print(f"  Profiles: {profiles['profiles']}")
        finally:
            client.close()


class TestClientContextManager(unittest.TestCase):
    """Test context manager usage."""

    def test_with_statement(self):
        with GinieClient(base_url=BASE_URL) as client:
            try:
                h = client.health()
                self.assertIn("daml_sdk", h)
            except GinieAPIError:
                self.skipTest("Backend not running")


# ---------------------------------------------------------------------------
# Run tests
# ---------------------------------------------------------------------------

def run_tests():
    """Run all SDK tests with verbose output."""
    print("=" * 60)
    print("  Ginie SDK — Test Suite")
    print("=" * 60)
    print(f"  Target: {BASE_URL}\n")

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test classes in order
    suite.addTests(loader.loadTestsFromTestCase(TestGinieConfig))
    suite.addTests(loader.loadTestsFromTestCase(TestTypes))
    suite.addTests(loader.loadTestsFromTestCase(TestClientHealth))
    suite.addTests(loader.loadTestsFromTestCase(TestClientAudit))
    suite.addTests(loader.loadTestsFromTestCase(TestClientGeneration))
    suite.addTests(loader.loadTestsFromTestCase(TestClientContextManager))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 60)
    total = result.testsRun
    failed = len(result.failures) + len(result.errors)
    skipped = len(result.skipped)
    passed = total - failed - skipped
    print(f"  TOTAL: {total}  PASSED: {passed}  FAILED: {failed}  SKIPPED: {skipped}")
    print("=" * 60)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
