---
phase: 08-destructive-execution-upload-delete-verification
plan: 02
subsystem: api
tags: [pydantic, httpx, pytest, boto3, sync-engine, error-handling]

requires:
  - phase: 08-destructive-execution-upload-delete-verification plan 01
    provides: AssetPartial model, fail-loud select_asset/remove_asset/batch_update, parameterized Aura.get_sqs(frame_id)
provides:
  - execute_plan(plan, aura, frame_id, *, s3_client, sqs_client) -> ExecutionResult — the module's only mutating function
  - ExecutionResult dataclass with separated upload/delete success counts and named per-item failures
  - _execute_upload() private helper preserving the double select_asset + SQS-poll sequence for the first live attempt
affects: [08-destructive-execution-upload-delete-verification plan 03 (CLI presentation/exit-code wiring), plan 04 (live delete-primitive verification)]

tech-stack:
  added: []
  patterns:
    - "Injected-client offline testability: execute_plan never constructs S3Client()/SQSClient() itself — callers pass them in, so the mutating function is fully testable with duck-typed fakes and zero AWS credentials"
    - "Uploads-before-deletes ordering (D-09) as a structural loop sequence, not a flag — enforced by source order and proven with a call-order recorder in tests"
    - "Per-item try/except continue-past-failure (D-08) with named failures collected into a list, mirroring Aura.download_images_from_assets()'s existing continue-past-failure shape"

key-files:
  created:
    - tests/test_execute_plan.py
  modified:
    - auraframes/sync.py

key-decisions:
  - "Resumed and verified a prior killed agent's uncommitted Task 1 implementation rather than rewriting from scratch — independently re-checked it against the plan's behavior/acceptance criteria (grep checks, import check, full offline suite) before committing, per the resume protocol"
  - "_execute_upload's double select_asset call + first discarded SQS poll preserved unchanged (RESEARCH.md Pitfall 4) — not collapsed to a single call, since this is only the first live attempt and the live checkpoint (plan 03/04) is the place to confirm whether the second call is load-bearing"
  - "Partial-failure tests monkeypatch aura.asset_api.batch_update / aura.frame_api.remove_asset directly (plan-sanctioned) rather than trying to make httpx.MockTransport discriminate by request payload, since MockTransport routes purely by path and can't return different responses to the two otherwise-identical select_asset/batch_update calls in a 2-item plan"

patterns-established:
  - "Injected S3/SQS duck-typed fakes (not botocore Stubber) as the standard offline-testability seam for any future AWS-touching mutating function in this codebase"

requirements-completed: [SYNC-03, SYNC-04]

coverage:
  - id: D1
    description: "execute_plan uploads each to_upload file (select_asset -> S3 -> batch_update) then removes each to_delete asset via remove_asset"
    requirement: SYNC-03
    verification:
      - kind: unit
        ref: "tests/test_execute_plan.py::test_execute_plan_happy_path_uploads_and_deletes"
        status: pass
    human_judgment: false
  - id: D2
    description: "All uploads are attempted before any delete (D-09)"
    requirement: SYNC-03
    verification:
      - kind: unit
        ref: "tests/test_execute_plan.py::test_execute_plan_all_uploads_precede_all_deletes"
        status: pass
    human_judgment: false
  - id: D3
    description: "A single upload's failure is caught, recorded with its path and message, and the loop continues (D-08)"
    requirement: SYNC-04
    verification:
      - kind: unit
        ref: "tests/test_execute_plan.py::test_execute_plan_upload_partial_failure_continues_and_records"
        status: pass
    human_judgment: false
  - id: D4
    description: "A single delete's failure is caught, recorded with its asset id and message, and the loop continues (D-08)"
    requirement: SYNC-04
    verification:
      - kind: unit
        ref: "tests/test_execute_plan.py::test_execute_plan_delete_partial_failure_continues_and_records"
        status: pass
    human_judgment: false
  - id: D5
    description: "execute_plan returns an ExecutionResult with separated upload/delete success counts and named failures (D-10)"
    requirement: SYNC-03
    verification:
      - kind: unit
        ref: "tests/test_execute_plan.py::test_execute_plan_happy_path_uploads_and_deletes"
        status: pass
      - kind: unit
        ref: "tests/test_execute_plan.py::test_execute_plan_upload_partial_failure_continues_and_records"
        status: pass
    human_judgment: false
  - id: D6
    description: "The delete loop calls remove_asset exclusively; the hard-delete primitive is entirely absent from sync.py (D-06 structural isolation)"
    requirement: SYNC-03
    verification:
      - kind: other
        ref: "grep -c 'delete_asset' auraframes/sync.py  ->  0"
        status: pass
    human_judgment: false
  - id: D7
    description: "S3 and SQS clients are injected as parameters so execute_plan is offline-testable with fakes"
    requirement: SYNC-04
    verification:
      - kind: other
        ref: "grep -Ec 'S3Client\\(|SQSClient\\(' auraframes/sync.py  ->  0"
        status: pass
      - kind: unit
        ref: "tests/test_execute_plan.py::test_execute_plan_happy_path_uploads_and_deletes"
        status: pass
    human_judgment: false

