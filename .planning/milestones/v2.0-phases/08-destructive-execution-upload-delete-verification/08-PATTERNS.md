# Phase 8: Destructive Execution (Upload + Delete Verification) - Pattern Map

**Mapped:** 2026-07-07
**Files analyzed:** 8 (modified) + 0 (new)
**Analogs found:** 8 / 8 (all are modifications of existing files, so the "analog" is each file's own established internal convention, plus one cross-file precedent for the new mutating-loop shape)

All Phase 8 files are **modifications** to existing modules, not new files — CONTEXT.md's "Files that will change" list and RESEARCH.md's "Recommended Project Structure" agree on no new files. Consequently every pattern assignment below points to the *closest existing convention already in the same file or its sibling*, per RESEARCH.md's own findings (which already did much of this mapping using direct source reads).

## File Classification

| File to Modify | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `auraframes/sync.py` (add `execute_plan()`) | service (orchestrator) | event-driven / request-response (mutating loop) | `auraframes/sync.py`'s own `compute_plan()` (pure-function shape, same module) + `Aura.download_images_from_assets()` (continue-past-failure loop) | role-match (shape) / exact (failure-handling idiom) |
| `auraframes/cli.py` (add `--apply`/`--yes`, confirm gate, call `execute_plan()`) | controller (CLI handler) | request-response | `run_sync()` in the same file (frame resolution + fail-loud try/except + dry-run print block) | exact |
| `auraframes/aura.py` (`get_sqs(frame_id)` fix; new narrower upload orchestration, e.g. `_upload_one`/`upload_new_file`) | service (facade) | request-response / file-I/O | `Aura.upload_image()` (same file, same intent, but flagged broken) + `Aura.download_images_from_assets()` (continue-past-failure + tqdm loop) | role-match (existing code is the direct predecessor, but explicitly not to be reused as-is) |
| `auraframes/api/frameApi.py` (`select_asset`/`remove_asset` gain fail-loud checks) | route/API-client | request-response | `FrameApi.get_assets()` in the same file (already has the fail-loud `if json_response.get('error'): raise RuntimeError(...)` convention, WRITE-05 precedent) | exact |
| `auraframes/api/assetApi.py` (`batch_update`/`delete_asset` gain fail-loud checks; `batch_update` type hint widens to `AssetPartial`) | route/API-client | request-response | `FrameApi.get_assets()` (cross-file, the only existing fail-loud precedent in the codebase) | role-match |
| `auraframes/models/asset.py` (add `AssetPartial = make_partial(Asset, 'AssetPartial')`) | model | transform | `auraframes/models/frame.py`'s `FramePartial = make_partial(Frame, "FramePartial")` | exact |
| `auraframes/aws/s3client.py`, `auraframes/aws/sqsclient.py` | service (AWS client) | file-I/O / event-driven | Reused as-is — no code changes expected; `upload_file`/`get_queue_url` signatures already correct | exact (no change) |
| `tests/*` (new offline tests for `execute_plan()`, SQS fix, `AssetPartial`) | test | request-response (mocked) | `tests/offline.py` (`offline_aura()` / `make_router()` DI seam) + `tests/test_cli_sync.py` (existing sync dry-run test shape) | exact |

## Pattern Assignments

### `auraframes/sync.py` — add `execute_plan()`

**Analog:** `compute_plan()` in the same file (pure-function doc-comment style) + `Aura.download_images_from_assets()`'s continue-past-failure loop (`auraframes/aura.py:86-94`)

**Module docstring / "no mutation" framing to update** (lines 1-10):
```python
"""Pure, offline-testable core of the dry-run sync engine (Phase 7).
...
There is deliberately NO execute/mutating counterpart in this module (no
upload, no delete, no S3/SQS call) -- the dry-run guarantee is structural.
The future `execute_plan()` lands in Phase 8.
"""
```
This comment block must be updated once `execute_plan()` is added — it is the explicit textual marker of the "structural, not `if apply:`" boundary CONTEXT.md's Claude's-Discretion section requires preserving. `execute_plan()` should get its own docstring in the same reStructuredText-adjacent doc-comment voice as `compute_plan()`'s (explaining *why*, citing the D-numbers it satisfies), not just a one-liner.

**Continue-past-failure loop pattern to copy** (`auraframes/aura.py:86-94`):
```python
def download_images_from_assets(self, assets: list[Asset], base_path: str):
    failed_to_retrieve = []
    for asset in tqdm(assets):
        try:
            get_image_from_asset(asset, base_path, self.exif_writer)
        except Exception as e:
            failed_to_retrieve.append(asset)
    if len(failed_to_retrieve) > 0:
        logger.debug(f'Failed to retrieve {len(failed_to_retrieve)} assets.')
```
Copy this exact shape (accumulate failures in a list, `continue` implicitly via loop end, one summary line after) for both the upload loop and delete loop inside `execute_plan()`, but capture `(item, str(e))` tuples instead of bare items so the per-file error message is retained for the D-10 separated summary output (this file's own convention doesn't carry the error message through — that gap is the one deviation to make, per RESEARCH.md Pattern 2).

**`SyncPlan`/dataclass field style to extend for results** (lines 71-77):
```python
@dataclass
class SyncPlan:
    to_upload: list[Path] = field(default_factory=list)
    to_delete: list = field(default_factory=list)
    unchanged: int = 0
    skipped_non_image: int = 0
    frame_no_hash: int = 0
```
If `execute_plan()` returns a result object (recommended, mirrors `SyncPlan`/`ScanResult`'s existing dataclass-result convention rather than a bare tuple), follow this same `@dataclass` + `field(default_factory=list)` shape, e.g. `ExecutionResult(upload_failures: list, delete_failures: list, upload_succeeded: int, delete_succeeded: int)`.

---

### `auraframes/cli.py` — `--apply`/`--yes` flags + confirm gate + `run_apply`/extended `run_sync`

**Analog:** `run_sync()` in the same file (lines 219-301) — frame resolution, fail-loud try/except at the CLI boundary, dry-run print block are all directly reusable.

**Argparse subparser extension pattern** (lines 41-44, extend in place):
```python
sync_parser = subparsers.add_parser('sync', help='Dry-run diff a local directory against a frame')
sync_parser.add_argument('dir', help='Local directory to scan for photos')
sync_parser.add_argument('--frame', required=True, help='Frame name (substring) or id')
```
Add `sync_parser.add_argument('--apply', action='store_true', default=False, ...)` and `sync_parser.add_argument('--yes', action='store_true', default=False, ...)` following the exact `action='store_true', default=False` convention already used for the root `--debug` flag (lines 32-36).

**Frame resolution + fail-loud pattern to copy verbatim** (lines 243-258, already inside `run_sync`):
```python
try:
    frames = aura.frame_api.get_frames()
    resolved = resolve_frame(frame_arg, frames)

    if resolved.status == 'ambiguous':
        print(f"'{frame_arg}' matches more than one frame name — re-run with --frame <id>:")
        for candidate in resolved.candidates:
            print(f'  - {candidate.name} (id: {candidate.id})')
        return 1

    if resolved.status == 'not_found':
        print(f"No frame matches name or id '{frame_arg}'. Available frames:")
        for candidate in resolved.candidates:
            print(f'  - {candidate.name} (id: {candidate.id})')
        return 1
```
Reuse this unchanged — `run_apply`/extended `run_sync` needs the identical resolution branch before it can build the D-04 confirmation-prompt frame echo (`f'About to apply this plan to "{frame.name}" (id: {frame.id}). Proceed? [y/N]'`).

**Login + top-level fail-loud pattern** (lines 235-241):
```python
try:
    aura.login()
except Exception as e:
    print(f'Login failed: {e}')
    return 1
```
Copy verbatim for the `--apply` path — same broad-catch-at-CLI-boundary convention (D-08 from Phase 5, cited in RESEARCH.md).

**Non-TTY detection (D-03) — new pattern, no existing analog in this codebase; RESEARCH.md's Don't-Hand-Roll table specifies:**
```python
import sys
if args.apply and not args.yes and not sys.stdin.isatty():
    print('--apply requires --yes when running non-interactively')
    return 1
```
Place this check immediately after frame resolution succeeds and the plan is computed/printed (per D-01/D-03 ordering: plan must print first, then the interactive-vs-non-interactive branch decides prompt-vs-fail-closed).

**Exit-code convention (every handler)** — `run_status`, `run_inspect`, `run_sync` all return `0`/`1` int, never call `sys.exit`. `run_apply` (or extended `run_sync`) must follow the identical convention so `main()`'s dispatch (`return run_sync(...)`) needs no change in shape (lines 304-314).

---

### `auraframes/aura.py` — `get_sqs(frame_id)` fix + new upload orchestration

**Analog:** The existing (broken) `Aura.upload_image()` (lines 106-134) is the direct predecessor but is explicitly flagged as **not to be reused as-is** (RESEARCH.md Anti-Patterns). Copy its DI/logging conventions, not its broken assumptions.

**`get_sqs()` fix — exact before/after** (lines 130-134, current):
```python
def get_sqs(self):
    self.sqsClient = SQSClient()
    # TODO: Is this a hardcoded queue URL?
    queueUrl = self.sqsClient.get_queue_url('4ab446b4-33a7-4a76-881d-d545d153ab5a')
    return queueUrl
```
Minimal fix (D-11, WRITE-04):
```python
def get_sqs(self, frame_id: str):
    self.sqsClient = SQSClient()
    return self.sqsClient.get_queue_url(frame_id)
```
One call site to update: line 114 (`queue_url = self.get_sqs()` → `queue_url = self.get_sqs(frame_id)`), `frame_id` is already in scope there.

**Constructor/DI seam pattern to preserve** (lines 25-33):
```python
def __init__(self, client: Client | None = None):
    self._init_logger()
    self._client = client or Client()
    self.account_api = AccountApi(self._client)
    self.frame_api = FrameApi(self._client)
    ...
```
`Aura`'s constructor already accepts an injected `Client`; RESEARCH.md's Pitfall 2 recommends extending the same DI-seam philosophy to the new upload function's S3/SQS clients (accept already-constructed client objects as parameters rather than constructing `S3Client()`/`SQSClient()` internally) so offline tests can substitute fakes, mirroring how `tests/offline.py`'s `offline_aura()` injects `Client(transport=...)`.

**Existing (to-be-superseded) upload sequence — preserve shape for first live attempt, per Pitfall 4** (lines 106-128):
```python
def upload_image(self, frame_id: str, image_path: str, asset: Asset):
    try:
        image = Image.open(image_path)
    except Exception as e:
        logger.error(e)
        return
    local_identifier = asset.local_identifier
    self.frame_api.select_asset(frame_id, AssetPartialId(local_identifier=local_identifier))
    queue_url = self.get_sqs()
    self.sqsClient.receive_message(queue_url, wait_time_seconds=5)
    self.frame_api.select_asset(frame_id, AssetPartialId(local_identifier=local_identifier))
    client = S3Client()
    filename, md5 = client.upload_file(open(image_path, 'rb').read(), '.jpg')
    asset.file_name = filename
    asset.md5_hash = md5
    asset.height = image.height
    asset.width = image.width
    self.asset_api.batch_update(asset)
    message = self.sqsClient.receive_message(queue_url, wait_time_seconds=5)
    print(message)
```
The new narrower function replaces `asset.local_identifier`/direct `Asset` mutation with a fresh `uuid.uuid4()` identifier and an `AssetPartial(...)` built from scratch (see RESEARCH.md's "Upload identity construction" code example, already vetted against the installed pydantic 2.13 — copy that example directly rather than re-deriving it). Preserve the double `select_asset` + discarded-first-poll sequence unchanged for the first live attempt (Pitfall 4), and replace `print(message)` with a debug-level `logger.debug(...)` call consistent with this file's existing logging conventions (`logger.error(e)` at line 110, `logger.debug(...)` at `auraframes/aura.py:94`).

**Logger usage convention** (lines 89-94, 110):
```python
except Exception as e:
    failed_to_retrieve.append(asset)
if len(failed_to_retrieve) > 0:
    logger.debug(f'Failed to retrieve {len(failed_to_retrieve)} assets.')
```
```python
except Exception as e:
    logger.error(e)
```
Use `logger.error(e)` for a caught exception at the point of failure (matches existing convention exactly) and `logger.debug(f'...')` for summary/count lines.

---

### `auraframes/api/frameApi.py` — fail-loud `select_asset`/`remove_asset`

**Analog:** `FrameApi.get_assets()` in the same file (lines 38-58) — this IS the fail-loud precedent WRITE-05 extends.

**Exact pattern to copy** (lines 50-56):
```python
json_response = self._client.get(f'/frames/{frame_id}/assets.json',
                                 query_params={'limit': limit, 'cursor': cursor})
if json_response.get('error'):
    raise RuntimeError(
        f"get_assets failed for frame {frame_id}: "
        f"{json_response.get('message') or json_response.get('error')}"
    )
```

**Target methods to modify** (lines 105-118, 135-148):
```python
def select_asset(self, frame_id: str, asset_partial_id: AssetPartialId) -> int:
    json_response = self._client.post(f'/frames/{frame_id}/select_asset.json',
                                      data={'assets': [asset_partial_id.to_request_format()]})
    return json_response.get('number_failed')

def remove_asset(self, frame_id: str, asset_partial_id: AssetPartialId) -> int:
    json_response = self._client.post(f'/frames/{frame_id}/remove_asset.json',
                                      data={'assets': [asset_partial_id.to_request_format()]})
    return json_response.get('number_failed')
```
Apply the `get_assets` error-field check to both, plus (per RESEARCH.md's exact recommendation) a `number_failed > 0` raise since each call carries exactly one `AssetPartialId`:
```python
def select_asset(self, frame_id: str, asset_partial_id: AssetPartialId) -> int:
    json_response = self._client.post(f'/frames/{frame_id}/select_asset.json',
                                      data={'assets': [asset_partial_id.to_request_format()]})
    if json_response.get('error'):
        raise RuntimeError(f"select_asset failed for frame {frame_id}: {json_response.get('error')}")
    number_failed = json_response.get('number_failed')
    if number_failed:
        raise RuntimeError(f"select_asset reported {number_failed} failure(s) for frame {frame_id}")
    return number_failed
```
Mirror identically for `remove_asset` (swap the docstring/message text only).

---

### `auraframes/api/assetApi.py` — fail-loud `batch_update`/`delete_asset`; widen `batch_update` type hint

**Analog:** `FrameApi.get_assets()` (cross-file — this file has no existing fail-loud precedent of its own).

**Current `batch_update`, target for both the error check and the type-hint widening** (lines 9-41):
```python
def batch_update(self, asset: Asset) -> tuple[list[str], list[AssetPartialId]]:
    json_response = self._client.put(f'/assets/batch_update.json', data={
        "assets": [
            asset.dict(include={...})
        ]
    })
    return json_response.get('ids'), [AssetPartialId(**partial_asset_id) for partial_asset_id in
                                      json_response.get('successes')]
```
Widen the parameter type hint to `Asset | AssetPartial` (import `AssetPartial` from `auraframes.models.asset` once added there) since `.dict(include={...})` works identically on both (it's the same underlying pydantic model shape via `make_partial`'s `__base__=model`). Add the `get_assets`-style check before the return:
```python
if json_response.get('error'):
    raise RuntimeError(f"batch_update failed: {json_response.get('error')}")
```

**`delete_asset` — currently returns raw unchecked response** (lines 74-88):
```python
def delete_asset(self, asset: Asset):
    if asset.is_local_asset:
        json_response = self._client.post(f'/assets/destroy_by_local_identifier.json',
                                          data={'local_identifier': asset.local_identifier})
    else:
        json_response = self._client.delete(f'/assets/{asset.id}.json')
    return json_response
```
Add the same `if json_response.get('error'): raise RuntimeError(...)` guard before returning — note this method is only called from the isolated, non-wired `checkpoint:human-verify` probe (D-06), not from `execute_plan()`, so the fail-loud check here is for the probe's own clarity, not the execute path.

---

### `auraframes/models/asset.py` — add `AssetPartial`

**Analog:** `auraframes/models/frame.py:101` (exact, same factory, same file-bottom placement convention)

```python
# Source: auraframes/models/frame.py:101
FramePartial = make_partial(Frame, "FramePartial")
```
Copy directly at the bottom of `auraframes/models/asset.py`, after the `AssetPartialId` class:
```python
from auraframes.models.meta import make_partial
# ... existing Asset, AssetPartialId classes unchanged ...
AssetPartial = make_partial(Asset, "AssetPartial")
```
Note the single/double-quote inconsistency already present between `FramePartial` (double quotes for the name arg) — match whichever style Phase 8's own diff prefers, but staying consistent within the new line is what matters; no functional difference.

---

### `tests/*` — offline test harness for `execute_plan()` / SQS fix / `AssetPartial`

**Analog:** `tests/offline.py`'s `offline_aura()`/`make_router()` DI seam (already the established pattern for every offline test in this codebase since Phase 4).

**DI seam construction to reuse verbatim** (lines 62-72):
```python
def offline_aura(overrides: dict | None = None):
    from auraframes.aura import Aura
    from auraframes.client import Client

    transport = httpx.MockTransport(make_router(overrides))
    return Aura(client=Client(transport=transport))
```
For `execute_plan()`'s S3/SQS calls specifically (which `offline_aura()` does NOT cover — it only seams the REST `Client`), RESEARCH.md's Pitfall 2 / Don't-Hand-Roll table recommends a small duck-typed fake object (`MagicMock` or a tiny local class with `.upload_file`/`.get_queue_url`/`.receive_message`) passed as a constructor/parameter argument to whatever new upload function is built — mirroring this exact "inject the already-constructed dependency" philosophy, not `botocore.stub.Stubber` (heavier, no other file in this project uses it).

**Router override pattern for forcing an error envelope** (lines 22-38, 50-58):
```python
def make_router(overrides: dict | None = None):
    overrides = overrides or {}
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path in overrides:
            return overrides[path]
        ...
        return httpx.Response(404, json=_load("error_envelope.json"))
    return handler
```
New tests exercising WRITE-05's fail-loud paths (`select_asset`/`remove_asset`/`batch_update` returning an `error` envelope) should pass `overrides={'/v5/frames/<id>/select_asset.json': httpx.Response(200, json={'error': '...'})}` into `make_router`/`offline_aura`, following this exact override-dict convention rather than adding new branching logic to the router itself.

## Shared Patterns

### Fail-loud error checking (WRITE-05)
**Source:** `auraframes/api/frameApi.py:50-56` (`get_assets`)
**Apply to:** `FrameApi.select_asset`, `FrameApi.remove_asset`, `AssetApi.batch_update`, `AssetApi.delete_asset`
```python
if json_response.get('error'):
    raise RuntimeError(f"<method> failed for frame {frame_id}: {json_response.get('error')}")
```

### Continue-past-failure loop with per-item attribution (D-08, WRITE-05)
**Source:** `auraframes/aura.py:86-94` (`download_images_from_assets`), extended with error-message capture per RESEARCH.md Pattern 2
**Apply to:** `execute_plan()`'s upload loop and delete loop (each independently)
```python
failures: list[tuple[Any, str]] = []
for item in sorted(items):  # sorted() per run_sync's existing WR-03 reproducibility convention
    try:
        _do_one(item)
    except Exception as e:
        failures.append((item, str(e)))
        continue
```

### CLI handler shape: int exit code, injected `Aura`, fail-loud top-level catch
**Source:** `auraframes/cli.py` — `run_status`/`run_inspect`/`run_sync` (all three, identical shape)
**Apply to:** The `--apply` execution path, whether as a new `run_apply()` or an extended `run_sync()`
```python
def run_apply(dir_arg: str, frame_arg: str, apply: bool, yes: bool, aura=None, debug: bool = False) -> int:
    aura = aura or Aura()
    _configure_cli_logging(debug)
    try:
        aura.login()
    except Exception as e:
        print(f'Login failed: {e}')
        return 1
    try:
        ...  # frame resolution (copy run_sync's resolve_frame block verbatim)
    except Exception as e:
        print(f'Failed to ...: {e}')
        return 1
    return 0
```

### `make_partial()` factory for all-Optional partial models
**Source:** `auraframes/models/frame.py:101` (`FramePartial = make_partial(Frame, "FramePartial")`)
**Apply to:** `auraframes/models/asset.py` (`AssetPartial = make_partial(Asset, "AssetPartial")`)

### DI seam for offline testability
**Source:** `Aura.__init__(self, client: Client | None = None)` (`auraframes/aura.py:25`) + `tests/offline.py`'s `offline_aura()`
**Apply to:** Any new upload orchestration function — accept S3/SQS client objects as parameters (or via an injected factory) rather than constructing `S3Client()`/`SQSClient()` internally, since `AWSClient.__init__` triggers live Cognito auth unconditionally (Pitfall 2).

## No Analog Found

None — every file in Phase 8's change list has at least a role-match analog either in the same file (most cases) or the one clear cross-file precedent (`get_assets`'s fail-loud pattern for the two files that lack one). No file requires falling back to RESEARCH.md's Code Examples as a first resort; those examples are already directly consistent with the analogs found above and are cited inline where they add detail beyond what static analog-reading alone provides (e.g. the `AssetPartial` upload-identity construction example, which is genuinely new orchestration code with no direct precedent to copy from, only the `make_partial` factory pattern and the broken `upload_image` predecessor to avoid).

## Metadata

**Analog search scope:** `auraframes/` (all subpackages), `tests/` (offline harness + existing sync test)
**Files scanned:** `auraframes/aura.py`, `auraframes/sync.py`, `auraframes/cli.py`, `auraframes/api/frameApi.py`, `auraframes/api/assetApi.py`, `auraframes/models/asset.py`, `auraframes/models/frame.py`, `auraframes/models/meta.py`, `auraframes/aws/s3client.py`, `auraframes/aws/sqsclient.py`, `tests/offline.py`
**Pattern extraction date:** 2026-07-07
