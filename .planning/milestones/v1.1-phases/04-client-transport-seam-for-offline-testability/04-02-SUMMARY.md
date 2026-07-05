---
phase: 04-client-transport-seam-for-offline-testability
plan: 02
subsystem: testing
tags: [pydantic, pytest, fixtures, httpx-mocktransport]

# Dependency graph
requires:
  - phase: 04-client-transport-seam-for-offline-testability (Plan 01)
    provides: "Client(transport=...) and Aura(client=...) additive DI seam"
provides:
  - "5 sanitized, model-valid fixture JSON files under tests/fixtures/ covering login, frames, two-page paginated assets, and a business-rule error envelope"
  - "tests/test_fixtures_validity.py — default-suite pytest guarding fixture/model drift"
affects: [04-03-offline-transport-harness]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Fixture files authored directly against pydantic model requiredness (not hand-guessed from API memory), then verified via direct model hydration before committing"

key-files:
  created:
    - tests/fixtures/login.json
    - tests/fixtures/frames.json
    - tests/fixtures/assets_page1.json
    - tests/fixtures/assets_page2.json
    - tests/fixtures/error_envelope.json
    - tests/test_fixtures_validity.py
  modified: []

key-decisions:
  - "Used entirely synthetic/fake data (no real recorded API response) since no live capture was available for this phase — the safer sanitization posture per RESEARCH.md, since there is no real secret to ever leak"
  - "assets_page1.json/assets_page2.json distinguished by next_page_cursor truthiness (non-null token vs null) and distinct asset ids (asset-fake-001 vs asset-fake-002), matching the query-param-based routing Plan 03 will build"

patterns-established:
  - "Fixture-validity test pattern: iterate tests/fixtures/*.json matched to their pydantic model, asserting bare construction does not raise — catches an accidental required-field trim at the fixture-authoring layer instead of deep inside an unrelated offline test"

requirements-completed: [R4-FIXTURES, R4-FIXTURE-VALIDITY]

coverage:
  - id: D1
    description: "5 sanitized fixture JSON files (login, frames, assets_page1, assets_page2, error_envelope) exist, are valid JSON, and hydrate their corresponding pydantic models without raising"
    requirement: "R4-FIXTURES"
    verification:
      - kind: unit
        ref: "tests/test_fixtures_validity.py::test_login_fixture_hydrates_user"
        status: pass
      - kind: unit
        ref: "tests/test_fixtures_validity.py::test_frames_fixture_hydrates_frame"
        status: pass
      - kind: unit
        ref: "tests/test_fixtures_validity.py::test_assets_page1_fixture_hydrates_asset"
        status: pass
      - kind: unit
        ref: "tests/test_fixtures_validity.py::test_assets_page2_fixture_hydrates_asset"
        status: pass
    human_judgment: false
  - id: D2
    description: "assets_page1.json/assets_page2.json are distinguishable only by next_page_cursor (truthy vs null) with distinct asset ids, ready for Plan 03's pagination router"
    requirement: "R4-FIXTURES"
    verification:
      - kind: unit
        ref: "manual verify command: next_page_cursor truthy/null + distinct asset id assertions in plan's <verify> block"
        status: pass
    human_judgment: false
  - id: D3
    description: "No fixture file contains a real recorded secret, cookie, GPS coordinate, or account identifier — all values are synthetic/obviously-fake"
    requirement: "R4-FIXTURES"
    verification:
      - kind: other
        ref: "grep -rn hunter2 tests/fixtures/ — zero matches"
        status: pass
    human_judgment: false

duration: 2min
completed: 2026-07-04
status: complete
---

# Phase 4 Plan 2: Fixture JSON Set + Fixture-Validity Test Summary

**Sanitized, model-valid fixture JSON set (login/frames/2-page-assets/error) plus a dedicated pytest that hydrates every fixture against `User`/`Frame`/`Asset` to guard against future accidental field-trim regressions.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-07-04T16:40:39Z
- **Completed:** 2026-07-04T16:42:19Z
- **Tasks:** 2 completed
- **Files modified:** 6 (5 fixtures + 1 test file)

