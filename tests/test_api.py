"""Integration tests for API endpoints."""

from unittest.mock import patch

from fastapi import BackgroundTasks, HTTPException
from fastapi.testclient import TestClient


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

        with patch.object(BackgroundTasks, "add_task", autospec=True) as add_task_mock:
            response = client.post("/chat", json={"message": "hello"})

        assert response.status_code == 502
        assert add_task_mock.called

        latency_values = [
            kwargs["latency_ms"]
            for _, kwargs in add_task_mock.call_args_list
            if "latency_ms" in kwargs
        ]
        assert latency_values, "Expected latency value in add_task call."
        assert latency_values[0] >= 0
