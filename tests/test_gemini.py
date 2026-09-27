"""Tests for Gemini service — generate_response and generate_response_stream."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from google.genai import errors as genai_errors

import app.services.gemini as gemini_module
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


class StallingAsyncIterator(FakeAsyncIterator):
    """Yields its chunks, then never produces another one."""

    async def __anext__(self):
        if self._index >= len(self._chunks):
            await asyncio.Event().wait()
        return await super().__anext__()


def quota_error() -> genai_errors.ClientError:
    """The error google-genai raises when the Gemini quota is exhausted."""
    return genai_errors.ClientError(
        429, {"error": {"code": 429, "message": "Quota exceeded", "status": "RESOURCE_EXHAUSTED"}}
    )


def server_error() -> genai_errors.ServerError:
    return genai_errors.ServerError(
        503, {"error": {"code": 503, "message": "Unavailable", "status": "UNAVAILABLE"}}
    )


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
    """Tests for GeminiService.generate_response (async path)."""

    async def test_success_returns_text_and_tokens(self, gemini_service):
        """Should return response text and token usage on success."""
        fake_response = FakeResponse(
            text="Test response",
            usage_metadata=FakeUsageMetadata(prompt_tokens=5, candidates_tokens=15),
        )
        gemini_service.client.aio.models.generate_content = AsyncMock(return_value=fake_response)

        text, token_usage = await gemini_service.generate_response("Hello")

        assert text == "Test response"
        assert token_usage == {"input_tokens": 5, "output_tokens": 15}
        gemini_service.client.aio.models.generate_content.assert_called_once()

    async def test_success_without_usage_metadata(self, gemini_service):
        """Should return zero tokens when usage_metadata is missing."""
        fake_response = FakeResponse(text="Response")
        fake_response.usage_metadata = None
        gemini_service.client.aio.models.generate_content = AsyncMock(return_value=fake_response)

        text, token_usage = await gemini_service.generate_response("Hello")

        assert text == "Response"
        assert token_usage == {"input_tokens": 0, "output_tokens": 0}

    async def test_empty_text_returns_empty_string(self, gemini_service):
        """Should return empty string when response.text is None."""
        fake_response = FakeResponse()
        fake_response.text = None
        gemini_service.client.aio.models.generate_content = AsyncMock(return_value=fake_response)

        text, token_usage = await gemini_service.generate_response("Hello")

        assert text == ""

    async def test_resource_exhausted_raises_429(self, gemini_service):
        """Should raise HTTPException 429 when Gemini quota is exceeded."""
        gemini_service.client.aio.models.generate_content = AsyncMock(
            side_effect=quota_error()
        )

        with pytest.raises(HTTPException) as exc_info:
            await gemini_service.generate_response("Hello")

        assert exc_info.value.status_code == 429
        assert "quota exceeded" in exc_info.value.detail.lower()

    async def test_generic_exception_raises_502(self, gemini_service):
        """Should raise HTTPException 502 on generic API errors."""
        gemini_service.client.aio.models.generate_content = AsyncMock(
            side_effect=RuntimeError("Connection failed")
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
        """Should raise HTTPException 429 when the quota is exhausted during streaming."""
        gemini_service.client.aio.models.generate_content_stream = AsyncMock(
            side_effect=quota_error()
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


class TestCallWithRetryBackoff:
    """Tests for _call_with_retry exponential backoff, jitter, and budget guard."""

    @pytest.fixture
    def service(self):
        with patch("app.services.gemini.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            svc = GeminiService()
            svc.client = mock_client
            yield svc

    async def test_exponential_backoff_delays(self, service, monkeypatch):
        """Retry sleep delays should follow exponential backoff with jitter."""
        sleep_calls: list[float] = []

        async def fake_sleep(delay: float) -> None:
            sleep_calls.append(delay)

        monkeypatch.setattr(gemini_module.asyncio, "sleep", fake_sleep)
        # time.monotonic returns a low value so budget is never exceeded
        monkeypatch.setattr(gemini_module.time, "monotonic", lambda: 0.0)
        # random.uniform always returns the midpoint of the jitter range
        monkeypatch.setattr(gemini_module.random, "uniform", lambda a, b: 0.05)

        call_count = 0

        async def flaky_call():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("transient error")
            return "ok"

        # Patch wait_for to just await the coroutine directly. (It used to sit
        # inside a patch.object on the same attribute, which made monkeypatch
        # restore the MagicMock at teardown and broke asyncio.wait_for for every
        # later test.)
        async def direct_wait_for(coro, timeout):
            return await coro

        monkeypatch.setattr(gemini_module.asyncio, "wait_for", direct_wait_for)

        with patch("app.services.gemini.settings") as mock_settings:
            # Use 3 retry attempts so both sleeps occur
            mock_settings.gemini_retry_attempts = 3
            mock_settings.gemini_timeout_seconds = 30
            result = await service._call_with_retry(flaky_call)

        assert result == "ok"
        assert len(sleep_calls) == 2
        # attempt=1: min(8.0, 0.5 * 2^0) + 0.05 = 0.5 + 0.05 = 0.55
        assert 0.5 <= sleep_calls[0] <= 0.6, f"attempt-1 sleep={sleep_calls[0]}"
        # attempt=2: min(8.0, 0.5 * 2^1) + 0.05 = 1.0 + 0.05 = 1.05
        assert 1.0 <= sleep_calls[1] <= 1.1, f"attempt-2 sleep={sleep_calls[1]}"

    async def test_sleep_capped_at_eight_seconds(self, service, monkeypatch):
        """Sleep delay should be capped at 8.0 seconds regardless of attempt number."""
        sleep_calls: list[float] = []

        async def fake_sleep(delay: float) -> None:
            sleep_calls.append(delay)

        monkeypatch.setattr(gemini_module.asyncio, "sleep", fake_sleep)
        monkeypatch.setattr(gemini_module.time, "monotonic", lambda: 0.0)
        monkeypatch.setattr(gemini_module.random, "uniform", lambda a, b: 0.05)

        call_count = 0
        total_attempts = 7

        async def always_fails_then_succeeds():
            nonlocal call_count
            call_count += 1
            if call_count < total_attempts:
                raise RuntimeError("transient error")
            return "ok"

        async def direct_wait_for(coro, timeout):
            return await coro

        monkeypatch.setattr(gemini_module.asyncio, "wait_for", direct_wait_for)

        with patch("app.services.gemini.settings") as mock_settings:
            mock_settings.gemini_retry_attempts = total_attempts
            mock_settings.gemini_timeout_seconds = 30
            await service._call_with_retry(always_fails_then_succeeds)

        # All sleep calls should be capped: max possible is 8.0 + 0.1 jitter
        for delay in sleep_calls:
            assert delay <= 8.1, f"Sleep not capped: {delay}"
        # At attempt >= 5, the base is min(8.0, 0.5 * 2^4) = min(8.0, 8.0) = 8.0
        assert sleep_calls[-1] <= 8.1

    async def test_budget_guard_stops_retrying(self, service, monkeypatch):
        """Should stop retrying when wall-clock time exceeds the total budget."""
        async def fake_sleep(delay: float) -> None:
            pass  # never actually sleep

        monkeypatch.setattr(gemini_module.asyncio, "sleep", fake_sleep)

        # Simulate monotonic advancing beyond budget on first check after failure
        # budget = timeout * attempts = 5 * 3 = 15; return 20 to exceed budget
        call_count = 0
        mono_values = [0.0, 20.0]  # start=0, first check after failure=20 > budget

        def fake_monotonic():
            if mono_values:
                return mono_values.pop(0)
            return 20.0

        monkeypatch.setattr(gemini_module.time, "monotonic", fake_monotonic)
        monkeypatch.setattr(gemini_module.random, "uniform", lambda a, b: 0.0)

        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("persistent error")

        async def direct_wait_for(coro, timeout):
            return await coro

        monkeypatch.setattr(gemini_module.asyncio, "wait_for", direct_wait_for)

        with patch("app.services.gemini.settings") as mock_settings:
            mock_settings.gemini_retry_attempts = 3
            mock_settings.gemini_timeout_seconds = 5
            with pytest.raises(RuntimeError, match="persistent error"):
                await service._call_with_retry(always_fails)

        # Budget guard should fire after first failure — only 1 call made
        assert call_count == 1


class TestRetryPolicy:
    """Which google-genai errors are retried, and how they map to HTTP errors."""

    @pytest.fixture(autouse=True)
    def no_backoff(self, monkeypatch):
        async def fake_sleep(delay: float) -> None:
            pass

        monkeypatch.setattr(gemini_module.asyncio, "sleep", fake_sleep)

    async def test_quota_error_is_not_retried(self, gemini_service):
        """A 429 from google-genai maps to HTTP 429 after a single attempt."""
        gemini_service.client.aio.models.generate_content = AsyncMock(side_effect=quota_error())

        with (
            patch.object(gemini_module.settings, "gemini_retry_attempts", 3),
            pytest.raises(HTTPException) as exc_info,
        ):
            await gemini_service.generate_response("Hello")

        assert exc_info.value.status_code == 429
        assert gemini_service.client.aio.models.generate_content.call_count == 1

    async def test_other_client_error_is_not_retried(self, gemini_service):
        """A 4xx other than 429 maps to 502 without retrying."""
        bad_request = genai_errors.ClientError(
            400, {"error": {"code": 400, "message": "bad", "status": "INVALID_ARGUMENT"}}
        )
        gemini_service.client.aio.models.generate_content = AsyncMock(side_effect=bad_request)

        with (
            patch.object(gemini_module.settings, "gemini_retry_attempts", 3),
            pytest.raises(HTTPException) as exc_info,
        ):
            await gemini_service.generate_response("Hello")

        assert exc_info.value.status_code == 502
        assert gemini_service.client.aio.models.generate_content.call_count == 1

    async def test_server_error_is_retried(self, gemini_service):
        """A 5xx is transient: the call is retried and can then succeed."""
        gemini_service.client.aio.models.generate_content = AsyncMock(
            side_effect=[server_error(), FakeResponse(text="recovered")]
        )

        with patch.object(gemini_module.settings, "gemini_retry_attempts", 3):
            text, _ = await gemini_service.generate_response("Hello")

        assert text == "recovered"
        assert gemini_service.client.aio.models.generate_content.call_count == 2


class TestStreamTimeoutAndRetry:
    """The stream's first chunk is retried under the timeout; later chunks are timed out."""

    @pytest.fixture(autouse=True)
    def fast_settings(self, monkeypatch):
        async def fake_sleep(delay: float) -> None:
            pass

        monkeypatch.setattr(gemini_module.asyncio, "sleep", fake_sleep)
        monkeypatch.setattr(gemini_module.settings, "gemini_timeout_seconds", 0.05)
        monkeypatch.setattr(gemini_module.settings, "gemini_retry_attempts", 2)

    async def test_stalled_first_chunk_is_retried_then_502(self, gemini_service):
        """A stream that never produces its first chunk is retried, then fails with 502."""
        gemini_service.client.aio.models.generate_content_stream = AsyncMock(
            side_effect=lambda **_: StallingAsyncIterator([])
        )

        async def consume():
            async for _ in gemini_service.generate_response_stream("Hi"):
                pass

        # The outer cap turns a regression into a failure instead of a hung suite.
        with pytest.raises(HTTPException) as exc_info:
            await asyncio.wait_for(consume(), timeout=5)

        assert exc_info.value.status_code == 502
        assert gemini_service.client.aio.models.generate_content_stream.call_count == 2

    async def test_failed_first_chunk_is_retried(self, gemini_service):
        """A transient failure opening the stream is retried and the retry streams normally."""

        class FailingIterator(FakeAsyncIterator):
            async def __anext__(self):
                raise server_error()

        gemini_service.client.aio.models.generate_content_stream = AsyncMock(
            side_effect=[FailingIterator([]), FakeAsyncIterator([FakeChunk(text="ok")])]
        )

        results = [item async for item in gemini_service.generate_response_stream("Hi")]

        assert results[0] == ("ok", None)
        assert gemini_service.client.aio.models.generate_content_stream.call_count == 2

    async def test_stall_after_first_chunk_times_out_without_retry(self, gemini_service):
        """A stream that stalls mid-way fails with 502 and is not re-requested."""
        gemini_service.client.aio.models.generate_content_stream = AsyncMock(
            return_value=StallingAsyncIterator([FakeChunk(text="partial")])
        )

        received = []

        async def consume():
            async for text, _ in gemini_service.generate_response_stream("Hi"):
                received.append(text)

        with pytest.raises(HTTPException) as exc_info:
            await asyncio.wait_for(consume(), timeout=5)

        assert received == ["partial"]
        assert exc_info.value.status_code == 502
        assert gemini_service.client.aio.models.generate_content_stream.call_count == 1
