---
phase: quick-260708-fyr
plan: 01
subsystem: api
tags: [pushd-api, batching, sync, write-path, httpx, pydantic]

# Dependency graph
requires:
  - phase: 08
    provides: select_asset/remove_asset/batch_update single-item fail-loud wrappers, execute_plan's chunk-free per-file upload/delete loop, throttle + ConsecutiveWriteFailureError backstop
provides:
  - "FrameApi.select_asset/remove_asset and AssetApi.batch_update accept a single item OR a list, sending the whole collection in one {\"assets\":[...]} call"
  - "execute_plan() chunks plan.to_upload/to_delete at WRITE_BATCH_SIZE=50 (injectable via batch_size), issuing ONE select_asset + ONE batch_update per upload chunk and ONE remove_asset per delete chunk"
  - "Per-file upload attribution via batch_update's successes[].local_identifier; per-chunk delete attribution (remove_asset returns only a count)"
affects: [sync, cli-apply, write-path-live-verification]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Native-batch API wrapper pattern: accept T | list[T], normalize to a list at the top, send one combined payload -- preserves single-item backward compat with zero call-site churn"
    - "Chunked mutating loop with per-chunk prep/write/attribute phases, reusing the existing throttle()/note_failure() closures unchanged in mechanism"

key-files:
  created: []
  modified:
    - auraframes/api/frameApi.py
    - auraframes/api/assetApi.py
    - auraframes/sync.py
    - tests/test_write_endpoints_failloud.py
    - tests/test_execute_plan.py
    - tests/test_write_throttling.py

key-decisions:
  - "select_asset/remove_asset/batch_update widened to accept T | list[T] rather than adding new *_batch methods -- zero call-site churn for the legacy single-item aura.py callers"
  - "batch_update's len(successes) < len(ids) partial-failure raise removed: a partial successes list is the NORMAL batch-mode signal the caller must attribute per-item, not a whole-call error"
  - "Deletes get coarser per-chunk (not per-file) attribution since remove_asset returns only a failure count, never per-item -- documented tradeoff (T-fyr-01)"
  - "Kept WRITE_THROTTLE_SECONDS and MAX_CONSECUTIVE_WRITE_FAILURES backstop unchanged in mechanism: batching fixes the call-count root cause, throttle/backstop remain a second independent defense layer"

requirements-completed: [SYNC-03, SYNC-04, WRITE-05]

coverage:
  - id: D1
    description: "select_asset/remove_asset/batch_update wrappers accept a single item or a list and send one batched {\"assets\":[...]} call, preserving legacy single-item fail-loud behavior"
    requirement: "WRITE-05"
    verification:
      - kind: unit
        ref: "tests/test_write_endpoints_failloud.py#test_select_asset_accepts_a_list_and_sends_one_batched_call"
        status: pass
      - kind: unit
        ref: "tests/test_write_endpoints_failloud.py#test_remove_asset_accepts_a_list_and_sends_one_batched_call"
        status: pass
      - kind: unit
        ref: "tests/test_write_endpoints_failloud.py#test_batch_update_accepts_a_list_and_does_not_raise_on_partial_successes"
        status: pass
    human_judgment: false
  - id: D2
    description: "execute_plan chunks uploads at WRITE_BATCH_SIZE (injectable), issuing exactly ONE select_asset + ONE batch_update call per chunk instead of ~3 calls per file"
    requirement: "SYNC-03"
    verification:
      - kind: unit
        ref: "tests/test_execute_plan.py#test_execute_plan_happy_path_uploads_and_deletes"
        status: pass
      - kind: unit
        ref: "tests/test_execute_plan.py#test_execute_plan_chunks_uploads_past_batch_size"
        status: pass
    human_judgment: false
  - id: D3
    description: "Per-file upload attribution recovered from batch_update's successes[].local_identifier, correctly splitting a partial response into upload_succeeded/upload_failures by Path"
    requirement: "SYNC-04"
    verification:
      - kind: unit
        ref: "tests/test_execute_plan.py#test_execute_plan_partial_batch_update_splits_upload_succeeded_and_failures"
        status: pass
      - kind: unit
        ref: "tests/test_execute_plan.py#test_execute_plan_reports_progress_per_item"
        status: pass
    human_judgment: false
  - id: D4
    description: "D-09 ordering, RateLimitError whole-batch fast-path, and the ConsecutiveWriteFailureError backstop all preserved under the batched flow, including a fixed double-catch bug found during implementation"
    verification:
      - kind: unit
        ref: "tests/test_execute_plan.py#test_execute_plan_all_uploads_precede_all_deletes"
        status: pass
      - kind: unit
        ref: "tests/test_write_throttling.py#test_rate_limited_upload_aborts_whole_batch"
        status: pass
      - kind: unit
        ref: "tests/test_write_throttling.py#test_run_of_plain_401_write_failures_aborts_batch"
        status: pass
      - kind: unit
        ref: "tests/test_write_throttling.py#test_all_files_unacknowledged_in_one_chunk_aborts_without_double_counting"
        status: pass
    human_judgment: false
  - id: D5
    description: "Full offline suite (pytest -m 'not live') green with zero network/AWS access -- no live writes performed, live re-verification explicitly deferred to a separate human-approved step"
    verification:
      - kind: unit
        ref: "python -m pytest -m 'not live' -q (108 passed, 4 deselected)"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-07-08
