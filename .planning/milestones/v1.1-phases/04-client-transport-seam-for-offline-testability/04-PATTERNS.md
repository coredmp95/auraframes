# Phase 4: Client transport seam for offline testability - Pattern Map

**Mapped:** 2026-07-01
**Files analyzed:** 6 (2 modified, 4+ new)
**Analogs found:** 6 / 6

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `auraframes/client.py` (modify `__init__`) | service (HTTP session wrapper) | request-response | itself (existing `__init__`, lines 45-51) | exact — additive param on existing constructor |
| `auraframes/aura.py` (modify `__init__`) | service (facade/DI root) | request-response | itself (existing `__init__`, lines 25-34) | exact — additive param on existing constructor |
| `tests/offline.py` (new) | test-harness / utility | request-response (router/dispatch) | `tests/conftest.py` (`aura` fixture, lines 13-32) | role-match — same "build authenticated Aura instance for tests" responsibility, different transport |
| `tests/fixtures/*.json` (new) | fixture data | file-I/O (static JSON) | none in-repo (no existing fixtures dir) — model shape is the real analog: `auraframes/models/frame.py`, `auraframes/models/asset.py`, `auraframes/models/user.py` | no direct file analog; model-shape analog only |
| `tests/test_offline_read_path.py` (new) | test | request-response | `tests/test_read_path.py` (whole file) | exact — mirrors its assertions offline |
| fixture-validity check (small pytest, optional per Pitfall 1) | test | file-I/O / transform | `tests/test_imports.py` (style: small, single-purpose smoke test) | role-match |

## Pattern Assignments

### `auraframes/client.py` — add `transport` param (service, request-response)

**Analog:** itself, current constructor.

**Current constructor** (`auraframes/client.py:45-51`):
```python
def __init__(self, history_len: int = 30):
    self.http2_client = httpx.Client(http2=True, base_url=f'{AURA_API_BASE_URL}/{AURA_API_VERSION}', headers={
        'accept-language': 'en-US',
        'cache-control': 'no-cache',
        'user-agent': USER_AGENT,
        'content-type': 'application/json; charset=utf-8',
    }, timeout=Timeout(timeout=20.0))

    self.history: Deque[Response] = deque(maxlen=history_len)
```

**Pattern to apply (additive-only, per RESEARCH.md Pattern 1):**
```python
def __init__(self, history_len: int = 30, transport: httpx.BaseTransport | None = None):
    self.http2_client = httpx.Client(http2=True, base_url=f'{AURA_API_BASE_URL}/{AURA_API_VERSION}', headers={
        'accept-language': 'en-US',
        'cache-control': 'no-cache',
        'user-agent': USER_AGENT,
        'content-type': 'application/json; charset=utf-8',
    }, timeout=Timeout(timeout=20.0), transport=transport)

    self.history: Deque[Response] = deque(maxlen=history_len)
```
Only the `httpx.Client(...)` call changes (add `transport=transport` kwarg); the signature type hint
`httpx.BaseTransport | None = None` follows the existing `Optional[dict]` style used elsewhere in
this same file (`get`/`post`/`put`/`delete` signatures, lines 55, 68, 80, 92) but as native `| None`
union syntax since this is a fresh param, not a retrofit — confirm against RESEARCH.md's exact
recommended signature (`httpx.BaseTransport | None = None`).

**Everything else in the class (redaction, cookie handling, `raise_for_status`, `history.append`,
logging) is UNCHANGED** — do not touch `get`/`post`/`put`/`delete`/`_redact`/`_set_cookies`
(`auraframes/client.py:55-113`); this is a single-line-of-intent change deepened only at the
constructor.

---

### `auraframes/aura.py` — add `client` param (facade, request-response)

**Analog:** itself, current constructor.

**Current constructor** (`auraframes/aura.py:25-34`):
```python
def __init__(self):
    self._init_logger()
    self._client = Client()
    # TODO: Can probably use DI for passing around the client?
    self.account_api = AccountApi(self._client)
    self.frame_api = FrameApi(self._client)
    self.people_api = PeopleApi(self._client)
    self.activity_api = ActivityApi(self._client)
    self.asset_api = AssetApi(self._client)
    self.exif_writer = ExifWriter()
```

**Pattern to apply:**
```python
def __init__(self, client: Client | None = None):
    self._init_logger()
    self._client = client or Client()
    self.account_api = AccountApi(self._client)
    self.frame_api = FrameApi(self._client)
    self.people_api = PeopleApi(self._client)
    self.activity_api = ActivityApi(self._client)
    self.asset_api = AssetApi(self._client)
    self.exif_writer = ExifWriter()
```
Remove the `# TODO: Can probably use DI...` comment (this phase closes it) — do not add a new TODO
in its place. All `*Api` constructors (`AccountApi(self._client)` etc.) are unchanged; they already
receive `self._client` via constructor injection through `BaseApi`.

---

### `tests/offline.py` — new offline harness (test-harness, request-response router)

