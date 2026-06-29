# Phase 2: Live Read-Path Verification - Research

**Researched:** 2026-06-29
**Domain:** Live integration testing of a reverse-engineered HTTP API client (Python 3.14 / pytest / httpx / piexif)
**Confidence:** HIGH (read-path code read line-by-line; key library behavior verified on the actual installed toolchain)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Verify via a **live pytest integration test** (`tests/test_read_path.py`) run with `uv run pytest`, reusing the Phase 1 harness (pytest already in the `dev` extra). pytest pass/fail output is the Phase 3 evidence.
- **D-02:** **Gate live tests so a credential-less run stays green.** Mark them (`@pytest.mark.live`) and auto-skip when `AURA_EMAIL`/`AURA_PASSWORD` are unset. Default `uv run pytest` must still pass on a clean checkout (Phase 1's import smoke test must not break).
- **D-03:** **One test per READ requirement** (READ-01/02/03/04), sharing a single authenticated session via a **login fixture**. Each requirement passes/fails independently (1:1 evidence mapping).
- **D-04:** **Genuinely exercise the cursor loop.** Default `limit=1000` returns a single page → cursor branch never runs. Fetch with a **small `limit`** so multiple pages traverse and the cursor handoff is asserted (>1 page seen).
- **D-05:** **Parametrize `Aura.get_all_assets`** with an optional `limit` so the test drives the real production helper. Also **shorten or drop the unconditional `time.sleep(1)`** (`auraframes/aura.py:60`). Pick a sensible test `limit` (2–3) and frame; prove the mechanism, do not stress-test.
- **D-06:** **Minimal error surfacing.** Add `raise_for_status()` in `Client` `get/post/put/delete` **before** `response.json()`, and convert the silent `pass`-on-`error`-key spots (`accountApi.login`, `frameApi.get_assets`) into a raised error / explicit log. **No typed exception hierarchy** (that's MOD-03 / out of scope).
- **D-07:** **Redact secrets from logs.** Scrub `password` / `auth_token` / `x-token-auth` from request+response logging before running live (secrets-out-of-VCS constraint).
- **D-08 (must-fix to run):** `_init_logger()` writes to `logs/file_{time}.log` but `logs/` is never created → `FileNotFoundError` on first live run. Ensure `logs/` exists at startup (`os.makedirs('logs/', exist_ok=True)`) and gitignore `logs/`, `cache/`, `asset_images/`.
- **D-09:** **Datetime mandatory; GPS conditional.** Always assert `DateTimeOriginal` is written and **read it back** from the saved file (reuse `exif.get_readable_exif` / piexif load). Require GPS **only when the chosen asset has location data**; if no geo-tagged asset exists, assert the GPS-write path ran and document the gap rather than failing.
- **D-10:** **Asset selection automatic.** Use the **first frame** from `get_frames`; from its assets pick the **first with a non-null `location_name`** (so GPS is exercised), falling back to the first asset. No manual config.
- **D-11:** **Surface silent download/EXIF failures + fix the geocoder UA.** Make the EXIF-write failure surface (don't silently return empty bytes for the verified download). Replace `user_agent="Upload Scripting Test"` with a proper identifier (e.g. `auraframes-python-client/1.0`).

### Claude's Discretion

- Exact pytest mechanics: fixture scoping, `live` marker registration, chosen small `limit`, how the login fixture exposes the session to the 4 tests.
- Which frame/asset edge cases to tolerate (e.g. video assets); default to picking an image asset for the READ-04 download.
- Whether to opportunistically close **Phase 1's deferred `.dict()` → `.model_dump()` migration** (`assetApi.py` / `frameApi.py:90`). **NOT on the read path** — optional; migrate only if trivial.
- Exact redaction mechanism for D-07 (log filter vs. sanitizing the payload dict).

### Deferred Ideas (OUT OF SCOPE)

- `.env` loader for credentials (plain shell env vars only).
- Video / non-image asset handling (download targets an image asset).
- Full typed exception hierarchy (MOD-03), AWS pool-ID config (MOD-02).
- Async HTTP migration (MOD-01), upload round-trip (UP-01).
- Phase 1 deferred `.dict()` → `.model_dump()` migration (optional, not read-path).
- **Retry/backoff on transient/429 errors — NOT built. If the live run is flaky, note it for the Phase 3 report, do not add retry logic.**
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| READ-01 | Client authenticates (login) against the live API | `Aura.login()` (`aura.py:36`) → `AccountApi.login()` (`accountApi.py:8`) POSTs `/login.json`, hydrates `User`, injects `x-token-auth`/`x-user-id`. Assert `user.id` + `user.auth_token` set and headers populated. Needs D-06 (`raise_for_status`) + D-07 (redaction) first. |
| READ-02 | Client lists the account's frames | `FrameApi.get_frames()` (`frameApi.py:13`) GETs `/frames.json` → `list[Frame]`. Assert non-empty, print `frame.name` + `frame.id`. |
| READ-03 | Client fetches a frame's assets, handling cursor pagination | `Aura.get_all_assets()` (`aura.py:55`) loops `FrameApi.get_assets()` (`frameApi.py:30`, returns `(assets, next_page_cursor)`). Parametrize with `limit` (D-05), small limit forces ≥2 pages (D-04). Cross-check count vs `get_frame()` `total_asset_count`. |
| READ-04 | Client downloads one asset image with EXIF (datetime + GPS) intact | `export.get_image_from_asset()` (`export.py:41`) downloads from imgproxy + `ExifWriter.write_exif()` (`exif.py:58`). Read back via `get_readable_exif()` (`exif.py:109`). Needs D-09/D-10/D-11. |
</phase_requirements>

## Summary

The read path is **fully implemented and import-clean** (Phase 1 migrated the models to pydantic v2 and added a green pytest harness — confirmed `9 passed in 0.08s`). Phase 2 is therefore a **verification phase, not a build phase**: write one live-marked pytest module with four tests (one per READ requirement) sharing a session-scoped login fixture, plus a small set of **surgical, trust-preserving edits** to the read-path code so that a real API failure or a corrupt save cannot masquerade as a green test.

The single biggest design decision is how to **genuinely exercise the cursor loop** (D-04/D-05) without either (a) failing on a small account that returns one page, or (b) hammering the live API with hundreds of tiny-page requests on a large frame. The recommended pattern: read `total_asset_count` from `get_frame()`, compute a `limit` that forces exactly 2–3 pages regardless of frame size (`limit = max(1, total // 2)`), drive the real `get_all_assets(frame_id, limit=limit)` helper, and assert `len(assets) == total_asset_count` with `total_asset_count > limit` — an indirect-but-airtight proof that the cursor branch ran, with a bounded request count.

The trust edits are small and localized: `raise_for_status()` before every `.json()` in `client.py`; a log-redaction filter for `password`/`auth_token`/`x-token-auth`; `os.makedirs('logs/', exist_ok=True)` in `_init_logger`; and converting `exif.py`'s two bare `except:` blocks into typed excepts that **re-raise on EXIF-write failure** (so a 0-byte save surfaces) while still tolerating geocode failure (GPS is conditional). All library behavior that matters — piexif `insert`/`load` round-trip on `BytesIO`, non-JPEG raising `ValueError` — was **verified on the actual installed toolchain** (pydantic 2.13.4, Pillow 12.2.0, httpx 0.28.1, piexif 1.1.3, geopy 2.4.1, Python 3.14).

**Primary recommendation:** Add `tests/test_read_path.py` + `tests/conftest.py` with a `live` marker and a session-scoped `aura` login fixture that `pytest.skip`s when creds are absent; make the four trust edits in `client.py`, `aura.py`, and `exif.py`; for READ-03 compute a 2–3-page `limit` from `total_asset_count` and assert `len == total`; for READ-04 select the first image asset with `location_name`, download via `get_image_from_asset`, then load the saved file with piexif and assert `DateTimeOriginal` (always) and GPS (when geocoding succeeded).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Login / token injection (READ-01) | API client (`AccountApi`) | Facade (`Aura.login` sets headers) | Auth state lives on the shared `Client.http2_client.headers` after login (`aura.py:45`). |
| Frame listing (READ-02) | API client (`FrameApi.get_frames`) | — | Thin REST wrapper → `list[Frame]`. |
| Cursor pagination (READ-03) | Facade (`Aura.get_all_assets` loop) | API client (`FrameApi.get_assets` page) | The loop/cursor handoff is orchestration; the single-page call is the REST wrapper. **D-05 parametrizes the facade helper.** |
| Image download + EXIF (READ-04) | Export module (`export.get_image_from_asset`) | EXIF writer (`exif.ExifWriter`), Geocoder (Nominatim) | Download is an **unauthenticated** direct `httpx.get` to imgproxy; EXIF/GPS injection is a separate concern delegated to `ExifWriter`. |
| Error surfacing (D-06) | HTTP client (`Client`) | API methods (`error`-key handling) | `raise_for_status` belongs at the transport layer; `error`-key checks at the resource layer. |
| Secret redaction (D-07) | HTTP client logging (`Client`) | — | The leak is in `Client.post`/response logging (`client.py:46,50`). |
| Test harness / evidence | pytest (`tests/`) | conftest fixtures | Live gating + session login fixture (D-01/D-02/D-03). |

## Standard Stack

**No new dependencies are required.** Every library needed for Phase 2 is already declared in `pyproject.toml` (Phase 1) and installed. pytest is already in the `dev` extra. This is a code-edit + test-authoring phase.

### Core (already installed — versions VERIFIED on this machine)
| Library | Installed Version | Purpose on read path | Notes |
|---------|-------------------|----------------------|-------|
| `pytest` | >=8 (dev extra) | Live integration test harness (D-01) | Already green: `uv run pytest` → 9 passed. [VERIFIED: `uv run pytest -q`] |
| `httpx[http2]` | **0.28.1** | REST client (`Client`) + imgproxy download | `raise_for_status()` raises `httpx.HTTPStatusError` (D-06). [VERIFIED: `uv run python -c "import httpx"`] |
| `pydantic` | **2.13.4** | Model hydration (`Frame`, `Asset`, `User`) | v2 (Phase 1). `.model_dump()` is the v2 API. [VERIFIED] |
| `piexif` | **1.1.3** | EXIF write/read for READ-04 | `insert(dump(dict), jpeg_bytes, BytesIO())` round-trips; `load(bytes)` works. [VERIFIED: round-trip script below] |
| `Pillow` (PIL) | **12.2.0** | JPEG decode in `get_thumbnail` / `write_exif` path | **Correction:** CLAUDE.md/requirements.txt say `~=9.5`; the installed/locked version is 12.2.0 (Phase 1 bumped to `>=10.4`). [VERIFIED] |
| `geopy` | **2.4.1** | Nominatim geocoding for GPS (`exif.py`) | `Nominatim(user_agent=...)` — UA fix is D-11. [VERIFIED] |
| `loguru` | >=0.7 | Logging (the secret-leak source, D-07) | — |

> **Stale-doc warning:** `CLAUDE.md` describes the *pre-Phase-1* pins (pydantic 1.10, httpx 0.23, Pillow 9.5, boto3 1.26). Those are historical. The numbers above are the live `uv` environment and are what the planner must target. [VERIFIED: `uv run python -c "import pydantic,PIL,httpx,geopy,piexif"`]

**Installation:** none — `uv sync` already provides everything.

### Verified piexif round-trip (the core of READ-04)
```
# [VERIFIED on Python 3.14 / piexif 1.1.3 / Pillow 12.2.0]
# insert DateTimeOriginal + GPS into JPEG bytes -> BytesIO, then read back:
#   insert ok, bytes: 795
#   DateTimeOriginal: b'2021:07:04 10:11:12'
#   GPS keys: [1, 2, 3, 4]            # GPSLatitudeRef/Latitude/LongitudeRef/Longitude
#   piexif.load accepts bytes: yes
#   PNG insert raises: ValueError    # <-- non-JPEG surfaces (matches D-11 intent)
```
This mirrors `exif.write_exif` exactly (`piexif.insert(exif_bytes, image, new_imag)` at `exif.py:90`, where `image` is the raw downloaded `bytes` and `new_imag` is a `BytesIO`). The existing call shape is correct under the current toolchain.

## Package Legitimacy Audit

**No external packages are installed in this phase.** All dependencies were vetted and locked in Phase 1 (`uv.lock` committed). Therefore the Package Legitimacy Gate is **not applicable** — there is nothing new to slopcheck. The planner should add **no** `pip install` / dependency tasks.

| Package | Disposition |
|---------|-------------|
| (none — phase installs nothing) | N/A |

## Architecture Patterns

### Read-path data flow (what the 4 tests exercise)
```
                         AURA_EMAIL / AURA_PASSWORD (shell env)
                                       │
                                       ▼
   READ-01  Aura.login() ──▶ AccountApi.login() ──POST /login.json──▶ api.pushd.com
                                       │ User(auth_token, id)
                                       ▼
                   Client.add_default_headers({x-token-auth, x-user-id})
                                       │  (state now on shared httpx session)
            ┌──────────────────────────┼───────────────────────────────┐
            ▼                          ▼                                ▼
   READ-02 FrameApi.get_frames   READ-03 Aura.get_all_assets(frame,limit)   READ-04 select asset
        GET /frames.json            │  loop: FrameApi.get_assets(cursor)        │ (first image w/ location_name)
        ──▶ list[Frame]            GET /frames/{id}/assets.json                 ▼
                                    ──▶ (assets, next_page_cursor) ×N    export.get_image_from_asset()
                                    until cursor falsy                    │ httpx.get imgproxy/{user_id}/{file_name}  (UNAUTH)
                                                                          │ ExifWriter.write_exif() ──▶ Nominatim geocode(location_name)
                                                                          ▼ piexif.insert -> file on disk
                                                              get_readable_exif(path) ──▶ assert DateTimeOriginal (+GPS)
```

### Pattern 1: live-gated pytest marker + session login fixture (D-01/D-02/D-03)
**What:** Register a `live` marker, auto-skip when creds absent, share one authenticated `Aura` across all four tests.
**When to use:** Always — this is the harness for every READ test.

```python
# tests/conftest.py
# Source: pytest docs — markers + fixtures (https://docs.pytest.org/en/stable/how-to/mark.html)
import os
import pytest
from auraframes.aura import Aura

@pytest.fixture(scope="session")
def aura():
    if not (os.getenv("AURA_EMAIL") and os.getenv("AURA_PASSWORD")):
        pytest.skip("AURA_EMAIL/AURA_PASSWORD not set — skipping live read-path tests")
    a = Aura()
    a.login()          # READ-01 happens here; tests assert on the resulting state
    return a
```
```toml
# pyproject.toml  (NEW section — none exists today)
[tool.pytest.ini_options]
markers = [
    "live: hits the live Aura API; requires AURA_EMAIL/AURA_PASSWORD (run only when set, deselect with -m 'not live')",
]
```
Each test is `@pytest.mark.live` and takes the `aura` fixture. On a credential-less checkout the fixture `skip`s, so all four report **skipped** and the existing import smoke test still **passes** → default `uv run pytest` stays green (D-02). [VERIFIED: baseline `uv run pytest` = 9 passed; the import test has no `live` marker so it is unaffected.]

> **Note on D-03 + fixture login:** putting `login()` in the fixture means READ-01's *act* is the fixture; READ-01's *assert* (token/user-id present, headers injected) lives in `test_read_01`. If login throws, all four tests **error** — which correctly reports "login broke." This preserves the 1:1 evidence mapping.

### Pattern 2: cursor-loop proof with bounded cost (D-04/D-05)
**What:** Drive the real `get_all_assets` helper with a `limit` computed to force 2–3 pages, then prove completeness against the server's own count.
**When to use:** READ-03.

```python
# READ-03
frame = aura.frame_api.get_frames()[0]            # D-10: first frame
_, total = aura.frame_api.get_frame(frame.id)     # total_asset_count
assert total >= 2, "first frame has <2 assets; cannot demonstrate multi-page cursor"
limit = max(1, total // 2)                         # forces exactly 2–3 pages, any frame size
assert limit < total                               # guarantees the cursor branch runs
assets = aura.get_all_assets(frame.id, limit=limit)
assert len(assets) == total                        # all pages traversed AND stitched correctly
```
Why this beats a fixed `limit=2`: a fixed tiny limit on a 500-asset frame = 250 live requests (slow + rude). `total // 2` keeps it to ~2–3 requests regardless of frame size while still **forcing** the cursor handoff. `len == total` is an indirect proof the loop ran without instrumenting page counts.

**Required edit to `get_all_assets` (`aura.py:55`)** — add `limit` and drop/shorten the sleep:
```python
def get_all_assets(self, frame_id: str, limit: int = 1000, page_delay: float = 0.0):
    paginated_assets, cursor = self.frame_api.get_assets(frame_id, limit=limit)
    assets = paginated_assets
    while cursor:
        paginated_assets, cursor = self.frame_api.get_assets(frame_id, limit=limit, cursor=cursor)
        if page_delay:
            time.sleep(page_delay)          # was unconditional time.sleep(1) at aura.py:60
        assets.extend(paginated_assets)
    return assets
```
Default `limit=1000`/`page_delay=0.0` preserves production behavior except for removing the always-on 1 s stall (the `# TODO: Make better (tm)` the team wanted gone). [CITED: CONCERNS.md "get_all_assets uses a fixed 1-second sleep"].

### Pattern 3: EXIF read-back assertion (READ-04, D-09)
**What:** Download to a temp dir, then load the **saved file** and assert tags — never trust the write return value.
**When to use:** READ-04.

```python
# READ-04 (sketch)
asset = _select_asset(aura.get_all_assets(frame.id, limit=...))   # D-10 selection, see below
out_dir = tmp_path  # pytest tmp_path fixture; clean dir
export.get_image_from_asset(asset, str(out_dir) + os.sep, aura.exif_writer)
saved = next(out_dir.iterdir())                       # exactly one file written
readable = get_readable_exif(str(saved))
assert readable["Exif"]["DateTimeOriginal"] == asset.taken_at_dt.strftime('%Y:%m:%d %H:%M:%S').encode()
if asset.location_name and readable.get("GPS"):       # GPS conditional (D-09)
    assert readable["GPS"]                            # non-empty IFD
else:
    # geocode returned nothing or no location — document the gap, do not fail
    ...
```
`get_image_from_asset` does **not return the saved path** (returns the raw bytes, `export.py:53`); the filename is `{taken_at_dt:%Y%m%dT%H%M%S}-{file_name}` (`export.py:42`). Easiest: write to a clean `tmp_path` and glob the single file (avoids re-deriving the name).

### Anti-Patterns to Avoid
- **Re-implementing pagination in the test.** D-05 requires driving the real `get_all_assets`; a hand-rolled loop wouldn't verify the production code path.
- **Asserting the write call's return.** `write_exif` returns a `BytesIO` even on failure today (`exif.py:93`); the only trustworthy proof is loading the file from disk (D-09).
- **Fixed tiny `limit` on an unknown-size frame.** Unbounded request count on large frames (see Pattern 2).
- **Hard-failing on missing GPS.** GPS depends on Nominatim geocoding `location_name` succeeding — conditional by design (D-09). A geocode miss must be documented, not fatal.
- **Adding retry/backoff.** Explicitly deferred — flag flakiness for the Phase 3 report instead.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Pagination loop in the test | Custom cursor loop | `Aura.get_all_assets(frame_id, limit=...)` | D-05 — must verify the production helper. |
| EXIF read-back | Manual byte parsing / Pillow `_getexif` | `exif.get_readable_exif(path)` (piexif) | Already exists (`exif.py:109`), maps IFD tags to names; reuse per D-09. |
| Credential gating | `os.environ` checks scattered per test | One session fixture that `pytest.skip`s | D-02/D-03 — single skip point, shared login. |
| HTTP status checking | Per-call `if status != 200` | `response.raise_for_status()` | D-06 — one line at the transport layer (`client.py`). |
| Image download | New httpx call in the test | `export.get_image_from_asset` | Exercises the real READ-04 path incl. EXIF injection. |

**Key insight:** Almost everything READ-01..04 needs already exists in `auraframes/`. Phase 2's job is to *call it and assert*, plus make four small edits so failures can't hide. Resist writing new helpers.

## Runtime State Inventory

This is **not** a rename/refactor/migration phase — it adds a test and makes localized trust edits. No stored data, OS-registered state, or build artifacts carry a renamed string. The only runtime-state-adjacent items:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — read-only against live API; no local DB. | None. |
| Live service config | None changed. (We *read* live frames/assets; we mutate nothing on the account.) | None. |
| OS-registered state | None. | None — verified: no scheduler/daemon registration in repo. |
| Secrets/env vars | `AURA_EMAIL`/`AURA_PASSWORD` read at `Aura.login()` default args (`aura.py:36`) and `settings.py`. **Must never be logged** (D-07). | Add redaction filter; gitignore `logs/`. |
| Build artifacts | `logs/`, `cache/`, `asset_images/` are created at runtime and must be gitignored (D-08); not currently in `.gitignore`. | Add to `.gitignore`. |

## Common Pitfalls

### Pitfall 1: `logs/` directory missing → `FileNotFoundError` on first live run (D-08, BLOCKING)
**What goes wrong:** `_init_logger()` (`aura.py:137`) calls `logger.add('logs/file_{time}.log')` but `logs/` does not exist in the repo and is never created. The very first `Aura()` instantiation in the fixture crashes before any request.
**Why it happens:** loguru does not `mkdir` the sink's parent.
**How to avoid:** `os.makedirs('logs/', exist_ok=True)` at the top of `_init_logger()`. [CITED: CONCERNS.md "logs/ and cache/ directories are never created"]
**Warning signs:** Fixture errors with `FileNotFoundError: [Errno 2] ... 'logs/file_....log'`.

### Pitfall 2: plaintext password + auth_token written to the log file (D-07, SECURITY-BLOCKING)
**What goes wrong:** `Client.post` logs the full `data` dict at INFO (`client.py:46`) and the full response body at DEBUG (`client.py:50`). The `/login.json` payload contains the plaintext password (`accountApi.py:19`); the response contains `auth_token`. Both land in `logs/file_{time}.log`. Running live as-is writes secrets to disk.
**Why it happens:** Unfiltered structured logging of request/response bodies.
**How to avoid:** Before running any live test, add redaction. Two viable mechanisms (Claude's discretion, D-07):
- **(a) Sanitize the dict before logging** — a small `_redact(d)` that masks keys `password`, `auth_token`, `x-token-auth` (recurse into nested `user` dict) used in the `logger.info`/`logger.debug` calls.
- **(b) loguru patcher/filter** — `logger.configure(patcher=...)` or a custom sink filter that scrubs the rendered message.
Recommendation: (a) is simpler and more targeted for this codebase (the leak is in two specific log lines). Also redact the response body before `logger.debug` (login response carries `auth_token`).
**Warning signs:** `grep -ri "AURA_PASSWORD value" logs/` or the literal token appearing in the log. [CITED: CONCERNS.md "Plaintext passwords and auth tokens logged to file"]

### Pitfall 3: silent `error`-key handling masks API drift (D-06)
**What goes wrong:** `accountApi.login` (`accountApi.py:28`) and `frameApi.get_assets` (`frameApi.py:42`) check `json_response.get('error')` then `pass`. A drifted/failed API response flows into `User(**...)` / `Asset(**...)` and either raises an opaque `ValidationError` or — worse — yields a "successful" object. Without `raise_for_status`, a 401/500 that returns JSON is processed as if OK. This is the exact "silent error can mask drift" blocker in STATE.md.
**Why it happens:** `# TODO: Error handling` stubs never implemented; `response.json()` called unconditionally (`client.py:43,54,65,76`).
**How to avoid:** (1) `response.raise_for_status()` immediately after each request, before `.json()`, in all four `Client` methods → raises `httpx.HTTPStatusError` (a real failure can't return green). (2) Replace the two read-path `pass` blocks with a raise/log including `json_response.get('message')`. **No typed hierarchy** — a plain `raise RuntimeError(...)` or re-raise is in scope; MOD-03 is not. [CITED: CONCERNS.md "No HTTP response status validation"]
**Warning signs:** Tests pass even when credentials are wrong (they should error/raise, not silently build a `User`).

### Pitfall 4: EXIF-write failure silently produces a 0-byte file (D-11)
**What goes wrong:** `write_exif` wraps `piexif.insert` in a bare `except:` that only logs (`exif.py:89-92`) and returns the (empty) `BytesIO`. `get_image_from_asset` then `shutil.copyfileobj`s that empty buffer to disk (`export.py:51-52`) → a 0-byte "image" with no error. A broken save looks fine. Verified: non-JPEG input raises `ValueError` here, which is exactly the failure that's being swallowed.
**Why it happens:** Bare `except:` + return-anyway.
**How to avoid (D-11):** Convert the `piexif.insert` bare `except:` (`exif.py:91`) to `except Exception` that **re-raises** (or raises a clear error) so the download path fails loudly. Keep the **geocode** bare `except:` (`exif.py:45`) tolerant — it should still log and `return None` (GPS is conditional, D-09) but use `except Exception` not bare `except:`. Treat the two differently: EXIF-write = fatal, geocode = tolerable.
**Warning signs:** A saved asset file of 0 bytes, or `get_readable_exif` raising on an empty file.

### Pitfall 5: imgproxy returns a non-JPEG / `thumbnail_url` is `None` (READ-04 selection)
**What goes wrong:** (a) `get_thumbnail` (`export.py:23`) does `httpx.get(asset.thumbnail_url)` **unconditionally** when an `exif_writer` is passed; `thumbnail_url` is `Optional` (`asset.py:86`) → `httpx.get(None)` fails. (b) `piexif.insert` only accepts JPEG/TIFF; an asset whose proxy render is non-JPEG raises `ValueError` (now surfaced by Pitfall-4 fix).
**Why it happens:** No format/null guard in the download path; video and some live-photo assets differ.
**How to avoid (D-10 + discretion):** In asset selection, **prefer an image asset**: skip assets with a truthy `video_url`/`is_live` (`asset.py:54,100`) and prefer one with a non-null `thumbnail_url` and a non-null `location_name`; fall back to the first plain image asset. Selection chain: *first image asset with `location_name` → first image asset → first asset*. Document if the fallback path is taken.
**Warning signs:** `TypeError`/`httpx` error inside `get_thumbnail`, or `ValueError` from `piexif.insert` on a HEIC/video frame.

### Pitfall 6 (drift observation, not a required fix): GPS lat/long swap in `build_gps_ifd`
**What goes wrong:** `_lookup_gps` returns `(longitude_dms, latitude_dms)` (`exif.py:56`) but `build_gps_ifd` reads `location_dms[0]` as **latitude** and `location_dms[1]` as **longitude** (`exif.py:23-26`) — and the refs are mismatched (latitude ref set from longitude's E/W). The written GPS coordinates are swapped/incorrect.
**Why it matters for verification:** D-09 only requires GPS **readable** in the file — the swap does not block "readable," so READ-04 can pass. But this is precisely the kind of latent correctness bug a verification milestone should **surface**. Recommendation: do **not** silently fix it under MVP scope; **note it for the Phase 3 drift/issues report** (or fix only if the planner deems it trivial and in-scope). Flagging here so the planner makes a conscious call. [VERIFIED by reading `exif.py:38-56` + `:17-30`]

## Code Examples

### Reading credentials gate + login (READ-01 assertion)
```python
# Source: auraframes/aura.py:36-50, accountApi.py:8-32
# login() POSTs /login.json, hydrates User, injects headers.
def test_read_01_login(aura):  # @pytest.mark.live
    # fixture already called login(); assert the resulting authenticated state
    assert aura._client.http2_client.headers.get("x-token-auth")
    assert aura._client.http2_client.headers.get("x-user-id")
```

### Listing frames (READ-02)
```python
# Source: auraframes/api/frameApi.py:13-19
def test_read_02_list_frames(aura):  # @pytest.mark.live
    frames = aura.frame_api.get_frames()
    assert frames, "no frames returned for this account"
    for f in frames:
        print(f"{f.name} ({f.id})")
```

### get_readable_exif tag shape (for the READ-04 assertion)
```python
# Source: auraframes/exif.py:109-121 — returns nested dict keyed by IFD then tag NAME
# DateTimeOriginal lives under "Exif"; GPS tags under "GPS".
# Verified read-back values: readable["Exif"]["DateTimeOriginal"] == b'YYYY:MM:DD HH:MM:SS'
```

## State of the Art

| Old (CLAUDE.md / requirements.txt) | Current (uv.lock, this machine) | When Changed | Impact |
|------------------------------------|---------------------------------|--------------|--------|
| pydantic 1.10.4 | **2.13.4** | Phase 1 | `.model_dump()` is the v2 serializer; `.dict()` deprecated (still works with warning). |
| httpx 0.23.1 | **0.28.1** | Phase 1 | `raise_for_status()` returns the response; behavior stable for D-06. |
| Pillow 9.5.0 | **12.2.0** | Phase 1 | JPEG decode path unchanged for this use. |
| boto3 1.26 | 1.34+ | Phase 1 | Not on the read path — ignore. |

**Deprecated/outdated:**
- The `.dict(exclude_unset=True)` call at `frameApi.py:90` is **update/upload code, not read-path** — leave it (Claude's discretion; Phase 1 deferred it as D-05). It emits a pydantic v2 deprecation warning but does not run during READ-01..04.
- `datetime.utcnow()` (`dt.py:11`) is deprecated but only used by `show_asset`/`format_dt_to_aura` — **not on the read path**; do not touch.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | imgproxy returns a JPEG for a normal image asset (so `piexif.insert` succeeds) | Pitfall 5 | If it returns HEIC/WebP, READ-04 download raises `ValueError` — now surfaced (D-11), so it fails loudly rather than silently. Mitigate via image-asset selection; document if it occurs. |
| A2 | The account's first frame has ≥2 assets (so multi-page can be demonstrated) | Pattern 2 | If the first frame has <2 assets, READ-03's multi-page proof can't run — the test should `skip`/`xfail` with a documented note, or pick the largest frame. Planner should add the guard. |
| A3 | Nominatim geocoding of `location_name` succeeds for the chosen asset (so GPS is written) | Pitfall 6 / D-09 | GPS assertion is conditional; a miss is documented, not fatal (by design). Possible Nominatim rate-limiting on repeated runs — note for Phase 3 if flaky. |
| A4 | The live `/login.json`, `/frames.json`, `/frames/{id}/assets.json` response shapes still match the pydantic models | All | This is the *entire point* of the phase — drift surfaces as `ValidationError`/`HTTPStatusError` once D-06 is in. Expected and desirable. |
| A5 | `x-token-auth`/`x-user-id` are still the correct auth headers | READ-01 | If the API changed auth, READ-02+ return 401 → `raise_for_status` fails loudly (D-06). |

## Open Questions

1. **Does the first frame have enough assets to force multi-page pagination?**
   - What we know: `get_frame()` returns `total_asset_count`; `get_all_assets` drains all pages.
   - What's unclear: account-specific data; can't know until login.
   - Recommendation: compute `limit = max(1, total // 2)`; `assert total >= 2` else `pytest.skip("first frame <2 assets")` with a note for Phase 3. (A2)

2. **Will Nominatim consistently geocode the chosen asset's `location_name`?**
   - What we know: GPS write depends on geocode success; conditional per D-09.
   - What's unclear: Nominatim availability/rate limits during the run.
   - Recommendation: assert GPS only when `readable["GPS"]` is populated; otherwise log/skip the GPS assertion and record the gap. Do not add retry (deferred). (A3)

3. **Should the lat/long swap bug (Pitfall 6) be fixed now?**
   - What we know: it produces incorrect (but readable) GPS; READ-04 can pass regardless.
   - Recommendation: leave the fix out of MVP scope; record it in the Phase 3 drift report. Planner to confirm.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.14 + `uv` | All | ✓ | 3.14 (`.python-version`) | — |
| pytest | Test harness (D-01) | ✓ | >=8 (dev extra) | — |
| Live network: `api.pushd.com` | READ-01/02/03 | runtime | — | none — required for live run (tests skip without creds) |
| Live network: `imgproxy.pushd.com` | READ-04 download | runtime | — | none |
| Live network: Nominatim/OSM | READ-04 GPS | runtime | — | GPS becomes unverifiable → document gap (D-09) |
| `AURA_EMAIL` / `AURA_PASSWORD` | All live tests | runtime (user) | — | tests `skip` (D-02) |

**Missing dependencies with no fallback:** none at author time — the live network + credentials are runtime conditions handled by the skip gate, not build blockers.

## Validation Architecture

> `workflow.nyquist_validation` is **false** in `.planning/config.json` — this section is **optional**. Included briefly because the phase deliverable *is* a test.

- **Framework:** pytest >=8 (already configured via Phase 1 `dev` extra). Config: add `[tool.pytest.ini_options]` to `pyproject.toml` (none today).
- **Quick run (default, credential-less):** `uv run pytest` → import smoke test passes, live tests skip. [VERIFIED baseline: 9 passed.]
- **Live run:** `AURA_EMAIL=… AURA_PASSWORD=… uv run pytest -m live` → the four READ tests execute against the live API. This output is the Phase 3 evidence.
- **Req → test map:** READ-01→`test_read_01_login`, READ-02→`test_read_02_list_frames`, READ-03→`test_read_03_pagination`, READ-04→`test_read_04_download_exif` (1:1 per D-03).
- **Wave 0 gaps:** `tests/test_read_path.py` (new), `tests/conftest.py` (new, session login fixture + skip gate), `[tool.pytest.ini_options].markers` in `pyproject.toml` (new).

## Security Domain

> `security_enforcement: true`, `security_asvs_level: 1`, `block_on: high`.

### Applicable ASVS categories (level 1)

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Token auth via `x-token-auth`; credentials from env vars, never hardcoded (`AURA_EMAIL`/`AURA_PASSWORD`). |
| V3 Session Management | partial | Token held in-memory on the httpx session; no persistence. No change this phase. |
| V4 Access Control | no | Single-user CLI; no authz surface. |
| V5 Input Validation | yes | pydantic models validate all API responses; `raise_for_status` (D-06) rejects error responses before parsing. |
| V6 Cryptography | no | No crypto implemented/changed; TLS handled by httpx. |
| **V7 Logging (secrets in logs)** | **yes (HIGH)** | **D-07 redaction** — password/`auth_token`/`x-token-auth` must be scrubbed from logs. This is the one `block_on: high` item in scope. |

### Known threat patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Plaintext secrets written to `logs/file_*.log` | Information Disclosure | D-07 redaction filter/sanitizer; gitignore `logs/` (D-08). **HIGH — must land before any live run.** |
| Credentials committed to VCS | Information Disclosure | Env-var only (existing); `.gitignore` covers `.env`; no creds in test files. |
| Drifted API error silently accepted | Tampering / repudiation of failure | `raise_for_status` + `error`-key raise (D-06). |
| Nominatim ToS-violating UA → IP ban | (availability) | D-11 UA fix to `auraframes-python-client/1.0`. |

**Security gate for this phase:** D-07 (log redaction) + D-08 (gitignore `logs/`) together close the only HIGH-severity item. They MUST be completed and verified (grep the log for the password/token after a live login) before READ evidence is considered trustworthy.

## Sources

### Primary (HIGH confidence)
- Read-path source files (read in full this session): `auraframes/aura.py`, `client.py`, `api/accountApi.py`, `api/frameApi.py`, `export.py`, `exif.py`, `models/asset.py`, `models/user.py`, `utils/settings.py`, `utils/dt.py`, `api/baseApi.py`, `tests/test_imports.py`, `pyproject.toml`, `.gitignore`.
- Installed-version probe: `uv run python -c "import pydantic,PIL,httpx,geopy,piexif"` → pydantic 2.13.4, PIL 12.2.0, httpx 0.28.1, geopy 2.4.1, piexif 1.1.3.
- piexif round-trip verification script (insert/load on `BytesIO`, non-JPEG `ValueError`) — run on Python 3.14 this session.
- Baseline test run: `uv run pytest -q` → 9 passed.
- `.planning/codebase/INTEGRATIONS.md`, `.planning/codebase/CONCERNS.md` — endpoint/auth map and risk map.
- CONTEXT.md (D-01..D-11), ROADMAP.md, REQUIREMENTS.md, STATE.md, Phase 1 CONTEXT.md.

### Secondary (MEDIUM confidence)
- pytest markers/fixtures idioms (`@pytest.mark`, session-scoped fixtures, `pytest.skip`) — standard, stable across pytest 8.x. [CITED: docs.pytest.org/en/stable/how-to/mark.html]

### Tertiary (LOW confidence)
- imgproxy output format (assumed JPEG) — A1, unverifiable without a live download.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions probed on the live `uv` env; no new deps.
- Architecture / read-path mechanics: HIGH — every read-path file read line-by-line; flow traced end to end.
- Trust edits (D-06/07/08/11): HIGH — exact file:line anchors identified; piexif failure mode reproduced.
- Live-data assumptions (frame size, geocode success, image format): MEDIUM — account-/network-dependent, handled with skip/conditional logic.

**Research date:** 2026-06-29
**Valid until:** ~2026-07-29 for the toolchain facts (stable, locked). The **live API shape is a moving target** (undocumented) — that volatility is the phase's subject, not a research staleness issue.
