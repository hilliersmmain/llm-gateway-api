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


class LatencyBucket(BaseModel):
    """Hourly latency statistics bucket."""

    hour: str = Field(..., description="Hour in ISO format: 2026-01-20T14:00:00")
    avg_latency_ms: float = Field(..., description="Average latency in milliseconds")
    request_count: int = Field(..., description="Number of requests in this hour")


class BlockedKeywordStat(BaseModel):
    """Statistics for a blocked keyword."""

    keyword: str = Field(..., description="The blocked keyword")
    count: int = Field(..., description="Number of times this keyword was blocked")


class AnalyticsResponse(BaseModel):
    """Response schema for analytics endpoint."""

    # Request counts
    total_requests_24h: int = Field(
        ..., description="Total successful requests in the last 24 hours"
    )
    total_requests_7d: int = Field(
        ..., description="Total successful requests in the last 7 days"
    )

    # Latency trend (last 24 hours, hourly buckets)
    latency_trend: list[LatencyBucket] = Field(
        default_factory=list,
        description="Hourly average latency for the last 24 hours",
    )

    # Token breakdown
    total_tokens_in_24h: int = Field(
        ..., description="Total input tokens in the last 24 hours"
    )
    total_tokens_out_24h: int = Field(
        ..., description="Total output tokens in the last 24 hours"
    )
    total_tokens_in_7d: int = Field(
        ..., description="Total input tokens in the last 7 days"
    )
    total_tokens_out_7d: int = Field(
        ..., description="Total output tokens in the last 7 days"
    )

    # Blocked keywords (top 10)
    top_blocked_keywords: list[BlockedKeywordStat] = Field(
        default_factory=list,
        description="Top 10 most commonly blocked keywords",
    )
    total_blocked_requests_24h: int = Field(
        ..., description="Total blocked requests in the last 24 hours"
    )
