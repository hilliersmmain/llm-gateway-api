"""Tests for rate limiting middleware."""

import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.rate_limit import (
    InMemoryRateLimitStore,
    RateLimitMiddleware,
    create_rate_limit_store,
)


class TestInMemoryRateLimitStore:
    """Tests for in-memory rate limit store."""

    def test_allows_requests_under_limit(self):
        """Should allow requests when under the limit."""
        store = InMemoryRateLimitStore()
        
        # Make 5 requests with limit of 10
        for _ in range(5):
            assert store.is_allowed("127.0.0.1", max_requests=10, window_seconds=60)

    def test_blocks_requests_over_limit(self):
        """Should block requests when limit is exceeded."""
        store = InMemoryRateLimitStore()
        
        # Make 10 requests (at limit)
        for _ in range(10):
            assert store.is_allowed("127.0.0.1", max_requests=10, window_seconds=60)
        
        # 11th request should be blocked
        assert not store.is_allowed("127.0.0.1", max_requests=10, window_seconds=60)

    def test_separate_limits_per_ip(self):
        """Different IPs should have separate rate limits."""
        store = InMemoryRateLimitStore()
        
        # Exhaust limit for IP1
        for _ in range(3):
            store.is_allowed("192.168.1.1", max_requests=3, window_seconds=60)
        
        # IP1 should be blocked
        assert not store.is_allowed("192.168.1.1", max_requests=3, window_seconds=60)
        
        # IP2 should still be allowed
        assert store.is_allowed("192.168.1.2", max_requests=3, window_seconds=60)

    def test_window_reset(self):
        """Requests should be allowed after window resets."""
        store = InMemoryRateLimitStore()
        
        # Use very short window for testing
        window_seconds = 1
        
        # Exhaust limit
        for _ in range(2):
            store.is_allowed("127.0.0.1", max_requests=2, window_seconds=window_seconds)
        
        # Should be blocked
        assert not store.is_allowed("127.0.0.1", max_requests=2, window_seconds=window_seconds)
        
        # Wait for window to expire
        time.sleep(window_seconds + 0.1)
        
        # Should be allowed again
        assert store.is_allowed("127.0.0.1", max_requests=2, window_seconds=window_seconds)

    def test_get_retry_after(self):
        """Should return correct retry-after value."""
        store = InMemoryRateLimitStore()
        
        # Make a request
        store.is_allowed("127.0.0.1", max_requests=1, window_seconds=60)
        
        # Get retry after
        retry_after = store.get_retry_after("127.0.0.1", window_seconds=60)
        
        # Should be approximately 60 seconds (with some margin)
        assert 58 <= retry_after <= 61

    def test_get_retry_after_unknown_ip(self):
        """Should return 0 for unknown IP."""
        store = InMemoryRateLimitStore()
        
        retry_after = store.get_retry_after("unknown_ip", window_seconds=60)
        assert retry_after == 0


class TestCreateRateLimitStore:
    """Tests for rate limit store factory."""

    def test_creates_in_memory_store_by_default(self):
        """Should create in-memory store when redis_url is None."""
        store = create_rate_limit_store(redis_url=None)
        assert isinstance(store, InMemoryRateLimitStore)

    def test_creates_redis_store_when_url_provided(self):
        """Should create Redis store when redis_url is provided."""
        with patch("app.middleware.rate_limit.RedisRateLimitStore") as mock_redis:
            mock_redis.return_value = MagicMock()
            create_rate_limit_store(redis_url="redis://localhost:6379")
            mock_redis.assert_called_once_with("redis://localhost:6379")


