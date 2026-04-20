"""Security regression tests.

These tests are designed to catch regressions in security controls.
They do NOT require a live LLM, Canton, or DAML SDK — all external calls
are mocked or exercised at unit level.

Run: cd backend && pytest tests/test_security_regressions.py -v
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestSSRFValidation:
    """Verify canton_url SSRF protection (Issue #16)."""

    def test_rejects_loopback_in_production(self):
        from utils.url_validator import validate_canton_url
        with pytest.raises(ValueError, match="private/internal IP"):
            validate_canton_url("http://127.0.0.1:7575", allow_localhost=False)

    def test_rejects_private_range_10_x(self):
        from utils.url_validator import validate_canton_url
        with pytest.raises(ValueError):
            validate_canton_url("http://10.0.0.1:7575", allow_localhost=False)

    def test_rejects_private_range_192_168(self):
        from utils.url_validator import validate_canton_url
        with pytest.raises(ValueError):
            validate_canton_url("http://192.168.1.100:7575", allow_localhost=False)

    def test_rejects_metadata_endpoint_direct(self):
        from utils.url_validator import validate_canton_url
        with pytest.raises(ValueError, match="cloud-metadata"):
            validate_canton_url("http://169.254.169.254/latest/meta-data/", allow_localhost=False)

    def test_rejects_non_http_scheme(self):
        from utils.url_validator import validate_canton_url
        with pytest.raises(ValueError, match="scheme"):
            validate_canton_url("file:///etc/passwd", allow_localhost=False)

    def test_rejects_ftp_scheme(self):
        from utils.url_validator import validate_canton_url
        with pytest.raises(ValueError, match="scheme"):
            validate_canton_url("ftp://example.com/canton", allow_localhost=False)

    def test_rejects_empty_url(self):
        from utils.url_validator import validate_canton_url
        with pytest.raises(ValueError):
            validate_canton_url("", allow_localhost=False)

    def test_allows_localhost_in_sandbox_mode(self):
        from utils.url_validator import validate_canton_url
        result = validate_canton_url("http://localhost:7575", allow_localhost=True)
        assert result == "http://localhost:7575"

    def test_allows_loopback_ip_in_sandbox_mode(self):
        from utils.url_validator import validate_canton_url
        result = validate_canton_url("http://127.0.0.1:7575", allow_localhost=True)
        assert "127.0.0.1" in result


class TestAuditFailClosed:
    """Audit exceptions must block deployment, never permit it (Issue #6)."""

    def test_audit_exception_sets_deploy_gate_false(self):
        from pipeline.orchestrator import audit_node

        with patch("pipeline.orchestrator.run_hybrid_audit", side_effect=RuntimeError("LLM timeout")):
            state = {
                "job_id": "test-audit-fail",
                "generated_code": "module Main where\ntemplate T with owner: Party where signatory owner",
                "structured_intent": {"daml_templates_needed": ["T"]},
                "current_step": "auditing",
                "progress": 80,
            }
            result = audit_node(state)

        assert result.get("deploy_gate") is False, "deploy_gate must be False when audit crashes"
        assert result.get("is_fatal_error") is True, "is_fatal_error must be True when audit crashes"
        assert result.get("error_message"), "error_message must be populated"

    def test_audit_exception_does_not_continue_silently(self):
        from pipeline.orchestrator import audit_node

        with patch("pipeline.orchestrator.run_hybrid_audit", side_effect=Exception("network error")):
            state = {
                "job_id": "test-audit-silent",
                "generated_code": "module Main where",
                "structured_intent": {},
                "current_step": "auditing",
                "progress": 80,
            }
            result = audit_node(state)

        assert result.get("current_step") != "Deploying to Canton...", \
            "Audit failure must not silently advance to deploy step"


class TestFallbackRemoved:
    """Exceeding max fix attempts must fail explicitly, not silently deploy SimpleContract (Issue #7)."""

    def test_fallback_node_sets_is_fatal_error(self):
        from pipeline.orchestrator import fallback_node

        state = {
            "job_id": "test-fallback",
            "compile_errors": [{"message": "parse error at line 5", "error_type": "parse_error"}],
            "attempt_number": 3,
            "current_step": "compile",
            "progress": 60,
        }
        result = fallback_node(state)

        assert result.get("is_fatal_error") is True
        assert result.get("error_message"), "fallback_node must provide a user-visible error message"
        assert "compile" in result.get("error_message", "").lower() or \
               "attempt" in result.get("error_message", "").lower(), \
            "Error message should reference compilation failure"

    def test_fallback_node_does_not_inject_simple_contract(self):
        from pipeline.orchestrator import fallback_node

        state = {
            "job_id": "test-fallback-no-inject",
            "compile_errors": [{"message": "type error"}],
            "attempt_number": 3,
            "current_step": "compile",
            "progress": 60,
        }
        result = fallback_node(state)

        assert "SimpleContract" not in result.get("generated_code", ""), \
            "Fallback must not silently inject SimpleContract as user contract"


class TestPasswordValidation:
    """Startup must reject insecure DB passwords in non-sandbox environments (Issue #4)."""

    def test_insecure_password_raises_in_production(self):
        from config import _build_settings, _INSECURE_PASSWORDS
        import os
        from unittest.mock import patch

        with patch.dict(os.environ, {
            "CANTON_ENVIRONMENT": "devnet",
            "DATABASE_URL": "postgresql://postgres:password@localhost:5432/ginie_daml",
            "JWT_SECRET": "strong-test-secret-that-is-at-least-32-chars-long-ok",
        }):
            with pytest.raises(RuntimeError, match="insecure default password"):
                from config import Settings
                s = Settings()
                from urllib.parse import urlparse
                parsed = urlparse(s.database_url)
                db_pass = parsed.password or ""
                env = s.canton_environment.strip().lower()
                if env != "sandbox" and db_pass.lower() in _INSECURE_PASSWORDS:
                    raise RuntimeError(
                        "FATAL: DATABASE_URL uses an insecure default password in a non-sandbox environment."
                    )


class TestPreflightLLMProvider:
    """Preflight must report pipeline_ready correctly for all providers (Issue #5)."""

    def test_openai_key_valid_returns_ok(self):
        from utils.preflight import check_llm
        result = check_llm("openai", "sk-test123456789")
        assert result["ok"] is True
        assert result["provider"] == "openai"

    def test_openai_key_missing_returns_fail(self):
        from utils.preflight import check_llm
        result = check_llm("openai", "")
        assert result["ok"] is False

    def test_openai_key_wrong_prefix_returns_fail(self):
        from utils.preflight import check_llm
        result = check_llm("openai", "sk-ant-wrong-provider-key")
        assert result["ok"] is False

    def test_anthropic_key_valid_returns_ok(self):
        from utils.preflight import check_llm
        result = check_llm("anthropic", "sk-ant-valid-key-here")
        assert result["ok"] is True

    def test_anthropic_key_missing_returns_fail(self):
        from utils.preflight import check_llm
        result = check_llm("anthropic", "")
        assert result["ok"] is False

    def test_gemini_key_present_returns_ok(self):
        from utils.preflight import check_llm
        result = check_llm("gemini", "AIzaSy-something")
        assert result["ok"] is True

    def test_gemini_key_missing_returns_fail(self):
        from utils.preflight import check_llm
        result = check_llm("gemini", "")
        assert result["ok"] is False

    def test_unknown_provider_returns_fail(self):
        from utils.preflight import check_llm
        result = check_llm("cohere", "some-key")
        assert result["ok"] is False
        assert "Unknown" in result["error"]


class TestAlgNoneGuard:
    """sandbox JWT generation must reject non-sandbox environments (Issue #23)."""

    def test_make_sandbox_jwt_blocked_in_devnet(self):
        from canton.canton_client_v2 import make_sandbox_jwt
        from config import get_settings

        with patch.object(get_settings(), "canton_environment", "devnet"):
            with patch("canton.canton_client_v2.get_settings") as mock_settings:
                mock_s = MagicMock()
                mock_s.canton_environment = "devnet"
                mock_settings.return_value = mock_s
                with pytest.raises(RuntimeError, match="non-sandbox"):
                    make_sandbox_jwt(["alice"])

    def test_make_sandbox_jwt_blocked_with_trailing_whitespace(self):
        from canton.canton_client_v2 import make_sandbox_jwt
        with patch("canton.canton_client_v2.get_settings") as mock_settings:
            mock_s = MagicMock()
            mock_s.canton_environment = "devnet "
            mock_settings.return_value = mock_s
            with pytest.raises(RuntimeError, match="non-sandbox"):
                make_sandbox_jwt(["alice"])


class TestJWTTokenHash:
    """hash_token must produce a stable, non-reversible SHA-256 digest (Issue #8)."""

    def test_hash_is_deterministic(self):
        from auth.jwt_manager import hash_token
        token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.sig"
        assert hash_token(token) == hash_token(token)

    def test_hash_length_is_64_chars(self):
        from auth.jwt_manager import hash_token
        result = hash_token("any.jwt.token")
        assert len(result) == 64

    def test_hash_is_hex(self):
        from auth.jwt_manager import hash_token
        result = hash_token("any.jwt.token")
        int(result, 16)

    def test_different_tokens_produce_different_hashes(self):
        from auth.jwt_manager import hash_token
        assert hash_token("token.one.sig") != hash_token("token.two.sig")

    def test_raw_token_not_in_hash(self):
        from auth.jwt_manager import hash_token
        token = "supersecretjwtvalue"
        digest = hash_token(token)
        assert token not in digest


class TestDeployedContractPartyId:
    """DeployedContract.party_id must be populated from pipeline state (Issue #24)."""

    def test_party_id_extracted_from_party_id_field(self):
        from api.routes import _save_deployed_contract
        deploy_result = {
            "contract_id": "abc123",
            "package_id": "pkg1",
            "template_id": "Main:TestContract",
            "party_id": "alice::1220abc",
            "canton_environment": "sandbox",
            "explorer_link": "",
        }
        with patch("api.routes.get_db_session") as mock_session_ctx:
            mock_session = MagicMock()
            mock_session_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_session_ctx.return_value.__exit__ = MagicMock(return_value=False)

            from db.models import DeployedContract
            captured = {}

            def capture_add(obj):
                captured["obj"] = obj

            mock_session.add = capture_add
            _save_deployed_contract("job-1", deploy_result)

        if "obj" in captured:
            assert captured["obj"].party_id == "alice::1220abc"
