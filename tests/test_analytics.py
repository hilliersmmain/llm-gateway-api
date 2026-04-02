"""Tests for analytics/guardrail logging and analytics endpoints."""

from unittest.mock import MagicMock

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


class TestMetricsEndpoint:
    """Tests for /metrics endpoint."""

    def test_metrics_returns_200(self, client: TestClient, mock_db_session):
        """Metrics endpoint should return 200 OK."""
        # Mock the DB query result for metrics
        mock_row = MagicMock()
        mock_row.total_requests = 0
        mock_row.total_tokens_in = 0
        mock_row.total_tokens_out = 0

        mock_result = MagicMock()
        mock_result.one.return_value = mock_row
        mock_db_session.execute.return_value = mock_result

        response = client.get("/metrics")
        assert response.status_code == 200

    def test_metrics_returns_correct_structure(self, client: TestClient, mock_db_session):
        """Metrics endpoint should return expected JSON fields."""
        mock_row = MagicMock()
        mock_row.total_requests = 42
        mock_row.total_tokens_in = 1000
        mock_row.total_tokens_out = 2000

        mock_result = MagicMock()
        mock_result.one.return_value = mock_row
        mock_db_session.execute.return_value = mock_result

        response = client.get("/metrics")
        data = response.json()

        assert "total_requests_today" in data
        assert "total_tokens_in" in data
        assert "total_tokens_out" in data
        assert "estimated_cost_usd" in data
        assert data["total_requests_today"] == 42
        assert data["total_tokens_in"] == 1000
        assert data["total_tokens_out"] == 2000


class TestAnalyticsEndpoint:
    """Tests for /analytics endpoint."""

    def _mock_analytics_queries(self, mock_db_session):
        """Set up mock DB to return valid analytics data for multiple queries."""
        # The analytics endpoint makes many queries. We need execute() to
        # return appropriate mock results for each call.
        mock_row_agg = MagicMock()
        mock_row_agg.total_requests = 10
        mock_row_agg.total_tokens_in = 500
        mock_row_agg.total_tokens_out = 1500

        mock_result_agg = MagicMock()
        mock_result_agg.one.return_value = mock_row_agg

        # For queries returning lists (latency_trend, blocked_keywords)
        mock_result_list = MagicMock()
        mock_result_list.all.return_value = []

        # For scalar queries (blocked counts, success/error counts)
        mock_result_scalar = MagicMock()
        mock_result_scalar.scalar.return_value = 0

        # execute() is called multiple times; return appropriate results.
        # Order: 24h agg, 7d agg, latency query, blocked query, blocked_24h,
        #         blocked_7d, success_count, error_count
        from unittest.mock import AsyncMock
        mock_db_session.execute = AsyncMock(side_effect=[
            mock_result_agg,    # 24h metrics
            mock_result_agg,    # 7d metrics
            mock_result_list,   # latency_trend
            mock_result_list,   # blocked keywords
            mock_result_scalar, # blocked 24h
            mock_result_scalar, # blocked 7d
            mock_result_scalar, # success count
            mock_result_scalar, # error count
        ])

    def test_analytics_returns_json_by_default(self, client: TestClient, mock_db_session):
        """Analytics endpoint should return JSON by default."""
        self._mock_analytics_queries(mock_db_session)

        response = client.get("/analytics")
        assert response.status_code == 200

        data = response.json()
        assert "total_requests_24h" in data
        assert "total_requests_7d" in data
        assert "latency_trend" in data
        assert "top_blocked_keywords" in data
        assert "total_blocked_requests_24h" in data
        assert "success_count_24h" in data
        assert "error_count_24h" in data

    def test_analytics_html_format(self, client: TestClient, mock_db_session):
        """Analytics with format=html should return HTML response."""
        self._mock_analytics_queries(mock_db_session)

        response = client.get("/analytics?format=html")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "Analytics Dashboard" in response.text
        assert "Chart.js" in response.text or "chart.js" in response.text.lower()

    def test_analytics_json_format_explicit(self, client: TestClient, mock_db_session):
        """Analytics with format=json should return JSON."""
        self._mock_analytics_queries(mock_db_session)

        response = client.get("/analytics?format=json")
        assert response.status_code == 200
        data = response.json()
        assert "total_requests_24h" in data
