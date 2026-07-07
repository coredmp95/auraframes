---
phase: 08-destructive-execution-upload-delete-verification
plan: 03
subsystem: cli
tags: [argparse, pytest, monkeypatch, sync-engine, cli-ux]

requires:
  - phase: 08-destructive-execution-upload-delete-verification plan 02
    provides: execute_plan(plan, aura, frame_id, *, s3_client, sqs_client) -> ExecutionResult, ExecutionResult dataclass
provides:
  - --apply/--yes flags on the sync subparser (auraframes/cli.py)
  - run_sync(dir_arg, frame_arg, apply=False, yes=False, aura=None, debug=False) extended with a D-01..D-04 confirmation gate + execute_plan wiring + D-10 summary + non-zero exit mapping
  - tests/test_cli_apply.py — offline proof of all six apply/confirm/execute behaviors
affects: [08-destructive-execution-upload-delete-verification plan 04 (live delete-primitive / execute_plan verification against a real frame)]

tech-stack:
  added: []
  patterns:
    - "Real AWS clients (S3Client()/SQSClient()) are constructed at the CLI boundary only, on confirmed --apply — execute_plan() itself never constructs them, preserving Plan 02's offline-testability seam all the way out to the CLI"
    - "Single confirmation gate covers the whole plan (uploads + deletes together) rather than per-item or per-phase gates, per D-02"
    - "Fail-closed non-interactive default: sys.stdin.isatty() gates whether input() is ever called, so a cron/CI invocation of --apply without --yes errors immediately instead of hanging on stdin"

key-files:
  created:
    - tests/test_cli_apply.py
  modified:
    - auraframes/cli.py

key-decisions:
  - "The apply/confirm/execute branch lives inside run_sync's existing try/except (not a separate function) so a login/API failure during execute_plan still surfaces through the same fail-loud catch as the dry-run path"
  - "auraframes.cli.execute_plan/S3Client/SQSClient are monkeypatched directly on the cli module namespace in tests (not via a DI parameter) since execute_plan's own signature is fixed by Plan 02 — the CLI is the last integration point where real vs. fake construction can be swapped for a test"
  - "add_argument calls for --apply/--yes kept single-line (not multi-line) to match this plan's own acceptance-criteria grep patterns"

patterns-established:
  - "CLI-boundary construction of real AWS/network clients, injected into an already-proven pure/offline-testable engine function — the same shape Plan 02 established for execute_plan is now the standard for any future CLI command that needs to call a mutating, injected-client function"

requirements-completed: [SYNC-03, SYNC-04]

coverage:
  - id: D1
    description: "sync --apply prints the plan then prompts 'Proceed? [y/N]' and only executes on an affirmative answer (D-01)"
    requirement: SYNC-03
    verification:
      - kind: unit
        ref: "tests/test_cli_apply.py::test_apply_interactive_confirm_echoes_frame_name_and_id"
        status: pass
      - kind: unit
        ref: "tests/test_cli_apply.py::test_apply_interactive_abort_on_non_y_answer"
        status: pass
    human_judgment: false
  - id: D2
    description: "sync --apply --yes executes without prompting (D-01)"
    requirement: SYNC-03
    verification:
      - kind: unit
        ref: "tests/test_cli_apply.py::test_apply_yes_executes_without_prompt"
        status: pass
    human_judgment: false
  - id: D3
    description: "sync --apply without --yes on a non-TTY prints an error and exits non-zero touching nothing (D-03)"
    requirement: SYNC-03
    verification:
      - kind: unit
        ref: "tests/test_cli_apply.py::test_apply_non_tty_without_yes_fails_closed"
        status: pass
    human_judgment: false
  - id: D4
    description: "the confirmation prompt echoes the resolved frame's name and id (D-04)"
    requirement: SYNC-03
    verification:
      - kind: unit
        ref: "tests/test_cli_apply.py::test_apply_interactive_confirm_echoes_frame_name_and_id"
        status: pass
    human_judgment: false
  - id: D5
    description: "the whole plan (uploads + deletes) is covered by one confirmation gate (D-02)"
    requirement: SYNC-03
    verification:
      - kind: other
        ref: "auraframes/cli.py run_sync — single input() call gates both the upload and delete loops inside execute_plan(), no per-item or per-phase second prompt exists"
        status: pass
    human_judgment: false
  - id: D6
    description: "the CLI exits non-zero if any upload or delete failed, prints a separated success/failure summary (D-10, SYNC-04)"
    requirement: SYNC-04
    verification:
      - kind: unit
        ref: "tests/test_cli_apply.py::test_apply_execution_failures_return_1_and_name_failed_items"
        status: pass
    human_judgment: false
  - id: D7
    description: "the apply branch constructs real S3Client()/SQSClient() and passes them to execute_plan; dry-run default (apply=False) behavior is unchanged"
    requirement: SYNC-03
    verification:
      - kind: unit
        ref: "tests/test_cli_apply.py::test_apply_false_no_prompt_no_execution"
        status: pass
      - kind: integration
        ref: "tests/test_cli_sync.py (unchanged, still passing)"
        status: pass
    human_judgment: false

