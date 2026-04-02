# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LLM Gateway API — a FastAPI backend that proxies chat requests to Google Gemini 2.5 Flash, with a vanilla JS frontend. Features rate limiting, input guardrails, request logging to PostgreSQL, and an analytics dashboard.

## Common Commands

```bash
# Development
pip install -r requirements.txt
fastapi dev app/main.py                    # Dev server with hot reload

# Docker (preferred for full stack with DB)
docker-compose up -d --build               # Start API + PostgreSQL
docker-compose logs -f                     # Tail logs

# Testing
pytest                                     # Full suite with coverage
pytest tests/test_guardrails.py -v         # Single file
pytest tests/test_api.py::test_chat -v     # Single test

# Linting
ruff check .
```

## Architecture

**Backend (FastAPI, async):** Routes are split into APIRouter modules under `app/routers/`. The app uses dependency injection for services and background tasks for non-blocking DB writes.

**Request flow:** Client → RateLimitMiddleware (per-IP) → endpoint → GuardrailsService.validate() → GeminiService.generate_response() → save logs via BackgroundTasks → return ChatResponse.

**Key modules:**
- `app/main.py` — App creation, lifespan, middleware setup, router inclusion, static file mount, exception handler
- `app/routers/chat.py` — `/chat` and `/chat/stream` (SSE) endpoints, `get_client_ip` helper
- `app/routers/analytics.py` — `/metrics` and `/analytics` endpoints, HTML dashboard generator
- `app/routers/health.py` — `/health` endpoint
- `app/services/gemini.py` — Gemini API client (sync + streaming). Singleton pattern.
- `app/services/guardrails.py` — Input validation: length check + blocked keyword regex
- `app/middleware/rate_limit.py` — Sliding window rate limiter with pluggable backends (in-memory default, Redis optional)
- `app/middleware/logging.py` — Async DB logging with truncation
- `app/core/config.py` — Pydantic Settings, all config via env vars
- `app/core/database.py` — SQLAlchemy async engine + session factory
- `app/models/log.py` — SQLModel tables: `RequestLog`, `GuardrailLog`
- `app/models/schemas.py` — Pydantic request/response models

**Frontend:** Static files in `static/` served by FastAPI's StaticFiles mount. Vanilla JS with localStorage for chat history. Uses SSE for streaming responses. CDN dependencies (Marked.js, DOMPurify, Chart.js, Stoplight Elements).

**Database:** PostgreSQL 17 with async driver (asyncpg). Tables auto-created on startup via `SQLModel.metadata.create_all()`. No migration tool — schema changes require manual handling.

## Testing

Tests use `pytest-asyncio` with `asyncio_mode = auto`. The test client overrides DB session and Gemini service with mocks defined in `tests/conftest.py`. Rate limit tests mock the store directly. A random IP is injected per test to avoid rate limit interference between tests.

## Environment

Required: `GEMINI_API_KEY`, `DATABASE_URL` (defaults to docker-compose PostgreSQL). See `.env.example` for template. Optional: `REDIS_URL` for distributed rate limiting.

## Deployment

- **Docker Compose:** API + PostgreSQL (Redis commented out)
- **Heroku:** `Procfile` + `runtime.txt` (Python 3.12.3, Gunicorn + Uvicorn workers)
- **CI:** GitHub Actions runs Ruff lint + pytest against PostgreSQL 17 service

## Custom Slash Commands

- `/improve` — Find and implement one high-impact code quality improvement
- `/security-audit` — Full security audit with severity ratings and fixes
- `/deploy-check` — Verify deployment readiness (tests, lint, config, secrets)
- `/polish-loop` — Iterative improvement loop: find issue → fix → test → commit

## Self-Modification Rules

**This file must stay accurate.** When you make changes that affect the architecture, module structure, endpoints, or deployment setup described above, update the relevant sections of this CLAUDE.md in the same commit. Examples:
- Split `main.py` into routers → update Architecture section
- Add new endpoint → update the endpoint list
- Add new environment variable → update Environment section
- Change deployment target → update Deployment section
- Add new test patterns → update Testing section

Do not add noise — only update when the existing documentation would mislead a future reader.