status: complete
---

# Quick Task 260708-fyr: Batch refactor of sync --apply write path Summary

**Collapsed the sync --apply write path's ~3N per-file Pushd calls (2x select_asset + 1x batch_update per file) to ~2 calls per WRITE_BATCH_SIZE=50-file chunk, matching the official Aura app's native batch endpoints, with per-file attribution recovered from batch_update's partial `successes` response.**

## Performance

- **Duration:** ~25 min
- **Tasks:** 3 planned tasks (executed as 2 commits per the plan-checker's flagged TDD-ordering note: Task 1 standalone, Task 2+Task 3 interleaved as one RED-then-GREEN cycle)
- **Files modified:** 5 (2 source, 3 test)

## Accomplishments

- `FrameApi.select_asset`/`remove_asset` and `AssetApi.batch_update` widened to accept a single item OR a list, sending the whole collection in one `{"assets":[...]}` payload — the root-cause fix for the ~3N Pushd write-call inflation that originally tripped the anti-abuse lockout (see `.planning/debug/resolved/select-asset-401-unauthorized.md`). Legacy single-item callers (`aura.py`'s `upload_image`) are untouched.
- `batch_update`'s partial-failure raise (`len(successes) < len(ids)`) removed: a partial `successes` list is now the expected batch-mode signal, not a whole-call error — attribution is the caller's job.
- `execute_plan()` rewritten to chunk `plan.to_upload`/`plan.to_delete` at `WRITE_BATCH_SIZE=50` (injectable via `batch_size`). Each upload chunk does per-file S3 prep (unchanged — AWS, not the Pushd anti-abuse surface) followed by exactly ONE `select_asset` + ONE `batch_update` call; per-file success/failure comes from matching each prepped file's `local_identifier` against `batch_update`'s `successes[]`. Each delete chunk issues one `remove_asset` call covering every asset id in the chunk (coarser, per-chunk attribution — `remove_asset` returns only a count).
- Dropped the double `select_asset` call and both per-file SQS polls the old flow carried over from `Aura.upload_image()` (RESEARCH.md Pitfall 4 cargo-cult) — at most one best-effort SQS poll per chunk remains, never gating success.
- D-09 ordering (all uploads before any delete), the `RateLimitError` whole-batch fast-path, and the `ConsecutiveWriteFailureError` backstop are all preserved and re-proven under the batched flow.
- Found and fixed a subtle bug during implementation: `note_failure()` raising `ConsecutiveWriteFailureError` from inside the per-file attribution loop was being re-caught by the sibling whole-chunk-failure `except Exception` branch, double-attributing every prepped file on abort. Added an explicit `except ConsecutiveWriteFailureError: raise` guard plus a regression test.

## Task Commits

Executed per the plan-checker's flagged critical-ordering note (Task 2's old-semantics verify would fail spuriously against Task 3's not-yet-rewritten tests), so Tasks 2+3 were interleaved as one TDD cycle rather than committed separately:

1. **Task 1: Make the Pushd write wrappers accept batches (frameApi + assetApi)** — `af344fa` (feat). Includes Task 3's list-mode coverage for `test_write_endpoints_failloud.py`, added alongside Task 1 per the plan's explicit "your call" note to keep that commit's own verify green without deferring backward-compat proof.
2. **Task 2 + Task 3 (interleaved TDD cycle): Chunk execute_plan into batched writes, with test_execute_plan.py/test_write_throttling.py rewritten to the batched semantics** — `52eaf80` (feat). Tests rewritten to batched semantics first (RED against the old sync.py, confirmed 11 failures), then `sync.py`'s chunked `execute_plan` implemented (GREEN), including the mid-implementation bug fix above.

**Plan metadata:** commit pending (this SUMMARY + STATE.md update, made by the orchestrator per this task's constraints).

## Files Created/Modified

- `auraframes/api/frameApi.py` — `select_asset`/`remove_asset` widened to `AssetPartialId | list[AssetPartialId]`, single-or-list normalization, docstrings updated for native-batch semantics.
- `auraframes/api/assetApi.py` — `batch_update` widened to `Asset | AssetPartial | list[...]`, partial-failure raise removed, docstring updated.
- `auraframes/sync.py` — `WRITE_BATCH_SIZE=50` constant added; `_execute_upload` replaced by `_prep_upload` (per-file S3 prep only) + `_chunked` helper; `execute_plan` rewritten around per-chunk batched writes with a `batch_size` keyword parameter; module docstring and `WRITE_THROTTLE_SECONDS` comment rewritten to describe the batched flow.
- `tests/test_write_endpoints_failloud.py` — added list-mode coverage for `select_asset`/`remove_asset`/`batch_update` proving one batched call and (for `batch_update`) no raise on partial successes.
- `tests/test_execute_plan.py` — rewritten: batched call-count assertions, a PARTIAL batch_update attribution test, a chunk-boundary test (`batch_size=2`), a chunk-level delete-failure test, updated progress/D-09 tests for the batched call shape.
- `tests/test_write_throttling.py` — rewritten: 2-throttles-per-upload-chunk / 1-throttle-per-delete-chunk expectations, updated RateLimitError-abort assertions (S3 prep now precedes select_asset so `s3.upload_calls == []` no longer proves nothing was attempted — `batch_update` call count is asserted instead), updated consecutive-failure-backstop tests (some rechunked at `batch_size=1` to keep per-chunk outcomes independently controllable), and a new regression test for the double-catch bug.

## Decisions Made

- Widened existing methods to accept `T | list[T]` rather than adding new `*_batch` methods — zero call-site churn for `aura.py`'s legacy single-item callers, matching the plan's explicit interface contract.
- `batch_update`'s partial-failure raise removed rather than kept behind a flag — the plan and the batched caller's needs agree that a partial `successes` list is the expected signal, and the sole existing single-item caller (`Aura.upload_image`) already discards the return value, so no behavior change there.
- Deletes get coarser per-chunk attribution (not per-file) — `remove_asset` fundamentally returns only a count, so per-file delete attribution was never possible in batch mode; this is called out explicitly in both the `sync.py` docstring and the threat register (T-fyr-01) rather than silently accepted.
- Task 1's Task-3-owned list-mode tests were added in the Task 1 commit itself (plan gave explicit "your call" latitude) so that commit's own fail-loud coverage was complete without waiting for Task 3.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed a double-catch of `ConsecutiveWriteFailureError` in the batched upload-chunk write path**
- **Found during:** Task 2/3 interleaved implementation, while writing the GREEN-phase `execute_plan` chunking logic
- **Issue:** `note_failure()` can raise `ConsecutiveWriteFailureError` from inside the per-file `batch_update` successes-attribution loop (e.g. a chunk where `batch_update` returns successfully but acknowledges none of the sent files). That loop lives inside the same `try` block whose sibling `except Exception as e:` branch exists to attribute a whole-chunk *Pushd call failure* (a raised exception from `select_asset`/`batch_update` itself). Since `ConsecutiveWriteFailureError` is an `Exception` subclass, the generic branch would re-catch it and re-attribute every already-processed prepped file a second time with the wrong error message, corrupting `result.upload_failures` (produced 6 failures instead of the expected 5 in the regression test below).
- **Fix:** Added an explicit `except ConsecutiveWriteFailureError: raise` clause between the `RateLimitError` and generic `Exception` handlers in the upload-chunk try block, so the intentional abort propagates untouched.
- **Files modified:** `auraframes/sync.py`
- **Verification:** New regression test `tests/test_write_throttling.py::test_all_files_unacknowledged_in_one_chunk_aborts_without_double_counting` reproduces the bug (failed with `count == 6` before the fix) and passes after (`count == 5`, `len(upload_failures) == 5`).
- **Committed in:** `52eaf80` (part of the Task 2+3 commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix, found and resolved during implementation before any commit)
**Impact on plan:** The fix is essential for correctness of the consecutive-failure backstop under the new batched attribution path; no scope creep — it was caught by writing a test for a behavior explicitly required by the plan's `must_haves` ("a single fully-failed chunk... aborts the run early").

## Issues Encountered

None beyond the auto-fixed bug above. The plan-checker's flagged Task 2/Task 3 ordering issue was handled exactly per the constraints' guidance (interleaved TDD cycle, RED confirmed with 11 failing tests against the old `sync.py` before implementing, then GREEN).

## User Setup Required

None — no external service configuration required. This refactor changes only in-process call shape/chunking; no new dependencies, no new env vars.

## Next Phase Readiness

- `pytest -m "not live" -q` is green (108 passed, 4 deselected live tests) with zero network/AWS access.
- The batched write path is fully offline-verified but has **never been exercised live** — live re-verification against a real (recovered/cooled-down) Aura account is explicitly deferred to a separate, human-approved step per the plan's DEFERRED/OUT OF SCOPE note. The account may still be sensitized from the prior `select-asset-401-unauthorized` incident.
- No blockers for that live re-verification step: the offline harness (`offline_aura`, duck-typed S3/SQS fakes) and CLI wiring (`cli.py`'s `run_sync`, unaffected by this refactor's added `batch_size` keyword) are unchanged and ready.

---
*Quick task: 260708-fyr*
*Completed: 2026-07-08*

## Self-Check: PASSED

- FOUND: auraframes/api/frameApi.py
- FOUND: auraframes/api/assetApi.py
- FOUND: auraframes/sync.py
- FOUND: tests/test_write_endpoints_failloud.py
- FOUND: tests/test_execute_plan.py
- FOUND: tests/test_write_throttling.py
- FOUND: commit af344fa (Task 1)
- FOUND: commit 52eaf80 (Task 2+3)
- Verified: `python -m pytest -m "not live" -q` -> 108 passed, 4 deselected, 0 failed
