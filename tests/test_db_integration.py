"""PostgreSQL-backed integration tests for logging and analytics."""

import os

import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from app.core.database import async_session
from app.main import app
from app.middleware.logging import save_request_log
from app.models.log import GuardrailLog, RequestLog
from app.services.guardrails import save_guardrail_log

pytestmark = pytest.mark.asyncio


def _is_postgres_configured() -> bool:
    return os.getenv("DATABASE_URL", "").startswith("postgresql+asyncpg://")


@pytest.fixture
def real_client():
    """Test client that uses real DB-backed application lifespan."""
    with TestClient(app) as client:
        yield client


@pytest.fixture
async def clean_logs():
    """Ensure request/guardrail logs are isolated between tests."""
    async with async_session() as session:
        await session.execute(RequestLog.__table__.delete())
        await session.execute(GuardrailLog.__table__.delete())
        await session.commit()
    yield


@pytest.mark.skipif(not _is_postgres_configured(), reason="Postgres DATABASE_URL required")
async def test_save_request_log_persists_record(clean_logs):
    async with async_session() as session:
        await save_request_log(
            session=session,
            input_prompt="integration prompt",
            output_response="integration response",
            latency_ms=42.0,
            tokens_in=10,
            tokens_out=20,
            status="success",
        )
    async with async_session() as session:
        rows = (await session.execute(select(RequestLog))).scalars().all()
        assert len(rows) == 1
        assert rows[0].status == "success"


@pytest.mark.skipif(not _is_postgres_configured(), reason="Postgres DATABASE_URL required")
async def test_save_guardrail_log_persists_record(clean_logs):
    async with async_session() as session:
        await save_guardrail_log(
            session=session,
            input_prompt="contains secret_key",
            violation_type="blocked_content",
            blocked_keyword="secret_key",
            client_ip="10.1.1.1",
        )
    async with async_session() as session:
        rows = (await session.execute(select(GuardrailLog))).scalars().all()
        assert len(rows) == 1
        assert rows[0].violation_type == "blocked_content"
        assert rows[0].client_ip is not None


@pytest.mark.skipif(not _is_postgres_configured(), reason="Postgres DATABASE_URL required")
async def test_metrics_analytics_queries_with_real_db(clean_logs, real_client):
    async with async_session() as session:
        await save_request_log(
            session=session,
            input_prompt="hello",
            output_response="world",
            latency_ms=30.0,
            tokens_in=5,
            tokens_out=7,
            status="success",
        )
        await save_guardrail_log(
            session=session,
            input_prompt="contains secret_key",
            violation_type="blocked_content",
            blocked_keyword="secret_key",
            client_ip="10.1.1.1",
        )
    metrics = real_client.get("/metrics")
    assert metrics.status_code == 200
    analytics = real_client.get("/analytics")
    assert analytics.status_code == 200
    assert "total_requests_24h" in analytics.json()