duration: ~20min (across two agent sessions; first session was killed mid-task by the orchestrator before committing)
completed: 2026-07-07
status: complete
---

# Phase 8 Plan 02: execute_plan Upload + Delete Orchestration Summary

**Added `execute_plan()` and `ExecutionResult` to `auraframes/sync.py` — the sole mutating counterpart to `compute_plan()`, performing the real upload round-trip and `remove_asset` disassociation with uploads-before-deletes ordering and per-item continue-past-failure, proven entirely offline with injected S3/SQS fakes.**

## Performance

- **Duration:** ~20 min total (a prior agent session was killed mid-Task-1 by the orchestrator before it could commit; this session verified that uncommitted work independently, committed it, then completed Task 2)
- **Completed:** 2026-07-07T15:07:51Z
- **Tasks:** 2 completed
- **Files modified:** 2 (1 source, 1 new test file)

## Accomplishments

- `ExecutionResult` dataclass added to `auraframes/sync.py` with `upload_succeeded`, `delete_succeeded`, `upload_failures: list[tuple[Path, str]]`, `delete_failures: list[tuple[str, str]]`
- `execute_plan(plan, aura, frame_id, *, s3_client, sqs_client) -> ExecutionResult` iterates `sorted(plan.to_upload)` then `plan.to_delete` (D-09), each item wrapped in its own try/except that records the failure and continues (D-08)
- `_execute_upload()` private helper performs the real upload round-trip: double `select_asset` + discarded first SQS poll (RESEARCH.md Pitfall 4, preserved unchanged), `s3_client.upload_file`, `AssetPartial` construction per RESEARCH.md's vetted "Upload identity construction" example, `batch_update`, then a best-effort trailing SQS poll logged at debug level
- Module docstring updated to state `execute_plan` is the module's single mutating entry point (no longer claims there is no execute counterpart)
- `tests/test_execute_plan.py` created: happy path, upload partial failure, delete partial failure, and upload-before-delete ordering — all offline via `offline_aura()` (REST mocked) plus duck-typed `_FakeS3Client`/`_FakeSQSClient` fakes injected as `s3_client=`/`sqs_client=`
- Full offline suite green: `uv run pytest tests/ -x` — 70 passed (66 non-live + 4 live, this dev machine has local credentials configured; `-m "not live"` alone: 66 passed, 4 deselected)

## Task Commits

Each task was committed atomically:

1. **Task 1: execute_plan upload + delete orchestration** - `82a47d5` (feat)
2. **Task 2: Offline tests for execute_plan with injected AWS fakes** - `0fa4234` (test)

**Plan metadata:** (this commit) - `docs(08-02): complete execute_plan upload + delete orchestration plan`

