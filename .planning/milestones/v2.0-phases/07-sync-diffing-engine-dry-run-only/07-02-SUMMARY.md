---
phase: 07-sync-diffing-engine-dry-run-only
plan: 02
subsystem: cli
tags: [python, argparse, pydantic, cli, sync]

# Dependency graph
requires:
  - phase: 07-01
    provides: "auraframes/sync.py: scan_directory()/compute_plan() pure diff engine (ScanResult, SyncPlan) — the compute core this plan wires into a CLI command"
  - phase: 06-inspect-frame-resolution
    provides: "resolve_frame()/FrameResolution, Aura DI seam, _configure_cli_logging(), fail-loud CLI conventions, root-level --debug flag — reused verbatim by run_sync()"
provides:
  - "auraframes/cli.py: `sync <dir> --frame <name|id>` subparser (positional dir + required --frame, no apply/yes flag)"
  - "auraframes/cli.py: run_sync() — resolves frame, scans dir, computes plan, prints untruncated dry-run report, returns int exit code"
  - "auraframes/cli.py: main() dispatch branch for `sync`"
  - "tests/test_cli_sync.py — 8 offline tests covering classification, full listing, D-08 delete format, skipped-non-image note, video-safety, ambiguous/not_found/login-failure paths"
affects: [07-03, phase-08]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "run_sync() mirrors run_inspect()'s shape exactly (DI seam, _configure_cli_logging, fail-loud login try/except, inner fail-loud try/except, int return) with one added positional dir_arg"
    - "Delete-candidate print format id + taken_at only (no filename/hash) per D-08 information-disclosure minimization"

key-files:
  created:
    - tests/test_cli_sync.py
  modified:
    - auraframes/cli.py

key-decisions:
  - "run_sync has structurally no path to a mutating primitive — no --apply/--yes flag exists anywhere in build_parser(), and the function body only calls scan_directory/compute_plan/print (verified via grep gate, T-07-04)"
  - "Plan output prints full upload/delete lists with no truncation (D-07) — unlike inspect's first-N + '+K more' convention, since a sync review needs every item visible before a future --apply lands in Phase 8"
  - "Unchanged items are reported as a count only, not a per-item listing — satisfies D-07's upload/delete review need without adding noise for the (by definition) untouched majority"

patterns-established:
  - "Dry-run CLI report format: header naming the resolved frame + DRY RUN notice, then counts, then full upload (+path) and delete (-id (taken date)) listings, then optional skipped/no-hash summary notes"

requirements-completed: [SYNC-01]

coverage:
  - id: D1
    description: "sync <dir> --frame <name|id> subparser (positional dir + required --frame, no apply/yes flag) parses correctly and main() dispatches to run_sync()"
    requirement: "SYNC-01"
    verification:
      - kind: other
        ref: "uv run python -c \"from auraframes.cli import build_parser; a=build_parser().parse_args(['sync','somedir','--frame','X']); assert a.command=='sync' and a.dir=='somedir' and a.frame=='X'; assert not hasattr(a,'apply') and not hasattr(a,'yes')\""
        status: pass
    human_judgment: false
  - id: D2
    description: "run_sync() resolves the frame (reusing resolve_frame/get_all_assets verbatim), scans the directory, computes the plan, and prints counts + full untruncated upload/delete listings with D-08 id+date delete format and skipped/no-hash summary notes"
    requirement: "SYNC-01"
    verification:
      - kind: unit
        ref: "tests/test_cli_sync.py#test_sync_classifies_upload_and_unchanged_by_hash"
        status: pass
      - kind: unit
        ref: "tests/test_cli_sync.py#test_sync_delete_candidate_shows_id_and_date_no_filename"
        status: pass
      - kind: unit
        ref: "tests/test_cli_sync.py#test_sync_lists_full_upload_and_delete_without_truncation"
        status: pass
      - kind: unit
        ref: "tests/test_cli_sync.py#test_sync_skips_non_image_files_with_summary_note"
        status: pass
      - kind: unit
        ref: "tests/test_cli_sync.py#test_sync_hashless_frame_asset_not_deleted"
        status: pass
    human_judgment: false
  - id: D3
    description: "run_sync() reuses Phase 6's ambiguous/not_found/login-failure fail-loud conventions verbatim and returns 1 in each case with no plan output printed"
    requirement: "SYNC-01"
    verification:
      - kind: unit
        ref: "tests/test_cli_sync.py#test_sync_ambiguous_name_returns_1"
        status: pass
      - kind: unit
        ref: "tests/test_cli_sync.py#test_sync_not_found_returns_1"
        status: pass
      - kind: unit
        ref: "tests/test_cli_sync.py#test_sync_login_failure_returns_1"
        status: pass
    human_judgment: false
  - id: D4
    description: "run_sync invokes no mutating call anywhere in its body (structural dry-run enforcement, T-07-04)"
    requirement: "SYNC-01"
    verification:
      - kind: other
        ref: "sed -n '/^def run_sync/,/^def main/p' auraframes/cli.py | grep -vE '^\\s*#' | grep -E 'put_object|upload_file|select_asset|remove_asset|delete_asset|\\.post\\(|\\.put\\(|\\.delete\\(' (expected: zero matches)"
        status: pass
    human_judgment: false

