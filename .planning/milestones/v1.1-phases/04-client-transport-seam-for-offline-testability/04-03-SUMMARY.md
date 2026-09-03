---
phase: 04-client-transport-seam-for-offline-testability
plan: 03
subsystem: testing
tags: [httpx, mocktransport, pytest, offline-testing]

# Dependency graph
requires:
  - phase: 04-client-transport-seam-for-offline-testability (Plan 01)
    provides: "Client(transport=...) and Aura(client=...) additive DI seam"
  - phase: 04-client-transport-seam-for-offline-testability (Plan 02)
    provides: "5 sanitized fixture JSON files + fixture-validity guard test"
provides:
  - "tests/offline.py — make_router()/offline_aura() reusable offline test harness"
  - "tests/test_offline_read_path.py — 5-test offline mirror of test_read_path.py, default (unmarked) suite"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Path + query-param MockTransport router (matches on fully-resolved /v5-prefixed path, branches assets.json pagination on cursor truthiness)"
    - "Per-path overrides dict checked before default router branches, letting individual tests force error responses without editing shared router logic"

key-files:
  created:
    - tests/offline.py
    - tests/test_offline_read_path.py
  modified: []

key-decisions:
  - "offline_aura()'s overrides mechanism is a plain dict keyed by the fully-resolved path (e.g. '/v5/frames/{id}/assets.json'), checked before the default routing branches — simplest option that satisfies the plan's 'exact mechanism is your call' latitude"
  - "test_offline_http_status_error_raises builds its own one-off Client(transport=MockTransport(...)) rather than going through offline_aura(), since it only needs Client's raise_for_status behavior, not a full Aura instance"

requirements-completed: [R4-HARNESS, R4-OFFLINE-TESTS, R4-LIVE-UNCHANGED]

coverage:
  - id: D1
    description: "tests/offline.py exposes make_router()/offline_aura() as plain module-level functions, correctly routes /v5-prefixed paths, and distinguishes the two-page asset pagination fixture by cursor truthiness"
    requirement: "R4-HARNESS"
    verification:
      - kind: unit
        ref: "uv run python -c \"from tests.offline import offline_aura; a=offline_aura(); frames=a.frame_api.get_frames(); assert len(frames)==1; assets=a.get_all_assets(frames[0].id, limit=1); assert len(assets)==2; print('PASS')\""
        status: pass
    human_judgment: false
  - id: D2
    description: "tests/test_offline_read_path.py's 5 unmarked tests (login headers, frame hydration, pagination drain, business-rule RuntimeError, HTTPStatusError) all pass offline with no network/credentials"
    requirement: "R4-OFFLINE-TESTS"
    verification:
      - kind: unit
        ref: "uv run pytest tests/test_offline_read_path.py -v"
        status: pass
    human_judgment: false
  - id: D3
    description: "tests/test_read_path.py and tests/conftest.py remain byte-identical (no diff); the @live suite still skips cleanly without credentials and the full default pytest run exits 0"
    requirement: "R4-LIVE-UNCHANGED"
    verification:
      - kind: unit
        ref: "git diff --stat tests/conftest.py tests/test_read_path.py (empty); AURA_EMAIL= AURA_PASSWORD= uv run pytest tests/test_read_path.py -v (4 skipped); uv run pytest (23 passed)"
        status: pass
    human_judgment: false

duration: 3min
completed: 2026-07-04
status: complete
---

# Phase 4 Plan 3: Offline Transport Harness + Offline Read-Path Tests Summary

**Built `tests/offline.py` (MockTransport router + `offline_aura()` helper) and `tests/test_offline_read_path.py` (5 unmarked tests) that together exercise the full `Aura`/`*Api`/`Client` read-path stack — login headers, frame hydration, cursor pagination, and both error-raise mechanisms — entirely offline via httpx's own `MockTransport`, with zero modification to the existing `@live` drift-oracle suite.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-07-04T16:44:18Z
- **Completed:** 2026-07-04T16:47:30Z (approx)
- **Tasks:** 2
- **Files modified:** 2 (both new)

