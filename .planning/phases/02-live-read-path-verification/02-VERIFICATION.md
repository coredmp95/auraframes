---
phase: 02-live-read-path-verification
verified: 2026-06-29T00:00:00Z
status: passed
score: 10/10 must-haves verified
overrides_applied: 0
re_verification: false
---

# Phase 02: Live Read-Path Verification — Verification Report

**Phase Goal:** Login, list frames, fetch assets, and download one image with EXIF verified against the live API.
**Verified:** 2026-06-29
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Credential-less `uv run pytest` passes with live tests skipped | VERIFIED | Direct run: `9 passed, 4 deselected in 0.19s` |
| 2 | Live login injects `x-token-auth` + `x-user-id` onto the session (READ-01) | VERIFIED | `aura.py:45-48` adds headers; test asserts both truthy; live evidence PASS |
| 3 | Live `get_frames()` returns a non-empty list with name+id printed (READ-02) | VERIFIED | `frameApi.py:13-19`; test asserts non-empty `list[Frame]`; live evidence: "«frame-name-redacted»" listed |
| 4 | After live login, no plaintext password or auth_token appears in `logs/file_*.log` (D-07) | VERIFIED | `_redact()` masks `password`/`auth_token`/`x-token-auth` in all 4 request+response log paths; live evidence: 0 occurrences, redaction marker confirmed |
| 5 | A failed/drifted API response raises instead of silently hydrating a model (D-06) | VERIFIED | `raise_for_status()` in all 4 client methods; `accountApi.login` raises `RuntimeError`; `frameApi.get_assets` raises `RuntimeError` on error key |
| 6 | `get_all_assets(frame_id, limit=N)` drains every page via cursor loop (D-05) | VERIFIED | `aura.py:55-64`: signature `limit: int = 1000, page_delay: float = 0.0`; `while cursor:` loop threads `limit` through both calls |
| 7 | Live `get_all_assets` fetches assets across >1 page with `len == total` (READ-03, D-04) | VERIFIED | Test drives `get_all_assets(frame.id, limit=max(1,total//2))`, asserts `len(assets)==total`; live evidence: 77 assets across multiple pages |
| 8 | Live download saves an image; `DateTimeOriginal` readable back from disk (READ-04, D-09) | VERIFIED | Test globs saved file from `tmp_path`, calls `get_readable_exif`, asserts `DateTimeOriginal`; live evidence PASS |
| 9 | When asset has location data and geocoding succeeds, GPS IFD is readable | VERIFIED | GPS assertion gated on `asset.location_name and readable.get("GPS")`; live evidence: GPS IFD readable for "«location-redacted»" |
| 10 | EXIF-write failure raises; geocode failure is tolerated and logged (D-11) | VERIFIED | `write_exif`: `except Exception: raise`; `_lookup_gps`: `except Exception: logger.info(...); return None`; no bare `except:` remains |

**Score:** 10/10 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `tests/conftest.py` | Session-scoped `aura` fixture that skips without creds | VERIFIED | `scope="session"` at line 13; `pytest.skip` when env vars unset; `Aura().login()` at line 31 |
| `tests/test_read_path.py` | READ-01..04 live tests | VERIFIED | All 4 functions decorated `@pytest.mark.live`; substantive assertions confirmed |
| `pyproject.toml` | `live` marker registration under `[tool.pytest.ini_options]` | VERIFIED | Section present; marker line: `"live: hits the live Aura API..."` |
| `auraframes/client.py` | `raise_for_status` in all 4 methods + `_redact()` applied | VERIFIED | 4 `raise_for_status` hits (lines 61, 73, 85, 97); `_redact` in request body (post/put) and response body (all 4) |
| `.gitignore` | `logs/`, `cache/`, `asset_images/` entries | VERIFIED | All 3 directory entries present |
| `auraframes/aura.py` | `get_all_assets` parametrized with `limit` and `page_delay` | VERIFIED | Signature at line 55; `while cursor:` loop confirmed; `time.sleep(1)` replaced with conditional `if page_delay:` |
| `auraframes/api/frameApi.py` | `get_assets` surfaces error key instead of silent pass | VERIFIED | `RuntimeError` raised on `json_response.get('error')` at lines 50-56 |
| `auraframes/exif.py` | Nominatim UA, typed-tolerant geocode except, re-raising EXIF-write except | VERIFIED | `user_agent="auraframes-python-client/1.0"` at line 34; `except Exception` (tolerated) in `_lookup_gps`; `except Exception: raise` in `write_exif` |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `tests/conftest.py` fixture | `Aura.login()` | `instance.login()` at conftest.py:31 | WIRED | Fixture instantiates `Aura()` and calls `.login()` before returning |
| `client.py get/post/put/delete` | `response.raise_for_status()` | Called after `history.append`, before `.json()` | WIRED | 4 confirmed occurrences; order: append → raise → debug log → return |
| `client.py logger.info/logger.debug` | `_redact()` | POST/PUT request bodies + all 4 response bodies | WIRED | `_redact(data)` in `logger.info` for post/put; `_redact(response.json())` in all 4 `logger.debug` calls |
| `test_read_03_pagination` | `aura.get_all_assets(frame_id, limit=...)` | Direct call at test_read_path.py:61 | WIRED | Drives the production helper with `limit=max(1, total//2)` |
| `aura.get_all_assets` | `frameApi.get_assets` cursor loop | `while cursor:` at aura.py:58 | WIRED | Seeds page 1, drains while cursor truthy, threads `limit` through both calls |
| `test_read_04_download_exif` | `get_readable_exif(saved_file)` | Imported and called at test_read_path.py:106 | WIRED | Globs saved file from `tmp_path`, reads EXIF, asserts `DateTimeOriginal` |

