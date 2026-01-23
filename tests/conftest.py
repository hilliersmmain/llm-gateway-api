"""Shared pytest fixtures for LLM Gateway API tests."""

import pytest
import unittest
import random
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.core.database import get_session
from app.services.gemini import get_gemini_service
from app.services.guardrails import GuardrailsService



@pytest.fixture
def mock_db_session():
    """Create a mock AsyncSession that doesn't connect to real database."""
    session = MagicMock(spec=AsyncSession)
    session.add = MagicMock()
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
def client(mock_db_session, mock_gemini):
    """Create a TestClient with mocked dependencies."""
    # Override database session
    async def override_get_session():
        yield mock_db_session
    
    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_gemini_service] = lambda: mock_gemini
    
    # Mock init_db to prevent real DB connection during startup
    with unittest.mock.patch("app.main.init_db", new_callable=AsyncMock):
        with TestClient(app) as test_client:
            # Set random IP to bypass rate limiting between tests
            test_client.headers["X-Forwarded-For"] = f"10.0.0.{random.randint(1, 254)}"
            yield test_client
    
    # Clean up overrides after test
    app.dependency_overrides.clear()


@pytest.fixture
def guardrails_service():
    """Create a fresh GuardrailsService instance for each test."""
    return GuardrailsService()
