---
phase: 08-destructive-execution-upload-delete-verification
reviewed: 2026-07-08T00:00:00Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - auraframes/models/asset.py
  - auraframes/api/frameApi.py
  - auraframes/api/assetApi.py
  - auraframes/aura.py
  - auraframes/sync.py
  - auraframes/cli.py
  - tests/test_asset_partial.py
  - tests/test_write_endpoints_failloud.py
  - tests/test_execute_plan.py
  - tests/test_cli_apply.py
findings:
  critical: 3
  warning: 4
  info: 1
  total: 8
status: issues_found
---

# Phase 8: Code Review Report

**Reviewed:** 2026-07-08T00:00:00Z
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Reviewed the destructive-execution upload/delete path added in Phase 8: `sync.execute_plan`/`_execute_upload`, the fail-loud upgrades to `FrameApi`/`AssetApi`, the new `AssetPartial` model, and the `--apply`/`--yes` CLI wiring, plus their offline test coverage.

The overall shape (uploads-before-deletes, per-item try/except with named failures, fail-closed confirmation gate) is sound and is backed by real tests. However, hands-on verification (actually constructing the models and reading the diffs against `master`) surfaced three correctness bugs that undercut the phase's own stated goal of "verification": a pre-existing but newly load-bearing validator on `AssetPartialId` that silently does nothing in the common case, a `batch_update` success check that doesn't actually verify the upload succeeded, and a hardcoded `data_uti` that contradicts the module's own declared support for `.png`/`.heic` files. None of these were caught by the test suite — each is a genuine gap in the "fail loud" guarantee this phase set out to build. Four further warnings (an unconditional SQS call that can abort delete-only plans, dead code, an inconsistent sibling method, and an unclosed file handle) round out the report.

## Critical Issues

### CR-01: `AssetPartialId`'s id-or-local_identifier guard is a no-op in the common case (and wrongly rejects valid input in another)

**File:** `auraframes/models/asset.py:114-124`

**Issue:** `check_id_or_local_id` is a `@field_validator('id')` that inspects `info.data.get('local_identifier')` to enforce "either `id` or `local_identifier` must be set." This is broken for two independent reasons that combine into a validator that provides essentially no real protection:

1. **Pydantic v2 skips field validators for fields that use their default value** (no `validate_default=True` on the field). Since both `id` and `local_identifier` default to `None`, *any* construction that omits `id` skips this validator entirely — including the "neither field set" case the validator exists to catch.
2. **`id` is declared before `local_identifier`** in the model, so even when the validator does run (i.e., `id` is passed explicitly), `info.data` does not yet contain `local_identifier`'s value — it hasn't been validated yet at that point in the field-declaration order.

Verified directly against the installed pydantic 2.13:
```python
>>> AssetPartialId()                                    # should fail — succeeds silently
AssetPartialId(id=None, local_identifier=None, user_id=None)
>>> AssetPartialId(user_id='abc')                        # should fail — succeeds silently
AssetPartialId(id=None, local_identifier=None, user_id='abc')
>>> AssetPartialId(id=None, local_identifier='abc')       # should succeed — raises instead
ValidationError: Either id or local_identifier is required
```
This is directly reachable in production code, not just a theoretical edge case: `AssetApi.batch_update` hydrates `AssetPartialId(**partial_asset_id)` straight from the server's `successes` payload (`auraframes/api/assetApi.py:42-43`). If any success entry the live API returns ever includes an explicit `id: null` alongside a valid `local_identifier` (plausible for a newly-created, not-yet-numbered asset correlated only by `local_identifier` — exactly `execute_plan`'s upload scenario), hydration will raise `ValidationError` on what the server reported as a *success*. Conversely, the intended safety net — refusing to build a degenerate identifier with neither `id` nor `local_identifier` — never fires for the common omitted-field construction pattern used throughout `sync.py`/`aura.py` (`AssetPartialId(local_identifier=local_identifier)`), so a caller bug that leaves `local_identifier` unset would silently produce `to_request_format() == {'asset_local_identifier': None}` sent straight to the frame-mutating `select_asset`/`remove_asset` endpoints.

