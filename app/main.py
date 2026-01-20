"""FastAPI application entry point."""

import json
import logging
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone

from fastapi import BackgroundTasks, Depends, FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_session, init_db
from app.middleware.logging import RequestTimer, save_request_log
from app.middleware.rate_limit import RateLimitMiddleware, create_rate_limit_store
from app.models.log import GuardrailLog, RequestLog
from app.models.schemas import (
    AnalyticsResponse,
    BlockedKeywordStat,
    ChatRequest,
    ChatResponse,
    ErrorResponse,
    HealthResponse,
    LatencyBucket,
    MetricsResponse,
)
from app.services.gemini import get_gemini_service
from app.services.guardrails import (
    GuardrailError,
    get_guardrails_service,
    save_guardrail_log,
)

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


def get_client_ip(request: Request) -> str | None:
    """Extract client IP from request, considering proxy headers."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    if request.client:
        return request.client.host
    return None


@app.post(
    "/chat",
    response_model=ChatResponse,
    responses={400: {"model": ErrorResponse}},
    tags=["Chat"],
    summary="Send a message to Gemini",
    description="Send a message through the guardrails and receive a response from Gemini 2.5 Flash",
)
async def chat(
    chat_request: ChatRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """Process a chat request through guardrails and Gemini."""
    guardrails = get_guardrails_service()
    gemini = get_gemini_service()
    client_ip = get_client_ip(request)

    with RequestTimer() as timer:
        try:
            guardrails.validate(chat_request.message)
        except GuardrailError as e:
            background_tasks.add_task(
                save_guardrail_log,
                session=session,
                input_prompt=chat_request.message,
                violation_type=e.error_type,
                blocked_keyword=e.blocked_keyword,
                client_ip=client_ip,
            )
            raise

        response_text, token_usage = await gemini.generate_response(chat_request.message)

    background_tasks.add_task(
        save_request_log,
        session=session,
        input_prompt=chat_request.message,
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
    chat_request: ChatRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """Process a chat request with streaming response."""
    guardrails = get_guardrails_service()
    gemini = get_gemini_service()
    client_ip = get_client_ip(request)

    try:
        guardrails.validate(chat_request.message)
    except GuardrailError as e:
        background_tasks.add_task(
            save_guardrail_log,
            session=session,
            input_prompt=chat_request.message,
            violation_type=e.error_type,
            blocked_keyword=e.blocked_keyword,
            client_ip=client_ip,
        )

        # Capture error details before creating generator to avoid scope issues
        error_detail = e.detail
        error_type = e.error_type

        async def error_generator():
            error_data = json.dumps({"detail": error_detail, "error_type": error_type})
            yield f"event: error\ndata: {error_data}\n\n"

        return StreamingResponse(
            error_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
        )

    async def generate_sse():
        import time
        start_time = time.perf_counter()
        full_response = ""
        final_token_usage = {"input_tokens": 0, "output_tokens": 0}

        try:
            async for chunk_text, token_usage in gemini.generate_response_stream(chat_request.message):
                if chunk_text:
                    full_response += chunk_text
                    chunk_data = json.dumps({"text": chunk_text})
                    yield f"event: chunk\ndata: {chunk_data}\n\n"
                if token_usage:
                    final_token_usage = token_usage

            done_data = json.dumps({"token_usage": final_token_usage})
            yield f"event: done\ndata: {done_data}\n\n"

            end_time = time.perf_counter()
            latency_ms = (end_time - start_time) * 1000

            background_tasks.add_task(
                save_request_log,
                session=session,
                input_prompt=chat_request.message,
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
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@app.get(
    "/metrics",
    response_model=MetricsResponse,
    tags=["Metrics"],
    summary="Get API usage metrics",
)
async def get_metrics(session: AsyncSession = Depends(get_session)):
    """Get API usage metrics for today."""
    today_start = datetime.combine(date.today(), datetime.min.time(), tzinfo=timezone.utc)

    query = select(
        func.count(RequestLog.id).label("total_requests"),
        func.coalesce(func.sum(RequestLog.tokens_in), 0).label("total_tokens_in"),
        func.coalesce(func.sum(RequestLog.tokens_out), 0).label("total_tokens_out"),
    ).where(RequestLog.timestamp >= today_start)

    result = await session.execute(query)
    row = result.one()

    input_cost = (row.total_tokens_in / 1_000_000) * settings.gemini_input_price_per_million
    output_cost = (row.total_tokens_out / 1_000_000) * settings.gemini_output_price_per_million

    return MetricsResponse(
        total_requests_today=row.total_requests,
        total_tokens_in=row.total_tokens_in,
        total_tokens_out=row.total_tokens_out,
        estimated_cost_usd=round(input_cost + output_cost, 6),
    )


@app.get(
    "/analytics",
    response_model=AnalyticsResponse,
    tags=["Analytics"],
    summary="Get detailed analytics",
)
async def get_analytics(
    format: str | None = Query(None, description="Response format: 'json' or 'html'"),
    session: AsyncSession = Depends(get_session),
):
    """Get detailed analytics for the API."""
    now = datetime.now(timezone.utc)
    time_24h_ago = now - timedelta(hours=24)
    time_7d_ago = now - timedelta(days=7)

    # 24h metrics
    query_24h = select(
        func.count(RequestLog.id).label("total_requests"),
        func.coalesce(func.sum(RequestLog.tokens_in), 0).label("total_tokens_in"),
        func.coalesce(func.sum(RequestLog.tokens_out), 0).label("total_tokens_out"),
    ).where(RequestLog.timestamp >= time_24h_ago)
    row_24h = (await session.execute(query_24h)).one()

    # 7d metrics
    query_7d = select(
        func.count(RequestLog.id).label("total_requests"),
        func.coalesce(func.sum(RequestLog.tokens_in), 0).label("total_tokens_in"),
        func.coalesce(func.sum(RequestLog.tokens_out), 0).label("total_tokens_out"),
    ).where(RequestLog.timestamp >= time_7d_ago)
    row_7d = (await session.execute(query_7d)).one()

    # Hourly latency buckets
    latency_query = (
        select(
            func.date_trunc("hour", RequestLog.timestamp).label("hour"),
            func.avg(RequestLog.latency_ms).label("avg_latency"),
            func.count(RequestLog.id).label("request_count"),
        )
        .where(RequestLog.timestamp >= time_24h_ago)
        .group_by(func.date_trunc("hour", RequestLog.timestamp))
        .order_by(func.date_trunc("hour", RequestLog.timestamp))
    )
    latency_rows = (await session.execute(latency_query)).all()
    latency_trend = [
        LatencyBucket(
            hour=row.hour.isoformat() if row.hour else "",
            avg_latency_ms=round(float(row.avg_latency), 2) if row.avg_latency else 0.0,
            request_count=row.request_count,
        )
        for row in latency_rows
    ]

    # Top blocked keywords
    blocked_query = (
        select(GuardrailLog.blocked_keyword, func.count(GuardrailLog.id).label("count"))
        .where(GuardrailLog.blocked_keyword.isnot(None), GuardrailLog.timestamp >= time_7d_ago)
        .group_by(GuardrailLog.blocked_keyword)
        .order_by(func.count(GuardrailLog.id).desc())
        .limit(10)
    )
    blocked_rows = (await session.execute(blocked_query)).all()
    top_blocked_keywords = [BlockedKeywordStat(keyword=row.blocked_keyword, count=row.count) for row in blocked_rows]

    # Total blocked 24h
    blocked_24h = (await session.execute(
        select(func.count(GuardrailLog.id)).where(GuardrailLog.timestamp >= time_24h_ago)
    )).scalar() or 0

    analytics_data = AnalyticsResponse(
        total_requests_24h=row_24h.total_requests,
        total_requests_7d=row_7d.total_requests,
        latency_trend=latency_trend,
        total_tokens_in_24h=row_24h.total_tokens_in,
        total_tokens_out_24h=row_24h.total_tokens_out,
        total_tokens_in_7d=row_7d.total_tokens_in,
        total_tokens_out_7d=row_7d.total_tokens_out,
        top_blocked_keywords=top_blocked_keywords,
        total_blocked_requests_24h=blocked_24h,
    )

    if format and format.lower() == "html":
        return _generate_analytics_html(analytics_data)

    return analytics_data


def _generate_analytics_html(data: AnalyticsResponse) -> HTMLResponse:
    """Generate HTML page with Chart.js visualizations."""
    latency_labels = [b.hour[-8:-3] for b in data.latency_trend]
    latency_values = [b.avg_latency_ms for b in data.latency_trend]
    latency_counts = [b.request_count for b in data.latency_trend]
    keyword_labels = [s.keyword for s in data.top_blocked_keywords]
    keyword_counts = [s.count for s in data.top_blocked_keywords]

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LLM Gateway Analytics</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: system-ui, sans-serif; background: linear-gradient(135deg, #1a1a2e, #16213e); color: #e4e4e7; min-height: 100vh; padding: 2rem; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        h1 {{ font-size: 2rem; margin-bottom: 0.5rem; background: linear-gradient(90deg, #6366f1, #8b5cf6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
        .subtitle {{ color: #a1a1aa; margin-bottom: 2rem; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }}
        .stat-card {{ background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 1.5rem; }}
        .stat-value {{ font-size: 2rem; font-weight: 700; color: #6366f1; }}
        .stat-label {{ color: #a1a1aa; font-size: 0.875rem; margin-top: 0.25rem; }}
        .charts-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 1.5rem; }}
        .chart-card {{ background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 1.5rem; }}
        .chart-title {{ font-size: 1.125rem; margin-bottom: 1rem; }}
        canvas {{ max-height: 300px; }}
        .back-link {{ display: inline-block; margin-bottom: 1rem; color: #6366f1; text-decoration: none; }}
    </style>
</head>
<body>
    <div class="container">
        <a href="/" class="back-link">Back to Chat</a>
        <h1>Analytics Dashboard</h1>
        <p class="subtitle">LLM Gateway API Usage Statistics</p>
        <div class="stats-grid">
            <div class="stat-card"><div class="stat-value">{data.total_requests_24h:,}</div><div class="stat-label">Requests (24h)</div></div>
            <div class="stat-card"><div class="stat-value">{data.total_requests_7d:,}</div><div class="stat-label">Requests (7d)</div></div>
            <div class="stat-card"><div class="stat-value">{data.total_tokens_in_24h + data.total_tokens_out_24h:,}</div><div class="stat-label">Total Tokens (24h)</div></div>
            <div class="stat-card"><div class="stat-value">{data.total_blocked_requests_24h:,}</div><div class="stat-label">Blocked (24h)</div></div>
        </div>
        <div class="charts-grid">
            <div class="chart-card"><h3 class="chart-title">Latency Trend</h3><canvas id="latencyChart"></canvas></div>
            <div class="chart-card"><h3 class="chart-title">Token Usage</h3><canvas id="tokenChart"></canvas></div>
            <div class="chart-card"><h3 class="chart-title">Blocked Keywords</h3><canvas id="blockedChart"></canvas></div>
            <div class="chart-card"><h3 class="chart-title">Request Volume</h3><canvas id="volumeChart"></canvas></div>
        </div>
    </div>
    <script>
        const colors = {{ primary: 'rgb(99,102,241)', secondary: 'rgb(139,92,246)', success: 'rgb(34,197,94)', danger: 'rgb(239,68,68)', grid: 'rgba(255,255,255,0.1)' }};
        const opts = {{ responsive: true, plugins: {{ legend: {{ labels: {{ color: '#e4e4e7' }} }} }}, scales: {{ x: {{ ticks: {{ color: '#a1a1aa' }}, grid: {{ color: colors.grid }} }}, y: {{ ticks: {{ color: '#a1a1aa' }}, grid: {{ color: colors.grid }} }} }} }};
        new Chart(document.getElementById('latencyChart'), {{ type: 'line', data: {{ labels: {latency_labels}, datasets: [{{ label: 'Latency (ms)', data: {latency_values}, borderColor: colors.primary, fill: true, tension: 0.4 }}] }}, options: opts }});
        new Chart(document.getElementById('tokenChart'), {{ type: 'bar', data: {{ labels: ['24h', '7d'], datasets: [{{ label: 'Input', data: [{data.total_tokens_in_24h}, {data.total_tokens_in_7d}], backgroundColor: colors.primary }}, {{ label: 'Output', data: [{data.total_tokens_out_24h}, {data.total_tokens_out_7d}], backgroundColor: colors.secondary }}] }}, options: opts }});
        new Chart(document.getElementById('blockedChart'), {{ type: 'bar', data: {{ labels: {keyword_labels if keyword_labels else ['None']}, datasets: [{{ label: 'Count', data: {keyword_counts if keyword_counts else [0]}, backgroundColor: colors.danger }}] }}, options: {{ ...opts, indexAxis: 'y' }} }});
        new Chart(document.getElementById('volumeChart'), {{ type: 'bar', data: {{ labels: {latency_labels}, datasets: [{{ label: 'Requests', data: {latency_counts}, backgroundColor: colors.success }}] }}, options: opts }});
    </script>
</body>
</html>"""
    return HTMLResponse(content=html)


# Mount static files (must be last)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
