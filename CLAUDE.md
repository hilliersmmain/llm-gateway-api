# CLAUDE.md — llm-gateway-api

Project rules only. **This file deliberately does not repeat `~/.claude/CLAUDE.md`** — that
file owns the machine, Sam, the safety limits and the toolchain conventions (rootless
podman, fully-qualified image names, `uv` or a venv, never `sudo pip`). `~/CLAUDE.md` owns
the contract every CLAUDE.md on this box obeys. This one owns only this project.

---

## What this is

**LLM Gateway API** — a FastAPI backend that proxies chat requests to Google Gemini 2.5
Flash, with a vanilla JS frontend. Optional API-key auth, rate limiting, input guardrails,
privacy-aware request logging to PostgreSQL, and an analytics dashboard.

## Status

**Public resume repo.** `git remote -v` is authoritative, not this line; it read
`https://github.com/hilliersmmain/llm-gateway-api.git` (HTTPS, the house default) on
2026-09-20, branch `main`.

**It is NOT archived on GitHub** — verified 2026-09-20, `gh repo view --json isArchived`
→ `false`; also public, MIT. Sam believed it was archived. Re-check if it matters.

**Pushing is outward-facing and needs Sam's say-so.** Commit locally on `main`; never
`git push` unasked. This is the repo a hiring manager reads.

## How work is done here

- **Large plan-mode plans, not `/goal`.** The goal cycle was retired machine-wide
  2026-09-09; the history is `~/.claude/reference/goal-cycle.md`. Nothing in this repo
  should reintroduce a self-improvement loop.
- **`Prompts/` holds the queued jobs** — one runnable job per file, prompt text only (no
  launch command, no status table, no notes: Sam select-alls and pastes). A finished one is
  `git mv`'d to `Prompts/Archived/`, never deleted.
- **`/wrap` unasked** at the end of a substantive session, before compacting.
- **`/code-review xhigh app/`** after a long coding session — `xhigh`, not `max`. Budget
  ~30 minutes and ~350k subagent tokens, and say so before launching.
- **Subagents run on sonnet** unless Sam calls the session heavy.
- **`context7` is the doc source** for FastAPI, SQLModel, Alembic, pydantic-settings and
  the Gemini SDK — the pinned versions in `requirements.txt` are recent, so guessing an API
  from memory is the failure mode here.

---

## Commands

Every command is venv-prefixed: the system interpreter is the wrong Python for this repo.
`runtime.txt` pins `python-3.12.3` and CI runs 3.12; `python3 -V` reports what the system
one actually is, and it is not 3.12. No `sudo` anywhere in this list.

### Setup, once per clone

```bash
uv venv --python 3.12 .venv                                      # uv is ~/.local/bin/uv
uv pip install --python .venv/bin/python -r requirements-dev.txt
```

`.venv/` is the venv path the `.gitignore` already covers. Verified 2026-09-20:
`.venv/bin/python -V` → `Python 3.12.14`.

### Database — rootless podman, not docker-compose

**First time only** (creates the container):

```bash
podman run -d --name llm-gateway-db -p 127.0.0.1:5432:5432 \
  -e POSTGRES_USER=user -e POSTGRES_PASSWORD=password -e POSTGRES_DB=llm_gateway \
  docker.io/library/postgres:17
```

**Every time after** (the container already exists, so re-running `podman run` fails on a
name conflict):

```bash
podman start llm-gateway-db
podman exec llm-gateway-db pg_isready -U user -d llm_gateway   # readiness check
podman stop llm-gateway-db                                      # when done
```

Why it is written that way: rootless `podman` and fully-qualified image names are house
convention (`~/.claude/CLAUDE.md`), and the `docker.io` *package* is sudo-only on this box.
The `127.0.0.1:` prefix binds the published port to loopback explicitly, so the database is
never reachable off-machine even if a firewall rule changes — that is deliberate under this
machine's threat model, not decoration. `docker-compose.yml` still exists and is the
deployment story; it is not how local work is done here.

### Local `.env`

```
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/llm_gateway
GEMINI_API_KEY=test_key
```

**`cp .env.example .env` does NOT work today** — see "Known broken" below. `.env` is
gitignored and must exist: `Settings` sets `env_file=".env"` (`app/core/config.py:68`).

