"""Privacy helpers for log sanitization and pseudonymization."""

import hashlib

from app.core.config import get_settings

settings = get_settings()


def hash_value(value: str | None) -> str | None:
    """Hash a value with configured salt to avoid storing plaintext."""
    if not value:
        return None
    digest = hashlib.sha256(f"{settings.hash_salt}:{value}".encode()).hexdigest()
    return digest


def redact_text(text: str, max_length: int) -> str:
    """
    Redact or retain text based on configuration.

    If raw content logging is disabled, return a deterministic hash marker.
    """
    truncated = text[:max_length]
    if settings.log_raw_content:
        return truncated
    hashed = hash_value(truncated)
    return f"[redacted_sha256:{hashed}]"
