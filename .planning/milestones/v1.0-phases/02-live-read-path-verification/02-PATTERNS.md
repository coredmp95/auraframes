# Phase 2: Live Read-Path Verification - Pattern Map

**Mapped:** 2026-06-29
**Files analyzed:** 10 (2 new, 8 modified)
**Analogs found:** 10 / 10

## File Classification

| New/Modified File | New/Mod | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|---------|------|-----------|----------------|---------------|
| `tests/test_read_path.py` | NEW | test | request-response | `tests/test_imports.py` | role-match (smoke→integration) |
| `tests/conftest.py` | NEW | test (fixture/config) | event-driven (session setup) | `tests/test_imports.py` + `auraframes/aura.py:36` login | role-match |
| `pyproject.toml` | MOD | config | n/a | self (existing `[project.optional-dependencies]`) | self-edit |
| `.gitignore` | MOD | config | n/a | self | self-edit |
| `auraframes/client.py` | MOD | service (HTTP transport) | request-response | self (4 sibling methods get/post/put/delete) | exact (internal) |
| `auraframes/aura.py` | MOD | facade | CRUD / orchestration | self (`get_all_assets`, `_init_logger`) | self-edit |
| `auraframes/api/accountApi.py` | MOD | api-client (controller) | request-response | `auraframes/api/frameApi.py` (sibling error-key sites) | exact |
| `auraframes/api/frameApi.py` | MOD | api-client (controller) | CRUD + cursor pagination | `auraframes/api/accountApi.py` (sibling) | exact |
| `auraframes/export.py` | MOD | utility (file-I/O) | streaming download → file | self (`get_image_from_asset`) | self-edit |
| `auraframes/exif.py` | MOD | utility (transform) | transform (bytes→bytes) | self (`_lookup_gps`, `write_exif`) | self-edit |

**Key insight (from RESEARCH.md):** the read path already exists and is import-clean. Phase 2 is verification + four surgical trust edits, NOT a build. Resist writing new helpers — call existing code and assert.

---

## Pattern Assignments

### `tests/conftest.py` (NEW — session login fixture + skip gate, D-01/D-02/D-03)

**Analog:** `tests/test_imports.py` (Phase 1 harness — pytest + `@pytest.mark.parametrize`, no `live` marker so it stays green) and the login state set up in `auraframes/aura.py:36-50`.

**Existing harness style to match** (`tests/test_imports.py:1-26`): plain `import pytest`, top-level functions, no classes, pydantic v2 idioms (`.model_fields`, `is_required()`). The new live tests must sit ALONGSIDE this file and NOT carry the `live` marker into it (the import smoke test must keep passing credential-less).

**Login state the fixture drives** — `Aura.login()` mutates the shared session; assertions read it back (`aura.py:36-50`):
```python
def login(self, email: str = os.getenv('AURA_EMAIL'), password: str = os.getenv('AURA_PASSWORD')):
    user = self.account_api.login(email, password)
    self._client.add_default_headers({
        'x-token-auth': user.auth_token,
        'x-user-id': user.id
    })
    return self
```
Auth state lands on `aura._client.http2_client.headers` (`client.py:78-79` `add_default_headers`). READ-01 asserts `aura._client.http2_client.headers.get("x-token-auth")` and `"x-user-id"` are populated.

**Fixture pattern (from RESEARCH.md Pattern 1):** session-scoped `aura` fixture that `pytest.skip`s when `AURA_EMAIL`/`AURA_PASSWORD` are unset, instantiates `Aura()`, calls `.login()`, returns it. A login throw errors all four tests (correctly reports "login broke").

---

### `tests/test_read_path.py` (NEW — 4 live tests, one per READ-01..04)

**Analog:** `tests/test_imports.py` for structure (flat functions, `import pytest`). Each test is `@pytest.mark.live` and takes the `aura` fixture.

**READ-01** — assert post-login session state (headers set on `client.http2_client.headers`, `user.id`/`user.auth_token` present).

**READ-02** — `aura.frame_api.get_frames()` returns `list[Frame]`; assert non-empty, print `f.name (f.id)`. Real call shape (`frameApi.py:13-19`):
```python
def get_frames(self) -> list[Frame]:
    json_response = self._client.get('/frames.json')
    return [Frame(**frame_data) for frame_data in json_response.get('frames')]
```

