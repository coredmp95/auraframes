# Phase 11: Write-Path Reliability & Format Support - Pattern Map

**Mapped:** 2026-09-03
**Files analyzed:** 9 (new + modified)
**Analogs found:** 9 / 9

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `auraframes/sync.py` (`execute_plan` retry logic, D-01..D-08) | service (write orchestration) | event-driven / request-response (retry-on-401) | `auraframes/sync.py` itself — its existing upload-chunk `try/except RateLimitError / except ConsecutiveWriteFailureError / except Exception` block (lines ~610-639) | exact (extend in place) |
| `auraframes/sync.py` (`_prep_upload` / `_DATA_UTI_BY_SUFFIX` → format-derived UTI, D-11/D-12) | utility (transform) | transform | `auraframes/sync.py:_prep_upload` (lines 348-373) | exact (modify in place) |
| `auraframes/api/assetApi.py` (`batch_update` return-shape change, D-18) | service (API wrapper) | request-response / CRUD | `auraframes/api/assetApi.py:batch_update` (lines 9-53) | exact (modify in place) |
| `auraframes/client.py` / `auraframes/sync.py` (new `AuraError` hierarchy + auth exception, D-20) | model (exception types) | n/a | `auraframes/client.py:RateLimitError` (lines 28-56) and `auraframes/sync.py:ConsecutiveWriteFailureError` (lines 127-...) | exact |
| `auraframes/models/asset.py` (`AssetPartialId` inbound tolerance, D-19) | model | transform / CRUD | `auraframes/models/asset.py:AssetPartialId` + `model_validator` (lines 132-146) | exact |
| `auraframes/reconcile.py` (new module, D-13/D-14/D-15/D-16) | service (data hygiene, not sync-path) | batch / request-response | `auraframes/sync.py` module shape (pure-diff function + separate mutating function), and `auraframes/cli.py:run_inspect` for the read/report half | role-match (new module, no direct 1:1 analog) |
| `auraframes/cli.py` (new `reconcile` subparser + verb wiring, D-13) | route/CLI | request-response | `auraframes/cli.py:build_parser` `push_parser` block (lines 79-101) and `main()` dispatch (lines 607-621) | exact |
| `auraframes/cli.py` (`run_reconcile` handler + `inspect` one-line addition) | controller (CLI handler) | request-response | `auraframes/cli.py:run_inspect` (lines 212-... ) | exact |
| `tests/test_read_path.py::test_read_03_pagination` (D-17 rewrite) | test | request-response | same file, existing test body (assert restructuring only) | exact |
| new tests for retry/format/reconcile (offline) | test | event-driven / transform | `tests/test_execute_plan.py`, `tests/test_write_endpoints_failloud.py`, `tests/offline.py` | exact |
| `pyproject.toml` (add `pillow-heif`, D-09) | config | n/a | existing `dependencies` list in `pyproject.toml` | exact |

## Pattern Assignments

### `auraframes/sync.py` — retry-then-verify in `execute_plan`'s upload chunk loop (D-01..D-08)

**Analog:** `auraframes/sync.py` lines 380-389 (signature) and 592-639 (the existing try/except ladder)

**Signature pattern to extend** (lines 380-389):
```python
def execute_plan(plan: SyncPlan, aura, frame_id: str, *, s3_client, sqs_client,
                 throttle_seconds: float = WRITE_THROTTLE_SECONDS, sleep=time.sleep,
                 max_consecutive_failures: int = MAX_CONSECUTIVE_WRITE_FAILURES,
                 progress=lambda *args: None,
                 batch_size: int = WRITE_BATCH_SIZE,
                 chunk_delay_seconds: float = WRITE_CHUNK_DELAY_SECONDS,
                 on_wait=lambda *args: None,
                 budget=None, geo_check=None, wait_on_budget: bool = True,
                 max_wait_seconds: float = 3600.0, clock=get_utc_now,
                 removal_mode: str = 'hide') -> ExecutionResult:
```
Follow this exact shape for any new retry-related keyword (e.g. a `relogin` callable or `verify_before_retry: bool = True`) — every prior cross-cutting concern in this function (budget, geo, throttle, removal mode) was added as an injectable keyword with a sensible default, never as a hidden branch. This is the seam D-03 explicitly reuses.

