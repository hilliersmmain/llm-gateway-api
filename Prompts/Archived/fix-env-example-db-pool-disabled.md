In `~/Projects/llm-gateway-api`, fix `.env.example` so that a fresh `cp .env.example .env`
no longer makes the app refuse to start.

## The bug

`cp .env.example .env` and then constructing `Settings` dies with:

```
pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings
db_pool_disabled
  Extra inputs are not permitted [type=extra_forbidden, input_value='0', input_type=str]
```

Verified 2026-09-20. `README.md:87` and `CONTRIBUTING.md:9` both tell a new contributor to
run exactly that, so this breaks every clone.

## The cause, already traced — confirm it, don't re-derive it from scratch

`.env.example` lines 44-48 currently read:

```
# Testing / CI: disable the asyncpg connection pool to prevent cross-loop errors
# when pytest-asyncio and Starlette's TestClient run in separate asyncio loops.
# Set to "1" in CI; leave unset (or "0") in production.
DB_POOL_DISABLED=0

```

`DB_POOL_DISABLED` is **not** a `Settings` field. It is read directly from the process
environment at `app/core/database.py:27`:

```python
_pool_disabled = os.getenv("DB_POOL_DISABLED", "").lower() in ("1", "true", "yes")
```

`Settings` (in `app/core/config.py`) declares 24 fields and sets its config at lines 67-71:

```python
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
```

Note that **nothing there sets `extra=`** — the rejection comes from pydantic-settings'
`BaseSettings` default of `extra="forbid"`. Its dotenv source feeds *every* key in the file
to `Settings`, so an unknown key in `.env` is fatal, while the same key as a process env var
is invisible to `Settings` and harmless. That asymmetry is why CI never caught it: the
workflow passes it as a step env var at `.github/workflows/ci.yml:50`
(`DB_POOL_DISABLED: "1"`), not through a dotenv file.

All 24 `Settings` fields were compared against `.env.example` on 2026-09-20 and
`DB_POOL_DISABLED` is the only offender. Re-run that comparison yourself before changing
anything, so the fix is not built on my word.

