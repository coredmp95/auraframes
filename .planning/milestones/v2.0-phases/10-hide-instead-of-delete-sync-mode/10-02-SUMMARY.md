---
phase: 10-hide-instead-of-delete-sync-mode
plan: 02
subsystem: api
tags: [sync, diff-engine, visibility, asset_settings, pydantic, pytest]

requires:
  - phase: 10-01
    provides: the live-confirmed read signal (asset_settings, not Asset.selected) and the filter=all requirement
provides:
  - FrameApi.get_assets returns hidden assets (filter=all) with true per-frame visibility joined onto Asset.selected
  - SyncPlan.to_reshow and SyncPlan.already_hidden
  - compute_plan 4-way visibility classification, pure and mode-agnostic
affects: [10-03, 10-04]

actuals:
  tokens: 6200
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Per-frame state is joined onto the model once at the API boundary, so callers read one honest field"

key-files:
  created: []
  modified:
    - auraframes/api/frameApi.py
    - auraframes/sync.py
    - tests/test_sync_engine.py
    - tests/test_offline_read_path.py

key-decisions:
  - "The asset_settings join happens in get_assets, not in compute_plan — one boundary fix instead of a signal every caller must remember to re-derive"
  - "to_delete keeps its name as the mode-agnostic removal-candidate list (D-07)"

patterns-established:
  - "compute_plan stays pure and never consults removal_mode — asserted by a purity check"

requirements-completed: [HIDE-02, HIDE-08]

coverage:
  - id: D1
    description: "get_assets sends filter=all so hidden assets stay in the listing"
    requirement: "HIDE-02"
    verification:
      - kind: unit
        ref: "tests/test_offline_read_path.py::test_offline_get_assets_requests_filter_all"
        status: pass
    human_judgment: false
  - id: D2
    description: "Asset.selected carries this frame's visibility, joined from asset_settings"
    requirement: "HIDE-02"
    verification:
      - kind: unit
        ref: "tests/test_offline_read_path.py::test_offline_get_assets_joins_per_frame_visibility_from_asset_settings"
        status: pass
      - kind: manual_procedural
        ref: "live read against frame c063b384-… — exactly the 3 known-hidden probe assets read selected=False"
        status: pass
    human_judgment: false
  - id: D3
    description: "compute_plan classifies frame assets 4 ways and never re-uploads a hidden match"
    requirement: "HIDE-02, HIDE-08"
    verification:
      - kind: unit
        ref: "tests/test_sync_engine.py (6 classification tests)"
        status: pass
    human_judgment: false

duration: 20min
completed: 2026-08-25
status: complete
---

# Phase 10 / Plan 02: Visibility-aware read + diff — Summary

**The diff engine can now see visibility: hidden assets stay in the listing, `asset.selected` finally means what it says, and every frame asset is classified re-show / unchanged / removal-candidate / already-hidden.**

## Performance

- **Duration:** ~20 min
- **Tasks:** 3 of 3
- **Files modified:** 4

## Accomplishments

- `FrameApi.get_assets` sends `filter='all'`. Live-verified this matters: without it the server returns 154 assets, with it 157 — the 3 hidden ones were being silently dropped, which would make a hidden photo look absent and get re-uploaded every sync.
- `get_assets` joins the response's parallel `asset_settings` array onto each `Asset.selected`, so downstream code reads one honest per-frame visibility field. Live-verified: exactly the 3 known-hidden probe assets come back `selected=False`.
- `SyncPlan` gained `to_reshow` and `already_hidden`; `compute_plan` does the 4-way classification, stays pure, and never consults the removal mode.
- 9 new offline tests (3 boundary, 6 classification). Full suite: 184 passed.

## Task Commits

1. **Task 1: filter=all + asset_settings join** — `5bfb79c` (feat)
2. **Task 2/3: 4-way classification** — `4e67d44` (test, RED) → `7d4cf20` (feat, GREEN)

## Decisions Made

- **The join lives in `get_assets`, not `compute_plan`.** Plan 10-02 assumed `Asset.selected` was already the visibility signal; Plan 10-01 proved it is not. Fixing it once at the API boundary means `compute_plan`'s design — keying on `asset.selected` — survives verbatim, the return signature stays `tuple[list[Asset], str]` as the plan required, and no caller has to remember to re-derive visibility. `Asset.selected` was declared but never consumed anywhere in the codebase, so overwriting it broke nothing.

## Deviations from Plan

### 1. [Incorrect plan assumption, corrected by 10-01] `Asset.selected` is not per-frame visibility

- **Found during:** Plan 10-01's live probe; applied here.
- **Issue:** Tasks 1–3 were written against `asset.selected` as the visibility flag. Live, that field stays `true` while the photo is hidden — real visibility is in the parallel `asset_settings` array. Executing the plan verbatim would have produced an engine that classifies every asset as visible forever and **silently never hides anything** — passing its own unit tests the whole time.
- **Fix:** Added `_apply_asset_settings` and called it from `get_assets`, plus 3 offline tests for the boundary. Task 1's stated constraints (no signature change, no Asset model change) are still honoured.
- **Verification:** offline tests + a live read confirming only the 3 hidden probe assets report `selected=False`.
- **Committed in:** `5bfb79c`

**Total deviations:** 1 (assumption correction inherited from 10-01)
**Impact on plan:** Tasks 2 and 3 executed exactly as written. No scope creep.

## Issues Encountered

- `tests/test_read_path.py::test_read_03_pagination` still fails — pre-existing `num_assets` (171) vs drained-pages (157) mismatch, logged in STATE.md. Unrelated to this plan; it is a live-data reconciliation gap, not a regression.

## Next Phase Readiness

Plan 10-03 can wire the executor: `to_reshow` → `select_asset`, `to_delete` → `exclude_asset` (default) or `delete_asset` (`--hard-delete`), both using the live-confirmed batch shape `{"assets":[{"asset_id":…},…]}`. Note `FrameApi.exclude_asset` still accepts only a single `AssetPartialId` and must be widened to a list.
