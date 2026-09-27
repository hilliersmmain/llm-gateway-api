# Security scan cost record — 2026-09-27

This records the cost of one whole-repository security scan (`claude-security` plugin v0.11.0), followed by patch drafting. It is a cost probe for sizing later scans of other repositories, so it holds wall clock, counts and assumptions only. The report and the patch notes are kept outside this repository.

## Wall clock

- Session launched: 2026-09-27T19:59:09Z (`launched_at` in the launcher's status file).
- Scan workflow: 20:01:05Z to about 20:17Z, 939 s (15.7 min) by the workflow's own count.
- Report written and stamped: 20:18Z.
- Patch stage: 20:20Z to 21:01Z, about 41 min, covering one finding (two attempts plus an adversarial pass).
- Keep-copy made and tree confirmed clean: 21:01:33Z.
- **Total, launch to cost record: about 63 min** of the 90-min budget. The record, commit and push took a few minutes more.

## Effort and size

- Effort: `medium`. Whole repository, no scope, focus off (74 tracked files, a small tree).
- Inventory: 3 components scanned and 3 areas deliberately skipped. The completeness check passed.
- Scan workflow, by its own count: 44 agents, 13 researchers (all returned), 10 candidates (9 after de-duplication), 27 panel votes, 507 tool uses.

## Tokens

- **Session total: wall clock only.** The launcher's status file carries no token figure, and the main loop's own usage was not visible.
- Subagent tokens as the harness reported them, for sizing only:
  - Scan workflow: 2,595,651.
  - Patch stage: 417,333 across five agents (two generators, two verifiers, one adversarial reviewer). By role:
    - Generator: 98,353 and 97,277.
    - Verifier: 69,899 and 71,532.
    - Adversarial reviewer: 80,272.
- Patch-stage agent durations: generator 636 s and 487 s, verifier 295 s and 370 s, adversarial reviewer 447 s. That is about 37 min of agent time for one finding.

## Results (counts only)

- Findings that survived verification: **2**. The report's stamp says `verification.status: verified`.
- Patch files written: **0**.
  - 1 finding was declined after two objections within its one allowed revision round.
  - 1 finding was not attempted because the wall-clock budget gate had been reached.
- The report directory has its own `.gitignore` of `*`, and `git status --porcelain` was empty after the run. The full report and patch notes were copied outside the repository.

## Assumptions and stops

1. **Start confirmation.** The scan's fixed start confirmation was answered by the cost acknowledgment in the queued prompt file. The launching user turn named that file as the request. The question was not asked, because the tab was unattended.
2. **Answers the prompt pre-set.** Scope was the whole repository, effort `medium` and patch selection `all`. Focus was off because the tree is small (the recipe's own size rule).
3. **Models.** The scan workflow's agents ran on the model it inherits, which this session does not set. Patch-stage agents were passed `sonnet` explicitly, per the standing subagent-model rule. The plugin's agent definitions say `model: inherit`, so without that they would have run on the main model.
4. **Revision round mechanics.** The recipe resets the scratch clone with `git reset --hard` and `git clean -fd`. Instead, the scratch was removed with the plugin's own script and re-cloned fresh at the same base, because the house rule forbids those two commands on a dirty tree. The result is the same clean starting point.
5. **Test harness in the scratch clones.** The scratch clones used the main checkout's `.venv` as the interpreter, with `DB_POOL_DISABLED=1` and a dummy Gemini key, and no `DATABASE_URL`. That means 3 DB integration tests skipped by design. Baseline was 98 passed and 3 skipped.
6. **Budget gate.** The second finding would start only if the first settled by 21:00Z, leaving room for one full unit (about 20 min) plus wrap-up inside the 90 min. The first settled at 21:00:47Z, so the second was recorded as not attempted.
7. **Launch shape.** The front-desk role file and job recipes were read from disk, because this launch replaced the agent's initial prompt. `/wrap` could not run in this agent and is owed to the next session in this repository.

## Sizing note for the next scans

On this 74-file repository, the `medium` scan alone took about 16 min and about 2.6M subagent tokens. Each patch unit took 10 to 20+ min of wall clock, and more when a revision round runs. A budget sized as scan time plus about 20 min per finding to patch, plus about 10 min of wrap-up, would have let both findings here be attempted. That estimate is derived from this one run's timings. It is not a measured rule.