duration: 6min
completed: 2026-07-07
status: complete
---

# Phase 7 Plan 2: Sync CLI Wiring (Dry-Run Only) Summary

**`aura-cli sync <dir> --frame <name|id>` prints a full, untruncated upload/delete/unchanged dry-run report by wiring Phase 6's frame resolution to Phase 7-01's compute_plan() engine — no apply/execute path exists.**

## Performance

- **Duration:** 6min
- **Started:** 2026-07-07T07:52:00+02:00
- **Completed:** 2026-07-07T07:58:00+02:00
- **Tasks:** 2 completed
- **Files modified:** 2 (1 modified, 1 created)

## Accomplishments
- `build_parser()` now exposes a `sync` subcommand with a required positional `dir` and required `--frame`, and deliberately no `--apply`/`--yes` flag.
- `run_sync(dir_arg, frame_arg, aura=None, debug=False)` mirrors `run_inspect`'s exact shape (DI seam, `_configure_cli_logging`, fail-loud login try/except, ambiguous/not_found branches copied verbatim, inner fail-loud try/except) and adds only the scan/compute/print body: `scan_directory(Path(dir_arg))` + `compute_plan(scan.local_hashes, assets, scan.skipped_non_image)`, then prints a header naming the resolved frame, upload/delete/unchanged counts, a full untruncated upload path listing, a full untruncated delete-candidate listing in `id (taken date)` format (no filename/hash, D-08), and optional skipped-non-image / frame-no-hash summary notes.
- `main()` dispatches `args.command == 'sync'` to `run_sync(args.dir, args.frame, debug=args.debug)`.
- Structural dry-run safety confirmed via grep gate: no mutating call token (`put_object`, `upload_file`, `select_asset`, `remove_asset`, `delete_asset`, or raw `.post(`/`.put(`/`.delete(`) exists anywhere in `run_sync`'s body — the no-`--apply`-flag guarantee is enforced by the absence of any code path to a mutating primitive, not a runtime check.
- 8 new offline unit tests in `tests/test_cli_sync.py` cover: hash-based upload/unchanged classification, D-08 delete-candidate id+date format with filename never leaking to output, untruncated 2-item upload listing, skipped-non-image summary note, hashless (video) frame asset never proposed for deletion, ambiguous/not_found frame resolution, and login failure — all offline, zero network access. Full project suite (57 tests, `-m "not live"`) still green.

## Task Commits

Each task was committed atomically:

1. **Task 1: `sync` subparser + run_sync() handler + main() dispatch** - `a37454e` (feat)
2. **Task 2: Offline CLI tests for run_sync (classification, full listing, dry-run)** - `ea91c70` (test)

