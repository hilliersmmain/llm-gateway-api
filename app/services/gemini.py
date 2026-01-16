"""Gemini API service using google-genai SDK."""

import logging

from google import genai
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
            response = self.client.models.generate_content(
                model=self.model,
                contents=message,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    max_output_tokens=2048,
                ),
            )

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
            logger.error(f"Gemini API error: {e}")
            raise


# Singleton instance
_gemini_service: GeminiService | None = None


def get_gemini_service() -> GeminiService:
    """Get or create Gemini service instance."""
    global _gemini_service
    if _gemini_service is None:
        _gemini_service = GeminiService()
    return _gemini_service
