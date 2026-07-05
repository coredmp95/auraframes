# Phase 4: Client transport seam for offline testability - Research

**Researched:** 2026-07-01
**Domain:** httpx transport injection (dependency injection seam) + pytest fixture/harness design for a synchronous Python HTTP client wrapper
**Confidence:** HIGH

## Summary

This phase has no open architectural questions — the `/grilling` session on 2026-06-30 already
settled the design (see locked decisions below). The research need was narrow and mechanical:
confirm the *exact* current signatures of `Client.__init__`/`Aura.__init__`, confirm how
`httpx.MockTransport` behaves with the pinned httpx `0.28.1` (routing signature, HTTP/2
interaction, cookie/header pass-through), and confirm the existing `@live` test harness shape so
the new offline harness composes with it instead of duplicating pytest config.

All of the below was verified by direct execution against the project's own pinned dependency
(httpx `0.28.1`, resolved from `uv.lock`) inside the project venv (`uv run python`), not from
general httpx knowledge — this is the highest-confidence verification available for this kind of
mechanical, version-specific question.

**Primary recommendation:** Add `transport: httpx.BaseTransport | None = None` to `Client.__init__`
and pass it straight through to the inner `httpx.Client(...)` constructor call; add
`client: Client | None = None` to `Aura.__init__` and use `self._client = client or Client()`. No
other production code changes are needed. The two load-bearing gotchas the plan must account for:
(1) the mock router must match on `request.url.path` **including the `/v5` base_url prefix**
(e.g. `/v5/frames.json`, not `/frames.json`), and (2) the two-page `get_all_assets` fixture pair
must be distinguished by **query parameter** (`request.url.params.get("cursor")`), not by path,
since both pages hit the identical path.

## Architectural Responsibility Map

This project is a synchronous Python API-client library, not a multi-tier web app, so the
standard browser/SSR/API/CDN/DB tiers don't map cleanly. Adapted tiers for this codebase:

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| HTTP transport (network I/O) | `httpx.BaseTransport` (real or `MockTransport`) | — | Owns the actual bytes-on-the-wire; everything above it is transport-agnostic once injected |
| Session/header/cookie/history state, redaction, `raise_for_status` | `Client` (`auraframes/client.py`) | — | This is the seam being deepened; must stay identical regardless of transport |
| Resource verbs, response→model hydration, business-rule error raising | `*Api` classes (`FrameApi`, `AccountApi`, etc.) | `Client` | Untouched by this phase; they only ever see `Client`, never the transport |
| Facade/orchestration (login, pagination loop, dump/export) | `Aura` | `*Api` | Gains the second seam (`client=None`); orchestration logic itself is untouched |
| Offline test harness (router, fixtures) | Test infrastructure (`tests/`) | — | New code this phase adds; not part of the shipped package |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | 0.28.1 (pinned via `pyproject.toml` `>=0.27`, resolved in `uv.lock`) `[VERIFIED: uv.lock + uv run python -c "import httpx; print(httpx.__version__)"]` | HTTP client; `httpx.MockTransport` is httpx's own first-party offline-testing mechanism | Already the project's only HTTP client; `MockTransport` ships in the same package, no new dependency |
| pytest | `>=8` (dev extra, already installed — `pytest-9.1.1` resolved) `[VERIFIED: pyproject.toml + uv.lock]` | Test runner; existing `@live` marker and `aura` fixture already live in `tests/conftest.py` | Already the project's only test runner |

### Supporting
No new libraries are needed. `httpx.MockTransport` and the stdlib `json`/`pathlib` cover the
entire harness (loading fixture JSON files, building a router). Do not add `respx`,
`pytest-httpx`, or similar third-party httpx-mocking add-ons for this phase — httpx's own
`MockTransport` is the currency-correct, zero-dependency mechanism and is exactly what the
settled design (ROADMAP.md) specifies.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `httpx.MockTransport` (stdlib-to-httpx, no new dep) | `respx` (third-party) | `respx` adds URL-pattern matching sugar but is an extra dependency for a problem `MockTransport` already solves cleanly at this project's size; violates the "pragmatic, minimal-diff" constraint in CLAUDE.md |
| Hand-rolled router function | `pytest-httpx` fixture plugin | Adds a pytest plugin dependency and its own fixture-injection magic; the settled design already specifies a plain `offline_aura(fixtures)` helper, which is simpler and more debuggable |

