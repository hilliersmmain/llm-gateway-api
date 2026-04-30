"""Gemini API service using google-genai SDK."""

import asyncio
import logging
import random
import time
from collections.abc import AsyncGenerator

from fastapi import HTTPException
from google import genai
from google.api_core import exceptions as google_exceptions
from google.genai import types

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class GeminiService:
    """Service for interacting with Google Gemini API."""

    def __init__(self) -> None:
        """Initialize Gemini client."""
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model = settings.model_name

    async def _call_with_retry(self, call):
        attempts = max(1, settings.gemini_retry_attempts)
        budget = settings.gemini_timeout_seconds * attempts
        start = time.monotonic()
        last_error = None
        for attempt in range(1, attempts + 1):
            try:
                return await asyncio.wait_for(call(), timeout=settings.gemini_timeout_seconds)
            except Exception as e:  # pragma: no cover - unified retry path
                last_error = e
                if isinstance(e, google_exceptions.ResourceExhausted):
                    raise
                if attempt >= attempts:
                    raise
                if time.monotonic() - start >= budget:
                    raise
                delay = min(8.0, 0.5 * 2 ** (attempt - 1)) + random.uniform(0, 0.1)
                await asyncio.sleep(delay)
        raise last_error  # type: ignore[misc]

    async def generate_response_stream(
        self, message: str
    ) -> AsyncGenerator[tuple[str, dict | None], None]:
        """
        Generate a streaming response from Gemini.

        Yields chunks of text as they arrive, with token usage in the final chunk.

        Args:
            message: The user's input message.

        Yields:
            Tuple of (chunk_text, token_usage_or_none)
            Token usage is only provided with the final chunk.
        """
        logger.info(f"Starting streaming request to Gemini model: {self.model}")

        try:
            async def stream_call():
                return await self.client.aio.models.generate_content_stream(
                    model=self.model,
                    contents=message,
                    config=types.GenerateContentConfig(
                        temperature=0.7,
                        max_output_tokens=2048,
                    ),
                )

            response_stream = await self._call_with_retry(stream_call)

            token_usage = {"input_tokens": 0, "output_tokens": 0}

            async for chunk in response_stream:
                # Extract text from chunk
                chunk_text = chunk.text if chunk.text else ""

                # Update token usage from final chunk's metadata
                if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
                    usage = chunk.usage_metadata
                    token_usage = {
                        "input_tokens": getattr(usage, "prompt_token_count", 0) or 0,
                        "output_tokens": getattr(usage, "candidates_token_count", 0) or 0,
                    }

                if chunk_text:
                    yield chunk_text, None

            # Yield final empty chunk with token usage
            yield "", token_usage
            logger.info(f"Streaming complete. Tokens: {token_usage}")

        except Exception as e:
            if isinstance(e, google_exceptions.ResourceExhausted):
                logger.warning("Gemini quota exceeded")
                raise HTTPException(
                    status_code=429,
                    detail="Gemini quota exceeded. Please try again later.",
                )

            logger.error("Gemini streaming API error: %s", type(e).__name__)
            raise HTTPException(
                status_code=502,
                detail="Failed to get response from LLM service. Please try again later.",
            )

    async def generate_response(self, message: str) -> tuple[str, dict]:
        """
        Generate a response from Gemini.

        Args:
            message: The user's input message.

        Returns:
            Tuple of (response_text, token_usage_dict)
        """
        logger.info(f"Sending request to Gemini model: {self.model}")

        try:
            async def generate_call():
                return await self.client.aio.models.generate_content(
                    model=self.model,
                    contents=message,
                    config=types.GenerateContentConfig(
                        temperature=0.7,
                        max_output_tokens=2048,
                    ),
                )

            response = await self._call_with_retry(generate_call)

            # Extract response text
            response_text = response.text if response.text else ""

            # Extract token usage from response metadata
            token_usage = {
                "input_tokens": 0,
                "output_tokens": 0,
            }

            if hasattr(response, "usage_metadata") and response.usage_metadata:
                usage = response.usage_metadata
                token_usage = {
                    "input_tokens": getattr(usage, "prompt_token_count", 0) or 0,
                    "output_tokens": getattr(usage, "candidates_token_count", 0) or 0,
                }

            logger.info(f"Gemini response received. Tokens: {token_usage}")
            return response_text, token_usage

        except Exception as e:
            if isinstance(e, google_exceptions.ResourceExhausted):
                logger.warning("Gemini quota exceeded")
                raise HTTPException(
                    status_code=429,
                    detail="Gemini quota exceeded. Please try again later."
                )
            logger.error("Gemini API error: %s", type(e).__name__)
            raise HTTPException(
                status_code=502,
                detail="Failed to get response from LLM service. Please try again later.",
            )


# Singleton instance
_gemini_service: GeminiService | None = None


def get_gemini_service() -> GeminiService:
    """Get or create Gemini service instance."""
    global _gemini_service
    if _gemini_service is None:
        _gemini_service = GeminiService()
    return _gemini_service
