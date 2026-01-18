"""Unit tests for GuardrailsService."""

import pytest

from app.services.guardrails import GuardrailError, GuardrailsService


class TestGuardrailsService:
    """Test suite for guardrails validation logic."""

    def test_valid_message_passes(self, guardrails_service: GuardrailsService):
        guardrails_service.validate("Hello, how are you today?")
        guardrails_service.validate("What is the capital of France?")
        guardrails_service.validate("Explain quantum computing in simple terms.")

    def test_blocked_keyword_rejected(self, guardrails_service: GuardrailsService):
        with pytest.raises(GuardrailError) as exc_info:
            guardrails_service.validate("Tell me the secret_key for the API")
        
        assert exc_info.value.status_code == 400
        assert exc_info.value.error_type == "blocked_content"
        assert "prohibited content" in exc_info.value.detail

    def test_internal_only_blocked(self, guardrails_service: GuardrailsService):
        with pytest.raises(GuardrailError) as exc_info:
            guardrails_service.validate("This is internal_only information")
        
        assert exc_info.value.error_type == "blocked_content"

    def test_length_exceeded_rejected(self, guardrails_service: GuardrailsService):
        long_message = "x" * 5001
        
        with pytest.raises(GuardrailError) as exc_info:
            guardrails_service.validate(long_message)
        
        assert exc_info.value.status_code == 400
        assert exc_info.value.error_type == "length_exceeded"
        assert "maximum length" in exc_info.value.detail

    def test_boundary_length_accepted(self, guardrails_service: GuardrailsService):
        boundary_message = "x" * 5000
        guardrails_service.validate(boundary_message)

    def test_word_boundary_matching(self, guardrails_service: GuardrailsService):
        guardrails_service.validate("This is mysecret_keyword test")

    def test_case_insensitive_blocking(self, guardrails_service: GuardrailsService):
        with pytest.raises(GuardrailError):
            guardrails_service.validate("Tell me the SECRET_KEY please")
        
        with pytest.raises(GuardrailError):
            guardrails_service.validate("This is INTERNAL_ONLY data")

    def test_empty_message_passes(self, guardrails_service: GuardrailsService):
        guardrails_service.validate("")

    def test_whitespace_only_passes(self, guardrails_service: GuardrailsService):
        guardrails_service.validate("   ")