**READ-03** — drive the REAL `aura.get_all_assets(frame.id, limit=...)` (do NOT re-implement the loop). Compute `limit` from server count to force 2–3 pages (RESEARCH Pattern 2):
```python
frame = aura.frame_api.get_frames()[0]            # D-10: first frame
_, total = aura.frame_api.get_frame(frame.id)     # frameApi.py:21-28 → (Frame, total_asset_count)
assert total >= 2                                 # else pytest.skip (A2)
limit = max(1, total // 2)
assets = aura.get_all_assets(frame.id, limit=limit)
assert len(assets) == total                       # indirect proof the cursor branch ran
```

**READ-04** — select first image asset with `location_name` (D-10), download via `export.get_image_from_asset`, then read the file back with `exif.get_readable_exif` (D-09). Asset selection fields (`models/asset.py`): `is_live` (:54), `location` (:63), `location_name` (:64), `thumbnail_url` (:86, Optional → guard before `httpx.get(None)`), `video_url` (:100), `user_id` (:91), `file_name` (:45), `taken_at_dt` property (:105). Read-back assertion:
```python
readable = get_readable_exif(str(saved))          # exif.py:109 — nested dict keyed by IFD then tag NAME
assert readable["Exif"]["DateTimeOriginal"] == asset.taken_at_dt.strftime('%Y:%m:%d %H:%M:%S').encode()
if asset.location_name and readable.get("GPS"):
    assert readable["GPS"]                        # GPS conditional (D-09)
```
Download writes filename `{taken_at_dt:%Y%m%dT%H%M%S}-{file_name}` and does NOT return the path (`export.py:42,53`) — write to `tmp_path` and glob the single file.

---

### `auraframes/client.py` (MOD — service, request-response) — D-06 + D-07

**Analog:** the four sibling methods are near-identical; the edit must be applied uniformly to `get` (33-43), `post` (45-54), `delete` (56-65), `put` (67-76).

**Current per-method shape (`post`, lines 45-54)** — the exact pattern to edit:
```python
def post(self, url, data: dict = None, query_params: Optional[dict] = None, headers: Optional[dict] = None):
    logger.info(f'POST request to {url}', data=data, query_params=query_params, headers=headers)
    response = self.http2_client.post(url=url, json=data, headers=headers, params=query_params)

    self.history.append(response)
    logger.debug(f'Response ({response.status_code}), body: {response.json()}')

    self._set_cookies(response)

    return response.json()
```

**D-06 edit:** insert `response.raise_for_status()` AFTER `self.history.append(response)` and BEFORE the `logger.debug(... response.json())` / `return response.json()` in all four methods. httpx 0.28.1 `raise_for_status()` raises `httpx.HTTPStatusError`. Keep `history.append` before the raise so failures stay in history.

**D-07 secret leak (SECURITY-HIGH):** two leak sites per method —
- `logger.info(... data=data ...)` (line 46 in `post`, 68 in `put`) logs the request body; `/login.json` body carries the plaintext `password`.
- `logger.debug(f'Response ({response.status_code}), body: {response.json()}')` (lines 39/50/61/72) logs the response body; the login response carries `auth_token`.

**Imports already present** (`client.py:1-6`): `httpx`, `from httpx import Response, Timeout`, `from loguru import logger`. Redaction (RESEARCH recommends mechanism (a): a small `_redact(d)` that masks `password`/`auth_token`/`x-token-auth`, recursing into nested `user` dict) needs no new imports. Apply to BOTH the `data=` kwarg in `logger.info` and the response body before `logger.debug`.

---

### `auraframes/aura.py` (MOD — facade) — D-05 + D-08

**D-05 — parametrize `get_all_assets` + de-sleep (current `aura.py:55-63`):**
```python
def get_all_assets(self, frame_id: str):
    paginated_assets, cursor = self.frame_api.get_assets(frame_id)
    assets = paginated_assets
    while cursor:
        paginated_assets, cursor = self.frame_api.get_assets(frame_id, cursor=cursor)
        time.sleep(1)  # TODO: Make better (tm)
        assets.extend(paginated_assets)
    return assets
```
Add `limit: int = 1000` (passthrough to `get_assets`, whose signature already accepts `limit`, `frameApi.py:30`) and make the `time.sleep(1)` conditional/removed (RESEARCH suggests `page_delay: float = 0.0`). Default args must preserve production behavior except dropping the always-on stall. `import time` is at `aura.py:3` (keep if a conditional delay is retained; otherwise it may become unused).

