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


class GuardrailLog(SQLModel, table=True):
    """Database model for logging guardrail violations."""

    __tablename__ = "guardrail_logs"

    id: int | None = Field(default=None, primary_key=True)
    input_prompt: str = Field(..., description="The blocked input message")
    blocked_keyword: str | None = Field(
        default=None, description="The keyword that triggered the block"
    )
    violation_type: str = Field(
        ..., description="Type: blocked_content, length_exceeded"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Violation timestamp",
    )
    client_ip: str | None = Field(default=None, description="Client IP address")
