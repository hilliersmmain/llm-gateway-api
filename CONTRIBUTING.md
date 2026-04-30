# Contributing

Thanks for considering a contribution. This is a small project — keep PRs focused.

## Development Setup

```bash
pip install -r requirements-dev.txt
cp .env.example .env  # then edit values
fastapi dev app/main.py
```

For full-stack with PostgreSQL:

```bash
docker-compose up -d --build
```

## Required Checks Before Opening a PR

```bash
pytest                # full suite, must pass with coverage ≥ 85%
ruff check .          # lint
mypy app              # type-check
```

CI runs the same three checks against PostgreSQL 17. Don't bypass hooks (`--no-verify`); fix the underlying issue.

## Commit Messages

Conventional-style, imperative, lowercase subject:

```
feat: add request-id middleware
fix: tighten admin-key auth
chore: pin requirements.txt
```

Group related changes in a single commit. Avoid drive-by changes outside the scope of the PR.

## Architectural Conventions

- Routes live under `app/routers/`, one router per topic.
- Services live under `app/services/` and are injected, not imported transitively.
- Middleware lives under `app/middleware/`.
- DB models go in `app/models/log.py`; Pydantic schemas in `app/models/schemas.py`.
- Anything that needs config goes through `app.core.config.get_settings()`; never read `os.environ` directly in app code.
- Background DB writes use FastAPI's `BackgroundTasks`.

## Adding a Dependency

- Add to `requirements.txt` (runtime) or `requirements-dev.txt` (test/lint).
- Pin to an exact version.
- Run `pip-audit -r requirements.txt` locally before pushing.

## Updating CDN Assets

When bumping a CDN script/stylesheet version, regenerate its SRI hash:

```bash
curl -sSL <url> | openssl dgst -sha384 -binary | openssl base64 -A
```

Update both the URL and the `integrity=` attribute in the same commit.
