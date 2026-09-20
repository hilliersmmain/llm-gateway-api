In `~/Projects/llm-gateway-api`, make `alembic check` pass. It currently fails, and it fails
on GitHub Actions too — this is a real, long-standing red step, not something a local
session broke.

## The failure

GitHub Actions run `25161331154` on `main` (2026-04-30, the merge of PR #8) failed on
exactly one step, `Check for schema drift`; every other step in that run passed. Locally,
with the pinned dependencies installed exactly as `requirements.txt` specifies
(sqlmodel 0.0.38, alembic 1.18.4, both confirmed 2026-09-20), the run reports eight columns
drifting:

```
INFO  [alembic.autogenerate.compare.types] Detected type change from TEXT() to AutoString() on 'guardrail_logs.input_prompt'
INFO  [alembic.autogenerate.compare.types] Detected type change from TEXT() to AutoString() on 'guardrail_logs.blocked_keyword'
INFO  [alembic.autogenerate.compare.types] Detected type change from TEXT() to AutoString() on 'guardrail_logs.violation_type'
INFO  [alembic.autogenerate.compare.types] Detected type change from TEXT() to AutoString() on 'guardrail_logs.client_ip'
INFO  [alembic.autogenerate.compare.types] Detected type change from TEXT() to AutoString() on 'request_logs.input_prompt'
INFO  [alembic.autogenerate.compare.types] Detected type change from TEXT() to AutoString() on 'request_logs.output_response'
INFO  [alembic.autogenerate.compare.types] Detected type change from TEXT() to AutoString() on 'request_logs.status'
INFO  [alembic.autogenerate.compare.types] Detected type change from TEXT() to AutoString() on 'request_logs.error_message'
FAILED: New upgrade operations detected: [[('modify_type', None, 'guardrail_logs', 'input_prompt', ... TEXT(), AutoString())], ...]
```

## Where the two halves disagree

The migration declares `sa.Text()`. `alembic/versions/0001_initial_schema.py` lines 22-46:

```python
def upgrade() -> None:
    op.create_table(
        "request_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("input_prompt", sa.Text(), nullable=False),
        sa.Column("output_response", sa.Text(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="success"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "guardrail_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("input_prompt", sa.Text(), nullable=False),
        sa.Column("blocked_keyword", sa.Text(), nullable=True),
        sa.Column("violation_type", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("client_ip", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
```

The models declare bare `str`, which SQLModel resolves to its own `AutoString`.
`app/models/log.py` lines 13-21 and 29-41 — the eight drifting columns are exactly the
plain-`str` ones, e.g.:

```python
    input_prompt: str
    output_response: str
    ...
    status: str = Field(default="success")
    error_message: str | None = Field(default=None)
```

`alembic/env.py:22` sets `target_metadata = SQLModel.metadata`, so autogenerate compares
the live PostgreSQL schema against what those model classes produce.

## Decide which side to change

Two defensible routes. Pick one, and write the reason into the commit message:

1. **Amend the model types** so SQLModel emits `Text` for those eight columns, matching the
   migration and the live database. Nothing in the database changes; no new migration.
2. **Add a new Alembic migration** that converts the eight columns to whatever the models
   actually resolve to, leaving the models alone.

Route 1 is the smaller change and leaves the database untouched, but the exact SQLModel API
matters — whether sqlmodel 0.0.38 wants `Field(sa_type=Text)`, `Field(sa_column=Column(Text,
...))`, or something else, and how that interacts with `nullable` and `default`. **Look it
up with `context7` against sqlmodel 0.0.38; do not write it from memory.** Watch out that
`sa_column` and `Field(default=...)`/`nullable` can conflict.

Route 2 is more machinery and means a second migration file in a repo that currently has
exactly one, `0001_initial_schema.py`. If you take it, `request_logs.status` carries
`server_default="success"` and `tokens_in`/`tokens_out` carry `server_default="0"` — a
`modify_type` that drops a server default is a silent behaviour change. Carry them through
and prove they survive.

Either way the goal is the same: `alembic check` exits clean against a database built from
scratch by the migrations, not against one that happens to be in the right state already.

## Prove it against a fresh database

Do not drop or rebuild `llm_gateway` — create a second database inside the container that
is already running, so nothing local is destroyed:

```bash
podman start llm-gateway-db
podman exec llm-gateway-db pg_isready -U user -d llm_gateway
podman exec llm-gateway-db psql -U user -d postgres -c 'CREATE DATABASE llm_gateway_probe'
```

Alembic takes its URL from `Settings`, not from `alembic.ini` — `alembic/env.py:29` reads
`get_settings().database_url` and rewrites `+asyncpg` to `+psycopg2`, and `alembic.ini:92`
leaves `sqlalchemy.url` commented out. A `DATABASE_URL` in the process environment
overrides `.env`, so pointing at the probe database is just:

```bash
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/llm_gateway_probe \
GEMINI_API_KEY=test_key \
.venv/bin/alembic upgrade head

DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/llm_gateway_probe \
GEMINI_API_KEY=test_key \
.venv/bin/alembic check
```

Both must be green: `upgrade head` builds the schema from nothing, and `check` then finds
no drift. Quote the literal output of each. A `check` that passes against the *existing*
`llm_gateway` database proves less, because that database was built before the change.

Drop the probe database when you are done:
`podman exec llm-gateway-db psql -U user -d postgres -c 'DROP DATABASE llm_gateway_probe'`.

Both the `CREATE DATABASE` and `DROP DATABASE` commands above were run on 2026-09-20 and
printed `CREATE DATABASE` / `DROP DATABASE` — the `user` role has createdb rights in that
image, so neither is a guess.

**Then the rest of the gate**, because a model-type change can break mypy or the tests and
CI runs all of them:

```bash
PYTHONDONTWRITEBYTECODE=1 \
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/llm_gateway \
DB_POOL_DISABLED=1 \
.venv/bin/pytest tests/ -q -p no:cacheprovider
.venv/bin/ruff check .
.venv/bin/mypy app
```

`DATABASE_URL` has to be in the process environment of the pytest command or three
integration tests skip silently. The 2026-09-20 baseline: `77 passed`,
`Total coverage: 91.64%` against an 85% gate, `All checks passed!`, and
`Success: no issues found in 23 source files`. Re-run rather than trusting those numbers.

Also confirm the running app still starts and `curl 127.0.0.1:8000/health` returns
`{"status":"healthy","version":"1.0.0"}` — `init_db()` runs `alembic upgrade head` in the
lifespan, so a broken migration surfaces at startup. Stop the dev server by PID — and note
that `fastapi dev` runs a reloader child that can outlive its parent and keep holding port
8000 (seen once on 2026-09-20, not on a second run), so check
`ps -eo pid,args | command grep 'app/main.py'` afterwards and kill anything left. Do not use
`pkill -f` with the command string, which on 2026-09-20 self-matched the Claude Code Bash
wrapper and killed the calling shell.

## Finishing

Update the `CLAUDE.md` "Known broken" entry to say this is fixed — that is a rewrite of an
existing section, so show Sam the diff rather than applying it silently.

Commit locally on `main` with a heredoc-quoted message, `git add` named paths only, and end
the message with:

```
Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
```

**Do not push.** `hilliersmmain/llm-gateway-api` is public and a resume repo; pushing is
outward-facing and needs Sam's say-so. Point out that pushing this is also what turns the
CI run green, so it is worth asking.

When it is done, `git mv Prompts/fix-alembic-check-schema-drift.md Prompts/Archived/` as
part of finishing, and run `/wrap`.
