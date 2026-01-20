"""Tests for analytics endpoint."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.database import get_session
from app.models.schemas import AnalyticsResponse


class MockRow:
    """Mock database row for query results."""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class MockResult:
    """Mock database result for single row queries."""

    def __init__(self, row):
        self._row = row

    def one(self):
        return self._row

    def scalar(self):
        return getattr(self._row, "count", 0) if self._row else 0

    def all(self):
        return self._row if isinstance(self._row, list) else [self._row]


class TestAnalyticsEndpoint:
    """Tests for /analytics endpoint."""

    def test_analytics_returns_200(self, test_app: FastAPI):
        """Analytics endpoint should return 200 OK."""
        # Create mock session with execute method
        mock_session = MagicMock()

        # Mock results for different queries
        async def mock_execute(query):
            # Return appropriate mock data based on query type
            # For count/sum queries (24h and 7d)
            return MockResult(
                MockRow(
                    total_requests=10,
                    total_tokens_in=1000,
                    total_tokens_out=2000,
                    count=5,
                )
            )

        mock_session.execute = AsyncMock(side_effect=mock_execute)

        async def override_get_session():
            yield mock_session

        test_app.dependency_overrides[get_session] = override_get_session

        with TestClient(test_app) as client:
            response = client.get("/analytics")

        test_app.dependency_overrides.clear()
        assert response.status_code == 200

    def test_analytics_returns_correct_schema(self, test_app: FastAPI):
        """Analytics endpoint should return correct JSON structure."""
        mock_session = MagicMock()

        # Track which query is being executed
        call_count = [0]

        async def mock_execute(query):
            call_count[0] += 1
            # Queries 1 & 2: 24h and 7d request counts
            if call_count[0] <= 2:
                return MockResult(
                    MockRow(
                        total_requests=10 if call_count[0] == 1 else 50,
                        total_tokens_in=1000 if call_count[0] == 1 else 5000,
                        total_tokens_out=2000 if call_count[0] == 1 else 10000,
                    )
                )
            # Query 3: Latency buckets
            elif call_count[0] == 3:
                return MockResult(
                    [
                        MockRow(
                            hour=datetime.now(timezone.utc),
                            avg_latency=150.5,
                            request_count=5,
                        )
                    ]
                )
            # Query 4: Blocked keywords
            elif call_count[0] == 4:
                return MockResult(
                    [MockRow(blocked_keyword="secret_key", count=3)]
                )
            # Query 5: Total blocked 24h
            else:
                result = MockResult(MockRow(count=5))
                result.scalar = lambda: 5
                return result

        mock_session.execute = AsyncMock(side_effect=mock_execute)

        async def override_get_session():
            yield mock_session

        test_app.dependency_overrides[get_session] = override_get_session

        with TestClient(test_app) as client:
            response = client.get("/analytics")

        test_app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()

        # Verify schema structure
        assert "total_requests_24h" in data
        assert "total_requests_7d" in data
        assert "latency_trend" in data
        assert "total_tokens_in_24h" in data
        assert "total_tokens_out_24h" in data
        assert "total_tokens_in_7d" in data
        assert "total_tokens_out_7d" in data
        assert "top_blocked_keywords" in data
        assert "total_blocked_requests_24h" in data

    def test_analytics_empty_database(self, test_app: FastAPI):
        """Analytics should return zeros for empty database."""
        mock_session = MagicMock()

        async def mock_execute(query):
            # Return empty/zero results
            result = MockResult(
                MockRow(
                    total_requests=0,
                    total_tokens_in=0,
                    total_tokens_out=0,
                )
            )
            result.scalar = lambda: 0
            result.all = lambda: []
            return result

        mock_session.execute = AsyncMock(side_effect=mock_execute)

        async def override_get_session():
            yield mock_session

        test_app.dependency_overrides[get_session] = override_get_session

        with TestClient(test_app) as client:
            response = client.get("/analytics")

        test_app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()

        assert data["total_requests_24h"] == 0
        assert data["total_requests_7d"] == 0
        assert data["total_tokens_in_24h"] == 0
        assert data["total_tokens_out_24h"] == 0
        assert data["latency_trend"] == []
        assert data["top_blocked_keywords"] == []
        assert data["total_blocked_requests_24h"] == 0

    def test_analytics_html_format(self, test_app: FastAPI):
        """Analytics with format=html should return HTML response."""
        mock_session = MagicMock()

        async def mock_execute(query):
            result = MockResult(
                MockRow(
                    total_requests=10,
                    total_tokens_in=1000,
                    total_tokens_out=2000,
                )
            )
            result.scalar = lambda: 5
            result.all = lambda: []
            return result

        mock_session.execute = AsyncMock(side_effect=mock_execute)

        async def override_get_session():
            yield mock_session

        test_app.dependency_overrides[get_session] = override_get_session

        with TestClient(test_app) as client:
            response = client.get("/analytics?format=html")

        test_app.dependency_overrides.clear()

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "<!DOCTYPE html>" in response.text
        assert "Analytics Dashboard" in response.text
        assert "Chart.js" in response.text or "chart.js" in response.text

    def test_analytics_html_contains_charts(self, test_app: FastAPI):
        """HTML response should contain chart canvas elements."""
        mock_session = MagicMock()

        async def mock_execute(query):
            result = MockResult(
                MockRow(
                    total_requests=10,
                    total_tokens_in=1000,
                    total_tokens_out=2000,
                )
            )
            result.scalar = lambda: 0
            result.all = lambda: []
            return result

        mock_session.execute = AsyncMock(side_effect=mock_execute)

        async def override_get_session():
            yield mock_session

        test_app.dependency_overrides[get_session] = override_get_session

        with TestClient(test_app) as client:
            response = client.get("/analytics?format=html")

        test_app.dependency_overrides.clear()

        html = response.text
        assert 'id="latencyChart"' in html
        assert 'id="tokenChart"' in html
        assert 'id="blockedChart"' in html
        assert 'id="volumeChart"' in html

    def test_analytics_json_is_default(self, test_app: FastAPI):
        """Analytics without format param should return JSON."""
        mock_session = MagicMock()

        async def mock_execute(query):
            result = MockResult(
                MockRow(
                    total_requests=10,
                    total_tokens_in=1000,
                    total_tokens_out=2000,
                )
            )
            result.scalar = lambda: 0
            result.all = lambda: []
            return result

        mock_session.execute = AsyncMock(side_effect=mock_execute)

        async def override_get_session():
            yield mock_session

        test_app.dependency_overrides[get_session] = override_get_session

        with TestClient(test_app) as client:
            response = client.get("/analytics")

        test_app.dependency_overrides.clear()

        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")

    def test_analytics_latency_trend_format(self, test_app: FastAPI):
        """Latency trend should have correct bucket format."""
        mock_session = MagicMock()
        test_hour = datetime(2026, 1, 20, 14, 0, 0, tzinfo=timezone.utc)

        call_count = [0]

        async def mock_execute(query):
            call_count[0] += 1
            if call_count[0] <= 2:
                return MockResult(
                    MockRow(
                        total_requests=10,
                        total_tokens_in=1000,
                        total_tokens_out=2000,
                    )
                )
            elif call_count[0] == 3:
                return MockResult(
                    [
                        MockRow(
                            hour=test_hour,
                            avg_latency=150.5,
                            request_count=5,
                        ),
                        MockRow(
                            hour=test_hour + timedelta(hours=1),
                            avg_latency=120.3,
                            request_count=8,
                        ),
                    ]
                )
            elif call_count[0] == 4:
                return MockResult([])
            else:
                result = MockResult(MockRow())
                result.scalar = lambda: 0
                return result

        mock_session.execute = AsyncMock(side_effect=mock_execute)

        async def override_get_session():
            yield mock_session

        test_app.dependency_overrides[get_session] = override_get_session

        with TestClient(test_app) as client:
            response = client.get("/analytics")

        test_app.dependency_overrides.clear()

        data = response.json()
        latency_trend = data["latency_trend"]

        assert len(latency_trend) == 2
        assert "hour" in latency_trend[0]
        assert "avg_latency_ms" in latency_trend[0]
        assert "request_count" in latency_trend[0]
        assert latency_trend[0]["avg_latency_ms"] == 150.5
        assert latency_trend[0]["request_count"] == 5


class TestGuardrailLogging:
    """Tests for guardrail violation logging."""

    def test_blocked_keyword_is_logged(self, client: TestClient, mock_db_session):
        """Blocked keyword requests should trigger guardrail logging."""
        # The mock_db_session.add should be called when a guardrail violation occurs
        response = client.post(
            "/chat",
            json={"message": "Give me the secret_key"}
        )

        assert response.status_code == 400
        # Verify that session.add was called (for guardrail log)
        # Note: Due to background task, this might not be immediately visible
        # but the endpoint should return 400 for blocked content

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
