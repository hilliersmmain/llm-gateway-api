"""Rate limiting middleware with pluggable storage backends."""

import logging
import time
from typing import Protocol

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class RateLimitStore(Protocol):
    """Protocol for rate limit storage backends."""

    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> bool:
        """Check if a request is allowed and record it if so."""
        ...

    def get_retry_after(self, key: str, window_seconds: int) -> int:
        """Get seconds until the rate limit resets."""
        ...


class InMemoryRateLimitStore:
    """In-memory rate limit store using sliding window algorithm."""

    def __init__(self) -> None:
        self._requests: dict[str, list[float]] = {}

    def _cleanup_old_requests(self, key: str, window_seconds: int) -> None:
        """Remove requests outside the current window."""
        if key not in self._requests:
            return
        
        cutoff = time.time() - window_seconds
        self._requests[key] = [ts for ts in self._requests[key] if ts > cutoff]
        
        # Remove empty keys to prevent memory leaks
        if not self._requests[key]:
            del self._requests[key]

    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> bool:
        """Check if request is allowed using sliding window."""
        self._cleanup_old_requests(key, window_seconds)
        
        current_requests = self._requests.get(key, [])
        
        if len(current_requests) >= max_requests:
            return False
        
        # Record this request
        if key not in self._requests:
            self._requests[key] = []
        self._requests[key].append(time.time())
        
        return True

    def get_retry_after(self, key: str, window_seconds: int) -> int:
        """Get seconds until oldest request expires from window."""
        if key not in self._requests or not self._requests[key]:
            return 0
        
        oldest_request = min(self._requests[key])
        retry_after = int(oldest_request + window_seconds - time.time()) + 1
        return max(1, retry_after)


class RedisRateLimitStore:
    """Redis-based rate limit store using sorted sets for sliding window."""

    def __init__(self, redis_url: str) -> None:
        import redis.asyncio as redis
        
        self._redis = redis.from_url(redis_url, decode_responses=True)
        self._prefix = "rate_limit:"

    def _get_key(self, key: str) -> str:
        """Get Redis key with prefix."""
        return f"{self._prefix}{key}"

    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> bool:
        """
        Check if request is allowed using Redis sorted sets.
        
        Note: This is a synchronous wrapper. For production with high concurrency,
        consider using async Redis operations.
        """
        import redis as sync_redis
        
        # Use sync redis for middleware compatibility
        redis_key = self._get_key(key)
        now = time.time()
        cutoff = now - window_seconds
        
        # Parse URL and create sync connection
        client = sync_redis.from_url(
            self._redis.connection_pool.connection_kwargs.get('url', 'redis://localhost:6379'),
            decode_responses=True
        )
        
        pipe = client.pipeline()
        
        # Remove old entries
        pipe.zremrangebyscore(redis_key, 0, cutoff)
        # Count current requests
        pipe.zcard(redis_key)
        # Add new request
        pipe.zadd(redis_key, {str(now): now})
        # Set expiry
        pipe.expire(redis_key, window_seconds)
        
        results = pipe.execute()
        current_count = results[1]
        
        if current_count >= max_requests:
            # Remove the request we just added since it's not allowed
            client.zrem(redis_key, str(now))
            return False
        
        return True

    def get_retry_after(self, key: str, window_seconds: int) -> int:
        """Get seconds until oldest request expires."""
        import redis as sync_redis
        
        redis_key = self._get_key(key)
        
        client = sync_redis.from_url(
            self._redis.connection_pool.connection_kwargs.get('url', 'redis://localhost:6379'),
            decode_responses=True
        )
        
        # Get oldest timestamp
        oldest = client.zrange(redis_key, 0, 0, withscores=True)
        
        if not oldest:
            return 0
        
        oldest_time = oldest[0][1]
        retry_after = int(oldest_time + window_seconds - time.time()) + 1
        return max(1, retry_after)


def create_rate_limit_store(redis_url: str | None = None) -> InMemoryRateLimitStore | RedisRateLimitStore:
    """Factory function to create appropriate rate limit store."""
    if redis_url:
        logger.info("Using Redis for rate limiting")
        return RedisRateLimitStore(redis_url)
    
    logger.info("Using in-memory store for rate limiting")
    return InMemoryRateLimitStore()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce rate limiting per IP address."""

    # Paths excluded from rate limiting
    EXCLUDED_PATHS = {"/health", "/metrics", "/docs", "/redoc", "/openapi.json"}

    def __init__(
        self,
        app,
        store: InMemoryRateLimitStore | RedisRateLimitStore,
        max_requests: int = 10,
        window_seconds: int = 60,
    ) -> None:
        super().__init__(app)
        self.store = store
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP, checking X-Forwarded-For for proxy setups."""
        # Check for proxy headers
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain (original client)
            return forwarded_for.split(",")[0].strip()
        
        # Check X-Real-IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()
        
        # Fall back to direct connection IP
        if request.client:
            return request.client.host
        
        return "unknown"

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Process request through rate limiting."""
        # Skip rate limiting for excluded paths
        if request.url.path in self.EXCLUDED_PATHS:
            return await call_next(request)
        
        # Also skip static files
        if request.url.path.startswith("/static"):
            return await call_next(request)
        
        client_ip = self._get_client_ip(request)
        
        if not self.store.is_allowed(client_ip, self.max_requests, self.window_seconds):
            retry_after = self.store.get_retry_after(client_ip, self.window_seconds)
            
            logger.warning(
                f"Rate limit exceeded for IP {client_ip}. "
                f"Retry after {retry_after}s"
            )
            
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests. Please try again later.",
                    "error_type": "rate_limit_exceeded",
                },
                headers={"Retry-After": str(retry_after)},
            )
        
        return await call_next(request)
