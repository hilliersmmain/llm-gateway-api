"""JSON log formatter that includes the current request ID."""

import json
import logging
from datetime import UTC, datetime

from app.middleware.request_id import request_id_var


class JsonLogFormatter(logging.Formatter):
    """Emit one JSON object per line with standard fields + request_id."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(""),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        elif record.exc_text:
            payload["exc_info"] = record.exc_text
        return json.dumps(payload)


def configure_json_logging(level: int = logging.INFO) -> None:
    """Replace all root-logger handlers with a single JSON StreamHandler."""
    root = logging.getLogger()
    root.setLevel(level)
    for handler in root.handlers[:]:
        root.removeHandler(handler)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root.addHandler(handler)