**Core existing except-ladder to extend** (lines 610-639):
```python
        except RateLimitError:
            # Anti-abuse throttle/lockout: abort the whole batch (do not
            # mask it as one per-item failure and keep hammering).
            if budget is not None:
                budget.reconcile_tripped(clock())
                budget.save()
            raise
        except ConsecutiveWriteFailureError:
            # note_failure() above can raise this from WITHIN the per-file
            # attribution loop (all prepped files already individually
            # appended/reported there) -- it must propagate as-is, NOT be
            # re-caught by the generic Exception branch below, which would
            # otherwise mistake the abort for a whole-chunk Pushd failure and
            # double-attribute every prepped file a second time. (Reconcile
            # already happened inside note_failure() before this raised.)
            raise
        except Exception as e:
            # A whole-chunk Pushd failure (select_asset or batch_update
            # raising) attributes ALL prepped files in this chunk as failed
            # -- there is no per-item signal to fall back on.
            for path, _, _ in prepped:
                result.upload_failures.append((path, str(e)))
                progress('upload', path, False)
                note_failure(str(e))
```
The D-01/D-02 retry inserts a new branch **between** `RateLimitError` and the generic `Exception` catch — a plain-HTTP-401 form (the new auth exception type from D-20, or a bare `except Exception` guarded by a status-code check depending on how the client surfaces it) triggers: (1) re-login via `aura.login()` (mirrors `auraframes/aura.py:35-51`'s existing `login()` method — call it as-is, do not reimplement), (2) on re-login failure, raise the new auth exception loudly (never retried, never softened — D-02); (3) on re-login success, verify each `prepped` item via `aura.asset_api.get_asset_by_local_identifier(local_identifier)` (already exists, `auraframes/api/assetApi.py:56-63`) and only re-send items that 404/are-absent; (4) re-send via the same `select_asset`/`batch_update` calls already in this block; (5) if the retried write still 401s, classify as anti-abuse and hand off via `note_failure()` exactly like the existing per-item failure path so `ConsecutiveWriteFailureError`'s backstop (already threaded through `note_failure`, referenced at line ~617) still applies. **One retry per chunk** (D-04) — a simple local `retried = False` flag guards re-entry, matching the existing single-pass-per-chunk shape of this loop (no other chunk-level state is tracked today, so introduce this flag adjacent to `prepped`).

**Budget costing pattern to copy** (lines 622-629, the existing chunk-end save):
```python
        if budget is not None:
            # Save after every chunk that returns normally (success OR
            # ordinary caught failure, Phase 09 ANTI-04) -- acquire() already
            # decremented tokens in-memory for the attempted requests
            # regardless of per-item outcome, so this keeps the on-disk
            # estimate from drifting optimistic after an interrupt.
            budget.save()
```
D-05/D-06's retry costing (2 for upload retry, 1 for delete retry, 1 for re-login) must go through `budget.acquire(n, wait=wait_on_budget, max_wait=max_wait_seconds, now=clock(), sleep=sleep, on_wait=on_wait)` — the exact call already used for the first attempt (find the sibling `budget.acquire(...)` call preceding this chunk's `select_asset`/`batch_update` sequence) — never a bespoke charge path. This is D-07's "same wait policy as any other write."

**Heavy rationale comment convention to copy** (from `WRITE_CHUNK_DELAY_SECONDS`, lines ~95-103, and `MAX_CONSECUTIVE_WRITE_FAILURES`, lines ~108-124): every new constant this phase introduces (e.g. a `RETRY_RELOGIN_COST` or the D-08 visibility counters) needs a comment paragraph in this same voice — cite the specific live incident/decision (D-01..D-08 reference numbers), not just "why this value."

---

### `auraframes/sync.py` — `_prep_upload` format-derived `data_uti` (D-11/D-12)

**Analog:** `auraframes/sync.py` lines 348-373 (current implementation) plus the `_DATA_UTI_BY_SUFFIX` dict at line 64 and its rationale comment (lines 58-63)

