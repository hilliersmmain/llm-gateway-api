"""Tests for Gemini service — generate_response and generate_response_stream."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
from google.api_core import exceptions as google_exceptions

from app.services.gemini import GeminiService


class FakeUsageMetadata:
    """Fake usage metadata for Gemini responses."""

    def __init__(self, prompt_tokens: int = 10, candidates_tokens: int = 20):
        self.prompt_token_count = prompt_tokens
        self.candidates_token_count = candidates_tokens


class FakeResponse:
    """Fake synchronous Gemini response."""

    def __init__(self, text: str = "Hello from Gemini", usage_metadata=None):
        self.text = text
        self.usage_metadata = usage_metadata or FakeUsageMetadata()


class FakeChunk:
    """Fake streaming chunk."""

    def __init__(self, text: str | None = None, usage_metadata=None):
        self.text = text
        self.usage_metadata = usage_metadata


class FakeAsyncIterator:
    """Async iterator over a list of chunks (returned by awaiting the stream call)."""

    def __init__(self, chunks):
        self._chunks = chunks
        self._index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._index >= len(self._chunks):
            raise StopAsyncIteration
        chunk = self._chunks[self._index]
        self._index += 1
        return chunk


@pytest.fixture
def gemini_service():
    """Create a GeminiService with a mocked client."""
    with patch("app.services.gemini.genai") as mock_genai:
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        service = GeminiService()
        service.client = mock_client
        yield service


class TestGenerateResponse:
    """Tests for GeminiService.generate_response (sync path)."""

    async def test_success_returns_text_and_tokens(self, gemini_service):
        """Should return response text and token usage on success."""
        fake_response = FakeResponse(
            text="Test response",
            usage_metadata=FakeUsageMetadata(prompt_tokens=5, candidates_tokens=15),
        )
        gemini_service.client.models.generate_content.return_value = fake_response

        text, token_usage = await gemini_service.generate_response("Hello")

        assert text == "Test response"
        assert token_usage == {"input_tokens": 5, "output_tokens": 15}
        gemini_service.client.models.generate_content.assert_called_once()

    async def test_success_without_usage_metadata(self, gemini_service):
        """Should return zero tokens when usage_metadata is missing."""
        fake_response = FakeResponse(text="Response")
        fake_response.usage_metadata = None
        gemini_service.client.models.generate_content.return_value = fake_response

        text, token_usage = await gemini_service.generate_response("Hello")

        assert text == "Response"
        assert token_usage == {"input_tokens": 0, "output_tokens": 0}

    async def test_empty_text_returns_empty_string(self, gemini_service):
        """Should return empty string when response.text is None."""
        fake_response = FakeResponse()
        fake_response.text = None
        gemini_service.client.models.generate_content.return_value = fake_response

        text, token_usage = await gemini_service.generate_response("Hello")

        assert text == ""

    async def test_resource_exhausted_raises_429(self, gemini_service):
        """Should raise HTTPException 429 when Gemini quota is exceeded."""
        gemini_service.client.models.generate_content.side_effect = (
            google_exceptions.ResourceExhausted("Quota exceeded")
        )

        with pytest.raises(HTTPException) as exc_info:
            await gemini_service.generate_response("Hello")

        assert exc_info.value.status_code == 429
        assert "quota exceeded" in exc_info.value.detail.lower()

    async def test_generic_exception_raises_502(self, gemini_service):
        """Should raise HTTPException 502 on generic API errors."""
        gemini_service.client.models.generate_content.side_effect = RuntimeError(
            "Connection failed"
        )

        with pytest.raises(HTTPException) as exc_info:
            await gemini_service.generate_response("Hello")

        assert exc_info.value.status_code == 502
        assert "Failed to get response" in exc_info.value.detail


class TestGenerateResponseStream:
    """Tests for GeminiService.generate_response_stream (async streaming)."""

    async def test_success_yields_chunks_and_done(self, gemini_service):
        """Should yield text chunks followed by a final chunk with token usage."""
        chunks = [
            FakeChunk(text="Hello "),
            FakeChunk(text="world", usage_metadata=FakeUsageMetadata(8, 12)),
        ]

        # The real code does: response_stream = await client.aio.models.generate_content_stream(...)
        # So the mock must be an async function returning an async iterable.
        gemini_service.client.aio.models.generate_content_stream = AsyncMock(
            return_value=FakeAsyncIterator(chunks)
        )

        results = []
        async for text, usage in gemini_service.generate_response_stream("Hi"):
            results.append((text, usage))

        # Should have: "Hello " (no usage), "world" (no usage), "" (with usage)
        assert len(results) == 3
        assert results[0] == ("Hello ", None)
        assert results[1] == ("world", None)
        # Final chunk has token usage
        assert results[2][0] == ""
        assert results[2][1] == {"input_tokens": 8, "output_tokens": 12}

    async def test_empty_chunks_are_skipped(self, gemini_service):
        """Chunks with empty text should not be yielded as content."""
        chunks = [
            FakeChunk(text=""),
            FakeChunk(text="data"),
            FakeChunk(text=None),
        ]

        gemini_service.client.aio.models.generate_content_stream = AsyncMock(
            return_value=FakeAsyncIterator(chunks)
        )

        results = []
        async for text, usage in gemini_service.generate_response_stream("Hi"):
            results.append((text, usage))

        # Only "data" chunk + final empty with usage
        assert len(results) == 2
        assert results[0] == ("data", None)
        assert results[1][0] == ""
        assert results[1][1] is not None

    async def test_resource_exhausted_raises_429(self, gemini_service):
        """Should raise HTTPException 429 on ResourceExhausted during streaming."""
        gemini_service.client.aio.models.generate_content_stream = AsyncMock(
            side_effect=google_exceptions.ResourceExhausted("Quota exceeded")
        )

        with pytest.raises(HTTPException) as exc_info:
            async for _ in gemini_service.generate_response_stream("Hi"):
                pass

        assert exc_info.value.status_code == 429

    async def test_generic_exception_raises_502(self, gemini_service):
        """Should raise HTTPException 502 on generic errors during streaming."""
        gemini_service.client.aio.models.generate_content_stream = AsyncMock(
            side_effect=RuntimeError("Connection lost")
        )

        with pytest.raises(HTTPException) as exc_info:
            async for _ in gemini_service.generate_response_stream("Hi"):
                pass

        assert exc_info.value.status_code == 502
