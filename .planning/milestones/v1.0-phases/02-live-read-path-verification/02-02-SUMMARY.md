---
phase: 02-live-read-path-verification
plan: 02
subsystem: testing
tags: [pytest, pagination, exif, piexif, geopy, nominatim, live-api, aura, pushd]

# Dependency graph
requires:
  - phase: 02-live-read-path-verification
    provides: "session aura login fixture, live pytest marker, raise_for_status transport, READ-01/02 (02-01)"
provides:
  - "get_all_assets(frame_id, limit=1000, page_delay=0.0): parametrized cursor drain, no always-on 1s/page sleep"
  - "frameApi.get_assets raises RuntimeError on the error key (no silent pass) — drifted asset page can't return green"
  - "exif.py hardened: compliant Nominatim UA, tolerant geocode except, re-raising EXIF-write except (no 0-byte saves)"
  - "READ-03 pagination + READ-04 download/EXIF-read-back live tests (credential-gated, auto-skip)"
affects: [phase-3-verification-report]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Drive the real production pagination helper from the test (limit=total//2 forces the cursor branch) rather than re-implementing it"
    - "EXIF read-back from disk as download proof that a no-op write cannot fake"
    - "Differential except handling: tolerable failure (geocode) returns None; fatal failure (EXIF write) re-raises"

key-files:
  created: []
  modified:
    - auraframes/aura.py
    - auraframes/api/frameApi.py
    - auraframes/exif.py
    - tests/test_read_path.py

key-decisions:
  - "get_all_assets gains limit + conditional page_delay; default removes the always-on 1s/page sleep while keeping opt-in throttle for production callers (D-05)"
  - "frameApi.get_assets raises RuntimeError (message or error) on the error key, mirroring 02-01's accountApi edit (D-06)"
  - "geocode except is TOLERANT (log + return None, GPS is conditional); piexif.insert except is FATAL (re-raise) so a corrupt/non-JPEG body never saves a 0-byte file (D-11)"
  - "lat/long swap in build_gps_ifd left unfixed — recorded as Phase 3 drift, not an MVP fix (T-02-09 accept)"
  - "READ-04 asset selection: first image asset with location_name -> first image asset -> first asset; image asset = truthy thumbnail_url, no video_url/is_live (avoids Pitfall-5 httpx.get(None)/non-JPEG)"

patterns-established:
  - "Live-API tests stay credential-gated and skip cleanly so default uv run pytest stays green"
  - "Pagination proven indirectly-but-airtight: len(assets) == total_asset_count after a forced multi-page drain"

requirements-completed: [READ-03, READ-04]

# Metrics
duration: 8min
completed: 2026-06-29
---

# Phase 2 Plan 02: Paginated Fetch + Image-Download-with-EXIF Summary

**Parametrized the real get_all_assets cursor helper and hardened the asset-error/EXIF-write/geocoder trust edges, then added READ-03 (multi-page drain proven by len==total) and READ-04 (download one image, read DateTimeOriginal back from disk) as credential-gated live tests that skip cleanly without creds.**

## Performance

- **Duration:** ~8 min
- **Completed:** 2026-06-29
- **Tasks:** 2
- **Files modified:** 4 (0 created, 4 modified)

## Accomplishments
- `get_all_assets` is now `get_all_assets(frame_id, limit=1000, page_delay=0.0)`: it threads `limit` into both `frame_api.get_assets` calls and replaced the unconditional `time.sleep(1)` with a guarded `if page_delay: time.sleep(page_delay)` (D-05). Default behavior is unchanged except the removed per-page stall, so a test can pass a small `limit` to force the cursor branch on any account size.
- `frameApi.get_assets` now raises `RuntimeError` (including the API's `message`/`error`) on the `error` branch instead of the silent `pass` (D-06). Combined with 02-01's transport `raise_for_status`, a drifted asset page can no longer masquerade as success. The `limit`/`cursor` signature and `update_frame`'s `.dict(exclude_unset=True)` were left untouched.
- `exif.py` hardened (D-11): Nominatim UA is now `auraframes-python-client/1.0` (ToS-compliant), the `_lookup_gps` geocode except is `except Exception` and stays TOLERANT (log + `return None`, GPS is conditional), and the `write_exif` `piexif.insert` except is `except Exception` that RE-RAISES so a corrupt/non-JPEG body fails loudly in `export.get_image_from_asset` rather than saving a 0-byte file. No bare `except:` remains in the module.
- READ-03 (`test_read_03_pagination`) drives the real `aura.get_all_assets(frame.id, limit=max(1, total//2))`, asserts `limit < total` (guarantees the cursor branch runs), and asserts `len(assets) == total_asset_count` — an indirect-but-airtight proof the loop traversed and stitched every page. It `pytest.skip`s with a documented message when the first frame has <2 assets (A2 data gap).
- READ-04 (`test_read_04_download_exif`) selects an asset via *first image asset with location_name -> first image asset -> first asset* (image asset = truthy `thumbnail_url`, no `video_url`/`is_live`, avoiding the Pitfall-5 `httpx.get(None)`/non-JPEG crash), downloads into a clean `tmp_path`, globs the single written file (the function does not return the path), asserts it is non-empty, and reads `DateTimeOriginal` back from disk via `get_readable_exif`. GPS is asserted only when `location_name` is set AND the GPS IFD is populated; otherwise it logs the skip and does not fail.

## Task Commits

Each task was committed atomically:

1. **Task 1: Parametrize pagination + surface asset error + harden EXIF/geocoder** - `dc7a08d` (feat)
2. **Task 2: READ-03 pagination + READ-04 download/EXIF read-back live tests** - `840cef7` (test)

## Files Created/Modified
- `auraframes/aura.py` - `get_all_assets` parametrized with `limit`/`page_delay`; passes `limit` into both `get_assets` calls; removed the unconditional 1s/page sleep.
- `auraframes/api/frameApi.py` - `get_assets` raises `RuntimeError` on the `error` key (was a silent `pass`).
- `auraframes/exif.py` - Compliant Nominatim UA; tolerant geocode `except Exception` (returns None); fatal `write_exif` `except Exception` that re-raises.
- `tests/test_read_path.py` - Added `_is_image_asset` helper, `test_read_03_pagination`, `test_read_04_download_exif` (both `@pytest.mark.live`).

## Decisions Made
- `get_all_assets` keeps a `page_delay` opt-in so production callers can still throttle, but the default no longer stalls — the test path drains pages immediately.
- The two `exif.py` excepts are treated asymmetrically on purpose: geocode is tolerable (GPS is conditional per D-09), EXIF-write is fatal (a silent 0-byte save would defeat READ-04's read-back proof).
- The `build_gps_ifd` lat/long swap was intentionally NOT fixed (T-02-09 accept) — GPS is still readable so READ-04 passes; the swap is recorded as Phase 3 drift.
- READ-03 proves pagination indirectly via `len == total_asset_count` rather than re-implementing the cursor loop, so the test exercises the real production code path.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None. Baseline before this plan was `9 passed, 2 skipped`; after appending the two live tests the default credential-less run is `9 passed, 4 skipped`, and `uv run pytest -q -m live --collect-only` lists all four READ tests.

## Verification Evidence
- `uv run python -c "import auraframes.aura, auraframes.api.frameApi, auraframes.exif"` — clean.
- `grep -n "time.sleep(1)" auraframes/aura.py` → no match (unconditional sleep removed).
- `grep -n "auraframes-python-client/1.0" auraframes/exif.py` → matches; `grep -nE "except\s*:" auraframes/exif.py` → no match (no bare except remains).
- `uv run pytest -q` (no creds) → `9 passed, 4 skipped`.
- `uv run pytest -q -m live --collect-only` → `test_read_01_login`, `test_read_02_list_frames`, `test_read_03_pagination`, `test_read_04_download_exif`.

## Threat Register Outcomes
- T-02-05 (silent asset-error `pass`) — mitigated: `get_assets` now raises on the error key.
- T-02-06 (0-byte EXIF save) — mitigated: `write_exif` re-raises; READ-04 read-back from disk is the proof.
- T-02-07 (ToS-violating geocoder UA) — mitigated: UA is now `auraframes-python-client/1.0`.
- T-02-08 (self-inflicted DoS on a large frame) — mitigated: READ-03 uses `limit = max(1, total // 2)` for a bounded 2-3 page request count.
- T-02-09 (GPS lat/long swap) — accepted: out of MVP scope, recorded as Phase 3 drift.

## Known Stubs
None.

## Next Phase Readiness
- READ-01..READ-04 are all wired and credential-gated. The live PASS evidence (multi-page cursor traversal; saved image with readable `DateTimeOriginal`, and whether the GPS branch ran) is the deferred human-check gathered as Phase 3 verification evidence — per plan, not run here without real credentials.
- Phase 3 drift to record: the `build_gps_ifd` lat/long swap (T-02-09), and any Nominatim flakiness / non-JPEG frames observed during the live run (no retry/backoff was added).

## Self-Check: PASSED

---
*Phase: 02-live-read-path-verification*
*Completed: 2026-06-29*
