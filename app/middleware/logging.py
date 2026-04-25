"""Request logging middleware with background task persistence."""

import logging
import time
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.log import RequestLog
from app.privacy import redact_text

logger = logging.getLogger(__name__)


async def save_request_log(
    session: AsyncSession,
    input_prompt: str,
    output_response: str,
    latency_ms: float,
    tokens_in: int,
    tokens_out: int,
    status: str = "success",
    error_message: str | None = None,
) -> None:
    """Save request log to database (background task)."""
    try:
        log_entry = RequestLog(
            input_prompt=redact_text(input_prompt, 5000),
            output_response=redact_text(output_response, 10000),
            latency_ms=latency_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            timestamp=datetime.now(UTC).replace(tzinfo=None),
            status=status,
            error_message=error_message,
        )
        session.add(log_entry)
        await session.commit()
        logger.debug("Saved request log: latency=%.2fms", latency_ms)
    except Exception as e:
        logger.error("Failed to save request log: %s", type(e).__name__)
        await session.rollback()


class RequestTimer:
    """Context manager for timing requests."""

    def __init__(self) -> None:
        self.start_time: float = 0
        self.end_time: float = 0

    def __enter__(self) -> "RequestTimer":
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, *args) -> None:
        self.end_time = time.perf_counter()

    @property
    def elapsed_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000
