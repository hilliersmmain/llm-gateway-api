"""Pydantic request/response schemas."""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request schema for chat endpoint."""

    message: str = Field(
        ...,
        min_length=1,
        description="The user message to send to Gemini",
        examples=["What is the capital of France?"],
    )


class ChatResponse(BaseModel):
    """Response schema for chat endpoint."""

    content: str = Field(..., description="The generated response from Gemini")
    token_usage: dict = Field(
        default_factory=dict,
        description="Token usage statistics",
        examples=[{"input_tokens": 10, "output_tokens": 50}],
    )


class HealthResponse(BaseModel):
    """Response schema for health check endpoint."""

    status: str = Field(default="healthy", description="Service health status")
    version: str = Field(default="1.0.0", description="API version")


class ErrorResponse(BaseModel):
    """Response schema for error responses."""

    detail: str = Field(..., description="Error message")
    error_type: str = Field(default="error", description="Type of error")


class MetricsResponse(BaseModel):
    """Response schema for metrics endpoint."""

    total_requests_today: int = Field(
        ..., description="Total API requests made today"
    )
    total_tokens_in: int = Field(
        ..., description="Total input tokens consumed today"
    )
    total_tokens_out: int = Field(
        ..., description="Total output tokens consumed today"
    )
    estimated_cost_usd: float = Field(
        ..., description="Estimated cost in USD based on Gemini pricing"
    )