**Fix:** Replace the field validator with a `model_validator(mode='after')`, which runs after every field is set regardless of whether defaults were used and has no field-order dependency:
```python
from pydantic import model_validator

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

### CR-02: `_execute_upload` treats a partial/no-op `batch_update` response as a successful upload

**File:** `auraframes/sync.py:175`, `auraframes/api/assetApi.py:39-43`

**Issue:** `AssetApi.batch_update` only raises when the JSON response has a top-level `error` key:
```python
if json_response.get('error'):
    raise RuntimeError(f"batch_update failed: {json_response.get('error')}")
return json_response.get('ids'), [AssetPartialId(**partial_asset_id) for partial_asset_id in json_response.get('successes')]
```
It never checks that `successes` actually contains an entry corresponding to what was sent, unlike its siblings `select_asset`/`remove_asset` (also touched in this phase), which explicitly raise on a nonzero `number_failed`. `_execute_upload` compounds this by discarding the return value entirely:
```python
aura.asset_api.batch_update(pending)   # return value never inspected
```
If the live API ever responds `200` with no `error` field but an empty or short `successes` list (a very plausible "partial success" shape for a batch endpoint — it is literally why `select_asset`/`remove_asset` gained a `number_failed` check in this same phase), `execute_plan` will still increment `result.upload_succeeded` even though the just-uploaded file's metadata (file_name/md5/dimensions/taken_at) was never actually attached to any asset server-side. This is precisely the "verification" gap the phase is named for, and it is untested — `tests/test_write_endpoints_failloud.py::test_batch_update_succeeds_with_asset_partial` only exercises the 1:1 `ids`/`successes` match case.

**Fix:** Validate the response shape in `batch_update` itself (mirroring the `number_failed` precedent already established for `select_asset`/`remove_asset` in this phase):
```python
ids = json_response.get('ids') or []
successes = json_response.get('successes') or []
if len(successes) < len(ids):
    raise RuntimeError(
        f"batch_update reported {len(ids) - len(successes)} failure(s) "
        f"out of {len(ids)} requested"
    )
return ids, [AssetPartialId(**s) for s in successes]
```

### CR-03: Hardcoded `data_uti='public.jpeg'` contradicts `ELIGIBLE_EXTENSIONS`; `.heic` uploads cannot succeed at all

**File:** `auraframes/sync.py:36`, `auraframes/sync.py:156-174`

**Issue:** `ELIGIBLE_EXTENSIONS = frozenset({'.jpg', '.jpeg', '.png', '.heic'})` declares that PNG and HEIC files are diffed and, when new, uploaded. But `_execute_upload` unconditionally builds:
```python
pending = AssetPartial(
    ...
    data_uti='public.jpeg',
    ...
)
```
regardless of the actual file's extension. Two distinct, verifiable failure modes result:
- A new `.png` file uploads "successfully" (per CR-02's weak check) but is permanently mislabeled with the JPEG UTI server-side.
- A new `.heic` file can **never** upload successfully: `Image.open(path)` (line 156) is called before any network activity, and this project's installed Pillow has no HEIC decoder registered (`Image.registered_extensions().get('.heic')` is `None` — no `pillow-heif` or equivalent dependency is declared in `pyproject.toml`). Every `.heic` candidate in `plan.to_upload` will raise `PIL.UnidentifiedImageError` and be recorded as a permanent, unactionable `upload_failure` on every run.

The project's own research doc (`08-RESEARCH.md`, Pitfall 5) explicitly scoped `data_uti='public.jpeg'` as an assumption for JPEG only ("`data_uti='public.jpeg'` for JPEG"), but that scoping was never reflected in `ELIGIBLE_EXTENSIONS`, which still advertises PNG/HEIC as eligible for the full upload round-trip.

**Fix:** Either restrict `ELIGIBLE_EXTENSIONS` to what upload can actually support today, or map extension to UTI and skip/report HEIC distinctly:
```python
_DATA_UTI_BY_SUFFIX = {'.jpg': 'public.jpeg', '.jpeg': 'public.jpeg', '.png': 'public.png'}

