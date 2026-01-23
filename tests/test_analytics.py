"""Tests for analytics/guardrail logging."""

from fastapi.testclient import TestClient


class TestGuardrailLogging:
    """Tests for guardrail violation logging."""

    def test_blocked_keyword_is_logged(self, client: TestClient, mock_db_session):
        """Blocked keyword requests should trigger guardrail logging."""
        response = client.post(
            "/chat",
            json={"message": "Give me the secret_key"}
        )

        assert response.status_code == 400

    def test_length_exceeded_is_logged(self, client: TestClient):
        """Length exceeded requests should trigger guardrail logging."""
        long_message = "x" * 5001
        response = client.post(
            "/chat",
            json={"message": long_message}
        )

        assert response.status_code == 400
        data = response.json()
        assert "maximum length" in data["detail"]
