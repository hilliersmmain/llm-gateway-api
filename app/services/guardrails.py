"""Input validation guardrails service."""

import logging
import re

from fastapi import HTTPException, status

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class GuardrailError(HTTPException):
    """Custom exception for guardrail violations."""

    def __init__(self, detail: str, error_type: str = "guardrail_violation") -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )
        self.error_type = error_type


class GuardrailsService:
    """Service for validating input against security guardrails."""

    def __init__(self) -> None:
        self.blocked_keywords = settings.blocked_keywords
        self.max_length = settings.max_input_length

    def validate(self, message: str) -> None:
        """
        Validate input message against all guardrails.

        Args:
            message: The user's input message.

        Raises:
            GuardrailError: If any guardrail check fails.
        """
        self._check_length(message)
        self._check_blocklist(message)
        logger.info("Message passed all guardrail checks")

    def _check_length(self, message: str) -> None:
        if len(message) > self.max_length:
            logger.warning(
                f"Message rejected: length {len(message)} exceeds max {self.max_length}"
            )
            raise GuardrailError(
                detail=f"Message exceeds maximum length of {self.max_length} characters",
                error_type="length_exceeded",
            )

    def _check_blocklist(self, message: str) -> None:
        message_lower = message.lower()

        for keyword in self.blocked_keywords:
            pattern = rf"\b{re.escape(keyword.lower())}\b"
            if re.search(pattern, message_lower):
                logger.warning(f"Message rejected: contains blocked keyword '{keyword}'")
                raise GuardrailError(
                    detail="Message contains prohibited content",
                    error_type="blocked_content",
                )


_guardrails_service: GuardrailsService | None = None


def get_guardrails_service() -> GuardrailsService:
    global _guardrails_service
    if _guardrails_service is None:
        _guardrails_service = GuardrailsService()
    return _guardrails_service
