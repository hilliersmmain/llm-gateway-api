"""SQLModel database models for request logging."""

from datetime import datetime

from sqlmodel import Field, SQLModel


class RequestLog(SQLModel, table=True):
    """Database model for logging API requests."""

    __tablename__ = "request_logs"

    id: int | None = Field(default=None, primary_key=True)
    input_prompt: str
    output_response: str
    latency_ms: float
    tokens_in: int = Field(default=0)
    tokens_out: int = Field(default=0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    status: str = Field(default="success")
    error_message: str | None = Field(default=None)
