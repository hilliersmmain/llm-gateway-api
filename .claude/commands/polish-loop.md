Run an improvement loop: find and fix issues to make this project more professional and resume-worthy.

For each iteration:
1. Run `ruff check .` and fix any lint issues
2. Run `pytest` to establish baseline — all tests must pass
3. Pick ONE improvement from this priority list:
   - Fix any broken or flaky tests
   - Security issues (CORS, missing validation, error leakage)
   - Code organization (split large files into proper modules/routers)
   - Test coverage for untested code paths
   - Frontend UI/UX polish
   - Better error handling and edge cases
   - OpenAPI documentation accuracy
4. Implement the fix
5. Run tests again to confirm nothing broke
6. **Manual verification (REQUIRED):** Start the app locally and use Playwright MCP to:
   - Navigate to localhost and take a screenshot
   - Verify the UI loads correctly
   - Test core functionality (send a chat message if possible)
   - Check for console errors or broken elements
   - Do a quick stranger test — would a first-time visitor find anything broken or unprofessional?
7. If CLAUDE.md architecture section is outdated, update it
8. Commit with a professional message

Keep each change small and focused. Quality over quantity.
