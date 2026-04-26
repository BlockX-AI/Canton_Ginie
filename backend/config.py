from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from pathlib import Path
import os
import secrets
import structlog

_logger = structlog.get_logger()

_ENV_FILE = str(Path(__file__).parent / ".env.ginie")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        case_sensitive=False,
        extra='ignore'
    )

    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    openai_api_key: str = ""
    llm_provider: str = "openai"

    redis_url: str = "redis://localhost:6379/0"
    database_url: str = ""

    # Canton sandbox PostgreSQL storage (separate DB from Ginie app)
    canton_db_host: str = "localhost"
    canton_db_port: int = 5432
    canton_db_name: str = "canton_sandbox"
    canton_db_user: str = ""
    canton_db_password: str = ""

    canton_sandbox_url: str = "http://localhost:7575"
    canton_devnet_url: str = ""
    canton_mainnet_url: str = ""
    canton_environment: str = "sandbox"
    canton_token: str = ""

    daml_sdk_path: str = os.path.expanduser("~/.daml/bin/daml")
    daml_sdk_version: str = "2.10.4"
    dar_output_dir: str = "/tmp/ginie_jobs"

    chroma_persist_dir: str = "./rag/chroma_db"

    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = int(os.getenv("PORT", "8000"))

    max_fix_attempts: int = 3
    llm_model: str = "gpt-4o"
    llm_temperature: float = 0.1
    # Per-request HTTP timeout for the LLM SDKs. The vendor defaults are
    # ~10 minutes, which is long enough that a network blip silently stalls
    # the whole pipeline (audit / writer / fix nodes all share this client).
    # 90s is plenty for an 8K-token completion and bounds the worst case.
    llm_request_timeout_seconds: float = 90.0
    # Wall-clock cap for the entire audit phase (security + compliance +
    # report generation combined). The phase runs on a worker thread; if it
    # blows the deadline we abandon the audit, log a warning, and let the
    # pipeline continue to the deploy stage with a degraded score.
    audit_max_seconds: float = 240.0

    # Auth / JWT
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expiry_days: int = 7

    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:3001,http://127.0.0.1:3000,https://canton.ginie.xyz,https://*.vercel.app"

    def get_canton_url(self) -> str:
        mapping = {
            "sandbox": self.canton_sandbox_url,
            "devnet": self.canton_devnet_url,
            "mainnet": self.canton_mainnet_url,
        }
        return mapping.get(self.canton_environment, self.canton_sandbox_url)


_DEFAULT_SECRET = "ginie-local-dev-secret-change-in-production"


@lru_cache()
def get_settings() -> Settings:
    s = Settings()

    # --- JWT secret validation ---
    if not s.jwt_secret or s.jwt_secret == _DEFAULT_SECRET:
        if s.canton_environment != "sandbox":
            raise RuntimeError(
                "FATAL: JWT_SECRET is not set or is the default value. "
                "A strong, unique secret is REQUIRED for non-sandbox environments. "
                "Set JWT_SECRET in backend/.env.ginie"
            )
        # Sandbox: auto-generate a random secret per startup
        s.jwt_secret = secrets.token_hex(32)
        _logger.warning("JWT_SECRET not configured — generated ephemeral secret (sandbox only)")

    # --- Resolve relative chroma_persist_dir to absolute ---
    chroma_path = Path(s.chroma_persist_dir)
    if not chroma_path.is_absolute():
        s.chroma_persist_dir = str((Path(__file__).parent / chroma_path).resolve())
        _logger.info("Resolved chroma_persist_dir to absolute path", path=s.chroma_persist_dir)

    return s
