"""FastAPI application entry point."""

import json
import logging
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone

from fastapi import BackgroundTasks, Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_session, init_db
from app.middleware.logging import RequestTimer, save_request_log
from app.middleware.rate_limit import RateLimitMiddleware, create_rate_limit_store
from app.models.log import RequestLog
from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    ErrorResponse,
    HealthResponse,
    MetricsResponse,
)
from app.services.gemini import get_gemini_service
from app.services.guardrails import GuardrailError, get_guardrails_service

# Configure logging
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting LLM Gateway API...")
    await init_db()
    logger.info("Database initialized")
    yield
    logger.info("Shutting down...")


# Create FastAPI application
app = FastAPI(
    title="LLM Gateway API",
    description="Enterprise-grade LLM gateway with input validation and request logging",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiting middleware
rate_limit_store = create_rate_limit_store(settings.redis_url)
app.add_middleware(
    RateLimitMiddleware,
    store=rate_limit_store,
    max_requests=settings.rate_limit_requests,
    window_seconds=settings.rate_limit_window_seconds,
)


@app.exception_handler(GuardrailError)
async def guardrail_exception_handler(request: Request, exc: GuardrailError):
    """Handle guardrail violations."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "error_type": exc.error_type,
        },
    )


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Health check endpoint",
)
async def health_check():
    """Check API health status."""
    return HealthResponse(status="healthy", version="1.0.0")


@app.post(
    "/chat",
    response_model=ChatResponse,
    responses={400: {"model": ErrorResponse}},
    tags=["Chat"],
    summary="Send a message to Gemini",
    description="Send a message through the guardrails and receive a response from Gemini 2.5 Flash",
)
async def chat(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """
    Process a chat request through guardrails and Gemini.

    - **message**: The user's input message (max 5000 characters)

    Returns the Gemini response along with token usage statistics.
    Blocked content and messages exceeding length limits will return 400 errors.
    """
    guardrails = get_guardrails_service()
    gemini = get_gemini_service()

    # Start timing
    with RequestTimer() as timer:
        # Validate input against guardrails
        guardrails.validate(request.message)

        # Generate response from Gemini
        response_text, token_usage = await gemini.generate_response(request.message)

    # Schedule background logging
    background_tasks.add_task(
        save_request_log,
        session=session,
        input_prompt=request.message,
        output_response=response_text,
        latency_ms=timer.elapsed_ms,
        tokens_in=token_usage.get("input_tokens", 0),
        tokens_out=token_usage.get("output_tokens", 0),
        status="success",
    )

    logger.info(f"Chat request processed in {timer.elapsed_ms:.2f}ms")

    return ChatResponse(
        content=response_text,
        token_usage=token_usage,
    )


@app.post(
    "/chat/stream",
    tags=["Chat"],
    summary="Stream a message to Gemini (SSE)",
    description="Send a message and receive streaming response chunks via Server-Sent Events",
)
async def chat_stream(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """
    Process a chat request with streaming response.

    - **message**: The user's input message (max 5000 characters)

    Returns Server-Sent Events (SSE) stream with:
    - `event: chunk` - Text chunks as they arrive
    - `event: done` - Final event with token usage statistics
    - `event: error` - Error event if something fails
    """
    guardrails = get_guardrails_service()
    gemini = get_gemini_service()

    # Validate input against guardrails (before streaming starts)
    try:
        guardrails.validate(request.message)
    except GuardrailError as e:
        # Return error as SSE event
        async def error_generator():
            error_data = json.dumps({"detail": e.detail, "error_type": e.error_type})
            yield f"event: error\ndata: {error_data}\n\n"

        return StreamingResponse(
            error_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    async def generate_sse():
        """Generate Server-Sent Events from Gemini stream."""
        import time

        start_time = time.perf_counter()
        full_response = ""
        final_token_usage = {"input_tokens": 0, "output_tokens": 0}

        try:
            async for chunk_text, token_usage in gemini.generate_response_stream(
                request.message
            ):
                if chunk_text:
                    full_response += chunk_text
                    # Send chunk as SSE event
                    chunk_data = json.dumps({"text": chunk_text})
                    yield f"event: chunk\ndata: {chunk_data}\n\n"

                if token_usage:
                    final_token_usage = token_usage

            # Send done event with token usage
            done_data = json.dumps({"token_usage": final_token_usage})
            yield f"event: done\ndata: {done_data}\n\n"

            # Calculate latency and log in background
            end_time = time.perf_counter()
            latency_ms = (end_time - start_time) * 1000

            background_tasks.add_task(
                save_request_log,
                session=session,
                input_prompt=request.message,
                output_response=full_response,
                latency_ms=latency_ms,
                tokens_in=final_token_usage.get("input_tokens", 0),
                tokens_out=final_token_usage.get("output_tokens", 0),
                status="success",
            )

            logger.info(f"Streaming request completed in {latency_ms:.2f}ms")

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            error_data = json.dumps({"detail": str(e), "error_type": "streaming_error"})
            yield f"event: error\ndata: {error_data}\n\n"

    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get(
    "/metrics",
    response_model=MetricsResponse,
    tags=["Metrics"],
    summary="Get API usage metrics",
    description="Returns today's usage statistics including request count, token usage, and estimated cost",
)
async def get_metrics(session: AsyncSession = Depends(get_session)):
    """
    Get API usage metrics for today.

    Returns:
    - **total_requests_today**: Number of requests made today
    - **total_tokens_in**: Total input tokens consumed today
    - **total_tokens_out**: Total output tokens consumed today
    - **estimated_cost_usd**: Estimated cost based on Gemini 2.5 Flash pricing
    """
    # Get start of today in UTC
    today_start = datetime.combine(date.today(), datetime.min.time(), tzinfo=timezone.utc)

    # Query aggregated metrics from request_logs
    query = select(
        func.count(RequestLog.id).label("total_requests"),
        func.coalesce(func.sum(RequestLog.tokens_in), 0).label("total_tokens_in"),
        func.coalesce(func.sum(RequestLog.tokens_out), 0).label("total_tokens_out"),
    ).where(RequestLog.timestamp >= today_start)

    result = await session.execute(query)
    row = result.one()

    total_requests = row.total_requests
    total_tokens_in = row.total_tokens_in
    total_tokens_out = row.total_tokens_out

    # Calculate estimated cost using Gemini pricing
    input_cost = (total_tokens_in / 1_000_000) * settings.gemini_input_price_per_million
    output_cost = (total_tokens_out / 1_000_000) * settings.gemini_output_price_per_million
    estimated_cost = round(input_cost + output_cost, 6)

    return MetricsResponse(
        total_requests_today=total_requests,
        total_tokens_in=total_tokens_in,
        total_tokens_out=total_tokens_out,
        estimated_cost_usd=estimated_cost,
    )


# Mount static files (must be last to avoid shadowing API routes)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