def _execute_upload(...):
    ...
    data_uti = _DATA_UTI_BY_SUFFIX.get(path.suffix.lower())
    if data_uti is None:
        raise ValueError(f'Unsupported upload extension: {path.suffix}')
    ...
```

## Warnings

### WR-01: `execute_plan` fetches an SQS queue URL even for delete-only plans, and its failure aborts everything

**File:** `auraframes/sync.py:211`

**Issue:** `queue_url = sqs_client.get_queue_url(frame_id)` runs unconditionally before either loop, including when `plan.to_upload` is empty. This call sits outside both per-item `try/except` blocks, so if it raises (auth hiccup, no queue provisioned for a frame that's never had an upload, transient AWS error), the exception propagates out of `execute_plan` entirely — aborting the delete loop too, even though deletes never need `queue_url`. A delete-only `sync --apply` can therefore fail closed for a reason that has nothing to do with deletion.

**Fix:** Only resolve the queue URL when there is something to upload:
```python
queue_url = sqs_client.get_queue_url(frame_id) if plan.to_upload else None
```

### WR-02: Dead code — unreachable trailing `return 0` in `run_sync`

**File:** `auraframes/cli.py:351`

**Issue:** Every path through the enclosing `try` block now returns explicitly (the `if not apply: return 0`, the `--yes`/tty checks, the abort path, and the final `return 1 if (...) else 0` added in this phase's `08-03` commit), and the `except Exception` branch also returns. The trailing `return 0` at the end of the function is unreachable. It was live code before this phase (the old body fell through after printing `frame_no_hash`) but became dead once the `--apply` branch was added and not cleaned up.

**Fix:** Remove the trailing `return 0` (or leave a `# unreachable` comment if intentionally kept as a defensive fallback — but then it should not silently mean "success").

### WR-03: `FrameApi.exclude_asset` was left out of this phase's fail-loud upgrade, inconsistent with its neighbors

**File:** `auraframes/api/frameApi.py:126-139`

**Issue:** `select_asset` and `remove_asset` were both upgraded in this phase to raise `RuntimeError` on an `error` envelope or nonzero `number_failed` (WRITE-05). `exclude_asset`, defined between them in the same file, still does neither:
```python
json_response = self._client.post(f'/frames/{frame_id}/exclude_asset', data={...})
return json_response.get('number_failed')
```
This was called out as explicitly out-of-scope in the phase plan, but it leaves a trap for future maintainers: someone extending the CLI to also exclude assets would silently inherit the old, already-identified-as-broken silent-failure pattern right next to two methods that look identical but aren't.

**Fix:** Apply the same guard used for `select_asset`/`remove_asset`:
```python
if json_response.get('error'):
    raise RuntimeError(f"exclude_asset failed for frame {frame_id}: {json_response.get('error')}")
number_failed = json_response.get('number_failed')
if number_failed:
    raise RuntimeError(f"exclude_asset reported {number_failed} failure(s) for frame {frame_id}")
return number_failed
```

### WR-04: `Image.open(path)` handles are never closed in `_execute_upload`

**File:** `auraframes/sync.py:156`

**Issue:** `image = Image.open(path)` opens a file handle that is only read for `.size` (via `image.height`/`image.width`) and is never closed — no context manager, no `.close()` call. Across a large batch (the live-verification run in `08-LIVE-FINDINGS.md` processed dozens of items in one `execute_plan` call), this accumulates open file descriptors for the life of the process.

**Fix:**
```python
with Image.open(path) as image:
    width, height = image.size
```
and use the captured `width`/`height` when building `AssetPartial`.

## Info

### IN-01: `AssetApi.crop_asset`/`update_taken_at_date` remain unguarded

**File:** `auraframes/api/assetApi.py:56-114`

**Issue:** `batch_update` and `delete_asset` gained `error`-key checks in this phase; `crop_asset` and `update_taken_at_date` in the same file did not (pre-existing, explicitly out of this phase's stated scope). Noting for future consistency since this file is now a mix of fail-loud and silent-failure methods.

**Fix:** When these methods are next touched, apply the same `if json_response.get('error'): raise RuntimeError(...)` guard used elsewhere in this file.

---

_Reviewed: 2026-07-08T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
