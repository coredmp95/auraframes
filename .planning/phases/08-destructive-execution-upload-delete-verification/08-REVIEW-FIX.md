---
phase: 08-destructive-execution-upload-delete-verification
fixed_at: 2026-07-08T05:44:06Z
review_path: .planning/phases/08-destructive-execution-upload-delete-verification/08-REVIEW.md
iteration: 1
findings_in_scope: 8
fixed: 8
skipped: 0
status: all_fixed
---

# Phase 8: Code Review Fix Report

**Fixed at:** 2026-07-08T05:44:06Z
**Source review:** .planning/phases/08-destructive-execution-upload-delete-verification/08-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 8 (fix_scope: critical_warning — 3 Critical, 5 Warning; the 2 Info findings were excluded)
- Fixed: 8
- Skipped: 0

## Fixed Issues

### CR-01: `AssetPartialId`'s id-or-local_identifier guard is a no-op in the common case (and wrongly rejects valid input in another)

**Files modified:** `auraframes/models/asset.py`
**Commit:** 2796ec6
**Applied fix:** Replaced the pydantic v2 `@field_validator('id')` (which skips when `id` defaults to `None`, and reads `info.data.get('local_identifier')` before it's populated due to field declaration order) with a `@model_validator(mode='after')` that runs unconditionally after all fields are set. Verified directly: `AssetPartialId()` and `AssetPartialId(user_id='abc')` now correctly raise `ValidationError`, and `AssetPartialId(id=None, local_identifier='abc')` now correctly succeeds. Removed the now-unused `field_validator`/`ValidationInfo` imports.

### CR-02: `_execute_upload` treats a partial/no-op `batch_update` response as a successful upload

**Files modified:** `auraframes/api/assetApi.py`
**Commit:** a46f2e9
**Applied fix:** `AssetApi.batch_update` now defaults `ids`/`successes` to `[]` and raises `RuntimeError` naming the failure count whenever `len(successes) < len(ids)`, mirroring the `number_failed` precedent already used by `select_asset`/`remove_asset`. This closes the gap where `execute_plan` would count an upload as succeeded even if the just-uploaded file's metadata was never attached server-side; the existing per-item `try/except` in `sync.execute_plan` now correctly routes this case to `upload_failures` since `_execute_upload` never inspected `batch_update`'s return value itself.

### CR-03: Hardcoded `data_uti='public.jpeg'` contradicts `ELIGIBLE_EXTENSIONS`; `.heic` uploads cannot succeed at all

**Files modified:** `auraframes/sync.py`
**Commit:** bb12503
**Applied fix:** Added a `_DATA_UTI_BY_SUFFIX` mapping covering only `.jpg`/`.jpeg` (the only extensions with a verified-correct UTI in this environment — no `pillow-heif` installed for `.heic`, no verified UTI for `.png`). `_execute_upload` now looks up the UTI from the file's actual suffix before any side-effecting calls and raises `ValueError('Unsupported upload extension: ...')` if unmapped, so `.heic`/`.png` uploads fail closed with a named, attributable reason instead of raising an opaque `PIL.UnidentifiedImageError` mid-flow or silently mislabeling a `.png` as JPEG server-side.

### WR-01: `execute_plan` fetches an SQS queue URL even for delete-only plans, and its failure aborts the whole run

**Files modified:** `auraframes/sync.py`
**Commit:** 43ac0bc
**Applied fix:** Changed `queue_url = sqs_client.get_queue_url(frame_id)` to `queue_url = sqs_client.get_queue_url(frame_id) if plan.to_upload else None`, so a delete-only plan no longer performs (or can be aborted by) an SQS call that deletes never reference.

### WR-02: `Asset.is_local_asset` is unreachable given `Asset.id`'s required-`str` typing, silently dead-ending two branches this phase hardened

**Files modified:** `auraframes/models/asset.py`, `auraframes/api/assetApi.py`
**Commit:** 7a8d7fa
**Applied fix:** Chose the "remove dead code + document" option (narrower blast radius than widening `Asset.id` to `Optional[str]` and auditing all callers, consistent with this project's pragmatic modernization-scope constraint). Removed the always-`False` `is_local_asset` property and replaced it with a comment explaining `Asset.id` is always populated for server-hydrated assets. Collapsed `AssetApi.delete_asset` and `update_taken_at_date`'s `is_local_asset` branches down to their single reachable (id-based) code path, each with an explanatory comment. Confirmed via grep that `is_local_asset` had no other production callers.

### WR-03: `FrameApi.exclude_asset` was left out of this phase's fail-loud upgrade, inconsistent with its neighbors

**Files modified:** `auraframes/api/frameApi.py`
**Commit:** 38e28c5
**Applied fix:** Added the same `error`-key and nonzero-`number_failed` `RuntimeError` guards already present on `select_asset`/`remove_asset` to `exclude_asset`, for consistency across the three sibling methods.

### WR-04: `Image.open(path)` handle is never closed in `_execute_upload`

**Files modified:** `auraframes/sync.py`
**Commit:** 092670b
**Applied fix:** Wrapped `Image.open(path)` in a `with` block, capturing `width, height = image.size` immediately so the file handle closes before the rest of the upload round-trip runs; `pending`'s `AssetPartial` now references the captured `width`/`height` locals instead of `image.width`/`image.height`.

### WR-05: Unreachable trailing `return 0` in `run_sync`

**Files modified:** `auraframes/cli.py`
**Commit:** cdf1b40
**Applied fix:** Deleted the dead trailing `return 0` after confirming every path through the enclosing `try`/`except` (including the `except Exception` branch) already returns explicitly.

## Skipped Issues

None — all in-scope findings were fixed.

---

_Fixed: 2026-07-08T05:44:06Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
