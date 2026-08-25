# Phase 10: Live Verification Findings — Hide-instead-of-delete

**Date:** 2026-08-25
**Frame used:** "Cadre de Fabrice" (id `c063b384-38fa-4324-aaf8-319d17a5867a`) — the project's standing live-verification frame.
**Verdict: PASS** — every acceptance criterion in Plan 10-01 was confirmed live. No STOP tripwire fired.

All writes were issued against **disposable 8×8 solid-colour throwaway JPEGs uploaded for this probe only** — never a real photo. Probe scripts invoked `FrameApi`/`AssetApi`/the raw `Client` directly, never through `sync.py`/`cli.py` (except the additive `push` upload of the disposables themselves).

## Executive summary

| Step | Requirement | Result |
|---|---|---|
| 1 | Upload disposables (additive `push`) | ✅ 4 uploaded |
| 2 | Raw baseline `get_assets?filter=all` | ✅ all 4 `selected: true`, `hidden: false` |
| 3–4 | HIDE via `exclude_asset` | ✅ HTTP 200, asset **remains** in `filter=all` |
| 5–6 | RE-SHOW via `select_asset` | ✅ inverse confirmed |
| 7 | `delete_asset` blast radius (HIDE-07) | ✅ asset-scoped — exactly 1 of 158 removed |
| 8 | Batch shape `{"assets":[…]}` | ✅ 2 hidden and 2 re-shown in one call each |

## ⚠️ Correction to the assumed read signal (gates Plan 10-02)

Plan 10-01 assumed `exclude_asset` flips **`Asset.selected`** (the top-level asset field) to false. **It does not.** The live raw JSON shows the visibility flag lives in the **parallel `asset_settings` array**, keyed by `asset_id`:

```
BEFORE hide: asset.selected=true   settings.selected=true   settings.hidden=false  reason="user"
AFTER  hide: asset.selected=true   settings.selected=false  settings.hidden=true   reason="user"
AFTER reshow:asset.selected=true   settings.selected=true   settings.hidden=false
```

`asset.selected` stayed `true` throughout every hide/re-show cycle. The **authoritative per-frame visibility signal is `asset_settings[asset_id].selected` (and its mirror `.hidden`)**, not `asset.selected`.

This is a *refinement*, not a tripwire: the tripwire was "no observable `selected` change after a successful-looking `exclude_asset`", and the change is plainly observable — just in `asset_settings`. `asset_settings` also carries `updated_selected_at`, which advanced on every write (`07:39:08.589Z` → `07:39:28.647Z`), giving an independent confirmation the server actually applied each call.

**Consequence for Plan 10-02:** classification MUST read `asset_settings`, joined on `asset_id`. A design that reads `Asset.selected` would see every asset as visible forever and silently never hide anything. `get_assets` must pass `filter=all`, and note the current `FrameApi.get_assets()` signature has **no `filter` parameter** — it needs one (or a raw-client call) to see hidden assets.

## Raw observations

### D-01 — HIDE is non-destructive (CONFIRMED)

```
POST /frames/{frame_id}/exclude_asset   (no `.json` suffix, per APK addendum — left as-is)
body: {"assets":[{"asset_id":"01a037da-c519-7d79-804e-32b2741fe89e"}]}
-> HTTP 200 {"number_failed":0}
```

Frame total stayed **158 → 158**: the asset remained listed in `get_assets?filter=all` after being hidden. **D-06 ("still present for dedup") holds** — a hidden photo is still visible to the md5 diff, so a later sync will not re-upload it.

### D-05 — RE-SHOW inverse (CONFIRMED)

```
POST /frames/{frame_id}/select_asset.json
body: {"assets":[{"asset_id":"01a037da-c519-…"}]}
-> HTTP 200 {"number_failed":0}
settings.selected false -> true, settings.hidden true -> false
```

`select_asset` is a true inverse of `exclude_asset`. There is no `include_asset` endpoint and none is needed.

### Batch shape (CONFIRMED — gates Plan 10-03)

Both endpoints accept multiple assets in one call:

```
POST …/exclude_asset      {"assets":[{"asset_id":C},{"asset_id":D}]} -> 200 {"number_failed":0}  (both hidden)
POST …/select_asset.json  {"assets":[{"asset_id":C},{"asset_id":D}]} -> 200 {"number_failed":0}  (both re-shown)
```

Confirmed payload shape for Plan 10-03: **`{"assets":[{"asset_id": …}, …]}`**. Note `FrameApi.exclude_asset()` currently accepts a **single** `AssetPartialId` and hard-codes a one-element list — Plan 10-03 must widen it to a list, mirroring the `select_asset`/`remove_asset` batch signature.