**D-08 — `_init_logger` missing dir (BLOCKING, `aura.py:131-137`):**
```python
def _init_logger(self):
    # logger.remove()  # remove / set this to debug if needed
    logger.add(sys.stderr, level="INFO", format=...)
    logger.add('logs/file_{time}.log')      # <-- logs/ never created → FileNotFoundError
```
Add `os.makedirs('logs/', exist_ok=True)` at the top of `_init_logger`. `import os` already present (`aura.py:2`).

---

### `auraframes/api/accountApi.py` (MOD — api-client) — D-06 read-path error surfacing

**Current silent `pass` on read path (`login`, lines 27-32):**
```python
json_response = self._client.post('/login.json', login_payload)
if json_response.get('error') or not json_response.get('result'):
    # TODO: Error handling
    pass
return User(**json_response.get('result').get('current_user'))
```
Convert the `pass` to a raised error / explicit log including `json_response.get('message')` (no typed hierarchy — a plain `raise RuntimeError(...)` is in scope; MOD-03 is out). Only `login` is on the read path; `register`/`delete` (lines 34-69) are out of scope — leave them.

---

### `auraframes/api/frameApi.py` (MOD — api-client, cursor pagination) — D-06

**`get_assets` cursor + silent `error` pass (lines 30-46):**
```python
def get_assets(self, frame_id: str, limit: int = 1000, cursor: str = None) -> tuple[list[Asset], str]:
    json_response = self._client.get(f'/frames/{frame_id}/assets.json',
                                     query_params={'limit': limit, 'cursor': cursor})
    if json_response.get('error'):
        # json_response.get('message')
        pass
    assets = [Asset(**asset_data) for asset_data in json_response.get('assets')]
    return assets, json_response.get('next_page_cursor')
```
Convert the `pass` to a raise/log (mirror the accountApi edit). `limit`/`cursor` signature already supports D-05 — no signature change needed here. `get_frames` (13-19) and `get_frame` (21-28) need no edit; they are called as-is by the tests. **Do NOT touch** `update_frame`'s `.dict(exclude_unset=True)` at line 90 — it is update/upload code, off the read path (Phase 1 deferred D-05; optional only).

---

### `auraframes/export.py` (MOD — utility, file-I/O) — read-path download

**`get_image_from_asset` (lines 41-53)** — the verified READ-04 download path:
```python
def get_image_from_asset(asset: Asset, path: str, exif_writer: ExifWriter = None, ignore_cache=False):
    new_filename = os.path.join(path, f'{_get_path_safe_datetime(asset.taken_at_dt)}-{asset.file_name}')
    ...
    original_image_bytes = httpx.get(f'{settings.IMAGE_PROXY_BASE_URL}/{asset.user_id}/{asset.file_name}').content
    thumbnail = get_thumbnail(asset, BytesIO(original_image_bytes)) if exif_writer else None
    image = exif_writer.write_exif(original_image_bytes, asset, thumbnail)
    with open(new_filename, 'wb') as out:
        shutil.copyfileobj(image, out)
    return original_image_bytes
```
Note: imgproxy download is UNauthenticated (direct `httpx.get`). `get_thumbnail` (18-38) does `httpx.get(asset.thumbnail_url)` unconditionally — `thumbnail_url` is Optional (`asset.py:86`), so non-image/null assets fail here (Pitfall 5 → handle via image-asset selection in the test, not necessarily a code edit). Mainly READ via this file; once D-11 makes `write_exif` raise, a broken save surfaces here as an exception (caught by the test, not silently copied).

---

### `auraframes/exif.py` (MOD — utility, transform) — D-11

**1. Nominatim UA (line 34):** replace `Nominatim(user_agent="Upload Scripting Test")` with a proper identifier, e.g. `auraframes-python-client/1.0`.

**2. Geocode bare except — keep tolerant but typed (`_lookup_gps`, lines 43-47):**
```python
try:
    location = self.geolocator.geocode(location_name)
except:                                    # → except Exception; still log + return None (GPS conditional, D-09)
    logger.info(f'Failed to read GPS data for {location_name}')
    return None
```

