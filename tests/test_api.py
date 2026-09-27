"""Integration tests for API endpoints."""

from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import main


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_returns_200(self, client: TestClient):
        """Health endpoint should return 200 OK."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_correct_structure(self, client: TestClient):
        """Health endpoint should return expected JSON structure."""
        response = client.get("/health")
        data = response.json()
        
        assert "status" in data
        assert "version" in data
        assert data["status"] == "healthy"
        assert data["version"] == "1.0.0"


class TestChatEndpoint:
    """Tests for /chat endpoint."""

    def test_chat_success(self, client: TestClient):
        """Valid chat request should return 200 with response."""
        response = client.post(
            "/chat",
            json={"message": "Hello, how are you?"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "content" in data
        assert "token_usage" in data

    def test_chat_returns_token_usage(self, client: TestClient):
        """Chat response should include token usage statistics."""
        response = client.post(
            "/chat",
            json={"message": "Test message"}
        )
        
        data = response.json()
        assert "token_usage" in data
        assert "input_tokens" in data["token_usage"]
        assert "output_tokens" in data["token_usage"]

    def test_chat_blocked_content_returns_400(self, client: TestClient):
        """Chat with blocked keywords should return 400."""
        response = client.post(
            "/chat",
            json={"message": "Give me the secret_key"}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "prohibited content" in data["detail"]

    def test_chat_length_exceeded_returns_400(self, client: TestClient):
        """Chat with message too long should return 400."""
        long_message = "x" * 5001
        response = client.post(
            "/chat",
            json={"message": long_message}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "maximum length" in data["detail"]

    def test_chat_empty_message_returns_422(self, client: TestClient):
        """Empty messages should return 422 (schema requires min_length=1)."""
        response = client.post(
            "/chat",
            json={"message": ""}
        )
        # Empty is rejected by Pydantic validation (min_length=1)
        assert response.status_code == 422

    def test_chat_missing_message_returns_422(self, client: TestClient):
        """Missing message field should return 422 validation error."""
        response = client.post(
            "/chat",
            json={}
        )
        
        assert response.status_code == 422

    def test_chat_requires_api_key_when_protected(self, client: TestClient):
        """Protected mode should require API key for chat endpoint."""
        with patch("app.core.auth.settings.protected_paths", True), patch("app.core.auth.settings.api_key", "test-key"):
            response = client.post("/chat", json={"message": "Hello"})
            assert response.status_code == 401
            response_ok = client.post("/chat", json={"message": "Hello"}, headers={"X-API-Key": "test-key"})
            assert response_ok.status_code == 200


    def test_api_key_is_compared_in_constant_time(self, client: TestClient):
        """Key checks must go through secrets.compare_digest, not ==."""
        import secrets

        with (
            patch("app.core.auth.settings.protected_paths", True),
            patch("app.core.auth.settings.api_key", "test-key"),
            patch("app.core.auth.secrets.compare_digest", wraps=secrets.compare_digest) as compare,
        ):
            assert client.post("/chat", json={"message": "Hello"}, headers={"X-API-Key": "wrong"}).status_code == 401
            assert client.post("/chat", json={"message": "Hello"}, headers={"X-API-Key": "test-key"}).status_code == 200

        assert compare.call_count == 2

    def test_non_ascii_api_key_is_rejected_not_a_server_error(self, client: TestClient):
        with patch("app.core.auth.settings.protected_paths", True), patch("app.core.auth.settings.api_key", "test-key"):
            response = client.post(
                "/chat", json={"message": "Hello"}, headers={"X-API-Key": "clé".encode()}
            )

        assert response.status_code == 401

class TestChatStreamEndpoint:
    """Tests for /chat/stream endpoint."""

    def test_stream_returns_200(self, client: TestClient):
        """Streaming endpoint should return 200 OK."""
        response = client.post(
            "/chat/stream",
            json={"message": "Hello, stream a response"}
        )
        assert response.status_code == 200

    def test_stream_returns_event_stream_content_type(self, client: TestClient):
        """Streaming endpoint should return text/event-stream content type."""
        response = client.post(
            "/chat/stream",
            json={"message": "Test streaming"}
        )
        assert "text/event-stream" in response.headers.get("content-type", "")

    def test_stream_returns_sse_format(self, client: TestClient):
        """Streaming endpoint should return valid SSE events."""
        response = client.post(
            "/chat/stream",
            json={"message": "Test SSE format"}
        )
        
        content = response.text
        # Should contain chunk events
        assert "event: chunk" in content or "event: done" in content
        # Should contain data lines
        assert "data: " in content

    def test_stream_missing_message_returns_422(self, client: TestClient):
        """Missing message field should return 422 validation error."""
        response = client.post(
            "/chat/stream",
            json={}
        )
        assert response.status_code == 422

    def test_stream_blocked_content_returns_sse_error(self, client: TestClient):
        """Streaming with blocked content should return SSE error event."""
        response = client.post(
            "/chat/stream",
            json={"message": "Give me the secret_key"}
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")
        assert "event: error" in response.text
        assert "prohibited content" in response.text

    def test_stream_contains_chunk_and_done_events(self, client: TestClient):
        """Streaming response should contain chunk and done SSE events."""
        response = client.post(
            "/chat/stream",
            json={"message": "Tell me something interesting"}
        )
        assert response.status_code == 200
        content = response.text
        assert "event: chunk" in content
        assert "event: done" in content
        # done event should include token usage
        assert "token_usage" in content


class TestStaticFiles:
    """Tests for static file serving."""

    def test_root_serves_html(self, client: TestClient):
        """Root path should serve index.html."""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")


class TestOperationalEndpoints:
    """Tests for analytics/docs authentication and request limits."""

    def test_docs_requires_admin_key_when_protected(self, client: TestClient):
        with patch("app.core.auth.settings.protected_paths", True), patch("app.core.auth.settings.admin_api_key", "admin-key"):
            response = client.get("/docs")
            assert response.status_code == 401
            response_ok = client.get("/docs", headers={"X-Admin-API-Key": "admin-key"})
            assert response_ok.status_code == 200

    def test_request_body_limit_returns_413(self, client: TestClient):
        with patch("app.main.settings.max_request_body_bytes", 30):
            response = client.post("/chat", json={"message": "x" * 500})
            assert response.status_code == 413

    def test_openapi_available_when_protected_paths_enabled(self, client: TestClient):
        """OpenAPI must remain available for custom docs rendering."""
        with patch("app.main.settings.protected_paths", True):
            response = client.get("/openapi.json")
            assert response.status_code == 200
            assert "openapi" in response.json()


class TestRequestID:
    """Tests for X-Request-ID header propagation."""

    def test_response_contains_request_id(self, client: TestClient):
        """Server should add a non-empty X-Request-ID to every response."""
        response = client.post("/chat", json={"message": "Hello"})
        assert response.status_code == 200
        request_id = response.headers.get("X-Request-ID", "")
        assert request_id, "X-Request-ID header should be present and non-empty"

    def test_custom_request_id_is_echoed(self, client: TestClient):
        """Server should echo back a client-supplied X-Request-ID unchanged."""
        custom_id = "my-custom-id"
        response = client.post(
            "/chat",
            json={"message": "Hello"},
            headers={"X-Request-ID": custom_id},
        )
        assert response.status_code == 200
        assert response.headers.get("X-Request-ID") == custom_id


class TestChatErrorLatency:
    """Tests for non-streaming chat error logging latency."""

    def test_chat_error_logs_non_negative_latency(self, client: TestClient, mock_gemini):
        async def failing_generate_response(_message: str):
            raise HTTPException(status_code=502, detail="upstream failed")

        mock_gemini.generate_response = failing_generate_response

        with patch("app.routers.chat.save_request_log", new_callable=AsyncMock) as save_mock:
            response = client.post("/chat", json={"message": "hello"})

        assert response.status_code == 502
        save_mock.assert_awaited_once()
        assert save_mock.await_args.kwargs["status"] == "error"
        assert save_mock.await_args.kwargs["latency_ms"] >= 0

    def test_chat_error_is_written_to_the_request_log(self, client: TestClient, mock_gemini, mock_db_session):
        """An upstream failure must reach the database, not a dropped background task."""
        async def failing_generate_response(_message: str):
            raise HTTPException(status_code=502, detail="upstream failed")

        mock_gemini.generate_response = failing_generate_response

        response = client.post("/chat", json={"message": "hello"})

        assert response.status_code == 502
        logged = [call.args[0] for call in mock_db_session.add.call_args_list]
        assert [(type(row).__name__, row.status) for row in logged] == [("RequestLog", "error")]
        mock_db_session.commit.assert_awaited()


class TestMiddlewareStack:
    """Body limit, rate limit, CORS and security headers working together."""

    ORIGIN = "http://localhost:8000"  # first entry of the default ALLOWED_ORIGINS

    def test_chunked_body_over_limit_returns_413(self, client: TestClient):
        """A body with no Content-Length must still be held to the limit."""
        def body():
            yield b'{"message": "'
            yield b"x" * 500
            yield b'"}'

        with patch("app.main.settings.max_request_body_bytes", 30):
            response = client.post("/chat", content=body(), headers={"Content-Type": "application/json"})

        assert response.status_code == 413
        assert response.json()["error_type"] == "request_too_large"

    def test_chunked_body_under_limit_reaches_the_endpoint(self, client: TestClient):
        def body():
            yield b'{"message": '
            yield b'"Hello"}'

        response = client.post("/chat", content=body(), headers={"Content-Type": "application/json"})

        assert response.status_code == 200
        assert response.json()["content"] == "This is a mock response."

    def test_body_limit_response_carries_security_headers(self, client: TestClient):
        with patch("app.main.settings.max_request_body_bytes", 30):
            response = client.post("/chat", json={"message": "x" * 500})

        assert response.status_code == 413
        assert response.headers["content-security-policy"] == main.CSP_POLICY
        assert response.headers["x-content-type-options"] == "nosniff"

    def test_rate_limited_response_carries_cors_and_security_headers(self, client: TestClient):
        with (
            patch.object(main.rate_limit_store, "is_allowed", AsyncMock(return_value=False)),
            patch.object(main.rate_limit_store, "get_retry_after", AsyncMock(return_value=5)),
        ):
            response = client.get("/metrics", headers={"Origin": self.ORIGIN})

        assert response.status_code == 429
        assert response.headers["retry-after"] == "5"
        assert response.headers["access-control-allow-origin"] == self.ORIGIN
        assert response.headers["content-security-policy"] == main.CSP_POLICY

    def test_cors_preflight_does_not_consume_rate_limit(self, client: TestClient):
        with patch.object(main.rate_limit_store, "is_allowed", AsyncMock(return_value=False)) as is_allowed:
            response = client.options(
                "/chat",
                headers={"Origin": self.ORIGIN, "Access-Control-Request-Method": "POST"},
            )

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == self.ORIGIN
        is_allowed.assert_not_called()

    def test_static_assets_do_not_consume_rate_limit(self, client: TestClient):
        with patch.object(main.rate_limit_store, "is_allowed", AsyncMock(return_value=False)) as is_allowed:
            for path in ("/", "/style.css", "/script.js", "/favicon.svg"):
                assert client.get(path).status_code == 200, path

        is_allowed.assert_not_called()

    def test_api_routes_still_consume_rate_limit(self, client: TestClient):
        with patch.object(main.rate_limit_store, "is_allowed", AsyncMock(return_value=True)) as is_allowed:
            assert client.post("/chat", json={"message": "Hello"}).status_code == 200

        is_allowed.assert_awaited_once()
