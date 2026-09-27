"""Tests for log redaction."""

from unittest.mock import patch

from app.privacy import redact_text


def test_empty_text_stays_empty_when_redacting():
    """An empty field has nothing to hide; it must not become a '[redacted_sha256:None]' marker."""
    with patch("app.privacy.settings.log_raw_content", False):
        assert redact_text("", 100) == ""


def test_text_is_replaced_by_a_hash_marker():
    with patch("app.privacy.settings.log_raw_content", False):
        redacted = redact_text("secret prompt", 100)

    assert redacted.startswith("[redacted_sha256:")
    assert "secret prompt" not in redacted
    assert "None" not in redacted
