This session runs in `~/Projects/llm-gateway-api`, link 1 of 2 of the llm-gateway-api chain.
Nothing ran before it: `Prompts/` holds only this file, link 2 and `Archived/`. Mode `auto` —
the job edits application code and tests inside one public repo of mine; it touches no boot,
network, encryption or security control, publishes nothing for the first time, edits no
CLAUDE.md and makes no design choice I haven't made. Nobody is watching this tab: don't ask me
anything; where this prompt says stop, stop.

## The job, in my words

This repo has never had a `/code-review xhigh` here. Run one over the application code, fix
every finding the review confirms, keep the suite green, commit, push. Then hand off to link 2,
the security scan, which has to see reviewed code — the scan plugin refuses to patch from a
report that no longer describes the tree, so the review-and-fix lands before the scan, never
after. This is the first of two chains I queued on 2026-09-27 to use the last of a Max window;
the point is a real review with real fixes, not a tidy-up.

## Established facts — use these, don't rediscover them

- HEAD was `3a3cea5` on `main`, tree clean, `main...origin/main` with nothing ahead, when this
  was written on 2026-09-27. `origin` is `https://github.com/hilliersmmain/llm-gateway-api.git`,
  a PUBLIC repo. Re-run `git status --short --branch` yourself before relying on any of that.
- There is no `src/`. The application code is `app/` — 23 source files, 1,711 lines. That is
  the review target; a clean branch with no target reviews an empty diff.
- The `code-review` skill is model-invocable through the Skill tool in this repo (read back
  from a session's skill listing 2026-09-27): "Review the current diff, or a PR
  number/branch/path target ... at the given effort level ... `--fix` to apply the findings to
  the working tree after the review."
- The venv is `.venv/` (Python 3.12 from `uv`; system Python has no wheels for this repo's
  pinned numpy/pandas — don't use it). Measured 2026-09-27:
  `DB_POOL_DISABLED=1 .venv/bin/pytest tests/ -q` → `74 passed, 3 skipped`, coverage 90.58%
  against an 85% floor; `.venv/bin/ruff check .` → `All checks passed!`; `.venv/bin/mypy app`
  → `Success: no issues found in 23 source files`. The 3 skips are integration tests gated on
  an exported `DATABASE_URL`; the Postgres container `llm-gateway-db` (rootless podman) is
  stopped and stays stopped for this job.
- `.venv/bin/alembic check` FAILS locally without that container — expected, not a regression.
  Upstream CI (`.github/workflows/ci.yml`: `pip install -r requirements-dev.txt`, `alembic
  upgrade head`, `pytest tests/ -v`, `ruff check .`, `mypy app`, `pip-audit -r requirements.txt
  --strict`, `alembic check`) passed on `3a3cea5`: run `36326604208`, conclusion `success`,
  2026-09-27. After your push, CI runs again; read its conclusion with
  `gh run list -R hilliersmmain/llm-gateway-api -L 1 --json databaseId,conclusion,headSha`.
- `gh run view --log` returns 0 bytes on this machine's gh 2.46.0. Read a job log with
  `gh api repos/hilliersmmain/llm-gateway-api/actions/jobs/<job-id>/logs`; get the job id from
  `gh run view <run-id> -R hilliersmmain/llm-gateway-api --json jobs -q '.jobs[] | "\(.databaseId) \(.name) \(.conclusion)"'`.
- Link 2 runs with the plugin's own orchestrator agent (`--agent claude-security:claude-security`,
  the `--` passthrough at the end of the chain block below). `cc-dispatch --dry-run` with that
  suffix was read back 2026-09-27: the flag lands before `--model`, as the launcher requires.
  Don't drop or move it.

## The work

1. `git status --short --branch`: clean and not behind. Run the suite, ruff and mypy exactly as
   above and read the counts back. Hard stop if anything is red before you touch code: write
   what you saw, don't fix it, don't hand off.
2. Invoke the `code-review` skill with the argument `xhigh app/`. Its subagents run on sonnet.
   Budget: 30 minutes and roughly 350k subagent tokens (measured here 2026-09-13); if it is
   still running at 45 minutes, let it finish but do no other work meanwhile.
3. Fix every finding the review confirms as a correctness bug, and the reuse/simplification
   items where the change is local and mechanical. Leave alone, and list in the commit body as
   "logged, not fixed": anything that needs a design choice I haven't made, anything touching
   the public API shape, anything outside `app/` and `tests/`. Add or adjust a test for each
   bug fix.
4. Re-run the suite, ruff and mypy. The passed count must not drop below your step-1 number
   and the skip count must not grow; the coverage floor must still be met.
5. Commit with a single-quoted or heredoc message (never backticks inside double quotes).
   `git push`. If it prompts for auth or fails, stop and say so rather than retrying blindly.
6. Confirm the new CI run on your commit reaches `success` with `gh run watch <run-id> -R
   hilliersmmain/llm-gateway-api --exit-status` (give the Bash call a 10-minute timeout, never
   a foreground `sleep` loop). If it fails on a step your change touched, fix and push once
   more; if it fails on `alembic check` or `pip-audit` alone, that is not yours — say so and
   continue.

## Constraints

- `command grep`, never bare `grep`, in any command that decides something.
- Subagents run on sonnet, passed explicitly on every Agent call; scratch files go in this
  session's scratchpad directory, and nothing is written into the repo except the fixes, their
  tests and this file's move.
- Nothing here needs `sudo`, a browser or a hotkey.

## Done means

- `DB_POOL_DISABLED=1 .venv/bin/pytest tests/ -q` exits 0
- `.venv/bin/ruff check .` exits 0
- `.venv/bin/mypy app` exits 0
- **judgement:** every confirmed finding is either fixed with a test or listed as "logged, not
  fixed" with its reason in the commit body
- **judgement:** the CI run for the pushed commit reads `success`, or its only red steps are
  `alembic check` / `pip-audit`
- everything is committed and pushed; this file is `git mv`'d to `Prompts/Archived/`

## Then hand off

1. Run `/wrap` and apply its proposals on your judgement; say in one line what you dropped.
2. `git mv Prompts/01-auto-code-review-xhigh-and-fix-the-findings.md Prompts/Archived/ && git add -A && git commit -m 'link 01: code review xhigh and fixes' && git push`
3. Launch the next link:

```
cc-dispatch --chain --model opus --advisor fable --mode auto \
  --title "llm-gateway-api link 2 of 2: security scan + draft patches" \
  --cwd ~/Projects/llm-gateway-api \
  --check 'DB_POOL_DISABLED=1 .venv/bin/pytest tests/ -q' \
  --check '.venv/bin/ruff check .' \
  --prompt Prompts/02-auto-security-scan-the-repo-and-draft-patches.md \
  -- --agent claude-security:claude-security
```

Show me the line you ran and say the tab is open. Give the clock time and the next link's
expected cost: it is the cost probe for every later scan, authorised for 90 minutes of opus
with a fable advisor. Hard stops — don't launch, say what blocked the chain and stop:
dispatch-session's generic ones; anything under "Done means" unmet; a red suite at any point
after your fixes; a review that never returned findings (an empty result is a finding to
write down, not a reason to re-run).
