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
  warning: 5
  info: 2
  total: 10
status: issues_found
---

# Phase 8: Code Review Report

**Reviewed:** 2026-07-08T00:00:00Z
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Reviewed the destructive-execution path added in Phase 8: `sync.execute_plan`/`_execute_upload`, the fail-loud upgrades to `FrameApi`/`AssetApi`, the new `AssetPartial`/`AssetPartialId` handling, and the `--apply`/`--yes` CLI wiring, plus their offline test coverage. The overall shape — uploads attempted before deletes, per-item try/except with named failures, a fail-closed confirmation gate — is sound and backed by real tests.

Independently re-deriving (not just trusting) the logic and executing the model directly against the installed pydantic 2.13.4 confirms three correctness bugs that undercut this phase's own "verification" goal: `AssetPartialId`'s guard validator is a no-op for the common case and wrongly rejects valid input in another (confirmed by direct construction, see CR-01); `AssetApi.batch_update`'s success check doesn't actually verify the upload was applied (CR-02); and a hardcoded `data_uti` makes `.heic` uploads guaranteed to fail and `.png` uploads permanently mislabeled, despite both being declared eligible via `ELIGIBLE_EXTENSIONS` (confirmed: this Pillow install has no `.heic` decoder registered) (CR-03). None of these are caught by the existing test suite. Additional findings below cover an unconditional SQS call that can abort delete-only plans, a genuinely dead branch in `AssetApi` inherited from a pre-existing model gap that this phase's `delete_asset` fail-loud change now sits directly on top of, unreachable trailing code, an inconsistent sibling method, and an unclosed file handle.

## Critical Issues

### CR-01: `AssetPartialId`'s id-or-local_identifier guard is a no-op in the common case (and wrongly rejects valid input in another)

**File:** `auraframes/models/asset.py:119-124`

**Issue:** `check_id_or_local_id` is declared as `@field_validator('id')` and inspects `info.data.get('local_identifier')` to enforce "either `id` or `local_identifier` must be set." Verified directly against the installed pydantic 2.13.4:

```
>>> AssetPartialId()                              # should fail — succeeds silently
AssetPartialId(id=None, local_identifier=None, user_id=None)
>>> AssetPartialId(user_id='abc')                 # should fail — succeeds silently
AssetPartialId(id=None, local_identifier=None, user_id='abc')
>>> AssetPartialId(id=None, local_identifier='abc')  # should succeed — raises instead
ValidationError: Either id or local_identifier is required
```

Two independent causes: (1) pydantic v2 skips a field validator when the field is left at its default (`None`) unless `validate_default=True` is set — since both `id` and `local_identifier` default to `None`, any construction that omits `id` entirely (the common "neither set" bug case) skips the validator. (2) `id` is declared before `local_identifier` in the model, so even when the validator *does* run (i.e. `id` is passed explicitly), `info.data` does not yet contain `local_identifier`'s validated value at that point in field-declaration order — the guard only "works" by accident when `_id` itself is truthy (short-circuits the `and`), and actively misfires when `id=None` is passed explicitly alongside a valid `local_identifier`.

This is reachable in production, not just theoretical: `AssetApi.batch_update` hydrates `AssetPartialId(**partial_asset_id)` straight from the server's `successes` payload (`auraframes/api/assetApi.py:42-43`). A success entry for a newly-created asset correlated only by `local_identifier` (exactly `execute_plan`'s upload scenario) that includes an explicit `id: null` would raise `ValidationError` on what the server reported as a success. Meanwhile the intended safety net never fires for the omitted-field construction pattern used throughout `sync.py`/`aura.py` (`AssetPartialId(local_identifier=local_identifier)`), so a caller bug that leaves `local_identifier` unset/empty would silently produce `to_request_format() == {'asset_local_identifier': None}` sent straight to the frame-mutating `select_asset`/`remove_asset` endpoints.

