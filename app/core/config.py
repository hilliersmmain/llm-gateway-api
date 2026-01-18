"""Application configuration using pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    gemini_api_key: str
    database_url: str = (
        "postgresql+asyncpg://user:password@localhost:5432/llm_gateway"
    )
    log_level: str = "INFO"
    model_name: str = "gemini-2.5-flash"
    max_input_length: int = 5000
    blocked_keywords: list[str] = ["secret_key", "internal_only"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