**Plan metadata:** (this commit, docs: complete plan)

_Note: both tasks carry `tdd="true"` in the plan, but Task 1 (implementation) and Task 2 (tests) were structured as separate sequential tasks rather than a single RED/GREEN unit — the tests in Task 2 exercise the already-implemented `run_sync()` from Task 1 and passed on first run (no RED phase applicable, since there was no failing-test-before-code step within Task 2 itself; the plan's own task split places implementation first). See TDD Gate Compliance note below._

## Files Created/Modified
- `auraframes/cli.py` - Added `sync` subparser, `run_sync()` handler, and `main()` dispatch branch; imports `Path` and `scan_directory`/`compute_plan` from `auraframes.sync`
- `tests/test_cli_sync.py` - 8 offline unit tests covering every `<behavior>` bullet from Task 2, following `test_cli_inspect.py`'s conventions (`_reset_loguru` autouse fixture, `offline_aura(overrides=...)`, `capsys`, fixture-copy-and-mutate pattern)

## Decisions Made
- Reused `assets_page1.json`'s single asset object as a copy-and-mutate base for all test fixtures (per the plan's suggested fallback), rather than hand-authoring full `Asset` JSON payloads — matches `test_cli_inspect.py`'s `_single_frame()` precedent.
- Report unchanged items as a count only (not a per-item listing) — the plan's `<action>` step 4 explicitly allows this ("Optionally list unchanged as a count... full per-item listing of unchanged is not required by D-08").
- Frame-no-hash note phrased as "N frame assets without a content hash (e.g. videos) left untouched" — Claude's discretion per the plan's wording latitude, kept consistent with Phase 6's spike finding language in STATE.md.

## Deviations from Plan

None - plan executed exactly as written. Both tasks' `<behavior>`, `<action>`, and `<verify>` requirements were implemented and verified precisely as specified; no bugs, missing functionality, or blocking issues were encountered.

## TDD Gate Compliance

The plan's `type` frontmatter is `execute` (not `tdd`), so plan-level mandatory-separate-`test`/`feat`-commit gate enforcement does not apply — per-task `tdd="true"` was honored at the task level instead. Task 1 (`a37454e`) is the `feat` implementation commit; Task 2 (`ea91c70`) is the `test` commit, run and confirmed passing (`uv run pytest tests/test_cli_sync.py -x -q` → 8 passed) before being committed. Because Task 1's implementation already existed when Task 2's tests were authored (the plan sequences implementation before tests as two separate tasks, unlike Plan 01's single-task RED/GREEN units), there was no failing-test-before-code step to observe within Task 2 — the tests exercised the Task 1 implementation directly and passed on first run. This is a direct consequence of the plan's own task ordering (Task 1: handler, Task 2: tests), not a skipped verification step.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required. Zero network access, zero credentials needed for this plan's entire test suite.

## Next Phase Readiness
- `aura-cli sync <dir> --frame <name|id>` is fully wired and offline-tested; SYNC-01's dry-run deliverable is complete for this phase's scope.
- Ready for 07-03 (the plan's remaining wave item per STATE.md — likely the one-time live hash-convention validation, D-09) to confirm `get_md5`'s local base64-MD5 output matches a real frame's `Asset.md5_hash` byte-for-byte before Phase 8 builds the destructive `--apply` path on top of this diff.
- No blockers. `run_sync()`'s fail-loud/DI-seam/no-mutating-call structure gives Phase 8 a safe foundation to extend with an `execute_plan()` counterpart without touching this plan's read-only dry-run path.

---
*Phase: 07-sync-diffing-engine-dry-run-only*
*Completed: 2026-07-07*

## Self-Check: PASSED

- FOUND: auraframes/cli.py
- FOUND: tests/test_cli_sync.py
- FOUND commit: a37454e
- FOUND commit: ea91c70