**3. EXIF-write bare except — must SURFACE (`write_exif`, lines 89-93):**
```python
new_imag = io.BytesIO()
exif_bytes = piexif.dump(exif_dict)
try:
    piexif.insert(exif_bytes, image, new_imag)
except:                                    # → except Exception that RE-RAISES (don't return empty BytesIO)
    logger.info(f'Failed to write to image.')
return new_imag
```
Today this returns an empty `BytesIO` on failure → `export.py` copies a 0-byte file (Pitfall 4). Make EXIF-write fatal (re-raise) so a corrupt save fails loudly. Treat the two excepts DIFFERENTLY: geocode = tolerable, EXIF-write = fatal.

**4. Reuse `get_readable_exif` (lines 109-121) UNCHANGED** for the READ-04 read-back. Returns a nested dict keyed by IFD then tag NAME; `DateTimeOriginal` under `"Exif"`, GPS tags under `"GPS"`.

**Out of scope (flag for Phase 3, do NOT fix under MVP):** lat/long swap in `build_gps_ifd` (lines 17-30) vs `_lookup_gps` return order (line 56) — GPS is still "readable," so READ-04 passes; record as drift (Pitfall 6).

---

### `pyproject.toml` (MOD — config) — register `live` marker

**Current file has NO `[tool.pytest.ini_options]` section** (lines 1-25; only `[project]`, `[project.optional-dependencies]` dev=pytest>=8, `[build-system]`). Add:
```toml
[tool.pytest.ini_options]
markers = [
    "live: hits the live Aura API; requires AURA_EMAIL/AURA_PASSWORD (deselect with -m 'not live')",
]
```
No new dependencies — everything is already installed (pytest in `dev` extra). **Stale-pin note:** CLAUDE.md describes pre-Phase-1 pins; the live env is pydantic 2.13.4 / httpx 0.28.1 / Pillow 12.2.0 / piexif 1.1.3 / geopy 2.4.1 / Python 3.14 — the planner targets these, not CLAUDE.md's numbers.

---

### `.gitignore` (MOD — config) — D-08

Runtime output dirs are NOT currently ignored. Add `logs/`, `cache/`, `asset_images/`. Note `.env` is already covered (line 89) and `*.log` is present (line 62) but the directory entries are still needed (so empty/created dirs and JSON cache files are excluded).

---

## Shared Patterns

### Error surfacing (D-06)
**Source:** transport edit in `auraframes/client.py` (`response.raise_for_status()` in all 4 methods, before `.json()`).
**Apply to:** every read-path call (READ-01/02/03). Resource-layer `error`-key `pass` blocks at `accountApi.py:28-30` and `frameApi.py:42-44` become raise/log. No typed exception hierarchy (MOD-03 deferred).

### Secret redaction (D-07, SECURITY-HIGH — gate)
**Source:** `auraframes/client.py` `logger.info(... data=...)` (lines 46/68) and `logger.debug(... response.json())` (lines 39/50/61/72).
**Apply to:** request body + response body logging. Mask `password` / `auth_token` / `x-token-auth` (recurse nested `user`). Must land before any live run; verify via `grep -ri` of the log after a login.

### Model hydration + typed assertions
**Source:** `frameApi.py:19` `[Frame(**...)]`, `frameApi.py:45` `[Asset(**...)]`, `accountApi.py:32` `User(**...)`.
**Apply to:** all tests assert on typed pydantic-v2 model fields, never raw dicts. Cursor pagination is manual: `get_assets` returns `(assets, next_page_cursor)`; callers loop until cursor falsy.

### Runtime-dir creation + gitignore (D-08)
**Source:** `aura.py:_init_logger` (`os.makedirs('logs/', exist_ok=True)`) + `.gitignore`.
**Apply to:** `logs/`, `cache/`, `asset_images/`.

---

## No Analog Found

None. Every new file has a same-repo analog (the Phase 1 pytest harness `tests/test_imports.py`), and every modified file is its own best reference. RESEARCH.md's Code Examples are sketches; prefer the real call shapes cited above.

## Metadata

**Analog search scope:** `tests/`, `auraframes/` (`client.py`, `aura.py`, `api/`, `export.py`, `exif.py`, `models/asset.py`), `pyproject.toml`, `.gitignore`.
**Files scanned:** 9 read in full + 1 grep (asset field lines).
**Pattern extraction date:** 2026-06-29
