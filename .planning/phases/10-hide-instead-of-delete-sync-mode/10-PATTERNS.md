# Phase 10: Hide-instead-of-delete sync mode - Pattern Map

**Mapped:** 2026-07-10
**Files analyzed:** 6 (modified only — no new files this phase)
**Analogs found:** 6 / 6 (all analogs are in the SAME files being modified — this phase extends existing siblings rather than importing patterns from elsewhere)

> **APK addendum applies.** No `include_asset` method is created (RESEARCH.md's body is superseded).
> Re-show reuses `select_asset`. `exclude_asset` is widened in place (batch). Read change is
> `get_assets` passing `filter='all'`. No `Asset`/`AssetSetting` model change.

## File Classification

| Modified File | Role | Data Flow | Closest Analog (in-file sibling) | Match Quality |
|---|---|---|---|---|
| `auraframes/api/frameApi.py` — `exclude_asset` (widen to batch) | service/API-client method | request-response (batch write) | `remove_asset` (same file, lines 157-186) | exact |
| `auraframes/api/frameApi.py` — `get_assets` (add `filter='all'`) | service/API-client method | request-response (paginated read) | itself, unchanged shape; `get_activity_assets` (activityApi.py) as a **rejected** parallel-array precedent (do NOT follow) | exact (self) |
| `auraframes/sync.py` — `SyncPlan` dataclass (add `to_reshow`, `already_hidden`, rename/repurpose `to_delete`→`to_remove`) | model/dataclass | transform (pure diff) | itself, `ExecutionResult` dataclass shape (same file) | exact |
| `auraframes/sync.py` — `compute_plan` (4-way classification) | transform/service | transform (pure, CRUD-classification) | itself (existing 3-way classification, lines 212-252) | exact |
| `auraframes/sync.py` — `execute_plan` (removal_mode param + re-show loop) | service (mutating engine) | event-driven/batch (chunked writes) | itself — existing delete chunk loop (lines 561-589) mirrored twice (re-show loop + mode-selected removal loop) | exact |
| `auraframes/cli.py` — `sync` subparser + `run_sync` (flags, verb wording, escalated gate) | controller/CLI handler | request-response | itself — existing `--apply`/`--yes`/`no_delete` flag pattern (lines 65-68, 374-395, 417-431) | exact |

## Pattern Assignments

### `auraframes/api/frameApi.py` — widen `exclude_asset` to batch

**Analog:** `remove_asset` in the same file (`auraframes/api/frameApi.py:157-186`), which already has the exact single-or-list normalization `exclude_asset` needs.

**Imports pattern** (lines 1-8, unchanged — no new imports needed):
```python
import uuid
from auraframes.api.baseApi import BaseApi
from auraframes.models.activity import Activity
from auraframes.models.asset import Asset, AssetPartialId
from auraframes.models.frame import Frame, FramePartial
from auraframes.utils.dt import get_utc_now, format_dt_to_aura
```

**Core pattern to copy** (`remove_asset`, lines 157-186 — copy structure verbatim, changing only the URL and the docstring):
```python
def remove_asset(self, frame_id: str, asset_partial_ids: AssetPartialId | list[AssetPartialId]) -> int:
    items = asset_partial_ids if isinstance(asset_partial_ids, list) else [asset_partial_ids]

    json_response = self._client.post(f'/frames/{frame_id}/remove_asset.json',
                                      data={'assets': [item.to_request_format() for item in items]})
    if json_response.get('error'):
        raise RuntimeError(f"remove_asset failed for frame {frame_id}: {json_response.get('error')}")

    number_failed = json_response.get('number_failed')
    if number_failed:
        raise RuntimeError(f"remove_asset reported {number_failed} failure(s) for frame {frame_id}")

    return number_failed
```

**Target shape for `exclude_asset`** (current single-item form to widen, lines 136-155 — KEEP the no-`.json` suffix, it is confirmed correct per the APK addendum, not a bug):
```python
def exclude_asset(self, frame_id: str, asset_partial_ids: AssetPartialId | list[AssetPartialId]) -> int:
    """
    Excludes one or more assets from displaying in the frame's slideshow ("hide").
    The asset(s) remain attached to the frame and visible in the app.

    Native Pushd BATCH endpoint (confirmed via APK decompile: service method is
    plural `excludeAssets`) -- mirrors `remove_asset`'s single-or-list normalization.
    NOTE: this endpoint has no `.json` suffix -- confirmed correct as-is (the
    official app posts to `/exclude_asset` with no suffix too), do not "fix" it.
    """
    items = asset_partial_ids if isinstance(asset_partial_ids, list) else [asset_partial_ids]
    json_response = self._client.post(f'/frames/{frame_id}/exclude_asset',
                                      data={'assets': [item.to_request_format() for item in items]})
    if json_response.get('error'):
        raise RuntimeError(f"exclude_asset failed for frame {frame_id}: {json_response.get('error')}")
    number_failed = json_response.get('number_failed')
    if number_failed:
        raise RuntimeError(f"exclude_asset reported {number_failed} failure(s) for frame {frame_id}")
    return number_failed
```

**Error handling pattern:** identical `error` envelope check + `number_failed` check + `RuntimeError` — used by every write method in this file (`select_asset`, `remove_asset`, `exclude_asset`). Copy verbatim, only the method name in the message strings changes.

**Re-show target:** NOT a new method. Reuse the EXISTING `select_asset` (lines 105-134) exactly as-is — it is already batch, already `.json`-suffixed, already live-verified (Phase 8 upload path). No pattern extraction needed beyond "call it with the re-show candidates' ids."

---

### `auraframes/api/frameApi.py` — `get_assets` filter change

**Analog:** itself (`auraframes/api/frameApi.py:38-58`) — this is a one-line query-param addition, not a new pattern.

**Current pattern** (lines 48-49):
```python
json_response = self._client.get(f'/frames/{frame_id}/assets.json',
                                 query_params={'limit': limit, 'cursor': cursor})
```

**Target change** — add `filter='all'` so hidden (`selected=false`) assets are returned too (per APK: `FilterParam` enum `{all, selected, unselected}`; server defaults to `filter=selected` when omitted, which is why hidden assets vanish from today's response):
```python
json_response = self._client.get(f'/frames/{frame_id}/assets.json',
                                 query_params={'limit': limit, 'cursor': cursor, 'filter': 'all'})
```
No change to the `Asset` model (`selected: bool` already exists at `auraframes/models/asset.py:89`) and no change to `get_assets`'s return signature (`tuple[list[Asset], str]`, line 38) — `compute_plan` classifies on `asset.selected` directly.

**Error handling** (lines 50-56, unchanged, already present):
```python
if json_response.get('error'):
    raise RuntimeError(
        f"get_assets failed for frame {frame_id}: "
        f"{json_response.get('message') or json_response.get('error')}"
    )
```

---

### `auraframes/sync.py` — `SyncPlan` + `compute_plan` (4-way classification)

**Analog:** itself — the existing 3-way classification (`auraframes/sync.py:203-252`).

**Current dataclass** (lines 203-209):
```python
@dataclass
class SyncPlan:
    to_upload: list[Path] = field(default_factory=list)
    to_delete: list = field(default_factory=list)
    unchanged: int = 0
    skipped_non_image: int = 0
    frame_no_hash: int = 0
```

**Extension pattern** — add `to_reshow: list = field(default_factory=list)` and `already_hidden: int = 0` fields (rename `to_delete`→`to_remove` per RESEARCH's naming, or keep `to_delete` and document its 3-tier meaning — planner's call per D-07 wording, but the dataclass shape itself follows this exact `field(default_factory=list)` / plain `int = 0` counter convention already used for every other field here).

**Core classification pattern to extend** (lines 228-244 — the loop-with-demand-dict shape; the 4-way split is a per-asset branch on `asset.selected` ADDED to the existing branch on `asset.md5_hash`, not a new loop):
```python
demand = {h: 1 for h in local_hashes}
to_delete: list = []
unchanged = 0
frame_no_hash = 0

for asset in frame_assets:
    if not asset.md5_hash:
        frame_no_hash += 1
        continue

    if demand.get(asset.md5_hash, 0) > 0:
        demand[asset.md5_hash] -= 1
        unchanged += 1
    else:
        to_delete.append(asset)

to_upload = [local_hashes[h][0] for h, remaining in demand.items() if remaining > 0]
```
Target shape: within the `demand.get(...) > 0` branch, additionally check `asset.selected` — `present-local + hidden (selected=False)` → `to_reshow`; `present-local + visible` → `unchanged` (today's branch, unchanged). Within the `else` (surplus) branch, check `asset.selected` — `gone-local + visible` → `to_delete`/`to_remove` (today's branch, unchanged); `gone-local + already hidden` → `already_hidden` counter, NOT appended to any removal list (no-op, per D-06).

**Docstring convention** (lines 212-227) — this module's docstrings cite the specific Decision ID driving each behavior (`D-05`, `D-06` etc.) inline; new docstring additions should cite the Phase 10 decision IDs (D-05/D-06) the same way.

**Purity constraint (critical, from Anti-Patterns in RESEARCH.md):** `compute_plan` must stay mode-agnostic — it classifies only on `asset.selected` + hash presence, never branches on `removal_mode`. Mode selection belongs entirely in `execute_plan`/CLI (mirrors this file's own module docstring at lines 1-36 describing the pure/mutating split).

---

### `auraframes/sync.py` — `execute_plan` (removal_mode param + re-show loop)

**Analog:** itself — the existing delete chunk loop (`auraframes/sync.py:561-589`), to be mirrored twice: once as an always-runs re-show loop, once as a mode-selected removal loop.

**Core pattern to copy** (the exact chunk/throttle/budget/failure-tracking shape, lines 561-589):
```python
for chunk in _chunked(plan.to_delete, batch_size):
    interchunk_pause()
    if budget is not None:
        budget.acquire(1, wait=wait_on_budget, max_wait=max_wait_seconds,
                        now=clock(), sleep=sleep, on_wait=on_wait)
    try:
        throttle()
        aura.frame_api.remove_asset(frame_id, [AssetPartialId(id=asset.id) for asset in chunk])
        for asset in chunk:
            result.delete_succeeded += 1
            consecutive_failures = 0
            progress('delete', asset.id, True)
    except RateLimitError:
        if budget is not None:
            budget.reconcile_tripped(clock())
            budget.save()
        raise
    except Exception as e:
        for asset in chunk:
            result.delete_failures.append((asset.id, str(e)))
            progress('delete', asset.id, False)
            note_failure(str(e))

    if budget is not None:
        budget.save()
```

**Re-show loop** — identical shape, calling `aura.frame_api.select_asset(frame_id, [AssetPartialId(id=asset.id) for asset in chunk])` instead of `remove_asset`, iterating `plan.to_reshow`, always runs (independent of `removal_mode`), and uses new `result.reshow_succeeded`/`result.reshow_failures` fields on `ExecutionResult` (same dataclass-field convention as `upload_succeeded`/`delete_succeeded` at lines 256-260) and `progress('reshow', asset.id, ok)`.

**Removal loop (mode-selected)** — same shape, but the primitive called is selected by `removal_mode`:
```python
_REMOVAL_PRIMITIVE = {
    'hide': lambda aura, frame_id, ids: aura.frame_api.exclude_asset(frame_id, ids),
    'delete': lambda aura, frame_id, ids: aura.frame_api.remove_asset(frame_id, ids),
    'hard_delete': lambda aura, frame_id, ids: [aura.asset_api.delete_asset(a) for a in ids],
}
```
**Budget accounting caveat (Pitfall 3):** `hard_delete` is NOT frame-batch-shaped (`AssetApi.delete_asset` is `/assets/{id}.json`, one call per asset) — `budget.acquire(len(chunk), ...)` for that mode, vs `budget.acquire(1, ...)` for `hide`/`delete` (mirrors the existing `budget.acquire(1, ...)` at line 565 for the single-call-per-chunk `remove_asset` case, and `budget.acquire(2, ...)` at line 489 for the two-call upload chunk — the acquire-count-matches-actual-HTTP-calls convention already established in this function).

**ExecutionResult dataclass extension** (analog: lines 255-260):
```python
@dataclass
class ExecutionResult:
    upload_succeeded: int = 0
    delete_succeeded: int = 0
    upload_failures: list = field(default_factory=list)
    delete_failures: list = field(default_factory=list)
    # NEW, same convention:
    reshow_succeeded: int = 0
    reshow_failures: list = field(default_factory=list)
```

**Docstring/param convention** (lines 304-424) — every `execute_plan` parameter is documented with a `:param:` block explaining WHY it exists and what decision it encodes; the new `removal_mode: str = 'hide'` parameter should follow this exact style, citing D-01/D-03.

**Ordering constraint (D-09 precedent, line 15/329):** uploads precede removals today ("Uploads are attempted before any delete"); the planner must decide re-show's position in that ordering (RESEARCH.md's diagram places it between uploads and removal — reasonable, since re-show is non-destructive and should happen before anything is hidden/removed in the same run).

---

### `auraframes/cli.py` — `sync` subparser + `run_sync` (flags, verb wording, escalated gate)

**Analog:** itself — the existing `--apply`/`--yes`/`no_delete` flag-and-print pattern (lines 65-68, 374-431).

**Subparser pattern to extend** (lines 64-68):
```python
sync_parser = subparsers.add_parser('sync', help='Dry-run diff a local directory against a frame')
sync_parser.add_argument('dir', help='Local directory to scan for photos')
sync_parser.add_argument('--frame', required=True, help='Frame name (substring) or id')
sync_parser.add_argument('--apply', action='store_true', default=False, help='Execute the plan (upload + delete) instead of only printing it')
sync_parser.add_argument('--yes', action='store_true', default=False, help='Skip the confirmation prompt (required for --apply when running non-interactively)')
```
Add, same `action='store_true', default=False` shape:
```python
sync_parser.add_argument('--delete', action='store_true', default=False, help='Actually remove gone-local photos from the frame instead of hiding them')
sync_parser.add_argument('--hard-delete', action='store_true', default=False, dest='hard_delete', help='Irreversibly destroy gone-local photos (asset-scoped delete) instead of hiding them')
```

**Plan-print pattern to extend** (lines 391-412 — the "print a count line, then an itemized list" convention repeated for every plan bucket):
```python
print(f'To upload: {len(plan.to_upload)}')
if no_delete:
    print('To delete: 0 (additive mode — existing frame photos left untouched)')
else:
    print(f'To delete: {len(plan.to_delete)}')
print(f'Unchanged: {plan.unchanged}')
for path in sorted(plan.to_upload):
    print(f'  + {path}')
for asset in plan.to_delete:
    print(f'  - {asset.id} (taken {asset.taken_at_dt})')
```
Extend with mode-aware verb (D-07) and a `To re-show: N` line (D-08), following this exact print-count-then-list shape.

**Confirmation gate pattern to extend** (lines 417-431 — the existing single fail-closed + single y/N gate):
```python
if not yes and not sys.stdin.isatty():
    print('--apply requires --yes when running non-interactively')
    return 1

if not yes:
    answer = input(f'About to apply this plan to "{frame.name}" (id: {frame.id}). Proceed? [y/N] ')
    if answer.strip().lower() not in ('y', 'yes'):
        print('Aborted.')
        return 0
```
**Escalation target (RESEARCH.md's CLI Integration Pattern, D-06/Pitfall 5 in CONTEXT.md/RESEARCH.md):** add a distinct, stronger gate specifically for `hard_delete` mode BEFORE the existing gate (or replacing it for that mode) — e.g. requiring the exact removal count to be re-typed, not just a differently-worded y/N. Keep `--yes` skipping ALL gates in every mode (existing contract, do not break it) and keep the single-gate-covers-the-whole-plan model (still one confirmation moment per run, escalated in wording/strength only).

**Summary-print pattern to extend** (lines 501-509 — same "print counts, then each failure named" shape as the plan section above):
```python
print(f'Uploads: {result.upload_succeeded} succeeded, {len(result.upload_failures)} failed')
for path, err in result.upload_failures:
    print(f'  ! {path}: {err}')
print(f'Deletes: {result.delete_succeeded} succeeded, {len(result.delete_failures)} failed')
for asset_id, err in result.delete_failures:
    print(f'  ! {asset_id}: {err}')
return 1 if (result.upload_failures or result.delete_failures) else 0
```
Extend with a `Re-shown: N succeeded, M failed` block (same shape) and mode-aware verb (`Hidden`/`Removed`/`Hard-deleted`) for the removal block; extend the final `return 1 if (...)` condition to also check `result.reshow_failures`.

**`no_delete`-as-precedent note:** the existing `no_delete: bool = False` parameter on `run_sync` (line 300, applied at lines 382-383) is the closest prior-art "mode toggle applied before the plan is printed" pattern — the new `removal_mode` derivation (`'hard_delete' if args.hard_delete else ('delete' if args.delete else 'hide')`) should be computed and applied at the same point in the function, before the plan print block, exactly like `no_delete`/`limit` are today (lines 374-385).

---

## Shared Patterns

### Batch write-call shape (applies to `exclude_asset` widening, and both new chunk loops in `execute_plan`)
**Source:** `auraframes/api/frameApi.py:157-186` (`remove_asset`) and `auraframes/sync.py:561-589` (delete chunk loop)
**Apply to:** `exclude_asset` widening, re-show loop, mode-selected removal loop
```python
items = asset_partial_ids if isinstance(asset_partial_ids, list) else [asset_partial_ids]
json_response = self._client.post(f'/frames/{frame_id}/<endpoint>',
                                  data={'assets': [item.to_request_format() for item in items]})
if json_response.get('error'):
    raise RuntimeError(f"<method> failed for frame {frame_id}: {json_response.get('error')}")
number_failed = json_response.get('number_failed')
if number_failed:
    raise RuntimeError(f"<method> reported {number_failed} failure(s) for frame {frame_id}")
return number_failed
```

### Chunk/throttle/budget/consecutive-failure scaffolding
**Source:** `auraframes/sync.py:436-479` (`throttle()`, `note_failure()`, `interchunk_pause()` closures) and the delete loop at lines 561-589
**Apply to:** the new re-show loop and the mode-selected removal loop — both MUST reuse these closures verbatim (they are already defined once per `execute_plan` call and closed over by every loop in the function), never duplicate a parallel simpler loop that skips budget/throttle/failure-counting (explicit Anti-Pattern in RESEARCH.md).

### Fail-loud `RuntimeError` on `error` envelope / nonzero `number_failed`
**Source:** every write method in `auraframes/api/frameApi.py` and `auraframes/api/assetApi.py`
**Apply to:** the widened `exclude_asset` — no new error-handling shape needed, copy verbatim.

### Injected-fake test convention
**Source:** `tests/test_sync_engine.py:13` and `tests/test_execute_plan.py:47` — `Asset.model_construct(id=id_, md5_hash=..., taken_at=...)` builds a minimal fake `Asset` bypassing full field validation (Pydantic's fast constructor path), used throughout both test files instead of a full valid `Asset(**{...66 fields...})`.
**Apply to:** all new offline tests (`compute_plan`'s 4-way classification, `execute_plan`'s re-show/hide/hard-delete branches) — extend the same `model_construct(id=..., md5_hash=..., taken_at=..., selected=...)` call with the new `selected` kwarg needed for hidden/visible classification, rather than constructing a fully valid `Asset`.

## No Analog Found

None — every file this phase touches already contains an in-file structural sibling (a same-shape existing method/loop/branch) that the new code mirrors. This phase is explicitly a "small, same-shape sibling" extension per RESEARCH.md's own framing ("Every write primitive this phase needs... is a small, same-shape sibling of a primitive that already exists").

## Metadata

**Analog search scope:** `auraframes/api/frameApi.py`, `auraframes/api/assetApi.py`, `auraframes/models/asset.py`, `auraframes/sync.py`, `auraframes/cli.py`, `tests/test_sync_engine.py`, `tests/test_execute_plan.py`
**Files scanned:** 7 (all read in full or targeted-range; all ≤ 2500 lines, no grep-then-offset needed)
**Pattern extraction date:** 2026-07-10
</content>
