# Phase 9: Proactive Write Rate-Limiter & Geo Guard - Research

**Researched:** 2026-07-09
**Domain:** Client-side proactive rate limiting (token bucket) + IP-geolocation pre-flight guard, integrated into an existing batched write-execution engine (Python 3.14, stdlib-only for the new module)
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Architecture / placement**
- Approach A (dedicated injectable module). New `auraframes/ratelimit.py` consulted by
  `execute_plan` — matches the existing injectable-seam pattern (`sleep`, `throttle_seconds`,
  `batch_size`, `chunk_delay`, `on_wait`). NOT bolted inline into `execute_plan` (B), NOT a
  client-level interceptor (C).
- `execute_plan` gains new injectable params: `budget: WriteBudget | None`,
  `geo_check: Callable | None`, `wait_on_budget: bool`, `max_wait_seconds: float`. When
  `budget is None`, behavior is exactly as today (backward compatible — existing offline
  tests stay green without a budget).

**`WriteBudget` (token bucket)**
- State: `tokens: float`, `updated_at: datetime`.
- `acquire(n, *, wait, max_wait, now, sleep, on_wait=None)`: refill by
  `refill_per_min * minutes_since(updated_at)` (capped at `capacity`); if `tokens >= n` consume;
  else compute `wait_seconds`; if `wait` and `wait_seconds <= max_wait` → `sleep()` (surface
  countdown via the existing `on_wait` hook) then consume, else raise `BudgetExhausted(wait_seconds)`.
- `reconcile_tripped(now)`: force `tokens = 0`, `updated_at = now`. Called when a real
  `RateLimitError` / `ConsecutiveWriteFailureError` occurs despite the budget.
- `load(path)` / `save(path)`: JSON round-trip.
- Clock (`now`) and `sleep` are injected for deterministic offline tests.
- Request currency, not photos: an upload chunk costs `2` (`select_asset` + `batch_update`);
  a delete chunk costs `1`.

**`check_geo(expected_country, *, resolver, fail_open=True)`**
- Falsy `expected_country` → return `None` (skip).
- Else `resolver()` returns exit-IP country code (default resolver: `GET ipinfo.io/json`,
  short timeout). Mismatch → raise `GeoMismatchError(found, expected)`.
- Resolver raises/times out → fail-open by default (log warning, allow write); configurable
  to fail-closed. An ipinfo outage must never block a legitimate upload.

**Persistence**
- State file: `~/.config/auraframes/budget-<sha1(email)[:12]>.json` (per-account, no collision).
- Directory from `AURA_STATE_DIR` (default `~/.config/auraframes`).
- Read once at start of a run; re-written after each successful write chunk so an
  interrupt (Ctrl-C/crash) leaves an accurate estimate. On a trip: `reconcile_tripped()` then save.

**Integration in `execute_plan`**
- Pre-flight: call `geo_check()` once before any write; `GeoMismatchError` propagates to CLI.
- Before each write chunk: `budget.acquire(reqs)` (`reqs=2` upload, `1` delete).
- Existing error paths unchanged, plus `budget.reconcile_tripped()` + `save()` grafted onto
  the `RateLimitError` and `ConsecutiveWriteFailureError` branches. The existing
  abort-after-N-failures backstop remains the ultimate safety net below the proactive budget.
- After each successful chunk: `budget.save()`.

**Configuration (settings.py + env + CLI flags)**

| Concept | Constant / env | Default |
|---|---|---|
| bucket capacity | `AURA_WRITE_BUDGET_CAPACITY` | `30` (conservative, < 42 measured) |
| refill rate | `AURA_WRITE_BUDGET_REFILL_PER_MIN` | `0.75` (≈ full in ~40 min) |
| wait vs stop | `AURA_WRITE_BUDGET_WAIT` | `true` |
| max wait | `AURA_WRITE_BUDGET_MAX_WAIT` | `3600` (seconds) |
| expected country | `AURA_COUNTRY` | unset → geo check skipped |
| geo fail mode | `AURA_GEO_FAIL_OPEN` | `true` |
| state dir | `AURA_STATE_DIR` | `~/.config/auraframes` |

- `push` CLI flags (per-run overrides): `--max-wait`, `--no-wait`, `--country`, `--ignore-budget`
  (escape hatch that bypasses the budget entirely for the run).

**Error handling**
- New exceptions in `ratelimit.py`:
  - `GeoMismatchError(found, expected)` → CLI: "VPN/exit IP in {found}, account expects {expected}
    — switch your VPN and retry." Refuses to write.
  - `BudgetExhausted(wait_seconds)` (stop-cleanly path) → CLI: "write budget exhausted, come back
    in ~{minutes} min (or pass --no-wait / raise --max-wait)."
- Existing `RateLimitError` (429/475) and `ConsecutiveWriteFailureError` remain the reactive
  safety net and now also drive `reconcile_tripped()`.

### Claude's Discretion
- Exact JSON schema/key names of the persisted state file (spec fixes semantics, not byte layout).
- Precise wording of CLI messages beyond the intent captured above.
- Where the default `ipinfo.io` resolver helper lives (in `ratelimit.py` vs a small helper).
- How `budget`/`geo_check` are constructed and wired from `cli.py` (factory vs inline).

### Deferred Ideas (OUT OF SCOPE)
None beyond the YAGNI list below — the spec fully scopes this phase.

**YAGNI (out of scope):**
- Client-level interception of *every* write path (only bulk `execute_plan` writes are the abuse vector).
- Reading the true server-side budget (not exposed; local estimate + reconcile is the model).
- Auto-detecting the account's home country (explicit `AURA_COUNTRY` config instead).
</user_constraints>

<phase_requirements>
## Phase Requirements

This is a **new hardening phase** with no pre-existing requirement IDs (ROADMAP lists
`Requirements: TBD (map during planning)`). Suggested new IDs for the planner to mint and
back-fill into `.planning/REQUIREMENTS.md` (prefix `ANTI-` per CONTEXT.md's suggestion):

| Suggested ID | Description | Research Support |
|----|-------------|------------------|
| ANTI-01 | `WriteBudget` token-bucket core: `acquire`/refill math/`reconcile_tripped`/`load`/`save`, fully offline (injected clock + sleep) | See "Architecture Patterns", "Pattern 1", "Pitfall 2" below |
| ANTI-02 | `check_geo` pre-flight guard: match / mismatch / fail-open / fail-closed, injected resolver, zero network in tests | See "Pattern 2", ipinfo.io contract findings below |
| ANTI-03 | `execute_plan` integration: new `budget`/`geo_check`/`wait_on_budget`/`max_wait_seconds` params; `budget is None` is a byte-identical no-op vs. today | See "Integration Reality" section — exact insertion points quoted |
| ANTI-04 | Reconcile-on-trip wiring: both `RateLimitError` branches and the `ConsecutiveWriteFailureError` raise-site in `note_failure()` call `reconcile_tripped()` + `save()` before propagating | See "Integration Reality" §4 |
| ANTI-05 | `settings.py` env config: `AURA_WRITE_BUDGET_CAPACITY/REFILL_PER_MIN/WAIT/MAX_WAIT`, `AURA_COUNTRY`, `AURA_GEO_FAIL_OPEN`, `AURA_STATE_DIR` — first bool/float env vars in this codebase, needs a small parsing helper | See "settings.py convention" section |
| ANTI-06 | `push` CLI flags `--max-wait`/`--no-wait`/`--country`/`--ignore-budget` + construction/wiring of `budget`/`geo_check` in `run_sync`, new exception branches for `GeoMismatchError`/`BudgetExhausted` | See "cli.py wiring" section |
| ANTI-07 | 100%-offline test coverage for `WriteBudget`, `check_geo`, and the `execute_plan` integration (fake budget asserting `acquire` call count/`reqs`, geo pre-flight called once, `reconcile_tripped` on trip paths) | See "Test Pattern" section |
</phase_requirements>

## Summary

This phase is pure integration work against a codebase that already has every seam it needs:
`execute_plan` (`auraframes/sync.py:304`) is already an injectable-parameter function (`sleep`,
`throttle_seconds`, `batch_size`, `chunk_delay_seconds`, `on_wait`, `progress`) with a mature
chunking loop, a `RateLimitError` fast-abort path (`auraframes/client.py:28`), and a
`ConsecutiveWriteFailureError` status-code-agnostic backstop (`auraframes/sync.py:127`). The new
`auraframes/ratelimit.py` module (a `WriteBudget` dataclass + `check_geo` function + two new
exceptions) is stdlib-only (`hashlib`, `json`, `pathlib`, `datetime`) plus a reused `httpx` call
for the default geo resolver — no new third-party dependency is required for this phase.

The one thing NOT already precedented in this codebase is **typed env-var parsing beyond plain
strings**: `auraframes/utils/settings.py` currently has zero bool/float coercion helpers (every
existing setting is `os.getenv(name, 'string-default')`). The new `AURA_WRITE_BUDGET_WAIT` and
`AURA_GEO_FAIL_OPEN` booleans, and the four numeric budget settings, are the first non-string env
vars in the project — a small `_bool_env`/`float(os.getenv(...))` idiom needs to be introduced,
matching the codebase's "plain functions, no config library" convention (confirmed: no
`pydantic-settings`, `python-decouple`, or similar in `pyproject.toml`).

