# History — 2026-09-20 run log

Demoted verbatim from `CLAUDE.md` on 2026-09-21; each sub-heading below names the original
CLAUDE.md line range it replaces.

## What those commands produced on 2026-09-20 (original lines 142-154)

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

## Known broken — pre-existing, both now fixed (original lines 158-174)

Both are fixed as of 2026-09-20. Neither was caused by a recent session; they are kept here
as a record of what was wrong and where the story lives.

**1. FIXED 2026-09-20.** `.env.example:47` set `DB_POOL_DISABLED=0`, an unknown `Settings`
key that made a fresh `.env` fatal. The assignment is removed; the comment above it says
where the variable belongs. Story: `Prompts/Archived/fix-env-example-db-pool-disabled.md`.
`.env.example:6` still carries the docker-compose `DATABASE_URL`; that was out of scope.

**2. FIXED 2026-09-20.** `alembic check` reported 8 columns drifting `TEXT()` →
`AutoString()` across `guardrail_logs` and `request_logs`: the migration declared
`sa.Text()` while the plain-`str` SQLModel fields resolved to SQLModel's `AutoString`. It
was red on GitHub too (Actions run `25161331154` on `main`, step `Check for schema drift`).
The eight fields in `app/models/log.py` now carry `Field(sa_type=Text)`, so the models match
the migration and the live schema; no DDL and no second migration. Proved green from an
empty database. Story: `git log -1 --grep 'alembic check'`.
