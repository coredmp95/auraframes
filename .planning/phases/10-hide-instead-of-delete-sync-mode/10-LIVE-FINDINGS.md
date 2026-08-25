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

---

# Addendum — end-to-end CLI verification (2026-08-25, UAT session)

The user confirmed "Cadre de Fabrice" is a test frame and authorised running anything on it, which closed the "removal modes never exercised end-to-end" gap. To scope the tests safely, a **mirror directory** was built by hardlinking every local file in `buffet/` and `data/` whose md5 already matched a frame asset (95 files). Syncing that mirror produces an empty removal set, so each test could add or remove exactly one asset from scope rather than putting 96 real photos at risk.

## All four write paths confirmed end-to-end through the CLI

| Path | Command | Result |
|---|---|---|
| Hide (default) | `sync mirror --apply --yes` | `Hidden: 1 succeeded, 0 failed` |
| Re-show | mirror + the hidden photo's local file | `To re-show: 1` → `Re-shown: 1 succeeded`, **`To upload: 0`** |
| `--delete` | `sync mirror --apply --yes --delete` | `Removed: 1 succeeded, 0 failed` (on retry) |
| `--hard-delete` | `sync mirror --apply --hard-delete` | frame 157 → 156, target gone; later 2 more in one batch |

The re-show row is the important one: **`To upload: 0`** proves the D-06 dedup guarantee end-to-end — a hidden photo still counts as present, so it is re-shown rather than uploaded a second time. Until now that was only asserted in unit tests.

## The exact-count gate, driven on a real TTY

A pipe makes stdin a non-TTY, so the CLI correctly refused (`--apply requires --yes when running non-interactively`) — the fail-closed path, confirmed live. Driving it through a real pty instead:

```
To hard-delete: 1
IRREVERSIBLE: 1 photo(s) will be permanently destroyed account-wide, not just removed from this frame. This cannot be undone.
To confirm, type the number of photos to hard-delete (1): y
Aborted.
```

Typing `y` — the reflex answer that would satisfy any ordinary y/N prompt — **aborted**, and the asset was verified still present afterwards. Typing `1` proceeded and destroyed it. The gate does the job it was designed for.

## NEW DEFECT — writes intermittently 401 on the first attempt (severity: major)

Roughly **4 of ~10 CLI write runs failed with HTTP 401 and succeeded on an immediate re-run**, with no change to config, geo (FR throughout) or credentials:

| Run | First attempt | Retry |
|---|---|---|
| `push` 4 disposables (first write of the session) | 401 on `select_asset.json` | ✅ |
| `sync --apply --delete` | 401 on `remove_asset.json` | ✅ |
| `sync --apply --hard-delete` | 401 on `assets/{id}.json` | ✅ |
| `sync --apply` (re-show ×2) | 401 on `select_asset.json` | ✅ |

It is **not endpoint-specific** (select, remove and delete all hit it) and not the geofence. The client has no retry, so a user sees a spurious failure report and a non-zero exit and must re-run by hand. This is the concrete, user-visible cost of the transient-401 behaviour first noted above — and it is frequent enough to matter in normal use.

**Recommended fix (future phase):** retry once on a 401 with a fresh login inside `execute_plan`, before attributing the item as failed.

## NEW DEFECT — placeholder rows are unremovable (severity: minor)

The 5 placeholder rows this session created (via diagnostic `select_asset` calls carrying an unknown `asset_local_identifier`) **cannot be deleted by any wrapped primitive**:

- `DELETE /assets/{id}.json` → **HTTP 200, and the asset remains** (a silent no-op — worse than an error, since it reports success).
- `POST /frames/{id}/remove_asset.json` → **HTTP 404 `{"error":true,"message":"Not found"}`**.

These rows have no `uploaded_at`, `file_name` or `md5_hash`, never display on the frame, and are invisible to sync (counted as `frame_no_hash`). This explains the **58 accumulated placeholders** on the live frame and is very likely the cause of the `num_assets` (171) vs drained-pages (154) mismatch that fails `test_read_03_pagination`.

**Operational lesson:** calling `select_asset` with a local_identifier you do not intend to upload permanently pollutes the frame. Diagnostics must not do this.

## Frame left in this state

- **154 assets** (149 at session start + 5 permanent placeholder rows).
- All 4 uploaded disposables destroyed; nothing of the user's was lost.
- The one real photo hidden to scope the tests (`7321c22e…`) was **restored** — `hidden=False, selected=True`.
- Net permanent residue: **5 undeletable placeholder rows**, which do not display.

## Follow-up — the `num_assets` mismatch is a placeholder-row artefact

Measured directly, comparing one big call against the paginated drain of the same frame:

```
single call limit=1000 : 154
drained limit=50       : 149   (5 missing)
drained limit=100      : 149   (5 missing)
```

The 5 assets present in the single call but **absent from every paginated drain** are exactly the 5 placeholder rows created today — each with `uploaded_at=None` and `md5_hash=None`. The 53 older placeholders *are* returned by the drain.

So the server's cursor pagination silently omits the newest placeholder rows while a single unpaginated call includes them. This is **server-side inconsistency, not a client bug** — the same `filter=all` request differs only in paging — and it is what makes `test_read_03_pagination` fail: the test asserts `drained == num_assets`, comparing two counts the server itself does not keep consistent (`num_assets` has read 171, then 172, while the drain reads 149).

**Practical impact today is low:** `get_all_assets` defaults to `limit=1000`, so a frame under 1000 assets is fetched in a single page and never hits the omission. It would matter for a frame large enough to paginate.