**Current fail-closed pattern to preserve exactly**:
```python
def _prep_upload(path: Path, s3_client) -> AssetPartial:
    data_uti = _DATA_UTI_BY_SUFFIX.get(path.suffix.lower())
    if data_uti is None:
        raise ValueError(f'Unsupported upload extension: {path.suffix}')

    local_identifier = str(uuid.uuid4())
    with Image.open(path) as image:
        width, height = image.size
    ...
```
D-11 replaces `path.suffix.lower()` lookup with `image.format` (available for free from the already-open `Image.open(path)` call — reorder so the `Image.open` block runs before the UTI lookup) mapped through an explicit `{'JPEG': 'public.jpeg', 'PNG': 'public.png', 'HEIF': 'public.heic'}`-shaped table (name TBD at Claude's discretion per CONTEXT.md), and the `if data_uti is None: raise ValueError(...)` fail-closed shape stays byte-for-byte identical — only the lookup key changes from filename-derived to content-derived. Keep raising `ValueError` (matches D-20's scope: `_prep_upload`'s `ValueError` is a per-file caught-and-attributed failure via the existing `except Exception as e: result.upload_failures.append(...)` block at lines 331-335 of the caller loop — do not convert this one to `AuraError`, since D-20 only converts write-endpoint `RuntimeError`s, not this pre-existing per-file `ValueError`).

**HEIC refusal-at-`_prep_upload` pattern (D-10):** if the live checkpoint finds the frame does not render HEIC, add a second fail-closed branch in this same function — same `raise ValueError(f'...')` shape, message naming the real reason (e.g. `'Frame does not accept HEIC uploads (verified live 2026-09-XX)'`), never a generic "missing decoder" string. This is a straight copy of the existing "fail closed with a named reason" convention already in this function.

---

### `auraframes/api/assetApi.py` — `batch_update` unacknowledged-set return (D-18)

**Analog:** `auraframes/api/assetApi.py` lines 9-53 (full existing method + its docstring)

```python
    def batch_update(self, assets: Asset | AssetPartial | list[Asset | AssetPartial]) -> tuple[list[str], list[AssetPartialId]]:
        ...
        items = assets if isinstance(assets, list) else [assets]
        json_response = self._client.put(f'/assets/batch_update.json', data={...})
        if json_response.get('error'):
            raise RuntimeError(f"batch_update failed: {json_response.get('error')}")
        ids = json_response.get('ids') or []
        successes = json_response.get('successes') or []
        return ids, [AssetPartialId(**partial_asset_id) for partial_asset_id in successes]
```
D-18 extends the return tuple to a third element — the sent-but-unacknowledged set — computed as `{item.local_identifier for item in items if item.local_identifier} - {s.local_identifier for s in successes}` (or equivalent), returned explicitly rather than left for `execute_plan` to recompute (it already does recompute this today at lines 604-618 of `sync.py` — that call site's logic is "already correct" per D-18 and should be left as-is; only `Aura.upload_image`'s silent discard of the return value needs the new signal). **This changes a public return shape** (D-18 flags this as "costly" — every destructuring caller must be updated in the same commit): grep all call sites of `batch_update(` before changing the signature (`auraframes/sync.py`, `auraframes/aura.py:upload_image`, and any test that destructures `_, successes = ...`).

**D-19 inbound tolerance pattern** (same method, the `successes` construction line):
```python
        return ids, [AssetPartialId(**partial_asset_id) for partial_asset_id in successes]
```
becomes a loop that wraps each `AssetPartialId(**partial_asset_id)` construction in `try/except Exception` (or a narrower validation-error type if pydantic v2 exposes one — check `pydantic.ValidationError`), logs via `logger.warning(...)` (matching this codebase's `loguru` convention, see `auraframes/aura.py`'s use of `logger`) and skips the malformed entry rather than propagating — while the **outbound** construction of `AssetPartialId` to send (the `select_asset` call sites in `sync.py`, e.g. `AssetPartialId(local_identifier=lid)`) keeps raising via the existing `model_validator` unchanged. Do not touch `auraframes/models/asset.py:132-140`'s validator itself — D-19/CONTEXT.md explicitly flags "verify before rewriting."

---

### `auraframes/models/asset.py` — `AssetPartialId` validator (reference only, D-19)

**Analog:** `auraframes/models/asset.py` lines 132-146
```python
class AssetPartialId(BaseModel):
    id: Optional[str] = None
    local_identifier: Optional[str] = None
    user_id: Optional[str] = None

    @model_validator(mode='after')
    def check_id_or_local_id(self) -> 'AssetPartialId':
        if not self.id and not self.local_identifier:
            raise ValueError('Either id or local_identifier is required')
        return self
```
This file itself is likely **unchanged** this phase (D-19's note says "verify before rewriting" — the tolerance lives at the `batch_update` call site in `assetApi.py`, not here). Cite this excerpt in the plan so the executor confirms the validator's current behavior before deciding whether any change here is needed.

---

### `auraframes/client.py` + `auraframes/sync.py` — `AuraError` hierarchy (D-20)

**Analog A:** `auraframes/client.py` lines 28-56 (`RateLimitError`)
```python
class RateLimitError(Exception):
    """..."""
    def __init__(self, status_code: int, retry_after=None, server_message: str | None = None):
        self.status_code = status_code
        self.retry_after = retry_after
        self.server_message = server_message
        ...
        super().__init__(...)
```
**Analog B:** `auraframes/sync.py` line 127 area (`ConsecutiveWriteFailureError(Exception)`), which carries `count`, `last_error`, `result` as constructor-set attributes with a docstring explaining exactly which live incident it exists for.

D-20's `AuraError` base is a plain `class AuraError(Exception): pass`-style root (place in `auraframes/client.py` alongside `RateLimitError`, since that is the existing home for cross-cutting exception types, or a new `auraframes/errors.py` if the planner prefers — no existing convention forces either, but co-locating with `RateLimitError` avoids a new module for one small hierarchy). Reparent `RateLimitError(AuraError)` and `ConsecutiveWriteFailureError(AuraError)` — a one-line base-class change each, preserving every existing attribute/docstring verbatim. The new auth exception type (naming at Claude's discretion — `AuthExpiredError` or `AuthenticationError`) follows Analog A's constructor-with-context-attributes shape (e.g. carry the failed re-login's underlying exception/message) and its own docstring in the same voice: what live incident motivates it, what it is distinct from, what a caller should do.

