Perform a security audit of the codebase. Check for:

1. **Injection vulnerabilities**: SQL injection (even with ORM), command injection, template injection
2. **XSS**: Frontend rendering of untrusted content, missing sanitization
3. **CORS misconfiguration**: Wide-open origins in production
4. **Secrets exposure**: API keys in code, logs, or error responses; .env committed
5. **Rate limiting bypasses**: Header spoofing, path exclusion gaps
6. **Input validation gaps**: Missing length limits, type coercion issues, regex DoS
7. **Dependency vulnerabilities**: Run `pip audit` or check known CVEs
8. **Error information leakage**: Stack traces, internal paths, or config in error responses
9. **Missing security headers**: CSP, X-Frame-Options, HSTS
10. **Authentication/Authorization**: Any endpoints that should be protected but aren't

For each finding:
- Severity: Critical / High / Medium / Low / Info
- Location: file:line
- Description: What's wrong
- Fix: Concrete remediation

Fix any Critical or High severity issues immediately. For Medium/Low, list them as TODOs.
