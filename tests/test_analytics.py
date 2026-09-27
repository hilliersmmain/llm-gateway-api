"""Tests for analytics/guardrail logging and analytics endpoints."""

import time
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
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
        logged = [call.args[0] for call in mock_db_session.add.call_args_list]
        assert [type(row).__name__ for row in logged] == ["GuardrailLog"]
        assert logged[0].violation_type == "blocked_content"
        mock_db_session.commit.assert_awaited()

    def test_length_exceeded_is_logged(self, client: TestClient, mock_db_session):
        """Length exceeded requests should trigger guardrail logging."""
        long_message = "x" * 5001
        response = client.post(
            "/chat",
            json={"message": long_message}
        )

        assert response.status_code == 400
        data = response.json()
        assert "maximum length" in data["detail"]
        logged = [call.args[0] for call in mock_db_session.add.call_args_list]
        assert [(type(row).__name__, row.violation_type) for row in logged] == [
            ("GuardrailLog", "length_exceeded")
        ]


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


class TestTimeWindowsAreUTC:
    """Log timestamps are naive UTC, so the query windows must be naive UTC too."""

    @pytest.fixture(autouse=True)
    def non_utc_local_time(self, monkeypatch):
        # A POSIX TZ string needs no tzdata: local time is UTC+9 while this runs,
        # so a window computed from local time is off by nine hours even on a
        # UTC CI host.
        monkeypatch.setenv("TZ", "TEST-9")
        time.tzset()
        yield
        monkeypatch.undo()
        time.tzset()

    @staticmethod
    def _cutoff(mock_db_session, call_index: int = 0) -> datetime:
        query = mock_db_session.execute.await_args_list[call_index].args[0]
        return query.whereclause.right.value

    def test_metrics_today_starts_at_utc_midnight(self, client: TestClient, mock_db_session):
        row = MagicMock(total_requests=0, total_tokens_in=0, total_tokens_out=0)
        mock_db_session.execute = AsyncMock(return_value=MagicMock(one=MagicMock(return_value=row)))

        assert client.get("/metrics").status_code == 200

        utc_midnight = datetime.now(UTC).replace(tzinfo=None, hour=0, minute=0, second=0, microsecond=0)
        assert self._cutoff(mock_db_session) == utc_midnight

    def test_analytics_24h_window_is_utc(self, client: TestClient, mock_db_session):
        TestAnalyticsEndpoint()._mock_analytics_queries(mock_db_session)

        assert client.get("/analytics").status_code == 200

        expected = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=24)
        assert abs(self._cutoff(mock_db_session) - expected) < timedelta(minutes=1)
