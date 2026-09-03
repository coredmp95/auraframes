---
phase: 02-live-read-path-verification
reviewed: 2026-06-29T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - auraframes/client.py
  - auraframes/api/accountApi.py
  - auraframes/api/frameApi.py
  - auraframes/aura.py
  - auraframes/exif.py
  - tests/conftest.py
  - tests/test_read_path.py
  - pyproject.toml
  - .gitignore
findings:
  critical: 0
  warning: 2
  info: 4
  total: 6
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-06-29
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Reviewed the Phase 02 live read-path hardening: HTTP-client `raise_for_status` +
secret redaction, raise-on-error in `accountApi.login` / `frameApi.get_assets`,
parametrized `get_all_assets` pagination, EXIF write/geocode except split, and the
credential-gated pytest harness.

The headline items hold up under scrutiny:

- **Redaction of documented secrets is correct.** `_redact` recurses dicts/lists and
  masks `password` (request side, including the nested `user.password`) and
  `auth_token` / `x-token-auth` (response side). JSON-decoded payloads are acyclic, so
  the recursion is safe in practice.
- **`raise_for_status` placement is correct.** Every verb appends the response to
  `self.history` *before* calling `raise_for_status()`, so a failed response is always
  retained in history for post-mortem inspection.
- **Pagination loop is correct.** `get_all_assets` seeds from page 1 and drains while
  `cursor` is truthy, threading `limit` through every call; `page_delay` is now opt-in.
- **EXIF write re-raise is correct and meaningful.** `piexif.insert` seeks the output
  BytesIO back to 0 (verified in `_insert.py:52`), and a non-JPEG/corrupt body falls
  into piexif's `open(image)` branch and raises — now re-raised instead of yielding a
  0-byte file. The geocode except is correctly tolerant (logs + returns `None`).

No blockers found. The two warnings concern a redaction gap (cookies) and drift-time
robustness; info items are mostly known/deferred or pre-existing adjacent debt.

## Warnings

### WR-01: Response cookies logged unredacted to the on-disk file sink

**File:** `auraframes/client.py:109`
**Issue:** `_set_cookies` logs the full cookie jar — values included — via
`logger.debug(f'Response Cookies: {response.cookies}')`. The loguru file sink is added
with no level (`logger.add('logs/file_{time}.log')` in `aura.py:141`), so DEBUG records
reach disk. The existence of `_set_cookies` implies the server sets cookies that matter
to the session; if any are auth/session tokens, their plaintext values land in
`logs/`, bypassing the `_redact` path this phase introduced. This directly undercuts
the D-07 "secrets must never reach on-disk logs" goal.
**Fix:** Log only cookie names, or run the jar through the same redaction policy, e.g.:
```python
def _set_cookies(self, response: httpx.Response) -> None:
    if len(response.cookies):
        logger.debug(f'Response set {len(response.cookies)} cookie(s): '
                     f'{sorted(response.cookies.keys())}')
    for cookie_name, cookie_data in response.cookies.items():
        self.http2_client.cookies.set(cookie_name, cookie_data)
```

### WR-02: Drift-time `None` payloads raise opaque TypeErrors instead of the intended loud error

**File:** `auraframes/api/frameApi.py:49`, `auraframes/api/accountApi.py:35`
**Issue:** The new error guards only catch the documented `error`/missing-`result`
shapes. If the API drifts to a 200 response that omits the expected key without setting
`error`, the code dereferences `None`:
- `frameApi.get_assets`: when `json_response.get('assets')` is `None`,
  `[Asset(**asset_data) for asset_data in None]` raises `TypeError: 'NoneType' object is
  not iterable` — defeating the stated D-06 intent of surfacing drift *clearly*.
- `accountApi.login`: the guard passes when `result` is truthy but `current_user` is
  absent; `User(**json_response.get('result').get('current_user'))` then raises
  `User(**None)` → `TypeError`.
**Fix:** Validate the specific keys before iterating/hydrating, e.g. in `get_assets`:
```python
assets_data = json_response.get('assets')
if assets_data is None:
    raise RuntimeError(f"get_assets: response for frame {frame_id} had no 'assets' key")
assets = [Asset(**asset_data) for asset_data in assets_data]
```
and in `login`, guard `current_user` is not `None` before unpacking.

## Info

### IN-01: GPS latitude/longitude swap (known, deferred)

**File:** `auraframes/exif.py:23-26`, `auraframes/exif.py:57-58`
**Issue:** `_lookup_gps` returns `(longitude_dms, latitude_dms)`, but `build_gps_ifd`
assigns `location_dms[0]` (longitude) to `GPSLatitude`/`GPSLatitudeRef` and
`location_dms[1]` (latitude) to `GPSLongitude`/`GPSLongitudeRef` — written-back GPS
coordinates are transposed. Confirmed intentionally deferred to a later phase; recorded
here for traceability, not as a phase-02 defect.
**Fix:** Deferred — when addressed, either return `(latitude_dms, longitude_dms)` or
swap the indices in `build_gps_ifd`.

### IN-02: `register()` retains the silent `pass` and crashes on a `None` result

**File:** `auraframes/api/accountApi.py:59-63`
**Issue:** Pre-existing, but now inconsistent with the hardened `login`: the
`if ... : pass` TODO leaves a failed/error response unhandled, then
`json_response.get('result').get('current_user')` raises `AttributeError` when `result`
is `None`. Out of the verified read path, so low priority, but the asymmetry with
`login` is worth closing in a follow-up.
**Fix:** Mirror the `login` guard — raise a `RuntimeError` instead of `pass`.

### IN-03: Batch download failures are near-silent and swallow the new EXIF re-raise

**File:** `auraframes/aura.py:87-90`
**Issue:** `download_images_from_assets` catches `except Exception as e` (`e` unused),
and only emits `logger.debug(f'Failed to retrieve {len(failed_to_retrieve)} assets.')`.
The stderr sink is INFO-level, so failures are invisible there, and individual asset
errors (including the EXIF re-raise added in D-11) are discarded without per-asset
context. The "fail loudly" value of the EXIF re-raise is therefore lost on the batch
path (it still works for the direct `export.get_image_from_asset` call exercised by
READ-04). Pre-existing line, not modified this phase.
**Fix:** Log at `warning`/`error` with the failing asset id and exception, e.g.
`logger.warning(f'Failed asset {asset.id}: {e}')` inside the except, and surface the
aggregate count at INFO.

### IN-04: Redaction key matching is exact and case-sensitive

**File:** `auraframes/client.py:14`
**Issue:** `_REDACT_KEYS = {'password', 'auth_token', 'x-token-auth'}` masks only those
exact, lowercased keys. Any drift to a differently-cased or renamed secret key (e.g.
`token`, `session_token`, `Authorization`, `Auth_Token`) would leak unredacted. Today's
responses use the covered lowercase keys, so this is forward-looking hardening rather
than a live leak.
**Fix:** Lowercase-normalize the key on compare and/or broaden the set:
`k.lower() in _REDACT_KEYS`, and consider adding `token`/`authorization` substrings.

---

_Reviewed: 2026-06-29_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
