"""Integration tests for API endpoints."""

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


class TestStaticFiles:
    """Tests for static file serving."""

    def test_root_serves_html(self, client: TestClient):
        """Root path should serve index.html."""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
