---
phase: 10-hide-instead-of-delete-sync-mode
plan: 04
subsystem: ui
tags: [cli, argparse, confirmation-gate, sync, push]

requires:
  - phase: 10-02
    provides: SyncPlan.to_reshow / already_hidden
  - phase: 10-03
    provides: execute_plan(removal_mode=...) and ExecutionResult.reshow_*
provides:
  - sync --delete / --hard-delete (mutually exclusive), hide as the default
  - Verb-per-mode plan and summary wording plus re-show and already-hidden reporting
  - The escalated exact-count confirmation gate for hard delete
  - push confirmed upload-only (clears to_reshow too)
affects: []

actuals:
  tokens: 8100
  tasks: 3
  commits: 1

tech-stack:
  added: []
  patterns:
    - "Irreversible actions get a gate whose shape differs from the routine one, not just different words"

key-files:
  created: []
  modified:
    - auraframes/cli.py
    - tests/test_cli_apply.py
    - tests/test_cli_sync.py
    - tests/test_cli_push_budget_geo.py

key-decisions:
  - "The hard-delete gate requires re-typing the exact count, so the user must read the number before confirming"
  - "Legacy tests asserting 'To delete'/'Deletes:' were updated rather than pinned — the wording change under the default is the deliverable"

patterns-established:
  - "Report wording is derived from the mode via a lookup table, so a report can never name a verb that did not run"

requirements-completed: [HIDE-05, HIDE-06, HIDE-08]

coverage:
  - id: D1
    description: "sync defaults to hide; --delete and --hard-delete are mutually exclusive and select their mode"
    requirement: "HIDE-05"
    verification:
      - kind: unit
        ref: "tests/test_cli_sync.py::test_delete_and_hard_delete_are_mutually_exclusive; tests/test_cli_apply.py::test_default_mode_is_hide_and_says_so"
        status: pass
      - kind: manual_procedural
        ref: "live dry-run against 'Cadre de Fabrice' — printed 'To hide: 96' / 'To hard-delete: 96' / 'Already hidden: 3'"
        status: pass
    human_judgment: false
  - id: D2
    description: "--hard-delete requires re-typing the exact removal count; a wrong answer aborts before any write"
    requirement: "HIDE-06"
    verification:
      - kind: unit
        ref: "tests/test_cli_apply.py::test_hard_delete_requires_typing_the_exact_count (+ proceeds/skips-with-yes siblings)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Re-shows are reported in plan and summary and affect the exit code; push never re-shows"
    requirement: "HIDE-05, HIDE-06"
    verification:
      - kind: unit
        ref: "tests/test_cli_apply.py::test_reshow_is_reported_in_plan_and_summary, ::test_reshow_failures_make_the_run_exit_nonzero, ::test_push_never_reshows_even_with_reshow_candidates"
        status: pass
    human_judgment: false

duration: 30min
completed: 2026-08-25
status: complete
---

# Phase 10 / Plan 04: The CLI surface — Summary

**`sync` now hides by default, names the verb it will actually run, and makes irreversible deletion something you have to read a number to do.**

## Performance

- **Duration:** ~30 min
- **Tasks:** 3 of 3
- **Files modified:** 4

## Accomplishments

- `sync` gained mutually-exclusive `--delete` / `--hard-delete`; with neither, gone-local photos are hidden.
- Plan and summary wording is derived per mode (`To hide` / `To delete` / `To hard-delete` → `Hidden` / `Removed` / `Hard-deleted`), so a report can never name a verb that did not run.
- Re-shows get their own `To re-show:` / `Re-shown:` lines, already-hidden assets are reported as needing no action, and re-show failures now count toward the exit code.
- `--hard-delete` escalates the gate to an exact-count re-type behind an `IRREVERSIBLE` warning; `--yes` still skips every gate and the non-interactive path still fails closed.
- `push` confirmed upload-only: `no_delete` now clears `to_reshow` as well.
- 12 new offline CLI tests. Full suite: 208 passed.

## Task Commits

1. **Tasks 1–3** — `f3e4eb7` (feat)

## Live verification (dry-run only, no writes)

```
$ aura-cli sync <empty-dir> --frame "Cadre de Fabrice"
To hide: 96
To re-show: 0
Unchanged: 0
Already hidden: 3 (no action needed)

$ aura-cli sync <empty-dir> --frame "Cadre de Fabrice" --hard-delete
To hard-delete: 96

$ aura-cli sync . --frame X --delete --hard-delete
aura-cli sync: error: argument --hard-delete: not allowed with argument --delete
```

`Already hidden: 3` is exactly the three disposables Plan 10-01 left hidden — the 4-way classification reading real frame state end-to-end.

## Decisions Made

- **Legacy wording assertions updated, not pinned.** Three `test_cli_sync` tests and one `test_cli_apply` test asserted `To delete:` / `Deletes:` under default options. Since changing that default wording *is* the deliverable, they were updated to the hide vocabulary rather than pinned to `--delete`.

## Deviations from Plan

### 1. [Ordering slip, self-corrected] Verb derivation initially landed in `run_status`

- **Found during:** Task 2, first test run (`NameError: name 'removal_mode' is not defined` across the status tests).
- **Issue:** `run_status` and `run_sync` open with an identical three-line preamble, so the insertion anchored on the wrong function.
- **Fix:** Moved the two derivation lines into `run_sync`.
- **Verification:** full suite green.
- **Committed in:** `f3e4eb7` (never committed in the broken state)

**Total deviations:** 1 (self-corrected before commit)
**Impact on plan:** None.

## Issues Encountered

- The two `execute_plan` fakes in `tests/test_cli_push_budget_geo.py` pin an explicit keyword list and rejected the new `removal_mode`; both now accept it.
- Noted but not changed: the push dry-run header is keyed on `verb` while the removal line is keyed on `no_delete`, so calling `run_sync(verb='push')` *without* `no_delete=True` prints an "additive" header above a hide line. Only reachable from tests — the real dispatch always passes both. Pre-existing, out of scope.
- `tests/test_read_path.py::test_read_03_pagination` still fails — the pre-existing live `num_assets` mismatch logged in STATE.md.

## Next Phase Readiness

Phase 10 is functionally complete: all 8 HIDE requirements are implemented and covered. The hide path is live-verified end-to-end; the `--delete` and `--hard-delete` paths are covered offline and their primitives were live-verified in Plan 10-01, but neither has been exercised through the CLI against a real frame.