**Fix:** Use a `model_validator(mode='after')`, which runs after every field regardless of default usage and has no field-order dependency:
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
It never checks that `successes` actually corresponds to what was sent — unlike its siblings `select_asset`/`remove_asset` (also touched in this phase), which explicitly raise on a nonzero `number_failed`. If the response omits `successes` entirely (no `error` key either), this raises an opaque `TypeError: 'NoneType' object is not iterable` instead of an attributable `RuntimeError`. `_execute_upload` compounds the risk by discarding the return value entirely:
```python
aura.asset_api.batch_update(pending)   # return value never inspected
```
If the live API ever responds `200` with no `error` field but an empty/short `successes` list, `execute_plan` still increments `result.upload_succeeded` even though the just-uploaded file's metadata (file_name/md5/dimensions/taken_at) was never attached to any asset server-side. This is precisely the "verification" gap the phase is named for, and it's untested — `tests/test_write_endpoints_failloud.py::test_batch_update_succeeds_with_asset_partial` only exercises the 1:1 `ids`/`successes` match case.

**Fix:** Validate the response shape in `batch_update` itself, mirroring the `number_failed` precedent from this same phase:
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

**Issue:** `ELIGIBLE_EXTENSIONS = frozenset({'.jpg', '.jpeg', '.png', '.heic'})` declares that PNG and HEIC files are diffed and, when new, uploaded. But `_execute_upload` unconditionally sets `data_uti='public.jpeg'` regardless of the file's actual extension, and calls `Image.open(path)` before any network activity. Verified directly against the installed environment:
```
>>> from PIL import Image
>>> Image.registered_extensions().get('.heic')
None
>>> Image.registered_extensions().get('.png')
'PNG'
```
No `pillow-heif` (or equivalent) dependency is declared in `pyproject.toml`. Consequences: every `.heic` candidate in `plan.to_upload` raises `PIL.UnidentifiedImageError` inside `_execute_upload` on every single run — a permanent, unactionable `upload_failure` for a file type the module's own `ELIGIBLE_EXTENSIONS` claims to support end-to-end. A new `.png` file, meanwhile, "succeeds" (per CR-02's weak check) but is permanently mislabeled server-side with the JPEG UTI.

**Fix:** Map extension to UTI and fail closed (or skip with a named reason) for unsupported ones instead of hardcoding one value for all four declared-eligible extensions:
```python
_DATA_UTI_BY_SUFFIX = {'.jpg': 'public.jpeg', '.jpeg': 'public.jpeg', '.png': 'public.png'}

def _execute_upload(...):
    ...
    data_uti = _DATA_UTI_BY_SUFFIX.get(path.suffix.lower())
    if data_uti is None:
        raise ValueError(f'Unsupported upload extension: {path.suffix}')
    ...
```
Or narrow `ELIGIBLE_EXTENSIONS` to `.jpg`/`.jpeg` only until PNG/HEIC upload is actually implemented.

## Warnings

### WR-01: `execute_plan` fetches an SQS queue URL even for delete-only plans, and its failure aborts the whole run

**File:** `auraframes/sync.py:211`