Be aware the line was added deliberately: commit `ed354ae` ("docs: add DB_POOL_DISABLED to
.env.example and CLAUDE.md environment section", 2026-04-30, by the copilot-swe-agent bot)
added this 5-line block. This fix reverses an intentional change, so the replacement must
keep the *information* that block was carrying.

## Decide the approach, then do it

Three options. Pick one and say why in the commit message:

1. **Minimal (preferred unless you find a reason otherwise):** remove the
   `DB_POOL_DISABLED=0` assignment from `.env.example` and rewrite the surrounding comment
   so it still tells a reader the variable exists, what it does, and that it belongs in the
   *process environment of the test command* — never in `.env`, where it is fatal.
2. Add `extra="ignore"` to `SettingsConfigDict` in `app/core/config.py`. This makes `.env`
   tolerant of any unknown key, which also silently swallows typos in real setting names.
   Weigh that.
3. Promote `db_pool_disabled` to a real `Settings` field and have `app/core/database.py:27`
   read `get_settings().db_pool_disabled` instead of `os.getenv`. Note that
   `app/core/database.py` builds the engine at import time from a module-level
   `settings = get_settings()`, so check what this does to import order and to the tests
   before choosing it.

## Prove it — two layers, both required

Do the work in the repo's existing `.venv` (Python 3.12). Start the database first with
`podman start llm-gateway-db` and confirm
`podman exec llm-gateway-db pg_isready -U user -d llm_gateway` prints
`/var/run/postgresql:5432 - accepting connections`.

**Layer 1 — the example file itself validates.** Copy the fixed `.env.example` to a scratch
path and construct `Settings` against it explicitly, without disturbing the repo's real
`.env`:

```bash
cp .env.example /tmp/probe.env
.venv/bin/python -c "
from app.core.config import Settings
Settings(_env_file='/tmp/probe.env')
print('probe LOADED OK')
"
```

That must print `probe LOADED OK`. Verified 2026-09-20 that this same command reproduces
the current failure, so it is a real falsification test and not a no-op.

**Layer 2 — the app actually boots from a probe env.** The fixed `.env.example` still can't
be used verbatim against the local database: line 6 points `DATABASE_URL` at host `db` with
password `change_me`, which is the docker-compose shape. So rewrite that one line in the
probe copy and boot the app against it, **from the repo root** — `app/main.py:144` mounts
`StaticFiles(directory="static", ...)` by relative path, so a different cwd fails at mount:

```bash
sed -i 's#^DATABASE_URL=.*#DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/llm_gateway#' /tmp/probe.env
.venv/bin/dotenv -f /tmp/probe.env run -- .venv/bin/fastapi dev app/main.py --port 8000
```

Use `.venv/bin/dotenv` (python-dotenv 1.2.2 is pinned, and its CLI is present in the venv —
checked 2026-09-20). **Do not** use `set -a; . /tmp/probe.env; set +a`: bash strips the
quotes, so `ALLOWED_ORIGINS=["http://localhost:8000","http://127.0.0.1:8000"]` reaches the
process as `[http://localhost:8000,http://127.0.0.1:8000]` — invalid JSON. Verified
2026-09-20, and `BLOCKED_KEYWORDS` mangles the same way. Pydantic's JSON parse of those two
then fails and you chase a phantom that has nothing to do with this bug. `dotenv run` puts the values
in the process environment, which pydantic-settings ranks above the repo's own `.env`, so
nothing in the tree is touched.

Startup runs `alembic upgrade head` in the lifespan, so this exercises a real connection.
Confirm `curl 127.0.0.1:8000/health` returns `{"status":"healthy","version":"1.0.0"}`. This
whole sequence was proved end to end on 2026-09-20 against the *current* example with line
47 simply deleted, so it is a working recipe, not a guess.

**Stop the dev server by PID, and check for a survivor.** `fastapi dev` runs a reloader
child that can outlive its parent and keep holding port 8000 — seen once on 2026-09-20 and
not on a second run, so check rather than assume. After killing the PID you recorded, run
`ps -eo pid,args | command grep 'app/main.py'`, kill anything left, then confirm the port is
free. Do not use `pkill -f` with the command string: on 2026-09-20 that self-matched the
Claude Code Bash wrapper and killed the calling shell.

**Then the full gate**, because a change to `config.py` (options 2 and 3) can break types or
tests:

```bash
PYTHONDONTWRITEBYTECODE=1 \
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/llm_gateway \
DB_POOL_DISABLED=1 \
.venv/bin/pytest tests/ -q -p no:cacheprovider
.venv/bin/ruff check .
.venv/bin/mypy app
```

`DATABASE_URL` must be in the process environment of the pytest command — three integration
tests in `tests/test_db_integration.py` read `os.getenv("DATABASE_URL", "")` directly and
skip without it. The 2026-09-20 baseline is `77 passed` with it, `74 passed, 3 skipped`
without. Ruff and mypy were both clean.

Ignore the `alembic check` failure if you happen to run it — it is pre-existing, red on CI
too, and has its own prompt file.

## Finishing

Update `README.md` and `CONTRIBUTING.md` if the fix changes what a new contributor should
do. Update the `CLAUDE.md` "Known broken" entry to say it is fixed — that is a rewrite of an
existing section, so show the maintainer the diff rather than applying it silently.

Commit locally on `main` with a heredoc-quoted message, `git add` named paths only, and end
the message with:

```
Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
```

**Do not push.** `hilliersmmain/llm-gateway-api` is public and a resume repo; pushing is
outward-facing and needs the maintainer's say-so. Ask, and let them decide.

When it is done, `git mv Prompts/fix-env-example-db-pool-disabled.md Prompts/Archived/` as
part of finishing, and run `/wrap`.