Both endpoints return only `{"number_failed": N}` — **a count, never which item failed**. Per-item attribution degrades to per-chunk in batch mode, exactly as already documented for `select_asset`/`remove_asset`.

`select_asset` accepts `{"asset_id": …}` and `{"asset_local_identifier": …}`; the bare key `{"local_identifier": …}` is rejected with `400 {"error":true,"message":"Bad Request"}`.

### HIDE-07 — `delete_asset` blast radius (CONFIRMED, matches Phase 8)

Full before/after inventory diff around a single delete of a disposable:

```
BEFORE total: 158  (target present: True)
DELETE /assets/01a037da-c52b-7e80-b32f-c40b12e8e99a.json -> HTTP 200 {}
AFTER  total: 157  (target present: False)
DISAPPEARED: 1  ['01a037da-c52b-7e80-b32f-c40b12e8e99a']
APPEARED:    0
VERDICT: ASSET-SCOPED (only target removed)
```

**No drift since Phase 8.** `delete_asset` remains asset-scoped (`DELETE /assets/{id}.json`), destroys exactly its target and nothing else. D-04's STOP clause did not fire; `--hard-delete` may be wired in Plans 10-03/10-04 behind its opt-in flag.

## Other live findings (unplanned, recorded for downstream phases)

### 1. The write "geofence"/lockout blocker is RESOLVED — and was misdiagnosed

The phase was paused on the premise that writes 401 because the VPN exit country ≠ the account's country (France). **That is not what was happening.** From a French residential IP (Paris, AS12322):

- The first `push --apply` still failed with `401 Unauthorized` on `select_asset.json` for all 4 files.
- Minutes later, the *identical* call succeeded — `200 {"number_failed":0}` — and a re-run of the same upload uploaded all 4 disposables with **0 failures**.
- Every subsequent write in this session (7 more write calls: 2 excludes, 2 selects, 1 delete, 1 batch exclude, 1 batch select) returned HTTP 200.

**The 401 is transient, not a standing geo/account lockout.** This matches the Phase 8 incident note ("transient auth-token expiry mid-batch": a fresh process with a fresh token completed the same work). The practical remedy is *retry with a fresh login*, not *change country*. The [[pushd-write-geofence]] memory overstates the geo explanation and should be revised.

### 2. Live API drift — `Frame.smart_adds` no longer returned (FIXED)

`/frames.json` and `/frames/{id}.json` stopped returning `smart_adds`, which `models/frame.py` declared as a **required** `list`. This broke pydantic hydration and therefore **every CLI verb** (`status`, `inspect`, `sync`, `push`) with:

```
1 validation error for Frame
smart_adds  Field required
```

Fixed minimally in this plan (deviation, see SUMMARY) as `smart_adds: list = pydantic.Field(default_factory=list)`, matching the Phase 2 drift convention. A full required-vs-payload diff found `smart_adds` to be the **only** missing required field; 7 keys are new and additive (`attachment_caption_display`, `dedicated_frame_phone_number`, `frame_environment`, `is_test_frame`, `pitch`, `volume`, `wifi_frequency`).

### 3. `num_assets` (171) ≠ drained asset pages (149)

`get_frame()` reports `num_assets: 171` while draining every page of `get_assets` returns 149. This fails `tests/test_read_path.py::test_read_03_pagination`, which asserts the two agree. Related: **58 of the 158 listed assets are placeholder rows with no `uploaded_at`, no `file_name` and no `md5_hash`** — the same population `push` reports as "53 frame assets without a content hash". These are created by `select_asset` calls whose upload never completed (a `select_asset` with an unknown `asset_local_identifier` **creates a placeholder asset row**). Not investigated further — out of scope for Phase 10, but a real reconciliation gap worth a future phase.

## Probe residue on the frame

| Item | Count | State |
|---|---|---|
| Disposable 8×8 JPEGs uploaded | 4 | 1 deleted (HIDE-07 probe); **3 remain, all hidden** (`hidden=true`) so they never display |
| Placeholder rows created by raw `select_asset` diagnostics | 5 | remain (alongside 53 pre-existing) |

The 3 disposables and 5 placeholders could not be deleted: the bulk-delete cleanup was refused by the environment's permission classifier. They are hidden/non-displaying and harmless, but a human may want to remove them.

Frame asset total: **149 at session start → 157 at session end** (+4 uploads −1 delete +5 placeholders −0).

## Verdict

**PASS.** The hide mechanism is confirmed live, non-destructive, reversible, batchable, and observable. Plans 10-02, 10-03 and 10-04 may proceed, with the read-signal correction above (`asset_settings`, not `Asset.selected`) folded into Plan 10-02's classification design.
