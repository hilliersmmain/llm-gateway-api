# Architecture

Demoted verbatim from `CLAUDE.md` (lines 180-222) on 2026-09-21.

**Backend (FastAPI, async):** Routes are split into APIRouter modules under `app/routers/`.
The app uses dependency injection for services and background tasks for non-blocking DB
writes.

**Request flow:** Client → body-size/security middleware → RateLimitMiddleware (per-IP) →
endpoint auth (optional) → GuardrailsService.validate() → GeminiService.generate_response()
(async + timeout/retry) → save logs via BackgroundTasks → return ChatResponse.

**Key modules:**
- `app/main.py` — App creation, lifespan, middleware setup, router inclusion, static file mount, exception handler
- `app/routers/chat.py` — `/chat` and `/chat/stream` (SSE) endpoints, `get_client_ip` helper
- `app/routers/analytics.py` — `/metrics` and `/analytics` endpoints, HTML dashboard generator
- `app/routers/health.py` — `/health` endpoint
- `app/services/gemini.py` — Gemini API client (sync + streaming). Singleton pattern.
- `app/services/guardrails.py` — Input validation: length check + blocked keyword regex
- `app/middleware/rate_limit.py` — Sliding window rate limiter with pluggable backends (in-memory default, Redis optional)
- `app/middleware/logging.py` — Async DB logging with truncation
- `app/middleware/request_id.py` — Injects / propagates a unique request identifier
- `app/core/auth.py` — Optional API-key and admin-key auth dependencies
- `app/core/config.py` — Pydantic Settings, all config via env vars
- `app/core/database.py` — SQLAlchemy async engine + session factory
- `app/core/logging_setup.py` — JSON log formatter that includes the current request ID
- `app/models/log.py` — SQLModel tables: `RequestLog`, `GuardrailLog`
- `app/models/schemas.py` — Pydantic request/response models
- `app/privacy.py` — Log sanitization and pseudonymization helpers
- `app/utils.py` — Shared utility functions

(The four middle-column modules `request_id.py`, `logging_setup.py`, `privacy.py` and
`utils.py` were missing from this list before 2026-09-20; re-derive it with
`find app -name '*.py'` rather than trusting the list.)

**Frontend:** Static files in `static/` served by FastAPI's StaticFiles mount. Vanilla JS
with localStorage for chat history. Uses SSE for streaming responses. CDN dependencies
(Marked.js, DOMPurify, Chart.js, Stoplight Elements).

**Database:** PostgreSQL 17 with async driver (asyncpg) at runtime; sync psycopg2 inside
Alembic for migrations. Schema is owned by Alembic — `init_db()` runs `alembic upgrade head`
via `asyncio.to_thread()` on startup. Startup also performs retention cleanup for old
request/guardrail logs based on `LOG_RETENTION_DAYS`. **Alembic takes its URL from
`Settings`, not from `alembic.ini`** — `alembic/env.py:29` reads
`get_settings().database_url` and rewrites `+asyncpg` to `+psycopg2`, and `alembic.ini:92`
leaves `sqlalchemy.url` commented out. A `DATABASE_URL` in the process environment therefore
overrides `.env` for any alembic command, which is how a probe database is targeted.
