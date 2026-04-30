# Security Policy

## Supported Versions

This project follows the latest commit on `main`. Security fixes are applied to `main` only.

## Reporting a Vulnerability

If you find a security issue, **please do not open a public GitHub issue.** Instead, email the maintainer at the address listed in the repo's git history (most recent commit author), or open a private security advisory through the GitHub UI ("Security" tab → "Report a vulnerability").

When reporting, please include:

- A description of the issue and its impact.
- Steps to reproduce, or a proof-of-concept.
- Affected component (router, middleware, frontend, deployment manifest, etc.).
- Whether you have a suggested fix.

You can expect an acknowledgement within a few business days. Severity and remediation timeline depend on the report — credentials/RCE-class issues get priority.

## Hardening Notes for Operators

- **Set `ADMIN_API_KEY` and `API_KEY` separately.** Admin-only routes (`/analytics`, `/metrics`, `/docs`) require `ADMIN_API_KEY`; there is no fallback to `API_KEY`. If you only set `API_KEY`, admin routes will return 503.
- **Always set `HASH_SALT` in production.** Outside `ENVIRONMENT=development` the app refuses to start without one.
- **Always set `DATABASE_URL` in production.** Same gating as `HASH_SALT`.
- **CSP:** the app ships a moderate CSP with `'unsafe-inline'` on script and style. If you add a reverse proxy, do not weaken it further.
- **SRI:** all CDN-hosted scripts and stylesheets carry `integrity=` hashes. If you upgrade a CDN dependency, regenerate the hash with `curl … | openssl dgst -sha384 -binary | openssl base64 -A`.
- **Rate limit + body-size middleware** are enabled by default. Keep them on.
