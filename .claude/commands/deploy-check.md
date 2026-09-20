Report on this project's deployment readiness. **This is a read-only check — report
findings, do not fix them.** If something is broken, say so and stop; Sam decides what
gets changed.

Run these, from the repo root, and quote the real output of each:

1. **Tests** — `PYTHONDONTWRITEBYTECODE=1 DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/llm_gateway DB_POOL_DISABLED=1 .venv/bin/pytest tests/ -q -p no:cacheprovider`
   The database must be up first: `podman start llm-gateway-db`, then
   `podman exec llm-gateway-db pg_isready -U user -d llm_gateway`. Without `DATABASE_URL` in
   the process environment three integration tests skip silently, so a pass count alone is
   not the check — read the skip count too. The coverage gate is 85% (`pytest.ini`).
2. **Lint** — `.venv/bin/ruff check .`
3. **Types** — `.venv/bin/mypy app`
4. **Schema drift** — `.venv/bin/alembic check`. **This is expected to FAIL** (8 columns,
   `TEXT()` vs `AutoString()`), pre-existing and red on CI too. Report it as a known
   failure, not a new one, unless the output differs from what `CLAUDE.md` describes.
5. **Container image** — `podman build -t llm-gateway-api:local .` builds the `Dockerfile`.
   Not verified on this machine as of 2026-09-20 and a first build is slow; say whether you
   ran it rather than assuming it works.
6. **Environment** — confirm `.env.example` documents every `Settings` field in
   `app/core/config.py`, and flag any key in `.env.example` that is *not* a `Settings`
   field. One such key exists today and is fatal; `CLAUDE.md` names it.
7. **Production config** — debug mode, wide-open CORS, verbose logging that shouldn't ship.
8. **Dependencies pinned** — `requirements.txt` and `requirements-dev.txt`.
9. **Secrets** — nothing real in code, `Dockerfile`, `docker-compose.yml` or any tracked
   file. `.env` is gitignored; confirm it is still untracked with `git check-ignore -v .env`.

Finish with a go/no-go and a list of blockers. Do not commit, do not push, do not edit any
file.