### Migrations, tests, lint, types

```bash
.venv/bin/alembic upgrade head

PYTHONDONTWRITEBYTECODE=1 \
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/llm_gateway \
DB_POOL_DISABLED=1 \
.venv/bin/pytest tests/ -q -p no:cacheprovider

.venv/bin/ruff check .
.venv/bin/mypy app
```

`PYTHONDONTWRITEBYTECODE=1` and `-p no:cacheprovider` keep a verification run from leaving
its own droppings in the tree — house rule, not optional.

**`DATABASE_URL` must be in the *process environment* of the pytest command, not only in
`.env`.** `tests/test_db_integration.py:19` reads `os.getenv("DATABASE_URL", "")` directly,
so without it three integration tests skip silently. Measured 2026-09-20: with it,
`77 passed`; without it, `74 passed, 3 skipped`.

**`DB_POOL_DISABLED=1` goes in the environment of the test command, never in `.env`.** Same
reason — `app/core/database.py:27` reads it with `os.getenv`, and putting it in `.env` is
fatal (below).

### Running the app

```bash
.venv/bin/fastapi dev app/main.py --port 8000
curl 127.0.0.1:8000/health          # -> {"status":"healthy","version":"1.0.0"}
```

`/docs` returns HTTP 200 (verified 2026-09-20).

**Stopping it: Ctrl-C in the foreground.** If it was backgrounded, killing the PID you
recorded may not be enough — `fastapi dev` runs a reloader child that can outlive its
parent and keep holding port 8000. Observed once on 2026-09-20 (parent 79999 killed, child
80001 still served `/health`) and *not* reproduced on a second run, so check rather than
assume: `ps -eo pid,args | command grep 'app/main.py'`, kill anything left, then confirm
with `curl --max-time 3 127.0.0.1:8000/health` that the port is free.

Do **not** use `pkill -f '<command string>'` — on 2026-09-20 that pattern self-matched the
Claude Code Bash wrapper and killed the calling shell (exit 144). `pkill -x` if a name match
is genuinely needed.

### What those commands produced on 2026-09-20 — re-run, don't trust

Volatile numbers, dated on purpose. The stable facts are that the coverage gate is **85%**
(`pytest.ini`, `--cov-fail-under=85`) and that lint and types are expected clean.

| Command | Output |
|---|---|
| `.venv/bin/alembic upgrade head` | `Running upgrade  -> 0001, initial schema` |
| the pytest command above | `77 passed, 2 warnings in 5.18s`; `Required test coverage of 85% reached. Total coverage: 91.64%` |
| `.venv/bin/ruff check .` | `All checks passed!` |
| `.venv/bin/mypy app` | `Success: no issues found in 23 source files` |
| `podman exec llm-gateway-db pg_isready -U user -d llm_gateway` | `/var/run/postgresql:5432 - accepting connections` |
| `git status --short` after all of the above | empty |

---

## Known broken — pre-existing, deliberately not fixed

Both are queued as `Prompts/` jobs. Neither was caused by a recent session; a session that
trips over one has not broken anything.

**1. `.env.example:47` makes a fresh `.env` fatal.** `cp .env.example .env` and the app
refuses to start:

```
pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings
db_pool_disabled
  Extra inputs are not permitted [type=extra_forbidden, input_value='0', input_type=str]
```

`DB_POOL_DISABLED` is not a `Settings` field — it is read by `os.getenv` at
`app/core/database.py:27`. `Settings` inherits pydantic-settings' `BaseSettings` default of
`extra="forbid"` (nothing in `app/core/config.py:67-71` sets `extra` either way), and the
dotenv source feeds it *every* key in the file. So an unknown key in `.env` is fatal while
the same key as a process env var is harmless. CI passes it as a workflow env var
(`.github/workflows/ci.yml:50`), which is why CI never caught it. All 24 `Settings` fields
were compared against `.env.example` on 2026-09-20; `DB_POOL_DISABLED` is the only offender.
`README.md:87` and `CONTRIBUTING.md:9` both tell a new contributor to run `cp .env.example
.env`, so this hits every clone. Fix queued:
`Prompts/fix-env-example-db-pool-disabled.md`.

Second, smaller reason not to copy it verbatim: `.env.example:6` points `DATABASE_URL` at
host `db` with password `change_me`, which is the docker-compose shape, not the local
podman one.

