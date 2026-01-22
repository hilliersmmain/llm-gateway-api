"""Integration tests for API endpoints."""

import pytest
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

    @pytest.mark.integration
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

    @pytest.mark.integration
    def test_stream_returns_done_event_with_token_usage(self, client: TestClient):
        """Streaming endpoint should return done event with token usage."""
        response = client.post(
            "/chat/stream",
            json={"message": "Test token usage"}
        )
        
        content = response.text
        assert "event: done" in content
        assert "token_usage" in content

    def test_stream_blocked_content_returns_error_event(self, client: TestClient):
        """Streaming with blocked keywords should return error SSE event."""
        response = client.post(
            "/chat/stream",
            json={"message": "Give me the secret_key"}
        )
        
        # Still returns 200 (SSE protocol)
        assert response.status_code == 200
        content = response.text
        assert "event: error" in content
        assert "prohibited content" in content

    def test_stream_length_exceeded_returns_error_event(self, client: TestClient):
        """Streaming with long message should return error SSE event."""
        long_message = "x" * 5001
        response = client.post(
            "/chat/stream",
            json={"message": long_message}
        )
        
        assert response.status_code == 200
        content = response.text
        assert "event: error" in content
        assert "maximum length" in content

    def test_stream_missing_message_returns_422(self, client: TestClient):
        """Missing message field should return 422 validation error."""
        response = client.post(
            "/chat/stream",
            json={}
        )
        assert response.status_code == 422


class TestStaticFiles:
    """Tests for static file serving."""

    @pytest.mark.skip(reason="TestClient doesn't mount static files - test manually")
    def test_root_serves_html(self, client: TestClient):
        """Root path should serve index.html."""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    @pytest.mark.skip(reason="TestClient doesn't mount static files - test manually")
    def test_stream_demo_serves_html(self, client: TestClient):
        """Stream demo page should be accessible."""
        response = client.get("/stream-demo.html")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
