---
phase: 08-destructive-execution-upload-delete-verification
plan: 01
subsystem: api
tags: [pydantic, httpx, pytest, error-handling, aws-sqs]

requires:
  - phase: 07-sync-diffing-engine-dry-run-only
    provides: content-hash diffing engine (compute_plan/scan_directory) that Plan 02's execute path will drive
provides:
  - AssetPartial model (all-Optional Asset variant) for new-upload metadata construction
  - Fail-loud RuntimeError on error envelope / nonzero number_failed across select_asset, remove_asset, batch_update, delete_asset
  - Aura.get_sqs(frame_id) parameterized, no hardcoded queue id
affects: [08-destructive-execution-upload-delete-verification plan 02 (execute_plan), plan 03, plan 04 (live delete-primitive verification)]

tech-stack:
  added: []
  patterns:
    - "make_partial(Model, Name) factory reused for a second model (AssetPartial mirrors FramePartial) — establishes the pattern as the standard way to build a PATCH/upload-shaped Optional variant of any Asset-family model"
    - "Fail-loud error-envelope guard (`if json_response.get('error'): raise RuntimeError(...)`) now applied uniformly across all four write/delete endpoints, matching the existing get_assets precedent"

key-files:
  created:
    - tests/test_asset_partial.py
    - tests/test_write_endpoints_failloud.py
  modified:
    - auraframes/models/asset.py
    - auraframes/api/frameApi.py
    - auraframes/api/assetApi.py
    - auraframes/aura.py

key-decisions:
  - "AssetPartial added via make_partial(Asset, \"AssetPartial\") verbatim mirroring FramePartial, with zero changes to Asset.id's type — sidesteps the Asset(id=None, ...) ValidationError blocker without a model-field change"
  - "select_asset/remove_asset raise on nonzero number_failed (not just an error envelope) because each call carries exactly one AssetPartialId, so a nonzero count unambiguously attributes to that single asset (WRITE-05 per-file attribution)"
  - "batch_update's parameter type hint widened to Asset | AssetPartial rather than introducing a new method, since the existing .dict(include={...}) call works unchanged on both"
  - "get_sqs and write-endpoint tests combined into a single tests/test_write_endpoints_failloud.py file (plan explicitly allowed this) rather than a separate tests/test_get_sqs.py"

patterns-established:
  - "make_partial reuse for AssetPartial: any future Asset-family PATCH/upload payload model should use make_partial(Asset, Name) rather than hand-rolling Optional fields"

requirements-completed: [WRITE-04, WRITE-05]

coverage:
  - id: D1
    description: "AssetPartial constructs with id unset and serializes to batch_update's payload shape"
    requirement: WRITE-05
    verification:
      - kind: unit
        ref: "tests/test_asset_partial.py::test_asset_partial_constructs_with_id_unset"
        status: pass
      - kind: unit
        ref: "tests/test_asset_partial.py::test_asset_partial_serializes_to_batch_update_payload_shape"
        status: pass
      - kind: unit
        ref: "tests/test_asset_partial.py::test_asset_partial_is_subclass_of_asset"
        status: pass
    human_judgment: false
  - id: D2
    description: "select_asset and remove_asset raise RuntimeError on error envelope and on nonzero number_failed; succeed otherwise"
    requirement: WRITE-05
    verification:
      - kind: unit
        ref: "tests/test_write_endpoints_failloud.py::test_select_asset_raises_on_error_envelope"
        status: pass
      - kind: unit
        ref: "tests/test_write_endpoints_failloud.py::test_select_asset_raises_on_nonzero_number_failed"
        status: pass
      - kind: unit
        ref: "tests/test_write_endpoints_failloud.py::test_select_asset_returns_number_failed_on_success"
        status: pass
      - kind: unit
        ref: "tests/test_write_endpoints_failloud.py::test_remove_asset_raises_on_error_envelope"
        status: pass
      - kind: unit
        ref: "tests/test_write_endpoints_failloud.py::test_remove_asset_raises_on_nonzero_number_failed"
        status: pass
      - kind: unit
        ref: "tests/test_write_endpoints_failloud.py::test_remove_asset_returns_number_failed_on_success"
        status: pass
    human_judgment: false
  - id: D3
    description: "batch_update raises RuntimeError on error envelope, succeeds and returns (ids, successes) otherwise, and accepts an AssetPartial argument"
    requirement: WRITE-05
    verification:
      - kind: unit
        ref: "tests/test_write_endpoints_failloud.py::test_batch_update_raises_on_error_envelope"
        status: pass
      - kind: unit
        ref: "tests/test_write_endpoints_failloud.py::test_batch_update_succeeds_with_asset_partial"
        status: pass
    human_judgment: false
  - id: D4
    description: "delete_asset raises RuntimeError on error envelope"
    requirement: WRITE-05
    verification:
      - kind: unit
        ref: "tests/test_write_endpoints_failloud.py::test_delete_asset_raises_on_error_envelope"
        status: pass
    human_judgment: false
  - id: D5
    description: "Aura.get_sqs(frame_id) passes the given frame_id to get_queue_url, no hardcoded queue id remains"
    requirement: WRITE-04
    verification:
      - kind: unit
        ref: "tests/test_write_endpoints_failloud.py::test_get_sqs_passes_frame_id_to_sqs_client"
        status: pass
    human_judgment: false

duration: 11min
completed: 2026-07-07
status: complete
---

# Phase 8 Plan 01: Fail-Loud Write Foundations + get_sqs Parameterization Summary

