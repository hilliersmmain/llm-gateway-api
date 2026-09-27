"""Authentication helpers for API key protected routes."""

import secrets

from fastapi import Header, HTTPException, status

from app.core.config import get_settings

settings = get_settings()


def _require_key(provided_key: str | None, expected_key: str | None, detail: str) -> None:
    if not expected_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication key is not configured.",
        )
    # Constant-time comparison, on bytes: compare_digest rejects non-ASCII str.
    if provided_key is None or not secrets.compare_digest(
        provided_key.encode(), expected_key.encode()
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        )


async def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Require general API key when protected mode is enabled."""
    if not settings.protected_paths:
        return
    _require_key(x_api_key, settings.api_key, "Invalid API key.")


async def require_admin_api_key(x_admin_api_key: str | None = Header(default=None)) -> None:
    """Require admin key for analytics/metrics and docs."""
    if not settings.protected_paths:
        return
    _require_key(x_admin_api_key, settings.admin_api_key, "Invalid admin API key.")
