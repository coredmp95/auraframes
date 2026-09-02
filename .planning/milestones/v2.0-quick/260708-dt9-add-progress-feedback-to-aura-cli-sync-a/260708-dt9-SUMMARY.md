---
phase: quick-260708-dt9
plan: 01
subsystem: cli
tags: [tqdm, cli, sync, execute_plan, progress-feedback]

# Dependency graph
requires:
  - phase: 08-03
    provides: run_sync's confirmed --apply path that calls execute_plan() with real S3Client()/SQSClient()
provides:
  - "execute_plan() gains a keyword-only `progress` reporter (no-op default) called once per attempted upload/delete with (kind, identifier, ok)"
  - "run_sync wraps the apply-path execute_plan() call in a tqdm progress bar so a large --apply batch shows live per-item feedback instead of running silently for minutes"
affects: [sync, cli]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Injectable progress-reporter seam (default no-op callable) mirrors the existing sleep= injection pattern on execute_plan, keeping the function offline-testable while giving the CLI a live-feedback hook"

key-files:
  created: []
  modified:
    - auraframes/sync.py
    - auraframes/cli.py
    - tests/test_execute_plan.py
    - tests/test_cli_apply.py

key-decisions:
  - "progress reporter is deliberately NOT called on the RateLimitError abort path — that item never resolves, and the whole batch stops there, so reporter call count always equals attempted-and-resolved items only"
  - "tqdm bar is opened/closed via a `with` block around the execute_plan() call so the existing D-10 success/failure summary prints cleanly after the bar closes, not interleaved with it"

requirements-completed: []

coverage:
  - id: D1
    description: "execute_plan() calls an injected progress reporter exactly once per attempted upload and once per attempted delete, reporting (kind, identifier, ok); never called on the RateLimitError abort path"
    verification:
      - kind: unit
        ref: "tests/test_execute_plan.py#test_execute_plan_reports_progress_per_item"
        status: pass
    human_judgment: false
  - id: D2
    description: "run_sync wires a tqdm-based reporter into execute_plan on the confirmed --apply path so a large batch shows live per-item progress instead of a multi-minute silent gap"
    verification:
      - kind: unit
        ref: "tests/test_cli_apply.py (fake_execute_plan/rate_limited_execute_plan updated to accept progress=; full suite passes)"
        status: pass
    human_judgment: true
    rationale: "Live per-item tqdm bar rendering during a real --apply run cannot be proven by an offline unit test (tests monkeypatch execute_plan itself); confirming the operator actually sees advancing progress on stderr during a real multi-minute apply requires a human to observe a live run."

duration: 5min
completed: 2026-07-08
status: complete
---

# Quick Task 260708-dt9: Progress feedback for aura-cli sync --apply Summary

**Injectable `progress` reporter on `execute_plan` wired to a live tqdm bar in `run_sync`'s --apply path, replacing the multi-minute silent gap during large batches with per-item stderr feedback.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-07-08T10:16:00+02:00 (approx, first task commit 10:16:59+02:00)
- **Completed:** 2026-07-08T10:17:54+02:00
- **Tasks:** 2 completed
- **Files modified:** 4

## Accomplishments
- `execute_plan` now accepts a keyword-only `progress` reporter (no-op default), called once per attempted upload/delete with `(kind, identifier, ok)`, never on the `RateLimitError` abort path (upload calls always precede delete calls, per D-09).
- `run_sync`'s confirmed `--apply` path wraps the `execute_plan()` call in a `tqdm(total=..., desc='Applying', unit='item')` bar; a reporter closure advances the bar and sets a postfix (`kind ok/FAIL identifier`) per item, giving live feedback during a large batch instead of a silent gap between the dry-run plan and the final summary.
- The existing D-10 success/failure summary now prints after the bar closes (moved outside the `with` block) so it isn't interleaved with bar output.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add injectable progress reporter to execute_plan** - `b471189` (feat, tdd)
2. **Task 2: Wire a tqdm progress bar into run_sync's apply path** - `dd92c9e` (feat)

**Plan metadata:** committed separately by the orchestrator (docs commit, not included here per this task's constraints).

## Files Created/Modified
- `auraframes/sync.py` - `execute_plan` gains a keyword-only `progress` reporter (default no-op); called after each upload/delete success/failure, never on the `RateLimitError` abort path.
- `auraframes/cli.py` - Imports `tqdm`; `run_sync`'s apply path opens a `tqdm` bar around the `execute_plan()` call with a reporter closure that advances the bar and sets a per-item postfix; summary printing moved after the `with` block.
- `tests/test_execute_plan.py` - New test `test_execute_plan_reports_progress_per_item` asserts the reporter is called once per attempted item with the right `(kind, identifier, ok)` triples and that all upload entries precede all delete entries.
- `tests/test_cli_apply.py` - `fake_execute_plan` and `rate_limited_execute_plan` fakes updated to accept `progress=None` so `run_sync` passing `progress=` doesn't raise `TypeError`.

## Decisions Made
- Reporter is deliberately not invoked on the `RateLimitError` abort path (matches the plan's `<behavior>` spec exactly) — the batch stops there, so reporter-call count always equals the number of items that actually resolved (succeeded or recorded-failed).
- tqdm writes to stderr, so none of the existing stdout-based (`capsys.readouterr().out`) test assertions needed changes beyond the fake signature update.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None during implementation. One pre-existing, unrelated failure was observed while running the plan's full `<verification>` command (`uv run pytest -q`, unfiltered): `tests/test_read_path.py::test_read_03_pagination` — a `@pytest.mark.live` test that hits the real Aura API — fails against the current live account state. Confirmed via `git stash` that this failure reproduces identically on the pre-dispatch base commit (`9239099`), i.e. it is unrelated to this task's changes. The project's own pytest marker convention is to run the offline suite as `uv run pytest -q -m "not live"`, which is green: `97 passed, 4 deselected`. Logged in `deferred-items.md` in this task's directory; no fix applied here per the deviation-rules scope boundary.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- No blockers. The progress-reporter seam is additive and backward-compatible (no-op default); existing callers of `execute_plan` without `progress=` are unaffected.
- Operators running a large `aura-cli sync --apply` batch will now see a live tqdm bar advance per upload/delete on stderr instead of a silent multi-minute gap.

---
*Quick task: 260708-dt9*
*Completed: 2026-07-08*

## Self-Check: PASSED

All created/modified files found on disk; both task commits (`b471189`, `dd92c9e`) found in `git log`.