**Convert only write-path bare `RuntimeError`s** — the two in `auraframes/api/assetApi.py`:
```python
raise RuntimeError(f"batch_update failed: {json_response.get('error')}")
...
raise RuntimeError(f"delete_asset failed: {json_response.get('error')}")
```
(lines ~52 and ~99) become `raise SomeAuraError(f"...")` subclasses of the new base — leave every other `RuntimeError`/read-path call untouched (D-20 explicitly scopes this down).

**Except-ordering guard (critical, do not break):** `auraframes/sync.py` lines 610-621's `except RateLimitError: ... except ConsecutiveWriteFailureError: ... raise ... except Exception:` ordering is load-bearing — reparenting must not cause a broader `except AuraError` anywhere in this file to accidentally swallow one of these two specific branches ahead of its own explicit handler. Grep for `except AuraError` before introducing one in `sync.py`.

---

### `auraframes/cli.py` — new `reconcile` subparser + verb wiring (D-13)

**Analog:** `auraframes/cli.py` lines 79-101 (`push` subparser block) and lines 607-621 (dispatch)

```python
    push_parser = subparsers.add_parser('push', help='Upload photos from a directory to a frame (additive -- never deletes)')
    push_parser.add_argument('dir', help='...')
    push_parser.add_argument('--frame', required=True, help='Frame name (substring) or id')
    push_parser.add_argument('--apply', action='store_true', default=False, help='Execute the upload instead of only printing the plan')
    push_parser.add_argument('--yes', action='store_true', default=False, help='Skip the confirmation prompt (required for --apply when running non-interactively)')
```
and dispatch:
```python
    if args.command == 'push':
        return run_sync(
            args.dir, args.frame, apply=args.apply, yes=args.yes, debug=args.debug,
            no_delete=True, ...
        )
```
Copy this exact shape for `reconcile`: `reconcile_parser = subparsers.add_parser('reconcile', help='...')`, a required `--frame`, a `--remove` flag (`action='store_true', default=False`) mirroring `--apply`'s report-vs-mutate split, and a `--yes` flag reusing the same help string verbatim ("Skip the confirmation prompt (required for --remove when running non-interactively)") for consistency with `sync`/`push`. Dispatch with `if args.command == 'reconcile': return run_reconcile(args.frame, remove=args.remove, yes=args.yes, debug=args.debug)`.