duration: ~10min
completed: 2026-07-07
status: complete
---

# Phase 8 Plan 03: --apply/--yes Confirm Gate + execute_plan CLI Wiring Summary

**Added `--apply`/`--yes` flags and a D-01..D-04 confirmation gate to `aura-cli sync`, wiring Plan 02's `execute_plan()` behind it with real `S3Client()`/`SQSClient()` construction, a D-10 separated success/failure summary, and non-zero exit on any failure — all proven offline with monkeypatched AWS clients and `execute_plan`.**

## Performance

- **Duration:** ~10 min
- **Completed:** 2026-07-07T17:00:00Z
- **Tasks:** 2 completed
- **Files modified:** 2 (1 source, 1 new test file)

## Accomplishments

- `--apply` and `--yes` flags added to the `sync` subparser, both `store_true`/`default=False` matching the existing convention — dry-run stays the unchanged default
- `run_sync` extended to `run_sync(dir_arg, frame_arg, apply=False, yes=False, aura=None, debug=False)`; the entire existing dry-run print block is untouched — counts still print before any gate (SYNC-04)
- Confirmation gate implemented inside the existing try/except: D-03 fail-closed check (`not yes and not sys.stdin.isatty()`) first, then the D-01/D-02/D-04 `input()` prompt (`'About to apply this plan to "{frame.name}" (id: {frame.id}). Proceed? [y/N]'`) only when `--yes` wasn't passed, covering both uploads and deletes with a single gate
- On confirmation, `S3Client()`/`SQSClient()` are constructed (the only place in `cli.py` that constructs them) and `execute_plan(plan, aura, frame.id, s3_client=s3_client, sqs_client=sqs_client)` is called
- D-10 summary printed after execution — `Uploads: N succeeded, M failed` / `Deletes: N succeeded, M failed`, each failed item named on its own line — and `run_sync` returns 1 if either failure list is non-empty, else 0
- `main()` updated to pass `apply=args.apply, yes=args.yes` through to `run_sync`
- `tests/test_cli_apply.py` created — 6 tests covering all six specified behaviors, offline via `offline_aura()` plus monkeypatched `auraframes.cli.execute_plan`/`S3Client`/`SQSClient` (zero network/AWS credentials touched)
- Full offline suite green: `uv run pytest tests/ -x -m "not live"` — 72 passed, 4 deselected (live-marked tests deliberately not run this plan; live verification is Plan 04's scope)

## Task Commits

Each task was committed atomically:

1. **Task 1: --apply/--yes flags + confirmation gate + execute wiring** - `b1f283b` (feat)
2. **Task 2: Offline CLI tests for the apply/confirm flow** - `18a3774` (test)

**Plan metadata:** (this commit) - `docs(08-03): complete --apply/--yes confirm gate plan`

_Note: as in Plans 01/02, tasks were marked `tdd="true"` but the plan's own `type: execute` frontmatter and well-bounded, additive nature of each change meant test-first RED/GREEN was not split into separate commits per task — see Deviations below._

## Files Created/Modified

- `auraframes/cli.py` - Added `--apply`/`--yes` sync subparser flags; extended `run_sync` with the confirm/execute/summary branch; imports `S3Client`, `SQSClient`, `execute_plan`; `main()` passes the new flags through
- `tests/test_cli_apply.py` - 6 offline tests covering the dry-run regression, `--yes` execution, non-TTY fail-closed, interactive abort, interactive confirm with frame echo, and failure-summary/non-zero-exit behaviors

## Decisions Made

- Kept the apply/confirm/execute logic inside `run_sync`'s existing single try/except block (rather than a new helper function) so a login/API failure surfaced by `execute_plan` (e.g. a dropped session) is caught by the same fail-loud handler as the dry-run path, per the plan's explicit instruction
- Constructed `S3Client()`/`SQSClient()` only in the CLI's apply branch — `execute_plan()` itself (Plan 02) never constructs AWS clients, so the offline-testability seam Plan 02 established extends cleanly to the CLI: tests monkeypatch `auraframes.cli.S3Client`/`SQSClient` with trivial fakes and `auraframes.cli.execute_plan` with a call-recording fake, proving the wiring without ever authenticating to Cognito
- Formatted the two new `add_argument` calls on single lines (not the multi-line style used elsewhere in the same method) specifically to satisfy this plan's own acceptance-criteria grep patterns (`grep -c "add_argument('--apply'"` etc.), which check for the flag and its opening paren on one line

## Deviations from Plan

### Auto-fixed Issues

**1. [Process deviation, not a Rule 1-4 fix] TDD RED/GREEN commits collapsed into per-task commits**
- **Found during:** Task 1
- **Issue:** Both tasks are marked `tdd="true"`, implying separate RED (failing test) and GREEN (implementation) commits. As in Plans 01/02, the plan's own `type: execute` frontmatter and the additive, well-bounded nature of each task meant the test file was authored and verified against the implementation before either was committed, then split into one commit per task (Task 1 = the CLI implementation, Task 2 = the dedicated test file) rather than a test-then-implementation split within Task 1 alone.
- **Fix:** N/A — granularity choice, not a bug. `tests/test_cli_apply.py` was written and run green against Task 1's implementation before Task 1 was committed (satisfying Task 1's own `<verify>` command), then committed on its own in Task 2 per the plan's file-ownership split.
- **Files modified:** None beyond what the tasks already specified.
- **Verification:** `uv run pytest tests/test_cli_apply.py -x` and `uv run pytest tests/ -x -m "not live"` both green after each commit.
- **Committed in:** `b1f283b`, `18a3774`