_Note: as in Plan 01, tasks were marked `tdd="true"` but the plan's own `type: execute` frontmatter and the small, additive, well-specified nature of each change meant test-first RED/GREEN was not split into separate commits — see Deviations below._

## Files Created/Modified

- `auraframes/sync.py` - Added `ExecutionResult` dataclass, `_execute_upload()` private helper, `execute_plan()` public entry point, and updated the module docstring
- `tests/test_execute_plan.py` - Offline tests covering happy path, upload/delete partial failure, and uploads-before-deletes ordering

## Decisions Made

- Resumed a prior killed agent's uncommitted Task 1 work after independently re-verifying it against the plan's `<behavior>`/`<acceptance_criteria>` (all four grep checks, a fresh `import auraframes.sync` check, and the full 62-test then 66/70-test offline suite) rather than blindly trusting the hand-off summary or rewriting from scratch
- Preserved the double `select_asset` call + first discarded SQS poll exactly as RESEARCH.md's Pitfall 4 specifies, for the first live attempt
- Used monkeypatching of `aura.asset_api.batch_update`/`aura.frame_api.remove_asset` for partial-failure test cases (plan-sanctioned) instead of trying to make `httpx.MockTransport` discriminate per-item by payload — MockTransport routes purely by path, so two uploads hitting the same `batch_update.json` path can't get different canned responses through overrides alone

## Deviations from Plan

### Auto-fixed Issues

**1. [Process deviation, not a Rule 1-4 fix] TDD RED/GREEN commits collapsed into per-task commits**
- **Found during:** Task 1 (resumed)
- **Issue:** Both tasks are marked `tdd="true"`, implying separate RED (failing test) and GREEN (implementation) commits. As in Plan 01, the plan's own `type: execute` frontmatter and the additive, well-bounded nature of each task meant implementation and its offline tests were verified together and committed as one commit per task (Task 1's implementation commit, Task 2's dedicated test-file commit).
- **Fix:** N/A — granularity choice, not a bug. Every `<behavior>` item is covered by a passing test before each commit; `tests/test_execute_plan.py` is itself the RED/GREEN proof for Task 1's implementation, just landed in the next task's commit rather than split test-then-implementation.
- **Files modified:** None beyond what the tasks already specified.
- **Verification:** `uv run pytest tests/test_execute_plan.py -x` and `uv run pytest tests/ -x` both green after each commit.
- **Committed in:** `82a47d5`, `0fa4234`

---

**Total deviations:** 1 (process/granularity, no code behavior affected)
**Impact on plan:** None on functionality — all `must_haves` truths and acceptance criteria are met and verified by passing offline tests. No scope creep.

## Issues Encountered

A previous executor agent attempt on this plan hung on a tool call and was killed by the orchestrator before committing. Its Task 1 work (ExecutionResult, `_execute_upload()`, `execute_plan()`) was left uncommitted in the working tree. This session independently re-verified that code against the plan's acceptance criteria (all grep checks, `import auraframes.sync`, and the full offline test suite) before committing it, then proceeded normally to Task 2. No code changes were needed — the prior agent's implementation matched RESEARCH.md's vetted code example and the plan's behavior spec exactly.

## User Setup Required

None - no external service configuration required. All work in this plan is offline-testable with injected fakes; no live S3/SQS calls were made.

## Next Phase Readiness

- `execute_plan()` and `ExecutionResult` are ready for Plan 03 to wire into the CLI's presentation and exit-code mapping (execute_plan deliberately returns a result object and does not print or compute an exit code itself)
- The upload/delete round-trip has not yet been exercised against the live API — that remains Plan 03/04's live-checkpoint responsibility, matching RESEARCH.md's Open Question 1 (double `select_asset` call) and Open Question 2 (`delete_asset` blast radius)
- No blockers identified for Plan 03

---
*Phase: 08-destructive-execution-upload-delete-verification*
*Completed: 2026-07-07*

## Self-Check: PASSED

All created/modified files found on disk; both task commits (`82a47d5`, `0fa4234`) verified present in git history.
