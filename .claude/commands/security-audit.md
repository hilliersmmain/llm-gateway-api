Perform a security audit of this codebase. **Report findings only — do not fix them, and do
not commit.** Sam decides what gets changed; an audit that also edits is two jobs, and the
second one was not asked for.

Check for:

1. **Injection** — SQL injection (even through SQLModel/SQLAlchemy), command injection,
   template injection.
2. **XSS** — the frontend in `static/` renders model output; check the sanitization path
   (DOMPurify) and the analytics dashboard's HTML generation in `app/routers/analytics.py`.
3. **CORS** — `allowed_origins` in `app/core/config.py` and how it is applied in
   `app/main.py`.
4. **Secrets exposure** — API keys in code, logs or error responses; anything real in a
   tracked file; `.env` still gitignored.
5. **Rate limiting bypasses** — header spoofing through `get_client_ip`, path exclusion
   gaps, the in-memory vs Redis backends in `app/middleware/rate_limit.py`.
6. **Input validation gaps** — missing length limits, type coercion, regex DoS in
   `app/services/guardrails.py`.
7. **Privacy** — `app/privacy.py` hashing and `LOG_RAW_CONTENT` / `HASH_SALT` handling;
   whether raw prompts can reach the database or the logs unintentionally.
8. **Dependency vulnerabilities** — `uvx pip-audit -r requirements.txt --strict`. Use `uvx`
   so nothing is installed into `.venv`; `pip-audit` is not in `requirements-dev.txt` and CI
   installs it ad hoc with `continue-on-error: true`, so CI is not enforcing this.
9. **Error information leakage** — stack traces, internal paths or config in responses.
10. **Missing security headers** — CSP, X-Frame-Options, HSTS.
11. **Authentication / authorization** — endpoints that should be protected but aren't.
    Note that `ADMIN_API_KEY` has no fallback to `API_KEY` by design.

For each finding report: **Severity** (Critical / High / Medium / Low / Info), **Location**
as `file:line`, **Description**, and a **concrete fix** — written out, not applied.

Present the findings as a table and stop. If Sam wants something fixed he will say so, and
it becomes its own job in `Prompts/`.