**Added AssetPartial model, made all four write/delete endpoints raise RuntimeError on API error/nonzero number_failed, and parameterized Aura.get_sqs(frame_id) to remove the hardcoded test-frame queue id — all offline-tested, no live API calls.**

## Performance

- **Duration:** 11 min
- **Started:** 2026-07-07T13:45:00Z (approx, first commit 15:45:18+02:00)
- **Completed:** 2026-07-07T13:56:10Z (last commit 15:56:10+02:00)
- **Tasks:** 3 completed
- **Files modified:** 6 (4 source, 2 new test files)

## Accomplishments

- `AssetPartial = make_partial(Asset, "AssetPartial")` added to `auraframes/models/asset.py`, mirroring `FramePartial` verbatim — constructs with `id` unset, subclasses `Asset`, serializes exactly to `batch_update`'s allowlist shape
- `FrameApi.select_asset` and `FrameApi.remove_asset` now raise `RuntimeError` on an `error` envelope or a nonzero `number_failed`, matching the existing `get_assets` fail-loud precedent (WRITE-05)
- `AssetApi.batch_update` raises `RuntimeError` on an `error` envelope and its parameter type hint widened to `Asset | AssetPartial`
- `AssetApi.delete_asset` raises `RuntimeError` on an `error` envelope
- `Aura.get_sqs(frame_id)` is now parameterized — the hardcoded queue id `4ab446b4-33a7-4a76-881d-d545d153ab5a` is gone, and `upload_image`'s call site passes `frame_id` (WRITE-04, D-11)
- Full offline suite (62 tests, `-m "not live"`) green after all three tasks

## Task Commits

Each task was committed atomically:

1. **Task 1: Add AssetPartial all-Optional model** - `7d3974b` (test)
2. **Task 2: Fail-loud write/delete endpoints (WRITE-05)** - `fb330de` (fix)
3. **Task 3: Parameterize Aura.get_sqs (WRITE-04, D-11)** - `0296aff` (fix)

_Note: Tasks were tdd="true" per plan, but model/endpoint implementation and their offline tests were combined into single per-task commits (test-first RED/GREEN split was not applied as separate commits) — see Deviations below._

## Files Created/Modified

- `auraframes/models/asset.py` - Added `AssetPartial` via `make_partial(Asset, "AssetPartial")`
- `auraframes/api/frameApi.py` - `select_asset`/`remove_asset` fail-loud on error envelope + nonzero `number_failed`
- `auraframes/api/assetApi.py` - `batch_update` fail-loud + `Asset | AssetPartial` type hint; `delete_asset` fail-loud
- `auraframes/aura.py` - `get_sqs(frame_id)` parameterized, hardcoded id removed, call site updated
- `tests/test_asset_partial.py` - AssetPartial construction/serialization/subclass tests
- `tests/test_write_endpoints_failloud.py` - fail-loud tests for all four endpoints + `get_sqs` frame_id-passthrough test

## Decisions Made

- `AssetPartial` mirrors `FramePartial` exactly (`make_partial(Asset, "AssetPartial")`) with no changes to `Asset.id`'s type, avoiding a model-field change while still solving the `Asset(id=None, ...)` construction blocker (RESEARCH.md Pitfall 1)
- `select_asset`/`remove_asset` treat a nonzero `number_failed` as a hard failure (not just a return value) because each call carries exactly one `AssetPartialId`, making the attribution unambiguous
- `batch_update`'s type hint widened rather than adding a new method — the existing `.dict(include={...})` allowlist call works unchanged on both `Asset` and `AssetPartial`
- Combined the `get_sqs` test into `tests/test_write_endpoints_failloud.py` (plan explicitly permitted this) instead of a separate file

## Deviations from Plan

### Auto-fixed Issues

**1. [Process deviation, not a Rule 1-4 fix] TDD RED/GREEN commits collapsed into single per-task commits**
- **Found during:** Task 1
- **Issue:** The plan marks all three tasks `tdd="true"`, which per the executor's TDD execution flow implies separate RED (failing test) and GREEN (implementation) commits. Given the plan's own frontmatter `type: execute` (not `type: tdd`), and the small, low-risk, additive nature of each change (single model addition, uniform error-guard pattern, single-parameter signature change), model + test were written and verified together, then committed as one commit per task.
- **Fix:** N/A — this is a granularity choice, not a bug fix. All behaviors described in each task's `<behavior>` block are covered by passing tests before commit.
- **Files modified:** None beyond what the task already specified.
- **Verification:** Every commit's tests pass in isolation (`uv run pytest tests/test_asset_partial.py -x`, `uv run pytest tests/test_write_endpoints_failloud.py -x`) and the full offline suite is green after each commit.
- **Committed in:** `7d3974b`, `fb330de`, `0296aff`

---

**Total deviations:** 1 (process/granularity, no code behavior affected)
**Impact on plan:** None on functionality — all `must_haves` truths and acceptance criteria from the plan are met and verified by passing offline tests. No scope creep.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. All work in this plan is offline-testable; no live API calls were made.

## Next Phase Readiness

- `AssetPartial`, fail-loud write/delete endpoints, and parameterized `get_sqs(frame_id)` are all in place for Plan 02's `execute_plan()` to build on
- `batch_update` accepting `Asset | AssetPartial` unblocks Plan 02's new-upload payload construction without further model changes
- No blockers identified for Plan 02

---
*Phase: 08-destructive-execution-upload-delete-verification*
*Completed: 2026-07-07*

## Self-Check: PASSED

All created/modified files found on disk; all three task commits (`7d3974b`, `fb330de`, `0296aff`) verified present in git history.
