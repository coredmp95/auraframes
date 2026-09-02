---
phase: 07-sync-diffing-engine-dry-run-only
plan: 01
subsystem: sync
tags: [python, pydantic, hashlib, pathlib, diff-engine]

# Dependency graph
requires:
  - phase: 06-inspect-frame-resolution
    provides: "Live confirmation that Asset.md5_hash is populated for photo assets and null for video assets, which justifies restricting content-hash diffing to eligible image extensions"
provides:
  - "auraframes/sync.py: ELIGIBLE_EXTENSIONS, ScanResult, scan_directory() — recursive local directory scan + base64-MD5 content hashing + dedup"
  - "auraframes/sync.py: SyncPlan, compute_plan() — pure diff function classifying frame assets into upload/delete/unchanged/frame_no_hash by content hash"
  - "tests/test_sync_engine.py — offline unit-test suite covering both functions, zero network"
affects: [07-02, 07-03, phase-08]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pure diff function mirroring resolve_frame's shape (dataclass result, no I/O) — compute_plan(local_hashes, frame_assets) -> SyncPlan"
    - "Reuse existing canonical helpers instead of reimplementing (S3Client.get_md5 for local hashing)"

key-files:
  created:
    - auraframes/sync.py
    - tests/test_sync_engine.py
  modified: []

key-decisions:
  - "scan_directory hashes only ELIGIBLE_EXTENSIONS = {.jpg, .jpeg, .png, .heic} (case-insensitive suffix match); all other files are counted in skipped_non_image, never erroring (D-02, D-03)"
  - "Local byte-identical files collapse to a single hash key (dedup to one logical want) before diffing (D-05)"
  - "compute_plan treats local demand as count-for-count multiset against frame assets: surplus frame-side duplicates beyond local demand become delete candidates, not deduped as a group (D-06 asymmetry)"
  - "Frame assets with a falsy md5_hash (e.g. videos) are excluded from both unchanged and to_delete, counted separately in frame_no_hash — prevents proposing deletion of every video"
  - "No execute/mutating function exists anywhere in sync.py — dry-run is structural, enforced by a no-write grep gate in the verify step"

patterns-established:
  - "auraframes/sync.py is the pure, offline-testable core of the sync engine; a future execute_plan() (Phase 8) is a separate module/function, never added here"

requirements-completed: [SYNC-01, SYNC-02]

coverage:
  - id: D1
    description: "scan_directory recursively walks a directory, hashes only eligible image files via the reused S3Client.get_md5 base64-MD5 convention, counts everything else as skipped_non_image without erroring, and collapses byte-identical files to one hash key"
    requirement: "SYNC-02"
    verification:
      - kind: unit
        ref: "tests/test_sync_engine.py#test_scan_directory_recurses_into_nested_subdirectories"
        status: pass
      - kind: unit
        ref: "tests/test_sync_engine.py#test_scan_directory_hashes_each_eligible_extension_case_insensitively"
        status: pass
      - kind: unit
        ref: "tests/test_sync_engine.py#test_scan_directory_skips_non_image_files_without_erroring"
        status: pass
      - kind: unit
        ref: "tests/test_sync_engine.py#test_scan_directory_collapses_byte_identical_files_to_one_hash_key"
        status: pass
      - kind: unit
        ref: "tests/test_sync_engine.py#test_scan_directory_empty_directory_yields_empty_result"
        status: pass
    human_judgment: false
  - id: D2
    description: "compute_plan is a pure function classifying frame assets into upload/delete/unchanged by content hash only, honoring the local-dedup vs frame-multiset asymmetry, and excluding hashless (video) frame assets from deletion"
    requirement: "SYNC-01"
    verification:
      - kind: unit
        ref: "tests/test_sync_engine.py#test_compute_plan_local_only_hash_becomes_single_upload"
        status: pass
      - kind: unit
        ref: "tests/test_sync_engine.py#test_compute_plan_matched_hash_is_unchanged_not_upload_or_delete"
        status: pass
      - kind: unit
        ref: "tests/test_sync_engine.py#test_compute_plan_multiset_surplus_frame_assets_become_delete_candidates"
        status: pass
      - kind: unit
        ref: "tests/test_sync_engine.py#test_compute_plan_frame_hash_absent_locally_becomes_delete"
        status: pass
      - kind: unit
        ref: "tests/test_sync_engine.py#test_compute_plan_hashless_frame_asset_excluded_from_unchanged_and_delete"
        status: pass
      - kind: unit
        ref: "tests/test_sync_engine.py#test_compute_plan_carries_skipped_non_image_onto_returned_plan"
        status: pass
    human_judgment: false
  - id: D3
    description: "No mutating API/S3/SQS call token appears anywhere in auraframes/sync.py (structural dry-run enforcement, T-07-03)"
    requirement: "SYNC-01"
    verification:
      - kind: other
        ref: "grep -vE '^\\s*#' auraframes/sync.py | grep -qE 'put_object|upload_file|select_asset|remove_asset|delete_asset|\\.post\\(|\\.put\\(|\\.delete\\(' (expected: zero matches)"
        status: pass
    human_judgment: false

duration: 2min
completed: 2026-07-07
status: complete
---

# Phase 7 Plan 1: Sync-Diffing Engine Core Summary

