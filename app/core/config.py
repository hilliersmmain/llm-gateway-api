"""Application configuration using pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Gemini API Configuration
    gemini_api_key: str

    # Database Configuration
    database_url: str = (
        "postgresql+asyncpg://user:password@localhost:5432/gemini_guardrails"
    )

    # Logging Configuration
    log_level: str = "INFO"

    # Model Configuration
    model_name: str = "gemini-3-flash"
    max_input_length: int = 5000

    # Guardrail Configuration
    blocked_keywords: list[str] = ["secret_key", "internal_only"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