`ipinfo.io/json` was live-verified during this research (see below): it answers anonymously,
with no token, returning a flat JSON body including `"country": "FR"` — directly confirming the
design spec's default-resolver contract. It is documented by IPinfo itself as a **legacy**
unauthenticated endpoint capped at ~1000 req/day shared per source IP, which will remain fine for
this phase's one-pre-flight-call-per-run usage but reinforces why fail-open-by-default is the
correct posture (a future deprecation or throttle of this specific free endpoint must never block
a legitimate write).

**Primary recommendation:** Build `ratelimit.py` as two plain `dataclasses` (mirroring
`SyncPlan`/`ExecutionResult`'s existing style in `sync.py`, NOT pydantic — pydantic in this repo
is reserved for API response DTOs) plus two exception classes; wire `budget`/`geo_check`
construction inside `run_sync()` in `cli.py` (not `main()`) so both `sync --apply` and
`push --apply` get proactive protection by default from `settings.py` env values, with the four
new override flags declared only on the `push` subparser (mirroring the existing
`--limit`/`--batch-size`/`--chunk-delay` push-only pattern) and threaded through as optional
`run_sync()` params exactly like `batch_size`/`chunk_delay` are today.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Token-bucket accounting (acquire/refill/reconcile) | Domain module (`auraframes/ratelimit.py`) | — | Pure logic + injected clock/sleep; no I/O of its own beyond `load`/`save` |
| Budget state persistence | Domain module (`ratelimit.py`, `load`/`save`) | Local filesystem (`~/.config/auraframes/`) | Per-account JSON file; write-through after each successful chunk |
| Geo pre-flight check | Domain module (`ratelimit.py`, `check_geo`) | External service (ipinfo.io) | One outbound GET per run; result never persisted |
| Write-budget consultation timing (when to call acquire/geo_check) | Sync engine (`auraframes/sync.py::execute_plan`) | — | Orchestrates chunk loop; the only mutating entry point in the module (per its own docstring) |
| CLI flag parsing / override precedence | CLI (`auraframes/cli.py`) | Settings (`auraframes/utils/settings.py`) | Flags override env defaults; construction of `budget`/`geo_check` objects happens at the CLI boundary, mirroring `S3Client()`/`SQSClient()` construction (§08-03 decision: "real clients constructed at the CLI boundary only") |
| Config defaults | Settings (`auraframes/utils/settings.py`) | Env vars | Matches existing `LOCALE`/`AURA_APP_IDENTIFIER`/`DEVICE_IDENTIFIER` idiom |
| Rate-limit/lockout *detection* (reactive) | HTTP client (`auraframes/client.py::RateLimitError`) + Sync engine (`ConsecutiveWriteFailureError`) | — | Unchanged this phase; only gains a `reconcile_tripped()` hook |

## Package Legitimacy Audit

**No new external packages this phase.** `auraframes/ratelimit.py` is implementable entirely
with stdlib (`hashlib`, `json`, `pathlib`, `dataclasses`, `datetime`) plus the project's existing
`httpx` dependency (already in `pyproject.toml`, `httpx[http2]>=0.27`) for the default geo
resolver's `GET https://ipinfo.io/json` call. No `pip install` / `uv add` step is required for
this phase.

| Package | Registry | Verdict | Disposition |
|---------|----------|---------|-------------|
| *(none)* | — | — | N/A — stdlib + existing `httpx` only |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Integration Reality: `execute_plan` (auraframes/sync.py)

### Current signature (line 304)

```python
def execute_plan(plan: SyncPlan, aura, frame_id: str, *, s3_client, sqs_client,
                 throttle_seconds: float = WRITE_THROTTLE_SECONDS, sleep=time.sleep,
                 max_consecutive_failures: int = MAX_CONSECUTIVE_WRITE_FAILURES,
                 progress=lambda *args: None,
                 batch_size: int = WRITE_BATCH_SIZE,
                 chunk_delay_seconds: float = WRITE_CHUNK_DELAY_SECONDS,
                 on_wait=lambda *args: None) -> ExecutionResult:
```
`[VERIFIED: auraframes/sync.py:304]`

New keyword-only params to add (all optional, all default to no-op/off so the function stays
backward compatible byte-for-byte when unused):

```python
budget: "WriteBudget | None" = None,
geo_check=None,                          # Callable[[], None] | None
wait_on_budget: bool = True,
max_wait_seconds: float = 3600.0,
clock=get_utc_now,                       # NEW injectable clock — see naming note below
```

`clock` naming note: `WriteBudget.acquire`'s spec signature is
`acquire(n, *, wait, max_wait, now, sleep, on_wait=None)` where `now` is a **value** (the current
instant), not a callable — `reconcile_tripped(now)` uses it the same way. `execute_plan` needs its
own injectable zero-arg clock *function* to produce that value for deterministic tests (mirroring
how `sleep` is already injected as a function). Naming it `clock` (not `now`) avoids a
parameter-name collision with the value `now=clock()` you pass into `budget.acquire(...)`. Default
should reuse the existing project convention: `auraframes.utils.dt.get_utc_now` (`datetime.utcnow`)
— NOT a new one. `[VERIFIED: auraframes/utils/dt.py:10-11]`

### Exact insertion points (quoting current code)

**1. Geo pre-flight — once, before any write.** Insert immediately after the docstring / before
`result = ExecutionResult()` (currently line 398), i.e. as the very first executable statement:

```python
    result = ExecutionResult()          # <- line 398 today
    consecutive_failures = 0
```
becomes
```python
    if geo_check is not None:
        geo_check()                     # raises GeoMismatchError; nothing written yet
    result = ExecutionResult()
    consecutive_failures = 0
```
This placement guarantees pitfall #7 (no partially-written plan on a geo mismatch) for free: no
S3 upload, no `select_asset`, no `remove_asset` call has happened yet at this point in the
function, regardless of whether the plan is upload-only, delete-only, or mixed.

**2. `budget.acquire(reqs)` before each write chunk.** Two call sites, one per loop:

Upload loop — insert right after `interchunk_pause()`, **before** the per-file S3-prep loop
(so a `BudgetExhausted` stop never wastes an S3 upload on a chunk that won't be written):
```python
    for chunk in _chunked(sorted(plan.to_upload), batch_size):   # line 440
        interchunk_pause()
        # NEW:
        if budget is not None:
            budget.acquire(2, wait=wait_on_budget, max_wait=max_wait_seconds,
                            now=clock(), sleep=sleep, on_wait=on_wait)
        prepped: list = []
        for path in chunk:
            ...
```
`[VERIFIED: auraframes/sync.py:440-450]`

Delete loop — insert right after `interchunk_pause()`, before `throttle()`:
```python
    for chunk in _chunked(plan.to_delete, batch_size):            # line 500
        interchunk_pause()
        # NEW:
        if budget is not None:
            budget.acquire(1, wait=wait_on_budget, max_wait=max_wait_seconds,
                            now=clock(), sleep=sleep, on_wait=on_wait)
        try:
            throttle()
            ...
```
`[VERIFIED: auraframes/sync.py:500-504]`

**3. `budget.save()` after each successful chunk.** CONTEXT.md's wording ("after each successful
chunk") is ambiguous between "the chunk raised nothing" (includes ordinary caught per-item/
per-chunk failures, D-08 style) and "every item in the chunk actually succeeded." Flagged
explicitly in Open Questions below — **recommendation:** save after every chunk iteration that
returns normally (i.e., doesn't raise `RateLimitError`/`ConsecutiveWriteFailureError`), because
`budget.acquire()` already decremented the in-memory token count for that chunk's *attempted*
requests regardless of whether Pushd accepted them — an ordinary ("some items failed but the
backstop didn't trip") chunk still consumed real anti-abuse budget server-side (per the design
doc's own Problem section: "Failed write attempts also appear to consume budget too"). Concretely:
add `if budget is not None: budget.save(state_path)` as the last statement inside each `for chunk
in ...:` loop body, after the try/except (or right before the `for chunk in _chunked(plan.to_delete
...)` line begins, covering the upload loop's tail; symmetric for the delete loop).

**4. `reconcile_tripped()` + `save()` grafted onto the existing trip branches.** Three exact sites:

Upload-loop `RateLimitError` (lines 479-482):
```python
        except RateLimitError:
            # Anti-abuse throttle/lockout: abort the whole batch (do not
            # mask it as one per-item failure and keep hammering).
            raise
```
→
```python
        except RateLimitError:
            if budget is not None:
                budget.reconcile_tripped(clock())
                budget.save(state_path)
            raise
```

Delete-loop `RateLimitError` (lines 509-510) — identical pattern.

`ConsecutiveWriteFailureError` is raised from inside the shared nested closure `note_failure()`
(lines 405-415), not from a `try/except` in the loop bodies — the reconcile call belongs **inside
`note_failure()`**, immediately before its `raise`:
```python
    def note_failure(last_error: str) -> None:
        nonlocal consecutive_failures
        consecutive_failures += 1
        if 0 < max_consecutive_failures <= consecutive_failures:
            if budget is not None:
                budget.reconcile_tripped(clock())
                budget.save(state_path)
            raise ConsecutiveWriteFailureError(consecutive_failures, last_error, result)
```
`[VERIFIED: auraframes/sync.py:405-415]` — this closure already closes over `result` via
`nonlocal`/enclosing scope, so closing over `budget`/`clock`/`state_path` (all `execute_plan`
params/locals) requires no new plumbing.

**`state_path` note:** `budget.save(path)`/`budget.load(path)` need a filesystem path. Two
options: (a) `execute_plan` takes a `state_path` param computed by the caller (CLI) and passed
in alongside `budget`, or (b) the `WriteBudget` instance itself remembers its own path (set at
construction) and `save()`/`reconcile_tripped()`-then-`save()` take no path argument. **(b) is
simpler and avoids a second injectable param threading through `execute_plan`** — recommend
`WriteBudget` holds `path: Path` as a field set at construction time (by the CLI-side factory),
so `execute_plan` only ever calls `budget.save()` / `budget.reconcile_tripped(clock())` with no
extra path plumbing. This also matches CONTEXT.md's spec pseudocode which shows `save(path)` as
the *class method's* signature (called by whoever constructed the instance), not something
`execute_plan` needs to know about.

## Existing Injectable-Seam + Fake-Based Test Pattern

Confirmed style across `tests/test_execute_plan.py`, `tests/test_write_throttling.py`,
`tests/test_cli_apply.py`, `tests/test_cli_sync.py`, `tests/test_client_rate_limit.py`:

- **Runner:** `uv run pytest` (confirmed working: `uv run pytest --collect-only -q` → 120 tests
  collected). `[VERIFIED: local run]`
- **Test location:** flat `tests/` directory, one file per concern (`test_execute_plan.py`,
  `test_write_throttling.py`, `test_client_rate_limit.py`). New tests should follow suit:
  `tests/test_ratelimit.py` (WriteBudget + check_geo unit tests) and either extend
  `tests/test_execute_plan.py`/`test_write_throttling.py` or add
  `tests/test_execute_plan_budget_geo.py` for the integration slice.
- **Zero network / zero real time:** every test injects `sleep=lambda *_: None` (or a recording
  `_SleepRecorder`/`_WaitRecorder` class — see `test_write_throttling.py:90-96, 478-484`) and
  drives the REST layer through `tests.offline.offline_aura(overrides={...})`
  (`httpx.MockTransport`-backed). S3/SQS are hand-written duck-typed fake classes
  (`_FakeS3Client`, `_FakeSQSClient` — see `test_execute_plan.py:67-95`), never `botocore.Stubber`.
  New `WriteBudget`/`check_geo` tests must mirror this: inject a fake `clock=lambda: <fixed dt>`,
  `sleep=<recorder>`, and for `check_geo`, a fake `resolver=lambda: 'FR'` (or one that raises, to
  test fail-open/fail-closed) — never a real `httpx` call.
- **`on_wait`/countdown assertion pattern:** `_WaitRecorder` (`test_write_throttling.py:478-484`)
  is a callable class recording every `on_wait(remaining)` call; tests assert the exact sequence
  (`[5.0, 4.0, 3.0, 2.0, 1.0]`, `test_write_throttling.py:508`). Budget-wait tests should reuse
  this exact recorder shape.
- **`_reset_loguru` autouse fixture:** every test file that touches `execute_plan`/`Client`/CLI
  handlers has an autouse fixture calling `logger.remove()` before/after — copy this into any new
  test file that imports `auraframes.sync`, `auraframes.client`, or `auraframes.cli` (loguru is a
  process-global singleton; a leftover sink bound to a torn-down `capsys` buffer will error).
- **State-file / tmp-dir pattern for `WriteBudget.load`/`save`:** no existing precedent for a
  persisted-JSON-file test exists in this codebase yet (this phase introduces the first one) —
  use pytest's built-in `tmp_path` fixture and pass an explicit `Path` into `WriteBudget(path=...)`
  at construction, never a real `~/.config/auraframes` path. This matches the design spec's
  explicit requirement: "Injected clock + `sleep` + tmp state file — no real time, no real
  disk-home."
- **CLI-level fakes:** `tests/test_cli_apply.py` monkeypatches `cli.execute_plan` wholesale
  (`_patch_execute_plan`, lines 84-104) to assert what `run_sync()` forwards into it — the new
  `--max-wait`/`--no-wait`/`--country`/`--ignore-budget` CLI flag tests should extend this same
  fake, asserting the constructed `budget`/`geo_check` (or their absence, for `--ignore-budget`)
  appear in `exec_kwargs`, exactly like the existing `test_push_forwards_batch_size_and_chunk_delay`
  test (`test_cli_apply.py:350-363`) asserts `batch_size`/`chunk_delay_seconds`.

## `settings.py` Env-Config Convention

Current full contents `[VERIFIED: auraframes/utils/settings.py]`:
```python
import os

LOCALE = os.getenv('AURA_LOCALE', 'en-US')
AURA_APP_IDENTIFIER = os.getenv('AURA_APP_IDENTIFIER', 'com.pushd.client')
# TODO: Load device identifier through config
DEVICE_IDENTIFIER = os.getenv('AURA_DEVICE_IDENTIFIER', '0000000000000000')
IMAGE_PROXY_BASE_URL = 'https://imgproxy.pushd.com'
```

**Every existing setting is a plain string** (`os.getenv(name, 'default-string')`) — there is
**no bool or float coercion helper anywhere in this codebase**. `AURA_WRITE_BUDGET_WAIT` and
`AURA_GEO_FAIL_OPEN` (booleans) and the four numeric budget settings are the first non-string env
vars introduced. No config library (`pydantic-settings`, `python-decouple`, `environs`, etc.) is
a dependency (`[VERIFIED: pyproject.toml — dependencies list has no config library]`), so the
correct idiom is a small local helper, matching the file's existing "plain module-level constants,
`os` only" style:

```python
def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ('1', 'true', 'yes', 'on')

AURA_WRITE_BUDGET_CAPACITY = float(os.getenv('AURA_WRITE_BUDGET_CAPACITY', '30'))
AURA_WRITE_BUDGET_REFILL_PER_MIN = float(os.getenv('AURA_WRITE_BUDGET_REFILL_PER_MIN', '0.75'))
AURA_WRITE_BUDGET_WAIT = _bool_env('AURA_WRITE_BUDGET_WAIT', True)
AURA_WRITE_BUDGET_MAX_WAIT = float(os.getenv('AURA_WRITE_BUDGET_MAX_WAIT', '3600'))
AURA_COUNTRY = os.getenv('AURA_COUNTRY')  # None -> geo check skipped, per check_geo's falsy contract
AURA_GEO_FAIL_OPEN = _bool_env('AURA_GEO_FAIL_OPEN', True)
AURA_STATE_DIR = Path(os.getenv('AURA_STATE_DIR', '~/.config/auraframes')).expanduser()
```
`pathlib.Path` is not currently imported in `settings.py` — add `from pathlib import Path` at the
top (stdlib, no new dependency). `float()` needs no helper (bare `float(os.getenv(...))` matches
the file's minimal style); only the boolean case needs `_bool_env` since Python has no built-in
`bool("false")` truthiness that does the right thing (`bool("false")` is `True`).

## `cli.py` Wiring

### Existing `push`-only flag pattern (lines 58-65, `[VERIFIED]`)

```python
push_parser = subparsers.add_parser('push', help='Upload photos from a directory to a frame (additive -- never deletes)')
push_parser.add_argument('dir', help='Local directory of photos to upload (a supply/"buffet"; the frame is NOT synced to match it)')
push_parser.add_argument('--frame', required=True, help='Frame name (substring) or id')
push_parser.add_argument('--apply', action='store_true', default=False, help='Execute the upload instead of only printing the plan')
push_parser.add_argument('--yes', action='store_true', default=False, help='Skip the confirmation prompt (required for --apply when running non-interactively)')
push_parser.add_argument('--limit', type=int, default=None, help='Upload at most N photos this run (for controlled anti-abuse budget probing)')
push_parser.add_argument('--batch-size', type=int, default=None, dest='batch_size', help='Assets per select_asset/batch_update call (default 50)')
push_parser.add_argument('--chunk-delay', type=float, default=None, dest='chunk_delay', help='Seconds to pause between write chunks (default 5)')
```

New flags follow the exact same `default=None` "unset means use the default elsewhere" idiom:
```python
push_parser.add_argument('--max-wait', type=float, default=None, dest='max_wait', help='Max seconds to wait for write budget before stopping (default 3600)')
push_parser.add_argument('--no-wait', action='store_true', default=False, help='Stop immediately instead of waiting when the write budget is exhausted')
push_parser.add_argument('--country', default=None, help='Override the expected account country for the geo pre-flight guard (default from AURA_COUNTRY)')
push_parser.add_argument('--ignore-budget', action='store_true', default=False, dest='ignore_budget', help='Escape hatch: bypass the write budget entirely for this run')
```

### Where budget/geo_check protection applies — recommendation, not fully locked

The design spec's "Integration in `execute_plan`" section describes the budget/geo guard as
integrated into `execute_plan` **universally** (no verb distinction), and `execute_plan` is
`run_sync()`'s single shared call site for **both** `sync --apply` and `push --apply`
(`auraframes/cli.py:403-406`, `main()` dispatches both verbs to `run_sync`, `[VERIFIED: cli.py
449-456]`). The CONTEXT.md Configuration table lists the four override flags under a `push`-only
heading, mirroring the pre-existing `--limit`/`--batch-size`/`--chunk-delay` push-only pattern —
but those flags are *overrides*, not the feature switch itself. **Recommendation for the
planner to confirm/lock during planning:** construct `budget`/`geo_check` unconditionally inside
`run_sync()` (from `settings.py` env defaults) whenever `apply=True`, so `sync --apply` also gets
proactive protection by default (it hits the exact same anti-abuse surface); thread the four
override params (`max_wait`, `no_wait`, `country`, `ignore_budget`) as optional `run_sync()` kwargs
(default `None`/`False`, exactly like `batch_size`/`chunk_delay`/`limit` today) forwarded only from
the `push` branch of `main()` — `sync_parser` continues to not expose them, using pure env
defaults, matching today's asymmetry where `sync_parser` also lacks `--batch-size`/`--chunk-delay`.

### Construction site (Claude's discretion per CONTEXT.md, but concrete recommendation)

Build a small factory, e.g. `_build_write_budget(email: str, ignore_budget: bool) -> WriteBudget | None`
and `_build_geo_check(country_override: str | None) -> Callable[[], None] | None`, called from
`run_sync()` right before the `execute_plan(...)` call (same place `S3Client()`/`SQSClient()` are
constructed today, `cli.py:377-378`) — mirrors the Phase 08-03 decision quoted in STATE.md: "Real
S3Client()/SQSClient() are constructed at the CLI boundary only, on confirmed --apply; execute_plan()
itself never constructs AWS clients." The email needed for the state-file hash is already available
via `os.getenv('AURA_EMAIL')` at this boundary (same source `run_status`/`run_inspect` already use,
`cli.py:104,128`).

### `exec_kwargs` forwarding pattern (lines 397-406, `[VERIFIED]`)

```python
            exec_kwargs = {}
            if batch_size is not None:
                exec_kwargs['batch_size'] = batch_size
            if chunk_delay is not None:
                exec_kwargs['chunk_delay_seconds'] = chunk_delay

            result = execute_plan(
                plan, aura, frame.id, s3_client=s3_client, sqs_client=sqs_client,
                progress=_report_progress, on_wait=_report_wait, **exec_kwargs,
            )
```
New forwarding, added the same way (`exec_kwargs['budget'] = budget` only if a budget object was
built i.e. not `ignore_budget`; `exec_kwargs['geo_check'] = geo_check` only if constructed;
`wait_on_budget`/`max_wait_seconds` forwarded only when the corresponding CLI flag was supplied,
else `execute_plan`'s own defaults apply) — this preserves
`test_sync_defaults_do_not_override_execute_plan_defaults`'s exact guarantee
(`test_cli_apply.py:366-379`): a classic `sync --apply` with none of the new flags must forward
**nothing** new, keeping `execute_plan`'s own defaults (`budget=None`, `geo_check=None`) in
effect — i.e., **fully backward compatible, zero new behavior unless explicitly enabled.**

### `on_wait`/`_report_wait` reuse nuance (Pitfall)

`_report_wait` (`cli.py:389-392`) currently hardcodes a "cooldown" label:
```python
            def _report_wait(remaining):
                # Inter-chunk cooldown -- the bar doesn't advance, so surface
                # the countdown in the postfix rather than looking frozen.
                bar.set_postfix_str(f'cooldown {remaining:.0f}s before next batch')
```
CONTEXT.md's decision explicitly says budget-wait reuses this same `on_wait` hook ("surfacing a
countdown via the existing `on_wait` hook"). Reusing it verbatim means a budget-exhaustion wait
will *also* say "cooldown ... before next batch," which is misleading (it's not the fixed
inter-chunk pacing pause, it could be a multi-minute budget-refill wait). This is flagged as an
**open pitfall for the planner**: either accept the shared/slightly-misleading label (simplest,
matches the locked "reuse on_wait" decision literally), or widen `_report_wait`'s message using
context it doesn't currently have (it would need to know *which* pause is running). Message
wording itself is explicitly Claude's Discretion per CONTEXT.md, so this is a planning-time call,
not a blocker.

### New exception handling in `run_sync()`

Add two new `except` blocks alongside the existing `RateLimitError`/`ConsecutiveWriteFailureError`
handlers (`cli.py:417-433`), importing `GeoMismatchError`, `BudgetExhausted` from
`auraframes.ratelimit` (mirroring the existing `from auraframes.sync import ...
ConsecutiveWriteFailureError` import at `cli.py:16`):
```python
    except GeoMismatchError as e:
        print(f'VPN/exit IP in {e.found}, account expects {e.expected} — switch your VPN and retry.')
        return 1
    except BudgetExhausted as e:
        minutes = e.wait_seconds / 60
        print(f'Write budget exhausted, come back in ~{minutes:.0f} min (or pass --no-wait / raise --max-wait).')
        return 1
```
Order matters: place these **before** the generic `except Exception as e:` catch-all
(`cli.py:434-438`) so they aren't swallowed by the fail-loud fallback, same reasoning that already
governs the existing `RateLimitError`/`ConsecutiveWriteFailureError` ordering in this function.

## Persistence Details

- `hashlib.sha1` — stdlib, and **already used in this exact pattern elsewhere** in the codebase:
  `auraframes/aws/s3client.py:14-15` — `base64.b64encode(hashlib.md5(data).digest()).decode('utf-8')`
  confirms `hashlib` + `base64` are an established idiom here (md5, not sha1, but same module).
  `[VERIFIED: auraframes/aws/s3client.py:4,14-15]` sha1 is a fine choice for a non-cryptographic
  filename-uniqueness hash (not a security boundary — see Security Domain below).
- `pathlib.Path.expanduser()` — stdlib, correctly expands `~` regardless of platform; use this
  (not manual `os.path.expanduser`) for `AURA_STATE_DIR`'s default `~/.config/auraframes`.
- `json` — stdlib; `WriteBudget.save`/`load` should use `json.dump`/`json.load` with
  `datetime.isoformat()`/`datetime.fromisoformat()` for `updated_at` (both stdlib, no extra
  serialization library needed — this codebase has no `orjson`/`ujson` dependency).
- **Test-injectable path:** `WriteBudget` should accept `path: Path` as a constructor field (not
  hardcode `Path.home() / '.config' / 'auraframes' / ...` internally) so tests pass a `tmp_path`
  fixture value directly — this is what CONTEXT.md means by "Injected clock + sleep + tmp state
  file — no real time, no real disk-home." The CLI-side factory (see above) is the one place that
  computes the *real* default path from `AURA_STATE_DIR` + `sha1(email)[:12]`.
- **No XDG-specific handling needed beyond `AURA_STATE_DIR`:** the design spec deliberately
  specifies a fixed default (`~/.config/auraframes`) with a single override env var, not full
  XDG Base Directory spec compliance (no `XDG_CONFIG_HOME` fallback chain) — consistent with
  YAGNI; do not add XDG auto-detection, it's out of scope.

## Default Geo Resolver (`ipinfo.io/json`)

**Live-verified during this research** (`[VERIFIED: direct curl from dev machine]`):
```
$ curl -s -m 4 https://ipinfo.io/json
{
  "ip": "146.70.194.20",
  "city": "Saint-Denis",
  "region": "Île-de-France",
  "country": "FR",
  "loc": "48.9356,2.3539",
  "org": "AS9009 M247 Europe SRL",
  "postal": "93200",
  "timezone": "Europe/Paris",
  "readme": "https://ipinfo.io/missingauth"
}
```
Confirms: anonymous, no token required, flat JSON body, `"country"` key is a plain 2-letter ISO
code string — directly usable for `check_geo`'s comparison against `expected_country`. The
`"readme": "https://ipinfo.io/missingauth"` field is IPinfo's own breadcrumb confirming this is
their intentionally-supported unauthenticated legacy endpoint, not an error response.

`[CITED: ipinfo.io FAQ/support docs, cross-checked via WebSearch]` — the unauthenticated
`ipinfo.io/json` endpoint is rate-limited to **~1000 requests/day, shared per source IP** (i.e.
shared across everyone behind the same NAT/VPN exit, not per-account) and is explicitly labeled
"legacy" — IPinfo's newer "Lite" tier (unlimited, country-level only) requires a free account
token. For this phase's usage pattern (at most one `check_geo()` call per CLI invocation), the
1000/day shared cap is not a practical concern, but it does reinforce two things: (1) fail-open
is the only safe default (a shared-IP throttle from unrelated traffic must never block a
legitimate upload), and (2) do not add retry/backoff logic around the resolver call — a bare
short-timeout `GET` with try/except is correct, matching YAGNI.

**Recommended implementation:**
```python
def _default_resolver() -> str:
    response = httpx.get('https://ipinfo.io/json', timeout=4.0)
    response.raise_for_status()
    return response.json()['country']
```
**Reuse vs. fresh client:** use a **fresh, short-timeout `httpx.get(...)` call**, NOT the
project's existing `Client` class (`auraframes/client.py`). Rationale: `Client` is purpose-built
for `api.pushd.com` (hardcoded `base_url`, Pushd-specific headers/cookies, `_raise_if_rate_limited`
logic tied to Pushd's 429/475 semantics) — reusing it for an unrelated third-party host would be
misusing that abstraction. A bare `httpx.get()` call with an explicit short timeout (4s suggested,
comfortably under the 20s timeout `Client` uses for Pushd itself) is simpler and correctly scoped.
`httpx` is already a hard dependency (`pyproject.toml`), so no new import is introduced.

**Test-injectability:** `check_geo(expected_country, *, resolver, fail_open=True)` takes
`resolver` as a required keyword — tests always pass a fake (`lambda: 'FR'`, or one that raises
`httpx.TimeoutException`/`httpx.HTTPStatusError` to test fail-open/fail-closed) and never invoke
`_default_resolver` in the test suite. `_default_resolver` itself needs **no dedicated unit test**
hitting the network (would violate the 100%-offline test requirement) — its only test-time
existence-check is that `check_geo`'s default param wiring resolves correctly, exercised via one
`@pytest.mark.live` smoke test if desired (matching this codebase's existing `live` marker
convention, `[VERIFIED: pyproject.toml — 'live: hits the live Aura API...']`), or skipped entirely
per YAGNI if the planner judges the manual curl verification above sufficient.

## Architecture Patterns

### System Architecture Diagram

```
 CLI boundary (auraframes/cli.py :: run_sync)
 ─────────────────────────────────────────────
   AURA_EMAIL/AURA_PASSWORD, --country, --no-wait,
   --max-wait, --ignore-budget
        │
        ▼
   ┌─────────────────────────┐      ┌──────────────────────────┐
   │ _build_write_budget()   │      │ _build_geo_check()        │
   │  reads AURA_STATE_DIR,  │      │  reads AURA_COUNTRY,      │
   │  AURA_WRITE_BUDGET_*,   │      │  AURA_GEO_FAIL_OPEN,      │
   │  sha1(email)[:12]       │      │  wraps check_geo() as a   │
   │  -> WriteBudget|None    │      │  zero-arg closure|None    │
   └───────────┬──────────────┘      └──────────────┬─────────────┘
               │ budget                              │ geo_check
               ▼                                     ▼
        ┌───────────────────────────────────────────────────────┐
        │  execute_plan(plan, aura, frame_id, ..., budget=,      │
        │               geo_check=, wait_on_budget=,             │
        │               max_wait_seconds=, clock=)                │
        │  (auraframes/sync.py:304)                                │
        │                                                            │
        │  1. geo_check()  ──► GeoMismatchError? propagate, NOTHING│
        │     written yet                                           │
        │  2. for each upload/delete CHUNK:                         │
        │       interchunk_pause()                                  │
        │       budget.acquire(reqs)  ──► BudgetExhausted? propagate│
        │       [S3 upload prep — uploads only]                     │
        │       select_asset / batch_update / remove_asset          │
        │         │                                                 │
        │         ├─ success ─► budget.save()                       │
        │         └─ RateLimitError /                                │
        │            ConsecutiveWriteFailureError                   │
        │               ─► budget.reconcile_tripped() + save()      │
        │                  then re-raise (existing behavior)         │
        └───────────────────────────────────────────────────────┘
               │                                     │
               ▼                                     ▼
     ~/.config/auraframes/budget-<hash>.json    GET https://ipinfo.io/json
     (read once at start, rewritten per chunk)   (once per run, fail-open)
```

### Recommended Project Structure
```
auraframes/
├── ratelimit.py         # NEW — WriteBudget, check_geo, GeoMismatchError, BudgetExhausted
├── sync.py              # MODIFIED — execute_plan gains budget/geo_check/wait_on_budget/
│                         #            max_wait_seconds/clock params (backward compatible)
├── client.py             # UNCHANGED — RateLimitError stays the fast-path signal
├── cli.py                # MODIFIED — push subparser flags, budget/geo_check construction,
│                          #            new exception branches
└── utils/
    └── settings.py       # MODIFIED — AURA_WRITE_BUDGET_*, AURA_COUNTRY, AURA_GEO_FAIL_OPEN,
                           #            AURA_STATE_DIR + a new _bool_env helper
tests/
├── test_ratelimit.py               # NEW — WriteBudget + check_geo unit tests
└── test_execute_plan_budget_geo.py # NEW (or extend test_execute_plan.py) — integration slice
```

### Pattern 1: Injected-clock token bucket (mirrors this repo's injected-sleep pattern)
**What:** `WriteBudget` never calls `datetime.utcnow()` internally for its own bookkeeping decisions
during `acquire`/`reconcile_tripped` — the caller (`execute_plan`, via its own `clock` param) always
supplies `now` as a value. This is the exact same seam discipline already used for `sleep` in
`execute_plan` (`sleep=time.sleep` default, overridden in every test).
**When to use:** Any time-dependent bookkeeping in this codebase, per the established convention.
**Example (project-idiomatic dataclass style, mirroring `ExecutionResult`/`SyncPlan`):**
```python
# Source: auraframes/sync.py:255-260 (ExecutionResult) — style precedent
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

@dataclass
class WriteBudget:
    capacity: float
    refill_per_min: float
    path: Path
    tokens: float = 0.0
    updated_at: datetime | None = None
```

### Pattern 2: Fail-open external check with injected resolver
**What:** `check_geo` treats resolver failure as "unknown, not necessarily bad" by default —
matching this codebase's broader philosophy of never letting a secondary/best-effort signal (see
`execute_plan`'s SQS poll: "Best-effort/observational poll only -- never gates success or
failure", `sync.py:460-461`) block the primary operation.
**When to use:** Any pre-flight check backed by a third-party service with no SLA guarantee.
**Example:**
```python
# Source: design spec + this research's live ipinfo.io verification
def check_geo(expected_country, *, resolver, fail_open: bool = True):
    if not expected_country:
        return None
    try:
        found = resolver()
    except Exception as e:
        if fail_open:
            logger.warning(f'Geo pre-flight resolver failed ({e}); proceeding (fail-open).')
            return None
        raise
    if found.upper() != expected_country.upper():
        raise GeoMismatchError(found, expected_country)
    return None
```

### Anti-Patterns to Avoid
- **Retrying the geo resolver call:** YAGNI per the design spec — a bare try/except with a short
  timeout is correct; retry/backoff logic here would be unjustified complexity for a single
  pre-flight call.
- **Reusing `auraframes.client.Client` for the ipinfo.io call:** wrong abstraction — `Client` is
  Pushd-specific (base URL, headers, 429/475 classification). Use a bare `httpx.get()`.
- **Hardcoding the state file path inside `WriteBudget` methods:** breaks the "no real disk-home
  in tests" requirement — always take `path` as a constructor field.
- **Calling `budget.acquire()` twice for one logical chunk** (e.g. once speculatively, once for
  real) — `execute_plan` has no retry loop today, so this isn't currently at risk, but any future
  change that adds chunk-retry logic must be careful not to double-acquire for the same chunk.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP GET with timeout to ipinfo.io | A custom socket/urllib wrapper | `httpx.get(url, timeout=...)` | `httpx` is already a hard dependency; no reason to bypass it |
| JSON state file round-trip | A custom binary/pickle format | stdlib `json.dump`/`json.load` | Matches `.dict()`/`**json_response` patterns already used throughout this codebase for JSON I/O |
| Country-code comparison | A `pycountry`/ISO-3166 validation library | Plain case-insensitive string equality (`found.upper() == expected.upper()`) | The design spec's `check_geo` contract is a direct string match against a user-configured `AURA_COUNTRY`, not general ISO validation — adding a country-code library is unjustified scope for this phase (YAGNI) |
| Env var boolean parsing | A config library (`pydantic-settings`, `environs`, `python-decouple`) | A ~5-line `_bool_env` helper in `settings.py` | This codebase has zero config-library dependencies; adding one for two booleans is disproportionate |

**Key insight:** every piece of this phase already has a stdlib or already-a-dependency solution;
the only genuinely new pattern this codebase hasn't needed before is typed env-var parsing, which
is small enough to hand-roll consistently with the file's existing style rather than pull in a
library.

## Common Pitfalls

### Pitfall 1: Backward compatibility regression (`budget is None` must be a true no-op)
**What goes wrong:** A conditional inserted carelessly (e.g. `budget.acquire(...)` without an
`if budget is not None:` guard) crashes every existing test in `test_execute_plan.py`/
`test_write_throttling.py` that calls `execute_plan` without a `budget` kwarg (all of them, today).
**Why it happens:** Adding a new required-looking call inside an existing hot loop is easy to
forget to guard.
**How to avoid:** Every single new touch point (geo pre-flight, `acquire`, `save`,
`reconcile_tripped`) must be wrapped in `if budget is not None:` / `if geo_check is not None:`.
Run the full existing suite (`uv run pytest`) after wiring — all 120 currently-collected tests
must stay green with zero modification, since none of them pass `budget=`/`geo_check=`.
**Warning signs:** Any existing test in `test_execute_plan.py`, `test_write_throttling.py`, or
`test_cli_apply.py` starts failing after this phase's changes without being intentionally updated.

### Pitfall 2: Float refill math edge cases (elapsed=0, clock skew)
**What goes wrong:** `tokens = min(capacity, tokens + refill_per_min * minutes_since(updated_at))`
can misbehave if `minutes_since` goes negative (clock moved backward — a bad test double, a system
clock adjustment) or if two `acquire()` calls happen in the same instant (`elapsed == 0`, which
should add exactly zero tokens, not error).
**Why it happens:** Naive time-delta math trusts the clock monotonically increases.
**How to avoid:** Clamp: `elapsed_minutes = max(0.0, (now - updated_at).total_seconds() / 60.0)`
before multiplying by `refill_per_min`. `[CITED: cross-checked via WebSearch — standard token-
bucket clock-skew mitigation is clamping negative/zero elapsed intervals to zero before the refill
multiply]` Also handle `updated_at is None` (first-ever `acquire`/fresh bucket) explicitly —
treat as "no refill this call, start the clock now" rather than raising on `None - now`.
**Warning signs:** A test with two `acquire()` calls using an identical fixed `now=` value, or a
`now=` value earlier than a previously-`save()`d `updated_at`, produces an unexpected token count.

### Pitfall 3: `save()` semantics ambiguity on ordinary (non-abort) per-chunk failures
**What goes wrong:** If `budget.save()` is only called on a chunk with zero item failures (a
strict reading of "successful chunk"), then a chunk with some per-item failures that DON'T trip
the `ConsecutiveWriteFailureError` backstop (isolated failures, D-08 style) never persists its
token consumption — an interrupt right after such a chunk loses that decrement, and the next run
starts with a stale (too-generous) token count, undermining the whole point of the feature.
**Why it happens:** CONTEXT.md's "after each successful chunk" wording is ambiguous between
"chunk processing completed without raising" and "every item in it succeeded."
**How to avoid:** Save after every chunk iteration that returns normally (see "Integration
Reality" §3 above) — tokens were already decremented in-memory at `acquire()` time regardless of
per-item outcome; persisting after every normal chunk return (success or ordinary partial
failure) keeps the on-disk state consistent with the in-memory state at all times except mid-chunk.
**Warning signs:** A test that simulates an ordinary per-item failure (not a `RateLimitError`/
`ConsecutiveWriteFailureError`) followed by a simulated crash shows a `budget-*.json` on disk with
a token count that doesn't reflect the failed chunk's `acquire()` call.

### Pitfall 4: `GeoMismatchError` must fire before ANY write, including delete-only plans
**What goes wrong:** If the geo pre-flight is accidentally placed only inside the upload loop
(e.g. near the `queue_url = sqs_client.get_queue_url(...)` line, which is itself gated by
`if plan.to_upload`), a delete-only plan (`plan.to_upload == []`, `plan.to_delete` non-empty)
would skip the geo check entirely and could still execute deletes under a mismatched geo.
**Why it happens:** The upload loop is visually "first" in `execute_plan`, making it a tempting
(but wrong) place to bolt on a "before any write" check.
**How to avoid:** Place `geo_check()` as the very first statement in `execute_plan`, before the
`queue_url = ...` line and before either `for chunk in ...:` loop — see "Integration Reality" §1.
**Warning signs:** A test with `plan.to_upload=[]`, non-empty `plan.to_delete`, and a
mismatch-raising `geo_check` fake does NOT raise `GeoMismatchError`.

### Pitfall 5: `on_wait` label collision between inter-chunk pacing and budget-wait
**What goes wrong:** See "cli.py Wiring" section above — reusing `_report_wait`'s hardcoded
"cooldown ... before next batch" string for a budget-exhaustion wait (which could be many minutes,
driven by `AURA_WRITE_BUDGET_REFILL_PER_MIN`) is misleading to the operator watching the CLI.
**Why it happens:** CONTEXT.md locks "reuse the existing `on_wait` hook" but the hook's current
single implementation has one hardcoded message.
**How to avoid:** Flagged as a planning-time wording decision (Claude's Discretion per CONTEXT.md)
— not a functional bug, just a UX nuance to resolve explicitly during planning rather than
silently.
**Warning signs:** N/A (cosmetic) — but worth a UAT note if the planner leaves the shared wording
in place.

### Pitfall 6: ipinfo.io's legacy unauthenticated endpoint may be deprecated in the future
**What goes wrong:** If IPinfo eventually removes or rate-limits the unauthenticated
`ipinfo.io/json` legacy endpoint harder than today, the default resolver could start failing
consistently.
**Why it happens:** External, third-party, non-contractual dependency — `[CITED: IPinfo's own
support docs note "the legacy free API will continue to work in the short term, but might receive
less updates and be discontinued in the future"]`.
**How to avoid:** This is exactly why `fail_open=True` is the locked default — a systemic
resolver failure degrades to "geo check skipped, write proceeds" rather than blocking all writes.
No code change needed to mitigate; just don't weaken the fail-open default or the design's core
safety property breaks silently.
**Warning signs:** N/A for this phase — a future maintenance signal, not a Phase 9 blocker.

### Pitfall 7: Double-counting on any future retry logic
**What goes wrong:** `execute_plan` currently has zero retry logic — every chunk is attempted
exactly once. If a future change introduces per-chunk retries (e.g. retrying a transient network
error before falling back to per-item failure attribution), a naive re-entry into the "acquire
before chunk" code path would call `budget.acquire(reqs)` a second time for the same logical
chunk, double-charging the budget for work that was only attempted once against the real API.
**Why it happens:** The budget is currency-metered per *call attempt*, and any retry-wrapping
code must be conscious that `acquire()` reserves tokens for exactly one outbound attempt.
**How to avoid:** Not applicable to this phase's scope (no retry logic exists or is being added)
— documented here purely as a landmine for future maintainers, per the phase's own instruction to
flag this pitfall explicitly.
**Warning signs:** N/A this phase.

## Code Examples

### `WriteBudget.acquire` (wait mode) — matches CONTEXT.md's spec verbatim, project style
```python
# Source: CONTEXT.md decisions + auraframes/sync.py's existing interchunk_pause() 1s-step
# sleep pattern (sync.py:419-436) as the project-idiomatic "sleep in steps, call on_wait each
# second" precedent to mirror for the wait-mode countdown.
def acquire(self, n: int, *, wait: bool, max_wait: float, now, sleep, on_wait=None) -> None:
    elapsed_minutes = max(0.0, (now - (self.updated_at or now)).total_seconds() / 60.0)
    self.tokens = min(self.capacity, self.tokens + self.refill_per_min * elapsed_minutes)
    self.updated_at = now

    if self.tokens >= n:
        self.tokens -= n
        return

    wait_seconds = (n - self.tokens) / self.refill_per_min * 60.0
    if not wait or wait_seconds > max_wait:
        raise BudgetExhausted(wait_seconds)

    remaining = wait_seconds
    while remaining > 0:
        if on_wait:
            on_wait(remaining)
        step = 1.0 if remaining >= 1.0 else remaining
        sleep(step)
        remaining -= step

    self.tokens = self.capacity  # fully refilled by definition of having waited wait_seconds
    self.tokens -= n
```

### `WriteBudget.save`/`load` — JSON round-trip, stdlib only
```python
# Source: this research — stdlib json + datetime.isoformat, no new dependency
import json
from datetime import datetime

def save(self) -> None:
    self.path.parent.mkdir(parents=True, exist_ok=True)
    self.path.write_text(json.dumps({
        'tokens': self.tokens,
        'updated_at': self.updated_at.isoformat() if self.updated_at else None,
    }))

@classmethod
def load(cls, path, *, capacity: float, refill_per_min: float) -> 'WriteBudget':
    if not path.exists():
        return cls(capacity=capacity, refill_per_min=refill_per_min, path=path)
    data = json.loads(path.read_text())
    return cls(
        capacity=capacity, refill_per_min=refill_per_min, path=path,
        tokens=data['tokens'],
        updated_at=datetime.fromisoformat(data['updated_at']) if data['updated_at'] else None,
    )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Reactive-only pacing (throttle + chunk delay + abort-after-N-failures) | Proactive budget that waits/stops *before* the trip, layered on top of the unchanged reactive backstop | This phase (Phase 9) | The reactive layers (`RateLimitError`, `ConsecutiveWriteFailureError`) remain the safety net; the budget is a new layer above them, not a replacement |
| No geo awareness at all | Pre-flight geo guard refusing writes on a country mismatch | This phase (Phase 9) | Directly addresses the empirically-measured #1 root cause of the persistent write-lockout (VPN geo mismatch), which the pure request-rate limiter alone could not have prevented |

**Deprecated/outdated:** N/A — no prior implementation of this capability exists in the codebase
to deprecate.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `budget`/`geo_check` construction should live inside `run_sync()` (protecting both `sync --apply` and `push --apply`), with override flags exposed only on `push` | cli.py Wiring | If the planner instead scopes the whole feature to `push` only, `sync --apply` remains unprotected against the exact same anti-abuse limit it already hit live in Phase 8 — worth explicit confirmation during planning, not blind acceptance of this research's reading |
| A2 | `budget.save()` should run after every normally-returning chunk (not only chunks with zero item failures) | Pitfall 3 / Integration Reality §3 | If narrowed to "zero failures only," an interrupt after a partially-failed-but-not-aborted chunk loses that chunk's token consumption from disk, letting the on-disk estimate drift optimistic over repeated runs |
| A3 | `WriteBudget` should hold its own `path: Path` field (set at construction) rather than `execute_plan` threading a separate `state_path` param | Integration Reality — "state_path note" | Low risk either way — a implementation detail; if the planner prefers `execute_plan` to own the path explicitly, that's a straightforward reshaping of the same information |
| A4 | The default geo resolver should be a bare `httpx.get()` call, not routed through `auraframes.client.Client` | Default Geo Resolver section | Low risk — `Client` is clearly Pushd-specific by inspection (`[VERIFIED]` above), so misuse here would be a design smell, not a hard blocker, if a future maintainer disagrees |
| A5 | 4-second timeout for the geo resolver call is a reasonable default | Default Geo Resolver section | Not specified in CONTEXT.md/design spec (which says only "short timeout") — if too aggressive, could trigger fail-open unnecessarily on a slow connection; if too long, delays every `--apply` run noticeably. Low risk given fail-open default, but the exact value is this research's own assumption, not a locked decision |

## Open Questions

1. **Does `sync --apply` get proactive protection by default, or only `push --apply`?**
   - What we know: `execute_plan`'s integration is described as universal in the design spec;
     `run_sync()` is the single shared handler for both verbs; the override-flag list in
     CONTEXT.md is grouped under a `push`-only heading (mirroring the pre-existing
     `--limit`/`--batch-size`/`--chunk-delay` push-only precedent).
   - What's unclear: Whether "push-only flags" means "push-only feature, defaulted off for
     `sync`" or "push-only *overrides* of a universally-on feature."
   - Recommendation: Default the feature ON for both verbs (via `settings.py` env defaults),
     scope only the four override flags to `push`'s argparse surface — see A1 above. Confirm
     this reading explicitly with the user/spec author during planning if there's any doubt,
     since it changes `sync --apply`'s default behavior.

2. **Exact `save()` cadence on ordinary per-chunk failures (not full aborts).**
   - What we know: CONTEXT.md says "after each successful chunk"; the in-memory token count is
     decremented at `acquire()` time regardless of that chunk's outcome.
   - What's unclear: Literal reading vs. intent — see Pitfall 3 / A2.
   - Recommendation: Save after every normally-returning chunk (success or ordinary partial
     failure), reserving the special `reconcile_tripped()`+`save()` treatment strictly for the
     two abort paths (`RateLimitError`, `ConsecutiveWriteFailureError`).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `httpx` | Default geo resolver's `GET ipinfo.io/json` call | ✓ | `>=0.27` (pyproject.toml; installed) | N/A — already a hard dependency |
| Outbound network to `ipinfo.io` | Live default-resolver behavior (never required by tests) | ✓ (verified live from this dev machine: `curl https://ipinfo.io/json` returned `200` with `country: "FR"`) | — | `fail_open=True` default means an unreachable network degrades to "geo check skipped," not a hard failure |
| Filesystem write access to `~/.config/auraframes/` (or `AURA_STATE_DIR`) | Budget state persistence | ✓ (standard user-writable config dir on this Linux dev machine) | — | None needed with fallback — if genuinely unwritable, `WriteBudget.save()` should surface a clear error rather than silently no-op (not explicitly specified by CONTEXT.md; flag as a planning-time decision, low priority since this is a standard user-config location) |
| `uv` / `pytest>=8` | Running the new offline test suite | ✓ (`uv run pytest --collect-only -q` → 120 tests collected during this research) | uv 0.11.7, Python 3.14.4 | N/A |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** ipinfo.io network reachability (fail-open covers this).

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | No | This phase adds no auth surface — `AURA_EMAIL`/`AURA_PASSWORD` handling is unchanged |
| V3 Session Management | No | No session state introduced |
| V4 Access Control | No | No access-control boundary introduced (budget/geo state is purely advisory client-side bookkeeping, not a security control) |
| V5 Input Validation | Yes | New env vars (`AURA_WRITE_BUDGET_*`, `AURA_COUNTRY`, `AURA_GEO_FAIL_OPEN`, `AURA_STATE_DIR`) and new CLI flags (`--max-wait`, `--country`, etc.) must be parsed defensively — `float(os.getenv(...))` will raise `ValueError` on a malformed value; this should surface as a clear config error, not an unhandled traceback deep inside `WriteBudget.acquire`. Recommend validating/parsing once at settings-load time (matching the existing eager-module-level-constant pattern), so a bad env var fails fast and loud at import time rather than mid-run. |
| V6 Cryptography | No (informational) | `hashlib.sha1(email)[:12]` is used purely for **filename collision-avoidance** across accounts (per-account state files), NOT as a security/authentication boundary — SHA-1's known cryptographic weaknesses (collision attacks) are irrelevant here since the input space (account email strings) is not adversarial and the output is not a security token. No stronger hash is warranted; flagging only so a future auditor doesn't mistake this for a security-sensitive use of SHA-1. |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|-----------------------|
| Local state-file tampering (another process on the same machine edits `budget-<hash>.json` to lie about remaining tokens) | Tampering | Out of scope for this phase — the budget is a **client-side courtesy limiter protecting the user's own account from a server-side lockout**, not a security boundary; a user who tampers with their own local file only hurts themselves (defeats their own proactive protection, falls back to the still-unchanged reactive `RateLimitError`/`ConsecutiveWriteFailureError` backstop). No mitigation needed beyond what already exists. |
| SSRF via the geo resolver | Tampering / Information Disclosure | Not applicable — the resolver URL (`ipinfo.io/json`) is a hardcoded constant, never derived from user input, so there's no SSRF surface to mitigate. |
| Malformed/adversarial env var crashing the CLI ungracefully | Denial of Service (to the user's own workflow, not a remote attacker) | Parse and validate env vars eagerly at `settings.py` import time (see V5 above) so failures are clear and immediate rather than a confusing mid-run stack trace. |
| Secrets leaking into the persisted state file | Information Disclosure | The persisted JSON (`tokens`, `updated_at`) carries no secret material — confirm the implementation never accidentally serializes `AURA_PASSWORD` or auth tokens into this file (it has no reason to, but worth a explicit negative-assertion test: `assert 'password' not in json.loads(state_file.read_text())`, echoing this codebase's existing `_REDACT_KEYS` discipline in `client.py:14-15`). |

## Sources

### Primary (HIGH confidence)
- `auraframes/sync.py` (read in full) — `execute_plan` signature, chunking loop, exact insertion
  points, `ConsecutiveWriteFailureError`
- `auraframes/client.py` (read in full) — `RateLimitError`, `_raise_if_rate_limited`
- `auraframes/cli.py` (read in full) — `push` subparser, `run_sync`, `exec_kwargs` forwarding,
  exception handling order
- `auraframes/utils/settings.py` (read in full) — current env-var convention (all-string, no
  bool/float helper)
- `auraframes/utils/dt.py` (read in full) — `get_utc_now`/`AURA_DT_FORMAT` clock convention
- `auraframes/aws/s3client.py` (read in full, relevant excerpt) — `hashlib`+`base64` precedent
- `tests/test_execute_plan.py`, `tests/test_write_throttling.py`, `tests/test_cli_apply.py`,
  `tests/test_cli_sync.py`, `tests/test_client_rate_limit.py`, `tests/offline.py` (all read in
  full) — test conventions, fake patterns, `_reset_loguru`, `on_wait`/`_WaitRecorder` pattern
- `pyproject.toml` (read in full) — confirmed dependency list (no config library), `uv run pytest`
  runner, `live` marker convention
- `.planning/phases/09-.../09-CONTEXT.md`, `docs/superpowers/specs/2026-07-09-write-rate-limiter-design.md`
  (both read in full) — the locked design decisions this research grounds
- `curl https://ipinfo.io/json` (executed directly during this research) — live-verified default
  resolver contract (`[VERIFIED]`)
- `uv run pytest --collect-only -q` (executed directly) — confirmed 120 tests collected, test
  runner works

### Secondary (MEDIUM confidence)
- WebSearch, cross-checked across 2 queries: `ipinfo.io/json` legacy unauthenticated endpoint
  behavior, ~1000 req/day shared-per-IP limit, "legacy, may be discontinued" status (IPinfo's own
  FAQ/support pages, `ipinfo.io/faq/...`, `support.ipinfo.io/...`)
- WebSearch, cross-checked: token-bucket clock-skew/negative-elapsed-time mitigation pattern
  (clamp elapsed to `max(0, elapsed)` before the refill multiply) — general distributed-systems
  rate-limiting literature, not project-specific

### Tertiary (LOW confidence)
- None — every claim above was either verified directly against this repository's source/tests,
  live-verified via a direct tool call, or cross-checked across independent web sources and
  upgraded to MEDIUM via the classify-confidence seam.

## Metadata

**Confidence breakdown:**
- Standard stack / integration points: HIGH — every insertion point is a direct line-number quote
  from the actual current source, not inferred
- Architecture: HIGH — Approach A is locked by CONTEXT.md and directly matches this codebase's
  existing injectable-seam precedent (`sleep`, `throttle_seconds`, `on_wait`, etc.)
- Pitfalls: HIGH for backward-compat/insertion-order pitfalls (derived from direct code reading);
  MEDIUM for the ipinfo.io-specific pitfall (external service, cross-checked via web search, not
  a guarantee)
- External resolver contract (ipinfo.io/json): HIGH — live-verified via direct `curl` during this
  research session, not assumed

**Research date:** 2026-07-09
**Valid until:** ~30 days for the internal integration findings (stable, own codebase); ~90 days
for the ipinfo.io external-endpoint behavior (third-party service, could change without notice —
re-verify with a live `curl` before relying on it if this phase's implementation is delayed)
</content>