**Pure offline dry-run diff engine (`auraframes/sync.py`): recursive image scanner with base64-MD5 dedup, plus a `compute_plan()` diff function that classifies frame assets into upload/delete/unchanged/frame_no_hash by content hash alone.**

## Performance

- **Duration:** 2min
- **Started:** 2026-07-07T07:45:XX+02:00
- **Completed:** 2026-07-07T07:46:54+02:00
- **Tasks:** 2 completed
- **Files modified:** 2 (both created)

## Accomplishments
- `scan_directory(root)` recursively walks a directory tree, hashes only `.jpg/.jpeg/.png/.heic` files (case-insensitive) via the exact `S3Client.get_md5` base64-MD5 convention, counts every other file as `skipped_non_image` without erroring, and collapses byte-identical files across folders into one hash key (dedup to a single logical want).
- `compute_plan(local_hashes, frame_assets, skipped_non_image=0)` is a pure diff function (no I/O, no mutation) mirroring `resolve_frame`'s dataclass-result shape: it matches local demand against frame assets count-for-count (multiset), producing `to_upload` (unmatched local hashes), `to_delete` (surplus/unmatched frame assets), `unchanged` (matched pairs), and `frame_no_hash` (hashless assets like videos, excluded from delete).
- Structural dry-run safety verified: no mutating call token (`put_object`, `upload_file`, `select_asset`, `remove_asset`, `delete_asset`, or raw `.post(`/`.put(`/`.delete(`) exists anywhere in `sync.py`.
- 11 offline unit tests in `tests/test_sync_engine.py`, all passing with zero network access; full project test suite (41 tests, `-m "not live"`) still green.

## Task Commits

Each task was committed atomically:

1. **Task 1: Recursive image scanner + local hashing + dedup** - `8d93f98` (feat)
2. **Task 2: Pure compute_plan diff (upload/delete/unchanged, multiset) + SyncPlan** - `e2fe932` (feat)

**Plan metadata:** (this commit, docs: complete plan)

_Note: Both tasks were TDD (`tdd="true"`) — for each, the test file was written and confirmed failing (RED, via `ModuleNotFoundError`/`ImportError`) before the corresponding implementation was added and confirmed passing (GREEN), then committed as a single `feat` commit per task rather than separate `test`/`feat` commits (see TDD Gate Compliance note below)._

## Files Created/Modified
- `auraframes/sync.py` - `ELIGIBLE_EXTENSIONS`, `ScanResult`, `scan_directory()`, `SyncPlan`, `compute_plan()` — the pure, offline-testable core of the dry-run sync engine
- `tests/test_sync_engine.py` - offline unit-test suite (pytest `tmp_path` fixture, `Asset.model_construct`) covering every `<behavior>` bullet from both tasks

## Decisions Made
- No deviations from the plan's algorithm design — implemented `scan_directory` and `compute_plan` exactly as specified in `07-01-PLAN.md`'s `<action>` blocks.
- Chose to commit each task's RED+GREEN cycle as a single `feat` commit (test file + implementation together) rather than splitting into separate `test(...)` then `feat(...)` commits, since the plan's task structure describes test-writing and implementation as one unified `<action>` per task. RED was still verified (tests confirmed failing via `ImportError` before implementation existed) before GREEN.

## Deviations from Plan

None - plan executed exactly as written. Both tasks' `<behavior>`, `<action>`, and `<verify>` requirements were implemented and verified precisely as specified; no bugs, missing functionality, or blocking issues were encountered.

## TDD Gate Compliance

Both tasks carry `tdd="true"`, but the plan's `type` frontmatter is `execute` (not `tdd`), so plan-level TDD gate enforcement (mandatory separate `test(...)`/`feat(...)` git commits) does not apply. Per-task RED/GREEN discipline was still followed procedurally: for each task, `uv run pytest tests/test_sync_engine.py -x -q` was run against the test file before the corresponding code existed (confirmed `ImportError`/`ModuleNotFoundError` failures), and again after implementation (confirmed all-green), before committing. Each task's test + implementation were committed together as one `feat(07-01): ...` commit rather than as two separate `test`/`feat` commits — a reasonable reading of the plan's single `<action>` block per task, and consistent with the task commit protocol's "commit after task completes" guidance. No functional gap results from this: git history for `8d93f98` and `e2fe932` each include the full test file + the code that makes those specific tests pass.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required. Zero network access, zero credentials needed for this plan's entire test suite.

## Next Phase Readiness
- `auraframes/sync.py`'s `scan_directory`/`compute_plan` pair is ready for Plan 07-02/07-03 to wire into a `sync` CLI subcommand (per `07-PATTERNS.md`'s `cli.py` `run_sync()`/`build_parser()` guidance) and for the one-time live hash-convention validation (D-09).
- No blockers. `compute_plan`'s pure, dependency-free shape means the CLI-layer plan (07-02/07-03) can call it directly with `Aura.get_all_assets(frame_id)` results and `scan_directory(dir).local_hashes` with no further engine work needed.

---
*Phase: 07-sync-diffing-engine-dry-run-only*
*Completed: 2026-07-07*

## Self-Check: PASSED

- FOUND: auraframes/sync.py
- FOUND: tests/test_sync_engine.py
- FOUND commit: 8d93f98
- FOUND commit: e2fe932