## Accomplishments
- `tests/offline.py` defines `FIXTURES_DIR`, `_load(name)`, `make_router(overrides=None)`, and `offline_aura(overrides=None)` as plain module-level functions (not pytest fixtures) — verified end-to-end: `offline_aura()` drives `get_frames()` to 1 hydrated `Frame` and `get_all_assets(..., limit=1)` to 2 distinct assets across the fixture pages, all through the `Aura(client=Client(transport=MockTransport(router)))` DI chain from Plan 01.
- The router matches on the fully-resolved `/v5`-prefixed path (`/v5/login.json`, `/v5/frames.json`) and branches the `assets.json` endpoint on `request.url.params.get("cursor")` truthiness (not key presence), correctly serving `assets_page1.json` on the first call and `assets_page2.json` once a cursor is present — matching RESEARCH.md Pitfalls 2 and 3 exactly.
- `tests/test_offline_read_path.py` adds 5 unmarked test functions mirroring `test_read_path.py`'s assertion shapes: login header-set, `get_frames()` hydration, `get_all_assets()` pagination drain (2 distinct asset ids), a business-rule `RuntimeError` via a router override on the assets endpoint, and an `httpx.HTTPStatusError` via `Client`'s unconditional `raise_for_status()` on a mocked 404 — exercising both distinct error-raise mechanisms identified in RESEARCH.md Pattern 3.
- `tests/test_read_path.py` and `tests/conftest.py` remain byte-identical (confirmed via `git diff --stat`, empty) — the `@live` suite continues to serve as the drift oracle, skipping cleanly with credentials unset and passing when a local `.env` supplies them.
- Full default `uv run pytest` run (no `-m` filter): 23 passed (4 fixture-validity + 10 import + 5 new offline + 4 live, since this checkout's `.env` supplies live credentials) — no regression to the pre-existing green state.

## Task Commits

Each task was committed atomically:

1. **Task 1: Build the offline harness (tests/offline.py)** - `513a77b` (feat)
2. **Task 2: Offline read-path test module mirroring test_read_path.py** - `efa57e7` (test)

**Plan metadata:** (pending — final docs commit follows this summary)

## Files Created/Modified
- `tests/offline.py` - `FIXTURES_DIR`, `_load(name)`, `make_router(overrides=None)` (path+query-param router with per-path override support), `offline_aura(overrides=None)` (builds the full DI chain)
- `tests/test_offline_read_path.py` - 5 unmarked test functions: `test_offline_login_sets_auth_headers`, `test_offline_get_frames_hydrates_frame`, `test_offline_get_all_assets_drains_pagination`, `test_offline_get_assets_raises_on_error_envelope`, `test_offline_http_status_error_raises`

## Decisions Made
- `offline_aura()`'s `overrides` mechanism is a plain `dict[str, httpx.Response]` keyed by the fully-resolved path, checked before the router's default branches — the plan explicitly left the exact override mechanism to the executor's judgment, and a plain dict is the simplest option that satisfies "let a test force any endpoint to return the 200-with-error-body shape or a non-2xx status without editing the router's default branches."
- `test_offline_http_status_error_raises` builds its own one-off `Client(transport=MockTransport(...))` directly rather than routing through `offline_aura()`, since it only needs to prove `Client.raise_for_status()` fires through the mock — no `Aura`/`*Api` layer is needed for that assertion, keeping the test minimal and matching RESEARCH.md's own verified code example shape.

## Deviations from Plan

None - plan executed exactly as written. Both tasks matched their `<action>` blocks; all acceptance criteria and the plan's `<verify>` commands passed on the first attempt.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- This was the final plan (wave 2 of 2) in Phase 4. The `Aura <- Client <- transport` DI seam (Plan 01), sanitized fixture set + validity guard (Plan 02), and offline harness + tests (this plan) together complete the phase's goal: most of `test_read_path.py`'s assertions now run offline with zero credentials/network, while `tests/test_read_path.py`/`tests/conftest.py` remain completely untouched as the drift oracle.
- No blockers. Phase 4 is ready for `/gsd-transition` or milestone completion review.

---
*Phase: 04-client-transport-seam-for-offline-testability*
*Completed: 2026-07-04*

## Self-Check: PASSED

- FOUND: tests/offline.py
- FOUND: tests/test_offline_read_path.py
- FOUND: .planning/phases/04-client-transport-seam-for-offline-testability/04-03-SUMMARY.md
- FOUND: 513a77b (Task 1 commit)
- FOUND: efa57e7 (Task 2 commit)
