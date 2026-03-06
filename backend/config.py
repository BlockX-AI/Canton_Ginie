from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Settings(BaseSettings):
    anthropic_api_key: str = ""

    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "postgresql://postgres:password@localhost:5432/ginie_daml"

    canton_sandbox_url: str = "http://localhost:6865"
    canton_devnet_url: str = "https://canton.network/ledger"
    canton_mainnet_url: str = "https://main.canton.network/ledger"
    canton_environment: str = "sandbox"

    daml_sdk_path: str = os.path.expanduser("~/.daml/bin/daml")
    dar_output_dir: str = "/tmp/ginie_jobs"

    chroma_persist_dir: str = "./rag/chroma_db"

    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    max_fix_attempts: int = 3
    llm_model: str = "claude-sonnet-4-20250514"
    llm_temperature: float = 0.1

    class Config:
        env_file = ".env"
        case_sensitive = False

    def get_canton_url(self) -> str:
        mapping = {
            "sandbox": self.canton_sandbox_url,
            "devnet": self.canton_devnet_url,
            "mainnet": self.canton_mainnet_url,
        }
        return mapping.get(self.canton_environment, self.canton_sandbox_url)


@lru_cache()
def get_settings() -> Settings:
    return Settings()