---

### Data-Flow Trace (Level 4)

Not applicable — this phase produces no components that render dynamic data (no UI/web layer). The tests assert on data flowing from the live API through the read-path functions. That flow is verified via direct live test execution documented in 02-LIVE-EVIDENCE.md.

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Credential-less suite stays green | `uv run pytest -q -m "not live"` | `9 passed, 4 deselected in 0.19s` | PASS |
| All 4 live tests collected under `live` marker | `uv run pytest -q --collect-only -m live` | 4 tests listed | PASS |
| `_redact` masks secret keys | `grep -n "_redact" auraframes/client.py` | Applied in both request body (post/put) and response body (all 4 methods) | PASS |
| No bare `except:` in exif.py | `grep -nE "except\s*:" auraframes/exif.py` | No matches | PASS |
| No unconditional `time.sleep(1)` | `grep -n "time.sleep(1)" auraframes/aura.py` | No matches | PASS |

---

### Probe Execution

No probe scripts were declared in the plan or exist at `scripts/*/tests/probe-*.sh`. Not applicable.

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| READ-01 | 02-01 | Client authenticates against live Aura API | SATISFIED | `accountApi.login` hydrates `User`, headers injected; live PASS |
| READ-02 | 02-01 | Client lists account frames | SATISFIED | `frameApi.get_frames()` returns `list[Frame]`; live PASS, "«frame-name-redacted»" printed |
| READ-03 | 02-02 | Client fetches assets with cursor-based pagination | SATISFIED | `get_all_assets` cursor loop; live PASS, 77 assets across multiple pages |
| READ-04 | 02-02 | Client downloads one asset image with EXIF intact | SATISFIED | `export.get_image_from_asset` + `get_readable_exif`; live PASS, DateTimeOriginal + GPS confirmed |
| DOC-01 | — | Verification report records what works and where API drifted | DEFERRED | Mapped to Phase 3 in REQUIREMENTS.md; 02-LIVE-EVIDENCE.md captures Phase 2's drift findings |

**Orphaned requirements check:** No Phase 2 requirements in REQUIREMENTS.md are unclaimed by either plan.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `auraframes/client.py` | 109 | `logger.debug(f'Response Cookies: {response.cookies}')` — full cookie jar (values included) reaches the on-disk file sink | WARNING (WR-01) | Cookies containing session tokens bypass `_redact`; only affects DEBUG-level disk sink; D-07 target secrets (password/auth_token/x-token-auth) are correctly redacted; live evidence confirmed 0 password/token occurrences in logs. Does not block the phase goal. |
| `auraframes/exif.py` | 23-26, 57-58 | GPS lat/long swap in `build_gps_ifd` / `_lookup_gps` return order | INFO (IN-01) | GPS coordinates written transposed; accepted per T-02-09; GPS IFD is still readable so READ-04 passes; deferred to a later phase. |
| `auraframes/client.py` | 41 | `TODO: This should be reworked to be async` | INFO | Pre-existing debt; references MOD-01 which is explicitly out of scope for this milestone. Not a new introduction by this phase. |

**Debt marker gate:** No `TBD`, `FIXME`, or `XXX` markers found in any file modified by this phase.

---

### Live Test Evidence (Human Verification — Completed)

The human-check items declared in both PLAN files were fulfilled during execution this session. Evidence is recorded in `02-LIVE-EVIDENCE.md`.

**READ-01:** Login injected `x-token-auth` + `x-user-id` onto the shared httpx session. PASS.

**READ-02:** Listed frame **"«frame-name-redacted»"** (`«uuid-redacted»`). PASS.

**READ-03:** `get_all_assets(limit=38)` drained **77 assets across multiple pages**; `len(assets) == total == 77`. PASS.

**READ-04:** Downloaded asset `«uuid-redacted»` via `image+location_name` branch; `DateTimeOriginal` read back from disk; GPS IFD readable for location **"«location-redacted»"**. PASS.

**Security gate (D-07):** After live login, `logs/file_*.log` contained 0 plaintext password occurrences, 0 unredacted auth_token/x-token-auth lines, and the redaction marker `auth_token': '***REDACTED***'` was confirmed present.

No human verification items remain open.

---

### Live API Drift (Discovered and Fixed — In-Scope)

Four schema drifts were discovered during live verification and repaired pragmatically (commit `93409f5`) within the milestone's "change only what's needed to prove the read path" constraint:

1. **`User` Optional fields** — `has_frame` and six other Optional fields missing `= None` defaults; added to all.
2. **`Feature` enum** — unknown value `text_to_frame_four_hour_reminders` rejected by closed enum; `_missing_` classmethod now maps unknown values to `Feature.UNKNOWN`.
3. **`Asset.unglacierable`** — live API returns `null`; changed to `Optional[bool] = None`.
4. **Asset count location** — `total_asset_count` moved from response top-level to `frame.num_assets`; `get_frame` reads new location with fallback to legacy key.

These fixes were an approved in-scope deviation and are fully verified in the codebase.

---

### Gaps Summary

No gaps. All 10 must-have truths are verified in the actual codebase. The credential-less suite is green. All four live tests passed against `api.pushd.com/v5`. The phase goal is achieved: login, list frames, fetch assets, and download one image with EXIF have been proven against the live API.

---

_Verified: 2026-06-29_
_Verifier: Claude (gsd-verifier)_
