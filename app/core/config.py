"""Application configuration using pydantic-settings."""

import logging
import secrets
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Gemini API Configuration
    gemini_api_key: str

    # Database Configuration
    # No default: must be supplied. In development the validator falls back
    # to a localhost dev URL with an obvious placeholder password; production
    # deployments must set DATABASE_URL explicitly or startup fails.
    database_url: str | None = None

    # Logging Configuration
    log_level: str = "INFO"
    environment: str = "development"

    # Model Configuration
    model_name: str = "gemini-2.5-flash"
    max_input_length: int = 5000

    # Guardrail Configuration
    blocked_keywords: list[str] = ["secret_key", "internal_only"]

    # Rate Limiting Configuration
    rate_limit_requests: int = 10
    rate_limit_window_seconds: int = 60
    redis_url: str | None = None  # Optional: enables Redis backend for rate limiting

    # API Authentication Configuration
    api_key: str | None = None
    admin_api_key: str | None = None
    protected_paths: bool = False

    # API Surface Configuration
    allowed_origins: list[str] = ["http://localhost:8000", "http://127.0.0.1:8000"]
    enable_docs: bool = True
    enable_openapi: bool = True

    # Reliability and Safety
    gemini_timeout_seconds: float = 30.0
    gemini_retry_attempts: int = 2
    max_request_body_bytes: int = 65536

    # Privacy and retention
    log_raw_content: bool = False
    # No default: required outside development. In development the validator
    # generates a random per-process salt and logs a warning.
    hash_salt: str | None = None
    log_retention_days: int = 30

    # Gemini Pricing (per 1M tokens) for cost estimation
    gemini_input_price_per_million: float = 0.15
    gemini_output_price_per_million: float = 0.60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @model_validator(mode="after")
    def _enforce_required_in_production(self) -> "Settings":
        is_dev = self.environment.lower() == "development"

        if not self.database_url:
            if is_dev:
                self.database_url = (
                    "postgresql+asyncpg://user:change_me@localhost:5432/llm_gateway"
                )
                logger.warning(
                    "DATABASE_URL not set; using development placeholder. "
                    "Set DATABASE_URL explicitly outside development."
                )
            else:
                raise ValueError(
                    "DATABASE_URL is required when ENVIRONMENT is not 'development'."
                )

        if not self.hash_salt:
            if is_dev:
                self.hash_salt = secrets.token_urlsafe(32)
                logger.warning(
                    "HASH_SALT not set; generated a random per-process salt for development. "
                    "IP hashes will not be stable across restarts. "
                    "Set HASH_SALT explicitly outside development."
                )
            else:
                raise ValueError(
                    "HASH_SALT is required when ENVIRONMENT is not 'development'."
                )

        return self


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
