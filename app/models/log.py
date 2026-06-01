"""SQLModel database models for request logging."""

from datetime import UTC, datetime

from sqlalchemy import Text
from sqlmodel import Field, SQLModel


class RequestLog(SQLModel, table=True):
    """Database model for logging API requests."""

    __tablename__ = "request_logs"

    id: int | None = Field(default=None, primary_key=True)
    input_prompt: str = Field(sa_type=Text)
    output_response: str = Field(sa_type=Text)
    latency_ms: float
    tokens_in: int = Field(default=0)
    tokens_out: int = Field(default=0)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC).replace(tzinfo=None))
    status: str = Field(default="success", sa_type=Text)
    error_message: str | None = Field(default=None, sa_type=Text)


class GuardrailLog(SQLModel, table=True):
    """Database model for logging guardrail violations."""

    __tablename__ = "guardrail_logs"

    id: int | None = Field(default=None, primary_key=True)
    input_prompt: str = Field(
        ..., sa_type=Text, description="The blocked input message"
    )
    blocked_keyword: str | None = Field(
        default=None,
        sa_type=Text,
        description="The keyword that triggered the block",
    )
    violation_type: str = Field(
        ..., sa_type=Text, description="Type: blocked_content, length_exceeded"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC).replace(tzinfo=None),
        description="Violation timestamp",
    )
    client_ip: str | None = Field(
        default=None, sa_type=Text, description="Client IP address"
    )
