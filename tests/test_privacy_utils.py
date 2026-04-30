"""Tests for privacy helpers and shared utilities."""

from unittest.mock import patch

from fastapi import Request

from app.privacy import hash_value, redact_text
from app.utils import get_client_ip


class TestHashValue:
    """Tests for hash_value."""

    def test_returns_none_for_none_input(self):
        assert hash_value(None) is None

    def test_returns_none_for_empty_string(self):
        assert hash_value("") is None

    def test_returns_hex_string_for_non_empty_input(self):
        result = hash_value("192.168.1.1")
        assert result is not None
        assert len(result) == 64  # sha256 hex digest

    def test_same_input_produces_same_hash(self):
        assert hash_value("test") == hash_value("test")

    def test_different_inputs_produce_different_hashes(self):
        assert hash_value("a") != hash_value("b")


class TestRedactText:
    """Tests for redact_text."""

    def test_truncates_to_max_length(self):
        text = "a" * 100
        with patch("app.privacy.settings") as mock_settings:
            mock_settings.log_raw_content = True
            result = redact_text(text, max_length=10)
        assert result == "a" * 10

    def test_returns_raw_text_when_log_raw_content_enabled(self):
        with patch("app.privacy.settings") as mock_settings:
            mock_settings.log_raw_content = True
            result = redact_text("hello world", max_length=100)
        assert result == "hello world"

    def test_returns_redacted_marker_when_raw_content_disabled(self):
        with patch("app.privacy.settings") as mock_settings:
            mock_settings.log_raw_content = False
            mock_settings.hash_salt = "test-salt"
            result = redact_text("sensitive text", max_length=100)
        assert result.startswith("[redacted_sha256:")
        assert "]" in result

    def test_redacted_marker_is_deterministic(self):
        with patch("app.privacy.settings") as mock_settings:
            mock_settings.log_raw_content = False
            mock_settings.hash_salt = "fixed-salt"
            r1 = redact_text("hello", max_length=100)
            r2 = redact_text("hello", max_length=100)
        assert r1 == r2


class TestGetClientIp:
    """Tests for get_client_ip utility."""

    def _make_request(self, headers: dict, client_host: str | None = None) -> Request:
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "query_string": b"",
            "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        }
        if client_host:
            scope["client"] = (client_host, 12345)
        request = Request(scope)
        return request

    def test_uses_rightmost_ip_from_x_forwarded_for(self):
        request = self._make_request({"X-Forwarded-For": "10.0.0.1, 10.0.0.2"})
        assert get_client_ip(request) == "10.0.0.2"

    def test_single_ip_in_x_forwarded_for(self):
        request = self._make_request({"X-Forwarded-For": "10.0.0.1"})
        assert get_client_ip(request) == "10.0.0.1"

    def test_falls_back_to_client_host_when_no_proxy_header(self):
        request = self._make_request({}, client_host="192.168.1.100")
        assert get_client_ip(request) == "192.168.1.100"

    def test_returns_none_when_no_client_and_no_header(self):
        request = self._make_request({})
        assert get_client_ip(request) is None