**Analog:** `tests/conftest.py`'s `aura` fixture (session-scoped authenticated instance builder) —
same job ("hand back a ready-to-use `Aura` instance to a test"), different transport.

**Analog excerpt** (`tests/conftest.py:13-32`):
```python
@pytest.fixture(scope="session")
def aura():
    """Authenticated Aura session shared by all live read-path tests. ..."""
    email = os.getenv("AURA_EMAIL")
    password = os.getenv("AURA_PASSWORD")
    if not email or not password:
        pytest.skip("AURA_EMAIL/AURA_PASSWORD not set; skipping live Aura API tests")

    from auraframes.aura import Aura

    instance = Aura()
    instance.login()
    return instance
```

**Pattern to apply** (RESEARCH.md's verified sketch — copy near-verbatim, this was validated by
direct execution against the pinned httpx in this session):
```python
import json
from pathlib import Path

import httpx

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


def make_router(overrides: dict | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path  # includes the '/v5' base_url prefix — see Pitfall 2
        if path == "/v5/login.json":
            return httpx.Response(200, json=_load("login.json"))
        if path == "/v5/frames.json":
            return httpx.Response(200, json=_load("frames.json"))
        if path.endswith("/assets.json"):
            cursor = request.url.params.get("cursor")  # None on page 1 — see Pitfall 3
            fixture = "assets_page2.json" if cursor else "assets_page1.json"
            return httpx.Response(200, json=_load(fixture))
        return httpx.Response(404, json=_load("error_envelope.json"))
    return handler


def offline_aura(overrides: dict | None = None):
    from auraframes.aura import Aura
    from auraframes.client import Client

    transport = httpx.MockTransport(make_router(overrides))
    return Aura(client=Client(transport=transport))
```
Keep this file plain (module-level functions), not a fixture-only file — `conftest.py`'s existing
`aura` fixture stays untouched and is a *separate* concern (live session). If a pytest fixture
wrapper over `offline_aura()` is wanted for ergonomics, add it to `conftest.py` alongside — but do
not merge/replace the existing `aura` fixture.

---

### `tests/fixtures/*.json` — new static fixture files (fixture data, file-I/O)

**No direct file analog exists** (no `tests/fixtures/` dir currently). The governing analog is the
**pydantic model shape**, not another file:

- `auraframes/models/frame.py` — `Frame` (~50 fields, most required, no defaults)
- `auraframes/models/asset.py` — `Asset` (~20 required fields: `data_uti`, `exif_orientation`,
  `file_name`, `height`, `width`, `taken_at`, `user`, etc.)
- `auraframes/models/user.py` — `User`

**Rule (Pitfall 1):** every fixture must hydrate its corresponding model without raising —
`Frame(**json.loads(path.read_text()))` / `Asset(**...)` / `User(**...)` must succeed. Record from
a real response, trim, then verify against the model — never hand-type from memory.

**Rule (security):** sanitize every field flagged by the project's own `_REDACT_KEYS` convention
(`auraframes/client.py:14`: `password`, `auth_token`, `x-token-auth`) plus cookies, GPS
coordinates, account emails/names, and account-scoped URLs before committing.

Required fixture set (per ROADMAP.md test plan + RESEARCH.md structure):
```
tests/fixtures/login.json           # AccountApi.login response shape: {"result": {"current_user": {...}}}
tests/fixtures/frames.json          # FrameApi.get_frames response shape: {"frames": [...]}
tests/fixtures/assets_page1.json    # FrameApi.get_assets page 1: {"assets": [...], "next_page_cursor": "<token>"}
tests/fixtures/assets_page2.json    # FrameApi.get_assets page 2: {"assets": [...], "next_page_cursor": null}
tests/fixtures/error_envelope.json  # {"error": "...", "message": "..."} shape used by both raise sites below
```

---

### `tests/test_offline_read_path.py` — new offline test module (test, request-response)

**Analog:** `tests/test_read_path.py` (whole file) — mirror its assertion intent, but drive it
through `offline_aura()` instead of the `aura` (live) fixture, and drop `@pytest.mark.live`.

**Analog excerpts:**

