"""Chat router — /chat and /chat/stream endpoints."""

import json
import logging
import time
from collections.abc import AsyncGenerator

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.middleware.logging import RequestTimer, save_request_log
from app.models.schemas import ChatRequest, ChatResponse, ErrorResponse
from app.services.gemini import GeminiService, get_gemini_service
from app.services.guardrails import (
    GuardrailError,
    GuardrailsService,
    get_guardrails_service,
    save_guardrail_log,
)
from app.utils import get_client_ip

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Chat"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    responses={400: {"model": ErrorResponse}},
    summary="Send a message to Gemini",
    description="Send a message through the guardrails and receive a response from Gemini 2.5 Flash",
)
async def chat(
    chat_request: ChatRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    guardrails: GuardrailsService = Depends(get_guardrails_service),
    gemini: GeminiService = Depends(get_gemini_service),
):
    """Process a chat request through guardrails and Gemini."""
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


@router.post(
    "/chat/stream",
    summary="Stream a message to Gemini (SSE)",
    description="Send a message and receive streaming response chunks via Server-Sent Events",
)
async def chat_stream(
    chat_request: ChatRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    guardrails: GuardrailsService = Depends(get_guardrails_service),
    gemini: GeminiService = Depends(get_gemini_service),
):
    """Process a chat request with streaming response."""
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

        async def error_generator(detail: str, error_type: str):
            error_data = json.dumps({"detail": detail, "error_type": error_type})
            yield f"event: error\ndata: {error_data}\n\n"

        return StreamingResponse(
            error_generator(e.detail, e.error_type),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
        )

    async def generate_sse() -> AsyncGenerator[str, None]:
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
            error_data = json.dumps({"detail": "An internal error occurred. Please try again later.", "error_type": "streaming_error"})
            yield f"event: error\ndata: {error_data}\n\n"

    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
