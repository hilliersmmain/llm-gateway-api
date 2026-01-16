"""Request logging middleware with background task persistence."""

import logging
import time
from datetime import datetime

from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.log import RequestLog

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
    """
    Save request log to database (background task).

    Args:
        session: Database session
        input_prompt: User's input message
        output_response: Generated response
        latency_ms: Request latency in milliseconds
        tokens_in: Input token count
        tokens_out: Output token count
        status: Request status (success/error)
        error_message: Error message if any
    """
    try:
        log_entry = RequestLog(
            input_prompt=input_prompt[:5000],  # Truncate to prevent DB issues
            output_response=output_response[:10000],
            latency_ms=latency_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            timestamp=datetime.utcnow(),
            status=status,
            error_message=error_message,
        )
        session.add(log_entry)
        await session.commit()
        logger.debug(f"Saved request log: latency={latency_ms:.2f}ms")
    except Exception as e:
        logger.error(f"Failed to save request log: {e}")
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
        """Get elapsed time in milliseconds."""
        return (self.end_time - self.start_time) * 1000
