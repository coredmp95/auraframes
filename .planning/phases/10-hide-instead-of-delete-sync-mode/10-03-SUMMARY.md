---
phase: 10-hide-instead-of-delete-sync-mode
plan: 03
subsystem: api
tags: [sync, execute_plan, exclude_asset, select_asset, delete_asset, rate-limiting, pytest]

requires:
  - phase: 10-01
    provides: live-confirmed exclude_asset batch shape and delete_asset blast radius
  - phase: 10-02
    provides: SyncPlan.to_reshow / to_delete classification
provides:
  - Batch-capable FrameApi.exclude_asset
  - execute_plan(removal_mode='hide'|'delete'|'hard_delete') with _REMOVAL_PRIMITIVE
  - An always-runs re-show loop and ExecutionResult.reshow_succeeded/reshow_failures
affects: [10-04]

actuals:
  tokens: 7400
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "One dict maps mode -> primitive, so the destructive path is unreachable unless named"
    - "Budget cost is a per-mode function of the chunk, not a constant"

key-files:
  created: []
  modified:
    - auraframes/api/frameApi.py
    - auraframes/sync.py
    - tests/test_execute_plan.py
    - tests/test_execute_plan_budget_geo.py
    - tests/test_write_throttling.py

key-decisions:
  - "Legacy tests that fake remove_asset are pinned to removal_mode='delete' rather than rewritten, keeping their original intent"
  - "Re-show runs before removals so an interrupted run leaves the least destructive partial state"

patterns-established:
  - "New write loops reuse the existing throttle/budget/consecutive-failure closures verbatim"

requirements-completed: [HIDE-03, HIDE-04, HIDE-08]

coverage:
  - id: D1
    description: "removal_mode selects exactly one primitive and leaves the other two untouched"
    requirement: "HIDE-03"
    verification:
      - kind: unit
        ref: "tests/test_execute_plan.py::test_hide_mode_excludes_and_never_removes_or_deletes (+ delete/hard_delete siblings)"
        status: pass
    human_judgment: false
  - id: D2
    description: "The re-show loop runs under every removal mode and precedes removals"
    requirement: "HIDE-04"
    verification:
      - kind: unit
        ref: "tests/test_execute_plan.py::test_reshow_loop_runs_under_every_removal_mode, ::test_reshow_precedes_removal"
        status: pass
    human_judgment: false
  - id: D3
    description: "hard_delete charges the write budget per asset; batch modes charge per chunk"
    requirement: "HIDE-03"
    verification:
      - kind: unit
        ref: "tests/test_execute_plan_budget_geo.py::test_hard_delete_acquires_one_token_per_asset_not_per_chunk"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-08-25
status: complete
---

# Phase 10 / Plan 03: Three-tier removal + re-show at the engine layer — Summary

**`execute_plan` now hides by default, re-shows restored photos under every mode, and can only reach the irreversible primitive if a caller names it.**

## Performance

- **Duration:** ~25 min
- **Tasks:** 3 of 3
- **Files modified:** 5

## Accomplishments

- `FrameApi.exclude_asset` widened to a batch endpoint mirroring `remove_asset`, keeping the deliberate no-`.json` path (documented so it isn't "fixed" later).
- `execute_plan(removal_mode=…)` selects one of three primitives via `_REMOVAL_PRIMITIVE`, defaulting to `'hide'`. The destructive tier stays unreachable unless named.
- An always-runs re-show loop calls `select_asset` on `plan.to_reshow` before removals, with `ExecutionResult.reshow_succeeded` / `reshow_failures`.
- Budget accounting is per-mode: `hard_delete` charges `len(chunk)` because `delete_asset` has no batch form; charging 1 would let a hard delete run the budget dry and re-trip the anti-abuse lockout.
- 13 new offline tests. Full suite: 196 passed.

## Task Commits

1. **Task 1: batch exclude_asset** — `65f9b0e` (feat)
2. **Task 2/3: removal_mode + re-show** — `4c8f5b8` (test, RED) → `6c62338` (feat, GREEN)

## Decisions Made

- **Legacy tests pinned rather than rewritten.** Eight existing tests asserted removal behavior through `remove_asset`, which stopped being the default. Those whose fakes/overrides target `remove_asset` specifically now pass `removal_mode='delete'`, preserving exactly what they were written to check; the rest just needed the `exclude_asset` route added to the offline router.
- **Re-show precedes removal.** If a budget stop or lockout ends a run part-way, the photos the user wants back are already restored and nothing has been removed yet.

## Deviations from Plan

### 1. [Test-harness gap] Offline router had no `exclude_asset` route

- **Found during:** Task 2, first GREEN run.
- **Issue:** With `hide` as the default, 8 legacy tests routed their removal call to an unmocked `/exclude_asset` and 404'd.
- **Fix:** Added `EXCLUDE_ASSET_PATH` to `_default_overrides()` in both execute-plan test modules; pinned the 4 tests that specifically fake `remove_asset` to `removal_mode='delete'`.
- **Verification:** `uv run pytest` → 196 passed.
- **Committed in:** `6c62338`

**Total deviations:** 1 (test-harness only, no production behavior change)
**Impact on plan:** None on scope.

## Issues Encountered

- `tests/test_read_path.py::test_read_03_pagination` still fails — the pre-existing live `num_assets` mismatch logged in STATE.md. Unrelated to this plan.

## Next Phase Readiness

Plan 10-04 can surface this at the CLI: a `--removal-mode`/`--hard-delete` flag mapping to `removal_mode`, plan output that reports re-shows and already-hidden counts, and the escalated confirmation gate before `hard_delete` ever touches real photos (T-10-07).
