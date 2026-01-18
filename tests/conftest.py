"""Shared pytest fixtures for LLM Gateway API tests."""

import pytest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.core.database import get_session
from app.services.gemini import get_gemini_service
from app.services.guardrails import GuardrailsService


@asynccontextmanager
async def empty_lifespan(app: FastAPI):
    yield


@pytest.fixture(scope="session")
def test_app() -> FastAPI:
    test_app = FastAPI(
        title="LLM Gateway API - Test",
        lifespan=empty_lifespan,
    )
    
    for route in app.routes:
        if hasattr(route, "path"):
            test_app.router.routes.append(route)
    
    return test_app


@pytest.fixture
def mock_db_session():
    session = MagicMock(spec=AsyncSession)
    session.add = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


class MockGeminiService:
    """Mock Gemini service for testing without API calls."""

    def __init__(self, response_text: str = "This is a mock response.", token_usage: dict | None = None):
        self.response_text = response_text
        self.token_usage = token_usage or {"input_tokens": 10, "output_tokens": 15}

    async def generate_response(self, message: str) -> tuple[str, dict]:
        return self.response_text, self.token_usage


@pytest.fixture
def mock_gemini():
    return MockGeminiService()


@pytest.fixture
def client(test_app: FastAPI, mock_db_session, mock_gemini):
    async def override_get_session():
        yield mock_db_session
    
    test_app.dependency_overrides[get_session] = override_get_session
    test_app.dependency_overrides[get_gemini_service] = lambda: mock_gemini
    
    with TestClient(test_app) as test_client:
        yield test_client
    
    test_app.dependency_overrides.clear()


@pytest.fixture
def guardrails_service():
    return GuardrailsService()