**Issue:** `queue_url = sqs_client.get_queue_url(frame_id)` runs unconditionally before either loop, including when `plan.to_upload` is empty. This call sits outside both per-item `try/except` blocks, so if it raises (auth hiccup, no queue provisioned for a frame that's never had an upload, transient AWS error), the exception propagates out of `execute_plan` entirely — aborting the delete loop too, even though deletes never reference `queue_url`. A delete-only `sync --apply` can therefore fail closed for a reason that has nothing to do with deletion, and no test exercises a delete-only plan combined with a raising `sqs_client`.

**Fix:**
```python
queue_url = sqs_client.get_queue_url(frame_id) if plan.to_upload else None
```

### WR-02: `Asset.is_local_asset` is unreachable given `Asset.id`'s required-`str` typing, silently dead-ending two branches this phase hardened

**File:** `auraframes/models/asset.py:53,109-111`, `auraframes/api/assetApi.py:68-71,84-88`

**Issue:** `Asset.id` is typed `id: str` (required, not `Optional[str]`), so any `Asset` built via normal validated construction (`Asset(**json_response)`, the only path used by `FrameApi.get_assets`/`AssetApi.get_asset_by_local_identifier`) can never have `id=None`. `Asset.is_local_asset` (`return self.id is None`) is therefore always `False` for every real, validated `Asset` — dead code. `AssetApi.delete_asset` (touched in this phase to add its fail-loud `error` check, `assetApi.py:90-91`) and `update_taken_at_date` both branch on `asset.is_local_asset` to decide between a local-identifier-based request and an id-based one; the local-identifier branch is unreachable through the normal hydration path and can only be exercised today via `Asset.model_construct(...)` (validation-bypassing), exactly as `tests/test_write_endpoints_failloud.py:137` does. In other words, `delete_asset`'s newly-added fail-loud guard was layered onto a branch that production code can never actually take for a locally-only asset — the phase hardened a path that isn't reachable, while the real question ("what happens if you try to delete an asset that only has a `local_identifier`") remains unanswered.

**Fix:** Either make `Asset.id: Optional[str] = None` and audit callers that assume it's always present, or remove `is_local_asset`/its dependent branches and document that `Asset` (as opposed to `AssetPartial`) always represents a server-hydrated asset.

### WR-03: `FrameApi.exclude_asset` was left out of this phase's fail-loud upgrade, inconsistent with its neighbors

**File:** `auraframes/api/frameApi.py:126-139`

**Issue:** `select_asset` and `remove_asset` were both upgraded in this phase to raise `RuntimeError` on an `error` envelope or nonzero `number_failed` (WRITE-05). `exclude_asset`, defined between them in the same file, does neither — it silently returns `json_response.get('number_failed')` with no validation. A future caller extending the CLI to exclude assets would inherit the already-identified-as-broken silent-failure pattern right next to two methods that look identical but aren't.

**Fix:**
```python
if json_response.get('error'):
    raise RuntimeError(f"exclude_asset failed for frame {frame_id}: {json_response.get('error')}")
number_failed = json_response.get('number_failed')
if number_failed:
    raise RuntimeError(f"exclude_asset reported {number_failed} failure(s) for frame {frame_id}")
return number_failed
```

### WR-04: `Image.open(path)` handle is never closed in `_execute_upload`

**File:** `auraframes/sync.py:156`

**Issue:** `image = Image.open(path)` opens a file handle read only for `.height`/`.width`; it's never closed (no context manager, no `.close()`). Across a large `execute_plan` batch this accumulates open file descriptors for the life of the process.

**Fix:**
```python
with Image.open(path) as image:
    width, height = image.size
```
and use the captured `width`/`height` when building `AssetPartial`.

### WR-05: Unreachable trailing `return 0` in `run_sync`

**File:** `auraframes/cli.py:351`

**Issue:** Every path through the enclosing `try` block now returns explicitly — the ambiguous/not-found checks, the `OSError` scan-failure branch, `if not apply: return 0`, the non-tty/`--yes` check, the abort-on-answer path, and the final `return 1 if (...) else 0` added in this phase's `08-03` commit — and the `except Exception` branch also returns. The trailing `return 0` at line 351 is therefore dead code; it predates this phase but became provably unreachable once the `--apply` branch's exhaustive returns were added here without removing it.

**Fix:** Delete the trailing `return 0`.

## Info

### IN-01: `AssetApi.crop_asset`/`update_taken_at_date` remain unguarded

**File:** `auraframes/api/assetApi.py:56-114`

**Issue:** `batch_update` and `delete_asset` gained `error`-key checks in this phase; `crop_asset` and `update_taken_at_date` in the same file did not (explicitly out of this phase's stated scope, per `08-RESEARCH.md`). Noting for future consistency since this file is now a mix of fail-loud and silent-failure methods.

**Fix:** Apply the same `if json_response.get('error'): raise RuntimeError(...)` guard when these methods are next touched.

### IN-02: `sync.py`/`assetApi.py`'s reliance on pydantic v1-style `.dict()` is deprecated in v2

**File:** `auraframes/api/assetApi.py:21,102`, project-wide pre-existing pattern also exercised by the new `AssetPartial` payloads in `sync.py:175`

**Issue:** `.dict(include={...})` is pydantic v2's deprecated alias for `.model_dump()`. It still works today (verified: `tests/test_asset_partial.py` passes against the installed pydantic 2.13.4) but emits a `PydanticDeprecatedSince20` warning and is not guaranteed to survive a future major pydantic bump. This phase's new `AssetPartial` upload path now depends on this deprecated call succeeding, widening its blast radius slightly.

**Fix:** When this file is next touched, migrate to `.model_dump(include={...})`.

---

_Reviewed: 2026-07-08T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
