"""Shared pytest fixtures for LLM Gateway API tests."""

import pytest
import pytest_asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from app.main import app
from app.core.database import get_session
from app.services.gemini import get_gemini_service
from app.services.guardrails import GuardrailsService
# Import models to ensure they are registered with SQLModel metadata
from app.models.log import RequestLog, GuardrailLog


@asynccontextmanager
async def empty_lifespan(app: FastAPI):
    """Empty lifespan that skips database initialization."""
    yield


@pytest.fixture(scope="session")
def test_app() -> FastAPI:
    """Create test app with empty lifespan (no DB init)."""
    # Create a new app with empty lifespan
    test_app = FastAPI(
        title="LLM Gateway API - Test",
        lifespan=empty_lifespan,
    )
    
    # Copy all routes from the main app (except the root which mounts static files)
    for route in app.routes:
        if hasattr(route, "path"):
            test_app.router.routes.append(route)
    
    return test_app


@pytest.fixture
def mock_db_session():
    """Create a mock AsyncSession that doesn't connect to real database."""
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
        """Return mock response without calling actual API."""
        return self.response_text, self.token_usage

    async def generate_response_stream(self, message: str):
        """Yield mock streaming chunks without calling actual API."""
        # Split response into chunks to simulate streaming
        words = self.response_text.split()
        chunk_size = max(1, len(words) // 3)  # Split into ~3 chunks

        for i in range(0, len(words), chunk_size):
            chunk_words = words[i : i + chunk_size]
            chunk_text = " ".join(chunk_words)
            if i > 0:
                chunk_text = " " + chunk_text  # Add space between chunks
            yield chunk_text, None

        # Final chunk with token usage
        yield "", self.token_usage


@pytest.fixture
def mock_gemini():
    """Fixture providing a mock Gemini service."""
    return MockGeminiService()


@pytest.fixture
def client(test_app: FastAPI, mock_db_session, mock_gemini):
    """Create a TestClient with mocked dependencies."""
    # Override database session
    async def override_get_session():
        yield mock_db_session
    
    test_app.dependency_overrides[get_session] = override_get_session
    test_app.dependency_overrides[get_gemini_service] = lambda: mock_gemini
    
    with TestClient(test_app) as test_client:
        yield test_client
    
    # Clean up overrides after test
    test_app.dependency_overrides.clear()


@pytest.fixture
def guardrails_service():
    """Create a fresh GuardrailsService instance for each test."""
    return GuardrailsService()


# Real database session fixture for tests that need actual tables
@pytest_asyncio.fixture(scope="function")
async def db_session():
    """Create a real async database session with tables for testing."""
    # Use in-memory SQLite for testing (or connect to test database)
    import os
    database_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    
    # Create async engine for tests
    test_engine = create_async_engine(
        database_url,
        echo=False,
        future=True,
    )
    
    # Create all tables
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    
    # Create session
    test_session_maker = sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with test_session_maker() as session:
        yield session
        await session.rollback()
    
    # Drop all tables after test
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    
    await test_engine.dispose()
