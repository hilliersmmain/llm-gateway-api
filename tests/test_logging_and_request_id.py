"""Tests for JsonLogFormatter, configure_json_logging, and RequestIDMiddleware."""

import io
import json
import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from alembic import command as alembic_command
from app.core import database
from app.core.logging_setup import JsonLogFormatter, configure_json_logging
from app.middleware.request_id import RequestIDMiddleware, request_id_var


class TestJsonLogFormatter:
    """Tests for JsonLogFormatter."""

    def test_format_returns_valid_json(self):
        formatter = JsonLogFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="hello world", args=(), exc_info=None,
        )
        result = formatter.format(record)
        data = json.loads(result)
        assert data["level"] == "INFO"
        assert data["logger"] == "test"
        assert data["message"] == "hello world"
        assert "timestamp" in data
        assert "request_id" in data

    def test_format_includes_exc_info(self):
        formatter = JsonLogFormatter()
        try:
            raise ValueError("boom")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test", level=logging.ERROR, pathname="", lineno=0,
            msg="error occurred", args=(), exc_info=exc_info,
        )
        result = formatter.format(record)
        data = json.loads(result)
        assert "exc_info" in data
        assert "ValueError" in data["exc_info"]

    def test_format_includes_exc_text(self):
        formatter = JsonLogFormatter()
        record = logging.LogRecord(
            name="test", level=logging.ERROR, pathname="", lineno=0,
            msg="error occurred", args=(), exc_info=None,
        )
        record.exc_text = "some traceback text"
        result = formatter.format(record)
        data = json.loads(result)
        assert data["exc_info"] == "some traceback text"

    def test_format_includes_request_id_from_context(self):
        token = request_id_var.set("req-abc-123")
        try:
            formatter = JsonLogFormatter()
            record = logging.LogRecord(
                name="test", level=logging.INFO, pathname="", lineno=0,
                msg="msg", args=(), exc_info=None,
            )
            result = formatter.format(record)
            data = json.loads(result)
            assert data["request_id"] == "req-abc-123"
        finally:
            request_id_var.reset(token)


class TestConfigureJsonLogging:
    """Tests for configure_json_logging."""

    def test_configure_replaces_handlers(self):
        root = logging.getLogger()
        original_handlers = root.handlers[:]
        try:
            configure_json_logging(level=logging.DEBUG)
            assert root.level == logging.DEBUG
            assert len(root.handlers) == 1
            assert isinstance(root.handlers[0].formatter, JsonLogFormatter)
        finally:
            # Restore original handlers
            root.handlers.clear()
            for h in original_handlers:
                root.addHandler(h)



class TestInProcessMigrationsKeepAppLogging:
    """init_db runs Alembic inside the app; that must not reconfigure logging."""

    def test_upgrade_leaves_app_loggers_and_json_handler_alone(self):
        root = logging.getLogger()
        original_handlers = root.handlers[:]
        original_level = root.level
        app_logger = logging.getLogger("app.routers.chat")
        try:
            configure_json_logging(level=logging.INFO)
            json_handler = root.handlers[-1]
            assert not app_logger.disabled

            # Offline mode (sql=True) runs alembic/env.py without a database.
            buffer = io.StringIO()
            alembic_command.upgrade(database._alembic_config(output_buffer=buffer), "head", sql=True)

            assert "CREATE TABLE" in buffer.getvalue(), "env.py did not run the migrations"
            assert not app_logger.disabled
            assert root.level == logging.INFO
            assert json_handler in root.handlers
            assert isinstance(json_handler.formatter, JsonLogFormatter)
        finally:
            app_logger.disabled = False
            root.setLevel(original_level)
            root.handlers.clear()
            for h in original_handlers:
                root.addHandler(h)

class TestRequestIDMiddleware:
    """Tests for RequestIDMiddleware via a minimal FastAPI app."""

    @pytest.fixture
    def app_with_middleware(self):
        app = FastAPI()
        app.add_middleware(RequestIDMiddleware)

        @app.get("/ping")
        async def ping():
            return {"request_id": request_id_var.get("")}

        return app

    def test_response_includes_x_request_id_header(self, app_with_middleware):
        client = TestClient(app_with_middleware)
        resp = client.get("/ping")
        assert "x-request-id" in resp.headers
        assert len(resp.headers["x-request-id"]) > 0

    def test_propagates_existing_x_request_id(self, app_with_middleware):
        client = TestClient(app_with_middleware)
        resp = client.get("/ping", headers={"X-Request-ID": "my-custom-id"})
        assert resp.headers["x-request-id"] == "my-custom-id"
        assert resp.json()["request_id"] == "my-custom-id"

    def test_generates_new_id_when_absent(self, app_with_middleware):
        client = TestClient(app_with_middleware)
        resp = client.get("/ping")
        rid = resp.headers["x-request-id"]
        assert len(rid) == 32  # uuid4().hex is 32 chars