Login header assertion (`tests/test_read_path.py:17-26`):
```python
@pytest.mark.live
def test_read_01_login(aura):
    headers = aura._client.http2_client.headers
    assert headers.get("x-token-auth"), "x-token-auth header missing after login"
    assert headers.get("x-user-id"), "x-user-id header missing after login"
```
Offline mirror should call `offline_aura()`, then `.account_api.login(email, password)` (or
whatever `Aura`'s public login path is) through the mocked transport and assert on the returned
`User`/header state — see RESEARCH.md's verified header-assertion example below.

Frame hydration assertion (`tests/test_read_path.py:29-38`):
```python
@pytest.mark.live
def test_read_02_list_frames(aura):
    frames = aura.frame_api.get_frames()
    assert frames, "expected at least one frame for the account"
    for f in frames:
        assert isinstance(f, Frame)
        assert f.id, "frame is missing an id"
```

Pagination-drain assertion shape (`tests/test_read_path.py:41-68`) — offline version should call
`aura.frame_api.get_assets(frame_id)` (or `Aura.get_all_assets`) with `limit` forcing the cursor
branch, and assert the stitched result equals `len(page1) + len(page2)` from the two fixtures.

**Verified login/redaction example from RESEARCH.md (Code Examples section)** — use this shape for
the login test's transport-level assertion:
```python
def handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == '/v5/login.json':
        return httpx.Response(200, json={
            "result": {"current_user": {"auth_token": "secret-token", "id": "u1"}}
        })
    return httpx.Response(404, json={"error": "not_found"})

c = Client(transport=httpx.MockTransport(handler))
resp = c.post('/login.json', data={'user': {'password': 'hunter2'}})
```

**Error-envelope raise pattern to test (two distinct mechanisms, RESEARCH.md Pattern 3):**

1. HTTP-status raise via `Client.raise_for_status` (unconditional, `client.py:61,73,85,97`):
```python
try:
    c.get('/missing.json')
except httpx.HTTPStatusError as e:
    assert e.response.status_code == 404
```

2. Soft "200 + `{"error": ...}` body" business-rule raise, from the actual source:
`AccountApi.login` (`auraframes/api/accountApi.py:26-31`):
```python
json_response = self._client.post('/login.json', login_payload)
if json_response.get('error') or not json_response.get('result'):
    raise RuntimeError(
        f"Aura login failed: {json_response.get('message') or json_response.get('error') or 'no result returned'}"
    )
```
`FrameApi.get_assets` (`auraframes/api/frameApi.py:47-52`):
```python
json_response = self._client.get(f'/frames/{frame_id}/assets.json',
                                 query_params={'limit': limit, 'cursor': cursor})
if json_response.get('error'):
    raise RuntimeError(
        f"get_assets failed for frame {frame_id}: "
        f"{json_response.get('message') or json_response.get('error')}"
    )
```
Both should be exercised with a mocked 200 response whose body is `error_envelope.json`'s shape,
asserting `pytest.raises(RuntimeError)`.

**pytest marker config** (`pyproject.toml:27-28`, `[tool.pytest.ini_options]` `markers = [...]`) —
the existing `live` marker is declared there; offline tests need **no new marker** (they are the
default/unmarked suite that already runs without credentials), consistent with ROADMAP.md's "New
offline tests (default `pytest` run, no creds)".

---

## Shared Patterns

### Additive-only constructor injection (both `Client` and `Aura`)
**Source:** `auraframes/client.py:45`, `auraframes/aura.py:25` (current signatures)
**Apply to:** Both modified files — new param always defaults to `None`, so `main.py:34` and every
existing call site (including `tests/conftest.py:30`'s `Aura()`) keeps working unmodified.

### Redaction stays intact through the mock
**Source:** `_redact()` in `auraframes/client.py:14-32`
**Apply to:** any offline test asserting on logged output — the mock does not bypass `_redact`;
verified directly in RESEARCH.md that a mocked login response still gets `auth_token` masked in the
debug log line.

### Business-rule error envelope raise (`{"error": ...}` in a 200 body)
**Source:** `auraframes/api/accountApi.py:26-31`, `auraframes/api/frameApi.py:47-52`
**Apply to:** `tests/test_offline_read_path.py`'s error-envelope tests, and the shape of
`tests/fixtures/error_envelope.json`.

### `/v5` path prefix in router matching
**Source:** `auraframes/client.py:46` (`base_url=f'{AURA_API_BASE_URL}/{AURA_API_VERSION}'`)
**Apply to:** `tests/offline.py`'s router — every `if` branch must match the fully-resolved path
(e.g. `/v5/frames.json`), never the relative path passed to `Client.get()`.

### Query-param-based routing for repeated-path endpoints
**Source:** RESEARCH.md Pattern 2 / Pitfall 3, `auraframes/client.py:56` (`None`-value filtering)
**Apply to:** the `assets.json` branch in `tests/offline.py`'s router — branch on
`request.url.params.get("cursor")` truthiness, not presence/absence of the key or empty-string.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `tests/fixtures/*.json` | fixture data | file-I/O | No existing `tests/fixtures/` directory; governed by model shape (`Frame`/`Asset`/`User`), not a file analog — see Pitfall 1 guidance above |
| optional fixture-validity smoke test | test | file-I/O/transform | No existing "validate every fixture hydrates its model" test exists yet; closest *style* analog is `tests/test_imports.py` (small, single-purpose) but no structural analog |

## Metadata

**Analog search scope:** `auraframes/client.py`, `auraframes/aura.py`, `auraframes/api/*.py`,
`auraframes/models/*.py`, `tests/conftest.py`, `tests/test_read_path.py`, `tests/test_imports.py`,
`pyproject.toml`
**Files scanned:** 6 read in full + `pyproject.toml` grep for pytest markers
**Pattern extraction date:** 2026-07-01