class TestRateLimitMiddleware:
    """Integration tests for rate limit middleware."""

    @pytest.fixture
    def test_app(self):
        """Create a test FastAPI app with rate limiting."""
        app = FastAPI()
        
        store = InMemoryRateLimitStore()
        app.add_middleware(
            RateLimitMiddleware,
            store=store,
            max_requests=3,
            window_seconds=60,
        )
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        @app.get("/health")
        async def health_endpoint():
            return {"status": "healthy"}
        
        @app.get("/metrics")
        async def metrics_endpoint():
            return {"requests": 100}
        
        return app

    def test_allows_requests_under_limit(self, test_app):
        """Should allow requests under the rate limit."""
        client = TestClient(test_app)
        
        # Make 3 requests (at limit)
        for _ in range(3):
            response = client.get("/test")
            assert response.status_code == 200

    def test_returns_429_when_limit_exceeded(self, test_app):
        """Should return 429 when rate limit is exceeded."""
        client = TestClient(test_app)
        
        # Exhaust the limit
        for _ in range(3):
            client.get("/test")
        
        # Next request should be blocked
        response = client.get("/test")
        assert response.status_code == 429
        
        data = response.json()
        assert "Too many requests" in data["detail"]
        assert data["error_type"] == "rate_limit_exceeded"

    def test_includes_retry_after_header(self, test_app):
        """Should include Retry-After header in 429 response."""
        client = TestClient(test_app)
        
        # Exhaust the limit
        for _ in range(3):
            client.get("/test")
        
        # Check 429 response headers
        response = client.get("/test")
        assert response.status_code == 429
        assert "Retry-After" in response.headers
        
        retry_after = int(response.headers["Retry-After"])
        assert retry_after > 0
        assert retry_after <= 61

    def test_health_endpoint_bypasses_rate_limit(self, test_app):
        """Health endpoint should not be rate limited."""
        client = TestClient(test_app)
        
        # Exhaust rate limit on regular endpoint
        for _ in range(3):
            client.get("/test")
        
        # Verify regular endpoint is blocked
        assert client.get("/test").status_code == 429
        
        # Health endpoint should still work
        response = client.get("/health")
        assert response.status_code == 200

    def test_metrics_endpoint_bypasses_rate_limit(self, test_app):
        """Metrics endpoint should not be rate limited."""
        client = TestClient(test_app)
        
        # Exhaust rate limit on regular endpoint
        for _ in range(3):
            client.get("/test")
        
        # Verify regular endpoint is blocked
        assert client.get("/test").status_code == 429
        
        # Metrics endpoint should still work
        response = client.get("/metrics")
        assert response.status_code == 200


class TestRateLimitMiddlewareIPExtraction:
    """Tests for IP extraction in rate limit middleware."""

    @pytest.fixture
    def test_app_with_store(self):
        """Create test app and return both app and store for inspection."""
        app = FastAPI()
        store = InMemoryRateLimitStore()
        
        app.add_middleware(
            RateLimitMiddleware,
            store=store,
            max_requests=5,
            window_seconds=60,
        )
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        return app, store

    def test_uses_x_forwarded_for_header(self, test_app_with_store):
        """Should use X-Forwarded-For header when present."""
        app, store = test_app_with_store
        client = TestClient(app)
        
        # Make request with X-Forwarded-For header
        response = client.get(
            "/test",
            headers={"X-Forwarded-For": "10.0.0.1, 10.0.0.2"}
        )
        assert response.status_code == 200
        
        # Check the store has the correct IP (first in chain)
        assert "10.0.0.1" in store._requests

    def test_uses_x_real_ip_header(self, test_app_with_store):
        """Should use X-Real-IP header when present."""
        app, store = test_app_with_store
        client = TestClient(app)
        
        # Make request with X-Real-IP header
        response = client.get(
            "/test",
            headers={"X-Real-IP": "192.168.1.100"}
        )
        assert response.status_code == 200
        
        # Check the store has the correct IP
        assert "192.168.1.100" in store._requests

    def test_prefers_x_forwarded_for_over_x_real_ip(self, test_app_with_store):
        """X-Forwarded-For should take precedence over X-Real-IP."""
        app, store = test_app_with_store
        client = TestClient(app)
        
        # Make request with both headers
        response = client.get(
            "/test",
            headers={
                "X-Forwarded-For": "10.0.0.1",
                "X-Real-IP": "192.168.1.100"
            }
        )
        assert response.status_code == 200
        
        # Should use X-Forwarded-For
        assert "10.0.0.1" in store._requests
        assert "192.168.1.100" not in store._requests
