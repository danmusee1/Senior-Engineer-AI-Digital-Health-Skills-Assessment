"""
Centralized application configuration.

All configurable values are read from environment variables (optionally via a
.env file in development). Centralizing configuration here means:

  - There is exactly one place to look for "what can be tuned".
  - Defaults are explicit and documented.
  - Nothing reaches into os.getenv() scattered across the codebase, which
    makes it easy to miss a variable when deploying to a new environment.

See .env.example for the full list of variables with descriptions.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, populated from environment variables / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Environment -----------------------------------------------------
    environment: str = "development"  # development | staging | production
    log_level: str = "INFO"

    # --- Database -----------------------------------------------------
    database_url: str
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout_seconds: int = 30
    db_pool_recycle_seconds: int = 1800  # recycle connections every 30 min

    # --- Ollama (LLM + embeddings) ----------------------------------------
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:latest"
    ollama_embedding_model: str = "nomic-embed-text"
    ollama_embedding_dim: int = 768
    ollama_request_timeout_seconds: float = 60.0
    ollama_generate_timeout_seconds: float = 120.0
    ollama_max_retries: int = 3
    ollama_retry_backoff_seconds: float = 1.0

    # --- RAG pipeline -------------------------------------------------
    chunk_size: int = 500
    chunk_overlap: int = 50
    retrieval_top_k: int = 3
    max_upload_size_mb: int = 20

    # --- Security -----------------------------------------------------
    # If unset, write endpoints (upload/delete) are open. Set this in any
    # environment that is reachable beyond localhost.
    api_key: str | None = None

    # Comma-separated list of allowed CORS origins, e.g.
    # "http://localhost:3000,https://app.example.org"
    allowed_origins: str = "http://localhost:3000,http://localhost:8000"

    # --- Rate limiting -------------------------------------------------
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance.

    lru_cache ensures the environment is only parsed once per process, while
    still being easy to override in tests via get_settings.cache_clear().
    """
    return Settings()


# Module-level convenience instance for the common case.
settings = get_settings()