**Installation:** None — `httpx` and `pytest` are already declared dependencies; no `pyproject.toml`
change is needed for this phase.

## Package Legitimacy Audit

**Not applicable — this phase installs no new packages.** `httpx.MockTransport` is a class already
present in the pinned `httpx==0.28.1` package (`httpx/_transports/mock.py`), and `pytest` is
already a dev-extra dependency. No `pip`/`uv add` step, no registry lookup, and no legitimacy gate
is required for this phase.

## Architecture Patterns

### System Architecture Diagram

```text
                         ┌─────────────────────────────┐
                         │   test_offline_*.py          │
                         │  (new offline test module)   │
                         └──────────────┬───────────────┘
                                        │ calls offline_aura(fixtures)
                                        ▼
                         ┌─────────────────────────────┐
                         │  tests/offline.py             │
                         │  - fixture loader (json)      │
                         │  - path+query → Response router│
                         └──────────────┬───────────────┘
                                        │ builds
                                        ▼
              Aura(client=Client(transport=MockTransport(router)))
                                        │
                     ┌──────────────────┴───────────────────┐
                     ▼                                       ▼
             Aura orchestration                      *Api classes (FrameApi,
        (login(), get_all_assets(),                   AccountApi, ...) — UNCHANGED
         dump_frame(), ...) — UNCHANGED                       │
                     │                                        ▼
                     └───────────────────────────────►   Client.get/post/put/delete
                                                         (headers, cookies, history,
                                                          _redact, raise_for_status) — UNCHANGED
                                                                │
                                                                ▼
                                                     httpx.Client(transport=…)
                                                                │
                                        ┌───────────────────────┴───────────────────────┐
                                        ▼                                               ▼
                              transport=None (default)                    transport=MockTransport(handler)
                              → real HTTPTransport                        → handler(request) returns a
                              → hits api.pushd.com over the network         canned httpx.Response from
                                (used by @live tests / main.py)              tests/fixtures/*.json
                                                                              (used by new offline tests)
```

Trace the primary use case (an offline `get_all_assets` pagination test): test module calls
`offline_aura(fixtures)` → builds `Aura(client=Client(transport=MockTransport(router)))` →
test calls `aura.get_all_assets(frame_id, limit=...)` → `Aura` (unchanged) calls
`FrameApi.get_assets` (unchanged) → `Client.get` (unchanged: logs, appends history, calls
`raise_for_status`, redacts, sets cookies) → `httpx.Client.get` → since `transport` was supplied,
`_init_transport` returns it directly (`httpx/_client.py:718-724`, confirmed by reading the
installed source) → `MockTransport.handle_request` invokes `router(request)` → router reads
`request.url.path` (`/v5/frames/{id}/assets.json`) and `request.url.params.get("cursor")` to pick
page 1 or page 2 fixture JSON → returns `httpx.Response(200, json=fixture_dict)` → flows back up
through `Client.get` (cookies/redact/raise_for_status all execute against the fake response
exactly as they would a real one) → `FrameApi.get_assets` hydrates `Asset` models → `Aura`'s
cursor loop repeats until `next_page_cursor` is `None`.

### Recommended Project Structure
```
tests/
├── conftest.py              # existing: @live marker, session `aura` fixture — UNCHANGED
├── offline.py               # NEW: router builder + offline_aura(fixtures) helper
├── fixtures/                # NEW: sanitized, hand-trimmed JSON recordings
│   ├── login.json
│   ├── frames.json
│   ├── assets_page1.json
│   ├── assets_page2.json
│   └── error_envelope.json
├── test_read_path.py        # existing live tests — UNCHANGED
├── test_offline_read_path.py  # NEW: offline mirror of test_read_path.py's assertions
└── test_imports.py          # existing — UNCHANGED
```

