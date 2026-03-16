from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


# Provider presets: (base_url, model, api_key_or_None)
_PROVIDER_PRESETS: dict[str, tuple[str, str, str | None]] = {
    "kimi": ("https://api.moonshot.cn/v1", "moonshot-v1-128k", None),
    "openrouter": ("https://openrouter.ai/api/v1", "anthropic/claude-sonnet-4", None),
    "ollama": ("http://localhost:11434/v1", "llama3", "ollama"),
}


@dataclass(frozen=True)
class LLMConfig:
    """Resolved LLM connection parameters."""

    api_key: str
    base_url: str
    model: str
    timeout: float
    max_retries: int
    retry_delay: float


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Kimi / Moonshot LLM (legacy, kept for backward compatibility)
    kimi_api_key: str = ""
    kimi_base_url: str = "https://api.moonshot.cn/v1"
    kimi_model: str = "moonshot-v1-128k"

    # LLM Provider (generic OpenAI-compatible)
    llm_provider: str = "kimi"  # "kimi" | "openrouter" | "ollama" | "custom"
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = ""
    llm_timeout: float = 120.0
    llm_max_retries: int = 3
    llm_retry_delay: float = 1.0

    # Orchestration
    orchestration_mode: str = "plan"  # "plan" | "agent"
    orchestration_max_iterations: int = 0  # 0 = unlimited

    # PostgreSQL + pgvector
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "mlops"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # RAG
    rag_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    rag_embedding_dimension: int = 384  # all-MiniLM-L6-v2 produces 384-dim vectors

    # Application
    app_name: str = "MLOps Service"
    app_version: str = "1.0.0"
    debug: bool = False
    mock_mode: bool = False

    def get_llm_config(self) -> LLMConfig:
        """Resolve provider presets and return the effective LLM configuration.

        Resolution order for each field:
          1. Explicit ``llm_*`` env var (if non-empty)
          2. Provider preset default
          3. Legacy ``kimi_*`` env var (backward compatibility)
        """
        provider = self.llm_provider.lower()

        if provider == "custom":
            # Custom provider: use llm_* fields as-is, fall back to kimi_*
            return LLMConfig(
                api_key=self.llm_api_key or self.kimi_api_key,
                base_url=self.llm_base_url or self.kimi_base_url,
                model=self.llm_model or self.kimi_model,
                timeout=self.llm_timeout,
                max_retries=self.llm_max_retries,
                retry_delay=self.llm_retry_delay,
            )

        preset_base_url, preset_model, preset_api_key = _PROVIDER_PRESETS.get(
            provider, _PROVIDER_PRESETS["kimi"]
        )

        # Resolve api_key: llm_api_key > preset default > kimi_api_key
        api_key = self.llm_api_key or preset_api_key or self.kimi_api_key

        return LLMConfig(
            api_key=api_key,
            base_url=self.llm_base_url or preset_base_url,
            model=self.llm_model or preset_model,
            timeout=self.llm_timeout,
            max_retries=self.llm_max_retries,
            retry_delay=self.llm_retry_delay,
        )

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
