"""Pydantic request/response schemas."""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request schema for chat endpoint."""

    message: str = Field(..., min_length=1, examples=["What is the capital of France?"])


class ChatResponse(BaseModel):
    """Response schema for chat endpoint."""

    content: str
    token_usage: dict = Field(
        default_factory=dict,
        examples=[{"input_tokens": 10, "output_tokens": 50}],
    )


class HealthResponse(BaseModel):
    """Response schema for health check endpoint."""

    status: str = Field(default="healthy")
    version: str = Field(default="1.0.0")


class ErrorResponse(BaseModel):
    """Response schema for error responses."""

    detail: str
    error_type: str = Field(default="error")