### Pattern 1: Additive-only constructor injection
**What:** `Client.__init__(self, history_len: int = 30, transport: httpx.BaseTransport | None = None)`
passes `transport=transport` straight into the existing `httpx.Client(...)` call
(`auraframes/client.py:46-51`); `Aura.__init__(self, client: Client | None = None)` becomes
`self._client = client or Client()` (`auraframes/aura.py:25-27`).
**When to use:** Any time a caller needs to swap in a fake transport (tests) while every other
caller (`main.py:34`, `tests/conftest.py:30`, the current `auraframes/aura.py:27`) keeps working
unmodified because both new params default to `None`.
**Example (verified against installed httpx source, `httpx/_client.py`):**
```python
# httpx.Client._init_transport (installed source, httpx==0.28.1)
def _init_transport(self, ..., transport: BaseTransport | None = None) -> BaseTransport:
    if transport is not None:
        return transport          # <-- explicit transport always wins, http2 flag is ignored
    return HTTPTransport(..., http2=http2, ...)
```
This confirms `http2=True` (currently hardcoded at `client.py:46`) and an injected `MockTransport`
do not conflict: the `if http2: import h2` guard still runs unconditionally before
`_init_transport` is called (so `h2` must stay importable, which it already is — it's a pinned
dependency), but the actual `HTTPTransport(http2=True, ...)` is never constructed when a transport
is supplied. `Client` needs zero special-casing for `http2` when adding the `transport` param.

