from pydantic_settings import BaseSettings, SettingsConfigDict
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
    database_url: str = "postgresql://postgres:password@localhost:5432/ginie_daml"

    # Canton sandbox PostgreSQL storage (separate DB from Ginie app)
    canton_db_host: str = "localhost"
    canton_db_port: int = 5432
    canton_db_name: str = "canton_sandbox"
    canton_db_user: str = "postgres"
    canton_db_password: str = "password"

    canton_sandbox_url: str = "http://localhost:7575"
    canton_devnet_url: str = "https://canton.network/ledger"
    canton_mainnet_url: str = "https://REPLACE_WITH_YOUR_MAINNET_JSON_API_URL"
    canton_environment: str = "sandbox"
    canton_token: str = ""

    daml_sdk_path: str = os.path.expanduser("~/.daml/bin/daml")
    daml_sdk_version: str = "2.10.4"
    dar_output_dir: str = "/tmp/ginie_jobs"

    chroma_persist_dir: str = "./rag/chroma_db"

    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    max_fix_attempts: int = 3
    llm_model: str = "gpt-4o"
    llm_temperature: float = 0.1

    # Auth / JWT
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expiry_days: int = 7

    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:3001,http://127.0.0.1:3000,https://canton.ginie.xyz"

    def get_canton_url(self) -> str:
        mapping = {
            "sandbox": self.canton_sandbox_url,
            "devnet": self.canton_devnet_url,
            "mainnet": self.canton_mainnet_url,
        }
        return mapping.get(self.canton_environment, self.canton_sandbox_url)


_DEFAULT_SECRET = "ginie-local-dev-secret-change-in-production"
_INSECURE_PASSWORDS = {"password", "postgres", "admin", "changeme", "secret", ""}

_settings_instance: "Settings | None" = None


def _build_settings() -> Settings:
    """Construct, validate, and return a fully-initialized Settings object.

    Called exactly once. All mutation happens here before the object is
    stored in the module-level singleton, avoiding the lru_cache-and-mutate
    anti-pattern.
    """
    s = Settings()
    env = s.canton_environment.strip().lower()

    # --- JWT secret validation ---
    if not s.jwt_secret or s.jwt_secret.strip() == _DEFAULT_SECRET:
        if env != "sandbox":
            raise RuntimeError(
                "FATAL: JWT_SECRET is not set or is the default value. "
                "A strong, unique secret is REQUIRED for non-sandbox environments. "
                "Set JWT_SECRET in backend/.env.ginie"
            )
        ephemeral = secrets.token_hex(32)
        s.jwt_secret = ephemeral
        _logger.warning("JWT_SECRET not configured — generated ephemeral secret (sandbox only)")

    # --- Database password validation in non-sandbox environments ---
    try:
        from urllib.parse import urlparse
        db_url = s.database_url
        parsed = urlparse(db_url)
        db_pass = parsed.password or ""
        if env != "sandbox" and db_pass.lower() in _INSECURE_PASSWORDS:
            raise RuntimeError(
                "FATAL: DATABASE_URL uses an insecure default password in a non-sandbox environment. "
                "Set a strong DATABASE_URL in backend/.env.ginie"
            )
        if env == "sandbox" and db_pass.lower() in _INSECURE_PASSWORDS:
            _logger.warning(
                "DATABASE_URL uses default password — acceptable for sandbox only; "
                "set a strong password before deploying to devnet/mainnet"
            )
    except RuntimeError:
        raise
    except Exception:
        pass

    # --- Canton environment normalisation ---
    s.canton_environment = env

    # --- Resolve relative chroma_persist_dir to absolute ---
    chroma_path = Path(s.chroma_persist_dir)
    if not chroma_path.is_absolute():
        s.chroma_persist_dir = str((Path(__file__).parent / chroma_path).resolve())
        _logger.info("Resolved chroma_persist_dir to absolute path", path=s.chroma_persist_dir)

    return s


def get_settings() -> Settings:
    """Return the process-wide Settings singleton.

    Built once on first call.  Uses a plain module-level variable rather than
    functools.lru_cache so that the initialization logic (which mutates the
    object) is not entangled with caching semantics.
    """
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = _build_settings()
    return _settings_instance