---

**Total deviations:** 1 (process/granularity, no code behavior affected)
**Impact on plan:** None on functionality — all `must_haves` truths and acceptance criteria are met and verified by passing offline tests. No scope creep.

## Issues Encountered

None. The initial `add_argument` calls were written in a multi-line style consistent with a hanging-indent convention, which caused the plan's own single-line grep acceptance criteria (`grep -c "add_argument('--apply'"`) to return 0 instead of 1; reformatted to single-line calls and re-verified all grep checks pass. Not a functional bug — purely a formatting mismatch against the plan's literal verification command.

## User Setup Required

None - no external service configuration required. All work in this plan is offline-testable with monkeypatched AWS clients and a monkeypatched `execute_plan`; no live S3/SQS/Cognito calls were made.

## Next Phase Readiness

- `sync --apply`/`--yes` is now a real, reachable destructive code path end-to-end (CLI flag -> confirm gate -> `execute_plan` -> summary -> exit code), but has never been run against the live API — that is Plan 04's scope: live-verifying the upload round-trip (including the open question of whether the double `select_asset` call is load-bearing, per RESEARCH.md Pitfall 4 / Open Question 1) and the `remove_asset` delete path against a real frame
- No blockers identified for Plan 04

---
*Phase: 08-destructive-execution-upload-delete-verification*
*Completed: 2026-07-07*

## Self-Check: PASSED

All created/modified files found on disk; both task commits (`b1f283b`, `18a3774`) verified present in git history.