**Confirmation-friction pattern to copy (Claude's Discretion note, escalating friction per Phase 10):** find `sync --apply`'s or `push --apply`'s confirmation-prompt code in `cli.py` (search for `'Proceed?'` or `input(`) and copy its `[y/N]` gate + `--yes` bypass verbatim for `reconcile --remove`.

---

### `auraframes/cli.py` — `run_reconcile` handler + `inspect` one-line addition (D-13)

**Analog:** `auraframes/cli.py` lines 212-... (`run_inspect`)
```python
def run_inspect(frame_arg: str, aura=None, debug: bool = False) -> int:
    aura = aura or Aura()
    _configure_cli_logging(debug)
    try:
        aura.login()
    except Exception as e:
        print(f'Login failed: {e}')
        return 1
    try:
        frames = aura.frame_api.get_frames()
        resolved = resolve_frame(frame_arg, frames)
        if resolved.status == 'ambiguous': ...
        if resolved.status == 'not_found': ...
        frame, total_asset_count = aura.frame_api.get_frame(resolved.frame.id)
        ...
```
`run_reconcile` copies this exact skeleton: injectable `aura=None` DI seam, `_configure_cli_logging(debug)` placement, the same login-failure `try/except Exception as e: print(...); return 1` shape, the same `resolve_frame` ambiguous/not_found branches, then calls into the new `auraframes/reconcile.py` module's pure functions to compute the placeholder set and (if `--remove`) apply the removal/completion mechanism found by D-16's probe. `run_inspect` itself gains one `print(f'Placeholder rows: {count}')`-style line using `auraframes.reconcile`'s counting function — call the same pure counter from both `run_inspect` and `run_reconcile` so the count is computed once, in one place.

---

### `auraframes/reconcile.py` — new module (D-13/D-14/D-15/D-16)

**Analog (module shape):** `auraframes/sync.py`'s own top-of-file docstring convention (pure-diff function `compute_plan` separate from the sole mutating function `execute_plan`) — apply the identical separation here: a pure `find_placeholders(assets: list[Asset], *, now, age_threshold_seconds=86400) -> ReconcileResult`-shaped function (D-14's strict conjunction predicate: `uploaded_at is None and file_name is None and md5_hash is None`, D-15's age guard via `Asset.created_at`, already non-optional per `auraframes/models/asset.py:22`) and a separate mutating `apply_reconciliation(...)` that is the module's only network-touching function, exactly mirroring `execute_plan`'s "ONLY mutating function" framing.

**Predicate excerpt to model D-14 on** — the existing hashless-video exclusion this phase deliberately does NOT reuse (contrast, cite in the plan so the executor does not accidentally reuse it): `auraframes/sync.py` lines 263-268 area (`compute_plan`'s `frame_no_hash` bucket) — D-14 explicitly requires a narrower three-way-null predicate, not this bucket.

**Result dataclass pattern to copy:** `auraframes/sync.py`'s `ExecutionResult` / `SyncPlan` dataclasses (`@dataclass` with `field(default_factory=...)` for list fields) — model a `ReconcileResult` dataclass the same way (e.g. `stuck: list[Asset]`, `recently_created: list[Asset]`, `removed: list[str]`).

---

### `tests/test_read_path.py::test_read_03_pagination` — assertion rewrite (D-17)

**Analog:** the test's own current body at `tests/test_read_path.py:64` — read it directly before editing (do not re-derive from memory); replace the `len(assets) == total` assertion with: `len(pages_fetched) > 1`, `len(set(asset.id for asset in assets)) == len(assets)` (no duplicate ids), and `0 < len(assets) <= total`. Follow the existing live-test module's marker convention (`@pytest.mark.live`, check the top of `tests/test_read_path.py` for the marker registration) — this test stays live, not moved offline, per D-17's explicit rejection of that option.

---

### New offline tests (retry, format, reconcile)

**Analog:** `tests/offline.py` (`make_router`, `_load` fixture pattern) + `tests/test_execute_plan.py` (`_default_overrides()`, `_FakeS3Client`, `@pytest.fixture(autouse=True) _reset_loguru`) + `tests/test_write_endpoints_failloud.py` (per-endpoint `overrides = {PATH: httpx.Response(...)}` shape, `pytest.raises(RuntimeError)` / soon `pytest.raises(SomeAuraError)`).

**Router-override pattern to copy** (`tests/test_execute_plan.py` lines 43-56):
```python
def _default_overrides():
    return {
        SELECT_ASSET_PATH: httpx.Response(200, json={'number_failed': 0}),
        REMOVE_ASSET_PATH: httpx.Response(200, json={'number_failed': 0}),
        EXCLUDE_ASSET_PATH: httpx.Response(200, json={'number_failed': 0}),
        BATCH_UPDATE_PATH: httpx.Response(200, json={
            'ids': ['local-id'],
            'successes': [{'id': 'new-asset-id', 'local_identifier': 'local-id'}],
        }),
    }
```
For the retry test: install a router override that returns `httpx.Response(401, ...)` on the **first** `select_asset`/`batch_update` call and a success response on the second (MockTransport handlers can use a mutable counter closure, matching `tests/offline.py`'s `make_router(overrides)` extensibility — `overrides` is checked before default branches, so a stateful override callable works if `httpx.Response` is swapped for a callable-based override; check `tests/offline.py`'s exact override-lookup code before assuming a callable is supported, and if not, add that capability there first). For the verify-probe: mock `asset_for_local_identifier.json` to return 404 for genuinely-missing items and 200 for already-landed ones, asserting the retry only re-sends the 404 set.

**Duck-typed fake pattern** (`tests/test_execute_plan.py` lines 60-68, `_FakeS3Client`) — reuse this exact fake for any new format test (HEIC/PNG upload) rather than constructing a real `S3Client`.

**`AuraError`-subclass raise assertions** — copy `tests/test_write_endpoints_failloud.py`'s `with pytest.raises(RuntimeError):` shape, updated to the new exception type once D-20 lands.

## Shared Patterns

### Injectable-seam-over-interceptor
**Source:** `auraframes/sync.py:execute_plan` signature (lines 380-389) — every cross-cutting concern (`throttle_seconds`, `sleep`, `batch_size`, `chunk_delay_seconds`, `on_wait`, `budget`, `geo_check`, `wait_on_budget`, `max_wait_seconds`, `clock`, `removal_mode`) is a keyword arg with a real default, never a hidden client-level hook.
**Apply to:** the D-01..D-08 retry logic; any new reconcile-module knobs (age threshold, probe candidate limit).

### Fail-closed-with-named-reason
**Source:** `auraframes/sync.py:_prep_upload` lines 358-360 (`raise ValueError(f'Unsupported upload extension: {path.suffix}')`).
**Apply to:** D-11/D-12's format table lookup, D-10's HEIC refusal message.

### Heavy rationale comments beside constants
**Source:** `auraframes/sync.py` — `WRITE_THROTTLE_SECONDS` (lines 66-76), `WRITE_BATCH_SIZE` (lines 78-87), `WRITE_CHUNK_DELAY_SECONDS` (lines 89-99), `MAX_CONSECUTIVE_WRITE_FAILURES` (lines 101-119).
**Apply to:** D-08's retry-costing constant and any new reconcile-module threshold (`RECONCILE_AGE_THRESHOLD_SECONDS`, a probe candidate cap).

### Per-item attribution recovered from a batch endpoint's response
**Source:** `auraframes/sync.py` lines 604-610 (`succeeded = {s.local_identifier for s in successes}` then per-file loop).
**Apply to:** D-18's unacknowledged-set computation inside `batch_update` itself, and D-16's probe of a bounded candidate set.

### CLI handler skeleton: injectable `aura=None`, `_configure_cli_logging(debug)`, login try/except, `resolve_frame` branches
**Source:** `auraframes/cli.py:run_inspect` (lines 212-257+).
**Apply to:** the new `run_reconcile` handler.

### Offline MockTransport test harness
**Source:** `tests/offline.py` (`make_router`, `_load`, `FIXTURES_DIR`), `tests/test_execute_plan.py` (`_default_overrides`, `_FakeS3Client`, `_reset_loguru` autouse fixture).
**Apply to:** every new offline test this phase adds (retry-then-verify, format detection, `batch_update` unacknowledged-set, reconcile predicate/probe).

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `auraframes/reconcile.py` | service | batch | No prior "data hygiene on existing bad state" module exists in this codebase; `auraframes/sync.py`'s pure/mutating split is the nearest structural analog, cited above, but the domain (placeholder rows, live probe of a removal mechanism) is new to this phase. |

## Metadata

**Analog search scope:** `auraframes/` (sync.py, client.py, cli.py, aura.py, api/assetApi.py, models/asset.py, ratelimit.py), `tests/` (offline.py, conftest.py, test_execute_plan.py, test_write_endpoints_failloud.py, test_read_path.py)
**Files scanned:** ~12
**Pattern extraction date:** 2026-09-03