**2. `alembic check` FAILS, and it fails on GitHub too.** Not a local artefact. GitHub
Actions run `25161331154` on `main` (2026-04-30, the merge of PR #8) failed on exactly one
step, `Check for schema drift`; everything else in that run passed. Locally it reports 8
columns drifting `TEXT()` → `AutoString()` across `guardrail_logs` and `request_logs`: the
migration at `alembic/versions/0001_initial_schema.py:26-44` declares `sa.Text()` while the
SQLModel models in `app/models/log.py` resolve to SQLModel's `AutoString`. Pinned versions
are installed exactly as `requirements.txt` specifies (sqlmodel 0.0.38, alembic 1.18.4).
Verified 2026-09-20. Fix queued: `Prompts/fix-alembic-check-schema-drift.md`.

---

## Architecture

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

## Testing

Tests use `pytest-asyncio` with `asyncio_mode = auto`. The test client overrides DB session
and Gemini service with mocks defined in `tests/conftest.py`. Rate limit tests mock the
store directly. A random IP is injected per test to avoid rate limit interference between
tests. `tests/test_db_integration.py` is the exception: it talks to a real PostgreSQL and
skips itself unless `DATABASE_URL` is in the process environment (see the pytest command
above).

## Environment

Required: `GEMINI_API_KEY`. Required outside `ENVIRONMENT=development` (startup fails
without them): `DATABASE_URL`, `HASH_SALT`. If `protected_paths` is true, admin routes also
require `ADMIN_API_KEY` to be set independently — there is **no fallback** to `API_KEY`.
Optional: `PROTECTED_PATHS`, `API_KEY`, `ALLOWED_ORIGINS`, `REDIS_URL`, `LOG_RAW_CONTENT`,
`LOG_RETENTION_DAYS`, `GEMINI_TIMEOUT_SECONDS`, `GEMINI_RETRY_ATTEMPTS`,
`MAX_REQUEST_BODY_BYTES`. CI/test only: `DB_POOL_DISABLED=1` disables the asyncpg connection
pool (uses `NullPool`) so pytest-asyncio and Starlette's `TestClient` don't collide across
asyncio loops — **process environment only, never in `.env`**. See `.env.example`, and the
"Known broken" warning about copying it.

## Deployment

- **Docker Compose:** API + PostgreSQL (Redis commented out). `podman-compose` 1.5.0 is
  installed here if it is ever needed; local work uses the plain `podman run` above.
- **Heroku:** `Procfile` + `runtime.txt` (Python 3.12.3, Gunicorn + Uvicorn workers)
- **CI** (`.github/workflows/ci.yml`): migrations → pytest with the coverage threshold →
  Ruff lint → mypy → `pip-audit` (`continue-on-error: true`, so it never blocks) →
  `alembic check`. That last step is the one that is currently red — see "Known broken".

## Custom slash commands

`.claude/commands/`, project-scoped. There is no `.claude/settings.json` here and no hooks;
don't create either without asking.

- `/deploy-check` — report-only deployment-readiness check. Reports; does not fix.
- `/security-audit` — report-only security review with severity ratings. Reports; does not fix.

`/improve` and `/polish-loop` were **deleted 2026-09-20**: both were artefacts of the retired
`/goal` self-improvement loop, and both instructed a session to edit this CLAUDE.md and
commit unprompted, which the contract in `~/CLAUDE.md` forbids. `/polish-loop` also required
Playwright MCP, which is not enabled here — read `~/.claude/settings.json` rather than
trusting this line. Plan-mode plans, `/code-review xhigh` and `/wrap` replace them.

## Maintenance

The contract for this file lives in `~/CLAUDE.md`, which loads in every session under the
home directory: **nothing appends to a CLAUDE.md automatically**, rewriting one is a
separate approval from Sam, rules live here while stories live in `~/.claude/reference/` or
the memory store, and a line states a stable fact or a pointer rather than a volatile value.

When a change makes a section above misleading, raise it as a numbered diff at `/wrap` and
let Sam decide. **Do not silently rewrite this file in the same commit as a code change** —
that is what the old "Self-Modification Rules" section told sessions to do, and it claimed a
looser rule than the contract allows. Removed 2026-09-20.