### Pattern 2: Path + query-param router (not path-only)
**What:** A single dict/function keyed by `request.url.path` is *not* sufficient to drive the
2-page `get_all_assets` fixture pair, because both pages hit the exact same path
(`/v5/frames/{id}/assets.json`) — only the `cursor` query param differs.
**When to use:** Any endpoint exercised more than once per test with different query params
(pagination is the only current case, but the pattern generalizes).
**Example (verified by direct execution against `auraframes.client.Client` + `httpx.MockTransport`):**
```python
# tests/offline.py — sketch confirmed to work end-to-end in this session
import json
from pathlib import Path
import httpx

FIXTURES_DIR = Path(__file__).parent / "fixtures"

def _load(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())

def make_router(overrides: dict | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path  # NOTE: includes the '/v5' base_url prefix, e.g. '/v5/frames.json'
        if path == "/v5/login.json":
            return httpx.Response(200, json=_load("login.json"))
        if path == "/v5/frames.json":
            return httpx.Response(200, json=_load("frames.json"))
        if path.endswith("/assets.json"):
            cursor = request.url.params.get("cursor")  # None on page 1, a token string on page 2
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

### Pattern 3: Two distinct error paths to test
**What:** The codebase has two separate error-surfacing mechanisms that must both be exercised:
(1) HTTP-status errors via `Client`'s unconditional `response.raise_for_status()`
(`client.py:61,73,85,97` — raises `httpx.HTTPStatusError` for any 4xx/5xx, verified by direct
execution returning `httpx.Response(404, ...)` through a mocked `Client` and observing the raise);
(2) soft "200 OK but `{"error": ...}` in the body" business-rule errors, raised explicitly as
`RuntimeError` in `AccountApi.login` (`accountApi.py:28-33`) and `FrameApi.get_assets`
(`frameApi.py:50-56`) — `register()` and `delete()` do **not** raise on this shape (TODO-marked
silent `pass` at `accountApi.py:59-61`, D-06-style gap not in this phase's scope).
**When to use:** The test plan's "error-envelope raise" bullet should cover both: a mocked
404/475-style HTTP response (proves `raise_for_status` still fires through the mock) and a mocked
200 response whose body is `{"error": "...", "message": "..."}` (proves `get_assets`'/`login`'s
own `RuntimeError` still fires).

### Anti-Patterns to Avoid
- **Routing only on `request.url.path` for paginated endpoints:** silently returns page-1 data
  forever, making the offline `get_all_assets` test falsely pass without ever exercising the
  cursor branch. Always inspect `request.url.params` for endpoints called more than once per test.
- **Forgetting the `/v5` base_url prefix in router `if` branches:** a router written to match
  `/frames.json` will never match, because `Client`'s `httpx.Client` is constructed with
  `base_url=f'{AURA_API_BASE_URL}/{AURA_API_VERSION}'` (`client.py:46`) and httpx's
  `request.url.path` reflects the *full* resolved path, not the relative path passed to `.get()`.
  Verified directly: a call to `c.get('/frames.json')` produces `request.url.path == '/v5/frames.json'`.
- **Adding a third-party mocking library:** `respx`/`pytest-httpx` are unnecessary weight given
  `httpx.MockTransport` already ships in the pinned dependency and the settled design specifies it
  explicitly.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Faking HTTP responses for a `httpx.Client` | A custom `Client` subclass that skips network calls, or monkey-patching `httpx.Client.get`/`.post` | `httpx.MockTransport(handler)` passed via the new `transport` param | It's httpx's own supported seam (`BaseTransport` is the documented extension point); monkeypatching would bypass `Client`'s own logic (`raise_for_status`, cookie-setting, redaction) instead of exercising it, defeating the point of this phase |
| Building minimal-but-valid `Frame`/`Asset` JSON fixtures by guessing field names | Hand-typing a JSON blob from memory of the API shape | Record a real response once, then trim it, validating against the actual pydantic model (`Frame(**data)` / `Asset(**data)` must not raise) | `Frame` (`auraframes/models/frame.py`) has ~50 fields with **no defaults** on the majority of them (only ~15 are `Optional[...] = None`); `Asset` similarly has ~20 required fields (`data_uti`, `exif_orientation`, `file_name`, `height`, `width`, `taken_at`, `user`, etc., `auraframes/models/asset.py`). A hand-guessed minimal JSON will almost certainly omit a required field and raise `pydantic.ValidationError` at hydration time inside the test, not at fixture-authoring time. See Pitfall 1 below. |

**Key insight:** The models in this codebase were built as a faithful straight-port of the
original API shape (D-01 era decisions), so they intentionally have very few optional fields.
Fixture minimization must be validated against the model, not against intuition about what "should"
be optional.

## Common Pitfalls

### Pitfall 1: Hand-trimmed fixtures silently missing required Pydantic fields
**What goes wrong:** A fixture JSON is trimmed down for readability, accidentally dropping a
required field (e.g. `Frame.contributor_tokens`, `Frame.last_feed_item`, `Asset.data_uti`).
**Why it happens:** `Frame` and `Asset` were ported 1:1 from the original API responses and use
very few `Optional[...] = None` fields — the JSON payload the live API actually returns already
contains every one of these keys, so it's easy to assume a field is "just noise" and cut it.
**How to avoid:** After trimming a fixture, add a one-line hydration assertion in the harness or a
dedicated fixture-validity test: `Frame(**json.loads(path.read_text()))` (and similarly for
`Asset`, `User`) must not raise. Do this once per fixture file, ideally as a small pytest that
iterates `tests/fixtures/*.json` matched to their model, so a future accidental trim is caught
immediately rather than surfacing as a confusing `ValidationError` deep inside an unrelated test.
**Warning signs:** `pydantic_core._pydantic_core.ValidationError: N validation errors for Frame`
raised from inside `FrameApi.get_frames()` during an offline test — this means the fixture is
missing (or mistyped) a required field, not that the seam/router logic is broken.

### Pitfall 2: Router keyed on relative path instead of resolved path
**What goes wrong:** offline test hits the router's fallback/404 branch for every request, even
though the URL "looks right" in the test code (e.g. `'/frames.json'`).
**Why it happens:** `Client`'s inner `httpx.Client` has `base_url='https://api.pushd.com/v5'`; the
`request.url.path` seen inside a `MockTransport` handler is always the fully-resolved path
(`/v5/frames.json`), not the relative path string that call sites (`FrameApi.get_frames`, etc.)
pass to `Client.get()`.
**How to avoid:** Either match against the full `/v5/...` path in the router, or strip the version
prefix once at router-entry (`path.removeprefix('/v5')`) before comparing against relative-path
keys. Verified directly in this session — this is not a version-specific quirk, it's how any
`base_url`-configured httpx client behaves.
**Warning signs:** Every offline test returns the router's fallback response (e.g. a 404), no
matter which endpoint is called.

### Pitfall 3: `cursor=None` filtered out of query params entirely (not sent as empty)
**What goes wrong:** A router that does `request.url.params.get("cursor") == ""` to detect "no
cursor" never matches, because page 1's request has *no* `cursor` key in the query string at all.
**Why it happens:** `Client.get()` (`client.py:56`) filters `query_params` to drop any key whose
value is `None` before calling `self.http2_client.get(...)`: `{k: v for k, v in
query_params.items() if v is not None}`. `FrameApi.get_assets` always passes `cursor=cursor`
(`frameApi.py:48-49`), so on page 1 (`cursor=None`) the key is stripped entirely by `Client`
before the request is even sent.
**How to avoid:** Use `request.url.params.get("cursor")` (returns `None`, not `""`, when the key
is absent — verified directly) and branch on truthiness, matching exactly what
`Aura.get_all_assets`'s `while cursor:` loop already assumes.
**Warning signs:** The offline pagination test always serves page 1's fixture, or a `KeyError`/
`AttributeError` if the router assumes the key is always present.

## Code Examples

### Login header assertion through a mocked transport (verified end-to-end this session)
```python
# Confirms Client's redaction, cookie handling, and header mutation all still work
# unchanged when `transport` is supplied — ran directly against this repo's Client
# (with a locally monkey-patched __init__ standing in for the not-yet-added `transport` param).
import httpx
from auraframes.client import Client

def handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == '/v5/login.json':
        return httpx.Response(200, json={
            "result": {"current_user": {"auth_token": "secret-token", "id": "u1"}}
        })
    return httpx.Response(404, json={"error": "not_found"})

c = Client(transport=httpx.MockTransport(handler))
resp = c.post('/login.json', data={'user': {'password': 'hunter2'}})
# DEBUG log line observed: body: {'result': {'current_user': {'auth_token': '***REDACTED***', ...}}}
# -> confirms `_redact()` still masks auth_token even though the response came from a mock.
```

### Raising through `raise_for_status` with a mocked 404 (verified this session)
```python
try:
    c.get('/missing.json')
except httpx.HTTPStatusError as e:
    assert e.response.status_code == 404  # raised exactly as it would for a real 4xx
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| All `*Api`/`Aura` tests hit the live `api.pushd.com` (Phase 2's `@live`-marked suite) | Offline `MockTransport`-backed harness for parsing/pagination/hydration logic; `@live` kept only as the "drift oracle" | This phase (v2.0, phase 4) | Most of `test_read_path.py`'s assertions can run in CI/locally with no credentials and no network; live tests shrink to the minimum needed to catch real API drift |

**Deprecated/outdated:** Nothing in the stack is deprecated — httpx `0.28.1` is current at the
time of this research and `MockTransport` is not a legacy API.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The exact byte-for-byte production shape of a *real* Aura API `error` envelope (i.e. whether `error` is a string, bool, or nested object, and whether `message` always accompanies it) is not independently confirmed in this research session — the codebase's own `.get('error')`/`.get('message')` handling was read directly from source (`accountApi.py`, `frameApi.py`), but no live error response was captured. `[ASSUMED]` | Pattern 3 / Code Examples (error-envelope fixture) | If the real shape differs (e.g. `error` is `{"code": ..., "detail": ...}` instead of a string), the hand-authored `error_envelope.json` fixture may not exactly match production, though it would still correctly exercise the `RuntimeError` raise since the code only checks truthiness of `.get('error')` |

**If this table is empty:** N/A — see A1 above. Everything else in this research (constructor
signatures, httpx internals, existing test structure, model field requiredness) was verified by
direct source inspection and/or live execution against the project's pinned dependencies in this
session.

## Open Questions

None — the architecture-review session already settled every design decision for this phase
(constructor signatures, seam boundaries, test-plan shape). The mechanical unknowns this research
was scoped to resolve (MockTransport routing signature, HTTP/2 interaction, path-prefix behavior,
pagination query-param distinguishing, existing `@live` harness shape, model field requiredness)
are all resolved above with HIGH confidence via direct execution.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| httpx (with `MockTransport`) | Offline transport seam | ✓ | 0.28.1 (pinned, `uv.lock`) | — |
| pytest | Running new/existing tests | ✓ | 9.1.1 (resolved) | — |
| uv | Running the test suite (`uv run pytest`) | ✓ (used throughout this research session) | — | — |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None.

## Security Domain

`security_enforcement` is enabled (`security_asvs_level: 1`) in `.planning/config.json`. This
phase adds a test-only dependency-injection seam and touches no new auth/session/crypto logic —
the `add_default_headers` auth mutation and login mechanism are explicitly out of scope (deferred
to architecture-review candidate #2). Most ASVS categories therefore do not apply; the two that
are marginally relevant are noted below for the planner's awareness.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | No | Untouched this phase (candidate #2's concern) |
| V3 Session Management | No | Untouched this phase — cookie/header persistence logic in `Client` is not modified, only made reachable through a different transport |
| V4 Access Control | No | N/A — client library, no access-control surface |
| V5 Input Validation | Marginal | Fixture JSON is hand-authored test data, not user input; the only "validation" surface is that fixtures must satisfy the existing pydantic models (see Pitfall 1) — not a security control, but a correctness one |
| V6 Cryptography | No | No crypto touched; note that fixtures must have real auth tokens/cookies/GPS/account identifiers scrubbed per the settled design's "sanitized" requirement — this is a data-hygiene concern (don't commit real secrets to `tests/fixtures/*.json`), not a cryptographic one |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|----------------------|
| Committing a real recorded auth token/cookie/account email into `tests/fixtures/*.json` | Information Disclosure | Sanitize every recorded fixture before committing: replace `auth_token`, `x-token-auth`, cookie values, GPS coordinates, account names/emails, and account-scoped URLs with clearly-fake placeholders (e.g. `"REDACTED-TOKEN"`, `40.0000,-74.0000`) — this mirrors the project's own existing `_redact()` convention in `client.py` and is already called out explicitly in the settled design |

## Sources

### Primary (HIGH confidence)
- Direct execution against installed `httpx==0.28.1` in this repo's `uv` venv (`uv run python`), this session — confirmed `MockTransport.__init__` signature, `_init_transport` transport-precedence-over-http2 behavior, `request.url.path` prefix behavior, `request.url.params.get("cursor")` presence/absence semantics, `Client` redaction/cookie/raise_for_status behavior through a mocked transport.
- Direct read of `auraframes/client.py`, `auraframes/aura.py`, `auraframes/api/baseApi.py`, `auraframes/api/accountApi.py`, `auraframes/api/frameApi.py`, `auraframes/models/user.py`, `auraframes/models/frame.py`, `auraframes/models/asset.py`, `auraframes/models/meta.py`, `auraframes/models/activity.py`, `tests/conftest.py`, `tests/test_read_path.py`, `tests/test_imports.py`, `pyproject.toml`, `uv.lock`, `.planning/ROADMAP.md`, `.planning/STATE.md`, `.planning/config.json` — all read in full this session.

### Secondary (MEDIUM confidence)
None used — direct execution/source-read against the exact pinned version was available and preferred over external docs for this narrow, mechanical research scope.

### Tertiary (LOW confidence)
None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependency; version confirmed directly via `uv.lock`/`uv run python`
- Architecture: HIGH — settled by prior `/grilling` session; mechanics confirmed by direct execution against pinned httpx
- Pitfalls: HIGH — all three pitfalls were reproduced/confirmed by direct execution in this session, not inferred

**Research date:** 2026-07-01
**Valid until:** 30 days (stable dependency surface — httpx/pytest are mature, slow-moving; re-verify sooner only if `httpx` is bumped past `0.28.x` in `uv.lock`)
