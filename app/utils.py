"""Shared utility functions."""

from fastapi import Request


def get_client_ip(request: Request) -> str | None:
    """Extract client IP from request, considering proxy headers.

    Uses the rightmost IP from X-Forwarded-For, which is the one appended
    by the trusted reverse proxy (e.g., Heroku router). The leftmost value
    is client-controlled and can be spoofed.

    Returns:
        The client IP address, or None if it cannot be determined.
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Rightmost IP is set by the trusted proxy (Heroku, nginx, etc.)
        return forwarded_for.split(",")[-1].strip()
    if request.client:
        return request.client.host
    return None
