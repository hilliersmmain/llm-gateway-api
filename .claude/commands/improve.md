Analyze the codebase and identify ONE concrete improvement to make. Focus areas (rotate through these):

1. Code quality: split large files, fix inconsistencies, improve type hints, add proper error handling
2. Test coverage: find untested paths, add missing edge cases, improve test isolation
3. Frontend polish: UI/UX improvements, accessibility, responsive design, loading states
4. Security: audit for vulnerabilities (injection, XSS, open CORS, missing auth checks)
5. Performance: unnecessary blocking calls, N+1 queries, missing indexes
6. Documentation: OpenAPI schema accuracy, docstrings on public interfaces

Rules:
- Pick the HIGHEST impact improvement you can find
- Make the change, run tests to verify nothing breaks
- Keep changes focused — one improvement per run
- After making the change, update CLAUDE.md if the architecture section is now outdated
- Commit with a clear, professional commit message

Do NOT:
- Add unnecessary abstractions or over-engineer
- Change things that are already working fine just for style
- Add features — this is about polishing existing code