## Accomplishments
- Authored 5 entirely-synthetic fixture JSON files (`login.json`, `frames.json`, `assets_page1.json`, `assets_page2.json`, `error_envelope.json`) satisfying every required field on `User`, `Frame`, and `Asset` with no real recorded API data
- Verified every fixture hydrates its corresponding pydantic model without raising, both manually (ad-hoc `uv run python -c` check) and via a permanent committed test
- Built the two-page asset pair so Plan 03's pagination router/test can distinguish pages purely by `next_page_cursor` truthiness and distinct asset ids (`asset-fake-001` vs `asset-fake-002`)
- Added `tests/test_fixtures_validity.py` (unmarked, part of the default pytest run) so a future accidental required-field trim in any fixture fails loudly and immediately at this file, not deep inside an unrelated offline test

## Task Commits

Each task was committed atomically:

1. **Task 1: Author sanitized, model-valid fixture JSON files** - `b3356f6` (feat)
2. **Task 2: Fixture-validity pytest — every fixture must hydrate its model** - `ad78504` (test)

**Plan metadata:** (pending — final docs commit follows this summary)

## Files Created/Modified
- `tests/fixtures/login.json` - `AccountApi.login` response shape (`{"result": {"current_user": {...User...}}}`), includes a fake `auth_token`
- `tests/fixtures/frames.json` - `FrameApi.get_frames` response shape (`{"frames": [...]}`), one Frame with all ~43 required fields populated
- `tests/fixtures/assets_page1.json` - `FrameApi.get_assets` page 1 (`next_page_cursor` = non-null fake token, asset id `asset-fake-001`)
- `tests/fixtures/assets_page2.json` - `FrameApi.get_assets` page 2 (`next_page_cursor` = `null`, asset id `asset-fake-002`)
- `tests/fixtures/error_envelope.json` - `{"error": "not_found", "message": "Resource not found"}` shape matching both `accountApi.py`/`frameApi.py`'s `.get('error')`/`.get('message')` raise sites
- `tests/test_fixtures_validity.py` - 4 test functions hydrating `User`, `Frame`, and `Asset` (2x, one per asset page) directly from fixture JSON, asserting no `ValidationError`

## Decisions Made
- Used entirely synthetic/fake data throughout rather than fabricating-then-scrubbing a real API response — there was no real recorded response available for this phase, and synthetic-from-the-start is the safer posture since no real secret ever exists to leak (RESEARCH.md Security Domain)
- Location/GPS fields (`location`, `location_name`) intentionally omitted on both asset fixtures (both `Optional`) rather than populated-then-redacted, per the plan's explicit instruction, to avoid ever needing to scrub a real coordinate

## Deviations from Plan

None - plan executed exactly as written. Both fixture-authoring and the validity test matched the plan's `<action>` blocks field-for-field; no missing-field surprises occurred because the fixtures were authored directly from the model source (`auraframes/models/user.py`, `frame.py`, `asset.py`) as instructed, and verified against the real pydantic models before committing.

## Issues Encountered

None. A manual sanity check (per Task 2's acceptance criteria) confirmed the fixture-validity test is not vacuous: deleting `data_uti` from a copy of `assets_page1.json`'s asset dict and re-constructing `Asset(**asset_data)` raised `pydantic_core._pydantic_core.ValidationError` as expected — this check was ad-hoc (`uv run python -c ...`) and not committed to the suite, per the plan's instruction.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Plan 03 (offline transport harness) can now build `tests/offline.py`'s router and `offline_aura()` helper directly against this fixture set — the `/v5`-prefixed path + query-param-based pagination routing design from RESEARCH.md Pattern 2 is fully supported by `assets_page1.json`/`assets_page2.json`'s `next_page_cursor` shape.
- `tests/test_fixtures_validity.py` will continue to run in the default (unmarked) `pytest` suite alongside Plan 03's new offline tests, providing an early-warning guard if a future edit to any fixture accidentally drops a required field.
- No blockers.

---
*Phase: 04-client-transport-seam-for-offline-testability*
*Completed: 2026-07-04*

## Self-Check: PASSED

All 6 created files verified present on disk; both task commits (`b3356f6`, `ad78504`) verified present in git log.
