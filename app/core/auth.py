"""Authentication helpers for API key protected routes."""

from fastapi import Header, HTTPException, status

from app.core.config import get_settings

settings = get_settings()


def _require_key(provided_key: str | None, expected_key: str | None, detail: str) -> None:
    if not expected_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication key is not configured.",
        )
    if provided_key != expected_key:
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
    expected = settings.admin_api_key or settings.api_key
    _require_key(x_admin_api_key, expected, "Invalid admin API key.")
