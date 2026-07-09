# Phase 10: Hide-instead-of-delete sync mode - Research

**Researched:** 2026-07-09
**Domain:** Reverse-engineered Aura/Pushd cloud API — per-asset visibility ("hide from slideshow, keep on frame") write/read mechanism, threaded into the existing `compute_plan`/`execute_plan` sync engine
**Confidence:** MEDIUM — every code-level claim below is a direct read of this repository (HIGH); the actual live behavior of `exclude_asset` and its inverse is **completely unverified** (no test, no prior live checkpoint, no public documentation exists) and is the single open question this whole phase depends on. This research narrows the mechanism to a ranked, evidence-backed recommendation and specifies exactly what a live spike must confirm — it does not and cannot resolve the mechanism itself, per CONTEXT.md's own framing.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Hidden end-state (what "hide" means)**
- **D-01:** "Hide" means **off the slideshow, kept on the frame** — no longer displays in rotation, remains attached to the frame and visible in the Aura app's frame view. Matches `FrameApi.exclude_asset`'s docstring, but this is product intent scoping the spike's target, NOT a lock on `exclude_asset` specifically if the live spike finds a different real mechanism (e.g. `AssetSetting.hidden`).

**Removal tiers / flag design**
- **D-02:** The opt-in "actually remove it" flag is named **`--delete`**.
- **D-03:** Three tiers on `sync --apply`: default (no flag) → **hide**; `--delete` → `remove_asset` (today's `--apply` removal behavior); `--hard-delete` → `delete_asset` (broad, irreversible, asset-scoped destroy).
- **D-04:** `--hard-delete → delete_asset` **supersedes Phase 8 D-06** (which left `delete_asset` unreachable from any executable path). Wiring it REQUIRES, before real photos are trusted to it: (a) a stronger/explicit confirmation gate distinct from hide/`--delete`'s gate, and (b) live re-verification of `delete_asset`'s blast radius. If re-verification reveals broader destruction than Phase 8 observed, **STOP and report** before shipping.

**Re-show / diff behavior**
- **D-05:** The local directory is the source of truth for visibility. A hidden frame photo whose file is still present locally is **re-shown** on plain `sync --apply`, regardless of removal mode. Requires a confirmed inverse "show/include" action.
- **D-06:** Hidden frame photos count as **present on the frame** for dedup (never re-uploaded). The diff engine must read each asset's hidden/visibility state to classify: present-local+hidden → re-show; present-local+visible → unchanged; gone-local+visible → hide (default)/delete/hard-delete; gone-local+already-hidden → no-op.

**Plan output & summary wording**
- **D-07:** Verb matches the mode. Dry-run plan and summary label the real action: `To hide: N` / `To delete: N` / `To hard-delete: N` (summary: `Hidden`, `Removed`, `Hard-deleted`).
- **D-08:** Re-show gets its own plan line (`To re-show: N`), never folded silently into "unchanged."

### Claude's Discretion
- **Confirmation gate design** — lean toward escalating friction by destructiveness: hide = normal `Proceed? [y/N]`; `--delete` = same gate, wording notes photos leave the frame; `--hard-delete` = a stronger, explicit gate (distinct warning and/or a count re-type) since it's irreversible. Keep `--yes` skipping the prompt in all modes; keep Phase 8's single-gate-covers-the-whole-plan model.
- **If a safe hide mechanism cannot be confirmed live** — STOP and report; keep today's `remove_asset` behavior until a real, live-confirmed hide/show path exists. Planner may choose a clean alternative only if the spike surfaces one.
- Exact endpoint(s) backing hide/re-show, precise CLI wording, and how visibility state threads through the plan dataclasses — implementation detail for research/planning.

### Deferred Ideas (OUT OF SCOPE)
- Standalone bulk visibility command (`show`/`hide` independent of a directory diff) — re-show here is driven only by the local-directory diff.
- `--hard-delete` as its own focused phase — offered but user chose to include all three tiers now; if live re-verification surfaces broader-than-documented `delete_asset` destruction, splitting `--hard-delete` back out is the fallback.
</user_constraints>

<phase_requirements>
## Phase Requirements

No requirement IDs exist yet for this phase — REQUIREMENTS.md explicitly defers minting to planning (same pattern as Phase 9's `ANTI-*`). Proposed IDs below (planner should adjust numbering/granularity as needed, but the checkpoint-gating dependency order should be preserved):

| Proposed ID | Description | Research Support |
|----|-------------|------------------|
| HIDE-01 | Live spike confirms (or refutes) the hide-write / re-show-write / read-side-visibility-signal mechanism against a disposable test asset; `checkpoint:human-verify`, gates every other HIDE-* task | See "Live-Spike Protocol" below — exact minimal call sequence, STOP tripwires. |
| HIDE-02 | `compute_plan` reads each frame asset's hidden/visible state and produces the 4-way classification (re-show / unchanged / removal-candidate / no-op) | See "Read-Side Visibility Signal" and "Pattern 2" below — exact field/model change and classification logic. |
| HIDE-03 | `execute_plan` gains a `removal_mode` parameter (`hide`/`delete`/`hard_delete`) selecting which single write primitive (`exclude_asset`/`remove_asset`/`delete_asset`) is applied to removal candidates | See "Pattern 3" below — batching, chunking, and budget-acquisition parity with the existing `remove_asset` loop. |
| HIDE-04 | Re-show wired: any hidden frame asset with a still-present local file is un-hidden on plain `--apply`, independent of `removal_mode` | See "Pattern 3" — a new, always-runs chunk loop calling the confirmed inverse primitive. |
| HIDE-05 | CLI gains `--delete`/`--hard-delete` flags on `sync`; dry-run plan and end-of-run summary label the verb per mode (D-07/D-08) | See "CLI Integration" pattern below. |
| HIDE-06 | Confirmation gate escalates by destructiveness; `--hard-delete` requires a distinct, stronger confirmation | See "Common Pitfalls" / Security Domain below. |
| HIDE-07 | `delete_asset`'s blast radius is re-verified live (fresh disposable asset) immediately before `--hard-delete` is wired to a reachable path — supersedes Phase 8 D-06's "no reachable path" constraint | See "Live-Spike Protocol," step 7. |
| HIDE-08 | Offline test coverage for the 4-way classification, 3-tier removal, and re-show execution paths, matching the existing injected-fake conventions | See `tests/test_sync_engine.py` / `tests/test_execute_plan.py` / `tests/test_cli_apply.py` conventions cited below. |

</phase_requirements>

## Summary

Phase 10 does not introduce new libraries, new HTTP client code, or a new architectural layer — it re-arranges an already-fully-mapped write surface (`FrameApi.exclude_asset`/`remove_asset`, `AssetApi.delete_asset`/`batch_update`) behind a mode-selecting flag, and adds exactly one new read requirement: a per-frame-asset hidden/visible signal that `compute_plan` does not have access to today. Every candidate mechanism named in CONTEXT.md was traced to its exact source location in this session:

- **`FrameApi.exclude_asset`** (`auraframes/api/frameApi.py:136-155`) already exists, already carries the exact docstring match for D-01 ("Excludes an asset from displaying in the frame's slideshow. The asset will still show in the app."), and is corroborated (not merely asserted) by the **official Aura Help Center**, which documents an "exclude/include" toggle distinct from "remove," rendering a crossed-eye icon on excluded items [CITED: help.auraframes.com]. It is, however, **single-item only** (no `list[AssetPartialId]` overload, unlike `select_asset`/`remove_asset`) and posts to a path with **no `.json` suffix** — both must be handled by the live spike, not assumed.
- **`AssetSetting.hidden`** (`auraframes/models/asset.py:19-30`) is a real, already-defined pydantic model with exactly the shape a per-(frame, asset, contributor) visibility record would need (`frame_id`, `asset_id`, `added_by_id`, `hidden`, `selected`, `reason`) — but it is **only ever returned by `ActivityApi.get_activity_assets`** (`/activities/{id}/assets.json`), never by `FrameApi.get_assets` (`/frames/{id}/assets.json`, the endpoint `inspect`/`sync` actually call). There is **no existing code path that reads or writes `AssetSetting` for a frame's asset listing** — this is the most load-bearing gap the live spike must close (see "Read-Side Visibility Signal" below).
- **`Asset.selected` / `AssetApi.batch_update`** is a real, already-writable field (`batch_update`'s payload allowlist includes `'selected': True`, and `execute_plan`'s upload path already sets it on every new upload). It is **not a plausible hide mechanism**: `batch_update`'s own docstring states "This does not appear to affect the frame" (`auraframes/api/assetApi.py:12`) — directly contradicting the requirement that hiding change what displays *on the frame*. Demoted to lowest-ranked candidate; documented as a rejected hypothesis, not silently dropped.

**Primary recommendation:** Rank `exclude_asset` (write) + a to-be-added `include_asset` (inverse, currently does not exist in this codebase and must be added) as the primary hide/show mechanism, with the read-side hidden signal most likely surfaced the same way `get_activity_assets` already surfaces it — a parallel `asset_settings` array alongside `assets` in the raw JSON response that `FrameApi.get_assets` currently silently drops (its pydantic `Asset` model has no `hidden` field, and pydantic ignores unknown keys by default). **Do not write a single line of `compute_plan`/`execute_plan` mechanism-specific code before the live spike (HIDE-01) confirms this** — the spike's first step is a raw-JSON read of `/frames/{id}/assets.json` for a disposable asset, before any write, specifically to check whether `asset_settings` (or an inline `hidden` key) is already present in the response today.

## Architectural Responsibility Map

Single-process CLI tool — tiers are this project's own layers (per `.planning/codebase/ARCHITECTURE.md`), not generic browser/API/DB tiers.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Hide default write (D-01, `exclude_asset`) | API Clients (`FrameApi.exclude_asset`, gains batch support) | Sync Engine (`execute_plan`'s new mode branch) | Endpoint already exists; only its single-item shape needs widening, mirroring `remove_asset`'s existing single-or-list normalization. |
| Re-show write (D-05, `include_asset`) | API Clients (**new** `FrameApi.include_asset`, does not exist yet) | Sync Engine (new always-runs chunk loop) | No inverse endpoint exists in this codebase today — this is genuinely new API surface, unlike every other primitive this phase touches. |
| `--delete` tier (`remove_asset`) | API Clients (existing, unchanged) | Sync Engine (mode-selected branch, same call as today) | Zero new code; the existing default behavior becomes one of three selectable tiers. |
| `--hard-delete` tier (`delete_asset`) | API Clients (existing, unchanged) | Sync Engine (**newly reachable** branch) + CLI (stronger confirm gate) | Endpoint and fail-loud wrapper already live-verified once (Phase 8 WRITE-03); this phase's only new work is making it reachable and re-verifying its blast radius hasn't drifted. |
| Read-side visibility signal (D-06) | API Clients (`FrameApi.get_assets` enrichment) | Sync Engine (`compute_plan`'s new classification) | The hidden/visible state must be read at the same layer `get_assets` already lives, then consumed one layer up in the pure diff function. |
| 4-way classification (re-show/unchanged/removal/no-op) | Sync Engine (`compute_plan`, pure function, unchanged shape) | — | Stays a pure, no-I/O function per Phase 7's structural dry-run guarantee — the new dimension (hidden vs visible) is just another input field per asset. |
| Mode-selecting execution (`removal_mode` param) | Sync Engine (`execute_plan`) | API Clients (three interchangeable removal primitives) | `execute_plan` already branches per-chunk on a fixed primitive (`remove_asset`); this phase parameterizes which primitive that chunk loop calls. |
| CLI flags + verb-per-mode output (D-07/D-08) | CLI (`cli.py` `sync` subparser + `run_sync`) | — | Pure UX; no business logic beyond flag parsing and label selection. |
| Confirmation gate escalation | CLI (`run_sync`) | — | Same layer as today's single `Proceed? [y/N]` gate; `--hard-delete` needs a second, stronger prompt at the same call site. |
| Anti-abuse budget/geo coverage for new write types | Sync Engine (`execute_plan`, extending existing `budget.acquire`/`geo_check` calls) | — | Phase 9's guard is already generic per-chunk; new write primitives just need their own `budget.acquire(N, ...)` call sites, no new guard machinery. |

## Live-Spike Protocol — Gates the Whole Phase (HIDE-01)

**This must be the first task of the first plan.** Every other HIDE-* requirement is blocked on its outcome, per CONTEXT.md's Claude's Discretion: *"If a safe hide mechanism cannot be confirmed live... STOP and report... Keep today's `remove_asset` behavior until a real, live-confirmed hide/show path exists."*

Use a **dedicated disposable test asset**, never a real photo — mirror Phase 8 D-05's exact convention (`/tmp/aura-disposable-probe/...`, an 8x8 solid-color throwaway JPEG uploaded via the existing, already-verified `sync --apply --yes` upload path to the project's standing live-verification frame, "Cadre de Fabrice"). All calls below are one-off `uv run python -c "..."` scripts invoking `FrameApi`/`AssetApi` methods directly — **never through `sync.py`/`cli.py`** until the mechanism is confirmed (same isolation Phase 8 used for the `delete_asset` probe).

1. **Upload a fresh disposable asset** (reuse the existing, verified upload round-trip). Capture its `asset.id`.
2. **RAW READ BASELINE (before any write).** Call `aura.frame_api.get_assets(frame_id)` but capture and print the **raw JSON**, not just the parsed `Asset` list — either by adding a temporary `print(json_response)` inside a scratch script that duplicates the request, or by running with `--debug` and reading `Client`'s logged response body. Specifically check:
   - Does the top-level response include a sibling key to `assets`, e.g. `asset_settings` (mirroring `ActivityApi.get_activity_assets`'s exact shape: `{'assets': [...], 'asset_settings': [...]}`)?
   - Does each individual asset object in `assets` already carry an inline `hidden`/`selected`-like key that the current `Asset` pydantic model silently drops (pydantic ignores unrecognized keys by default — this asset's raw dict may already contain more than the 60-odd fields `Asset` declares)?
   - Record the disposable asset's exact raw dict for later diffing. **This step alone answers the phase's #1 open question — do it before any write.**
3. **HIDE.** Call `aura.frame_api.exclude_asset(frame_id, AssetPartialId(id=disposable_asset_id))` directly. Record the raw HTTP status/body/`number_failed`. If the call 404s specifically because of the missing `.json` suffix (`/frames/{id}/exclude_asset`, no `.json` — a genuine quirk in the current code, see Pitfall 1), retry once with `.json` appended before concluding the endpoint itself is wrong.
4. **VERIFY HIDDEN STATE.** Re-fetch raw `get_assets` output. Diff against step 2's baseline for this one asset:
   - Did a `hidden`/`asset_settings[...].hidden` value flip to `true`?
   - Does the asset **still appear** in the `assets` list at all? (It must — D-06 requires hidden assets to still count as "present on the frame" for dedup; if `exclude_asset` makes the asset vanish from `get_assets` entirely, that is a STOP condition, see below.)
   - If an official Aura mobile app is available, visually confirm the photo now shows a crossed-eye icon in the frame's photo list and is absent from the frame's physical slideshow rotation (the actual product-intent confirmation of D-01, independent of the raw JSON diff).
5. **RE-SHOW.** No inverse endpoint exists in this codebase today (`grep -c include_asset auraframes/` returns 0). Attempt, in order:
   a. Add a `FrameApi.include_asset` method mirroring `exclude_asset`'s exact shape (`POST /frames/{frame_id}/include_asset` — try both with and without `.json`), call it against the disposable asset.
   b. If (a) errors/404s, attempt a `batch_update` call carrying whatever field flipped in step 4 (only if step 4 found an inline `Asset`-level field, not a separate `asset_settings` record — `batch_update` operates on `/assets/batch_update.json`, asset-scoped, and its own docstring disclaims frame-level effect, so this is a lower-confidence fallback).
   c. If both fail, treat re-show as **unconfirmed** — this alone is a STOP condition per D-05 (re-show is a locked decision, not optional).
6. **VERIFY RE-SHOW.** Re-fetch raw `get_assets` a third time; confirm the field reverts to its step-2 baseline value, and (if the app is available) visually confirm the crossed-eye icon is gone.
7. **RE-VERIFY `delete_asset` BLAST RADIUS (D-04(b), HIDE-07).** On a **second, separate** fresh disposable asset (do not reuse the hide/show asset — keep the destructive probe's blast-radius signal uncontaminated by the visibility probe), repeat Phase 8's exact `delete_asset` probe (`AssetApi.delete_asset` called directly, never through `sync.py`). Confirm the observed behavior still matches Phase 8's finding (`DELETE /assets/{id}.json`, asset-scoped, not frame-scoped) — the API is undocumented and has already drifted once before (Phase 2's `total_asset_count` → `frame.num_assets` move, noted in `FrameApi.get_frame`'s own comment), so re-confirming rather than assuming Phase 8's finding still holds is warranted before trusting it on real photos.
8. **BATCH SHAPE CHECK.** Using two fresh disposable assets, call whatever hide/show primitives step 3-6 confirmed with **both** asset ids in a single `{"assets": [...]}` payload (mirroring `select_asset`/`remove_asset`'s existing batch pattern). Confirm both hide and both re-show; record whether `number_failed` is the only per-call signal (as with `remove_asset`) or something finer-grained.

### STOP-and-report tripwires

Any of the following means: **do not ship a hide default this phase.** Keep `remove_asset` as `sync --apply`'s sole removal behavior (today's status quo), document the finding, and report back per Claude's Discretion:

- `exclude_asset` (with or without the `.json` suffix retry) returns an `error` envelope, a non-2xx status, or a nonzero `number_failed` against the disposable asset.
- `exclude_asset` succeeds but the asset **disappears from `get_assets`'s response entirely** rather than remaining listed with a flipped visibility field — this breaks D-06's "still counts as present on the frame" requirement outright.
- No raw JSON field change is observable anywhere in the response after a successful-looking `exclude_asset` call — hidden and visible states would be indistinguishable on read, and `compute_plan` cannot classify what it cannot see.
- No inverse (`include_asset` or any working fallback) can be found within the probe attempts in step 5 — D-05 is a locked decision requiring re-show to exist, not optional.
- Step 7's `delete_asset` re-verification shows broader-than-Phase-8 destruction (e.g. now touches other frames/assets, or something clearly irreversible beyond the single targeted asset) — per D-04's explicit STOP clause.

If batch support (step 8) fails but single-item hide/show/re-show (steps 3-6) succeed, this is **not** a STOP condition — document it as a scope/perf tradeoff (see Pitfall 4) and ship single-item calls per removal candidate, since correctness matters more than call-count optimization for a first cut, though this reintroduces some of the per-call anti-abuse risk Phase 9's batching was built to avoid and should be flagged prominently for the planner to weigh.

## Standard Stack

**No new libraries this phase.** Every primitive is either already implemented (`exclude_asset`, `remove_asset`, `delete_asset`, `batch_update`) or a small, same-shape addition to an existing class (`include_asset` on `FrameApi`, mirroring `exclude_asset`; batch-list support on `exclude_asset`/`include_asset`, mirroring `remove_asset`'s existing `AssetPartialId | list[AssetPartialId]` pattern).

| Component | Status | Notes |
|-----------|--------|-------|
| `pydantic` 2.13 (installed) | Unchanged | No new models required if the hidden signal turns out to be a field addition to `Asset`/a small wrapper dataclass (see Pattern 2); `AssetSetting` (already defined) may be reused as-is if the read signal is a parallel array. |
| `FrameApi.exclude_asset` | Needs widening | Single-item → single-or-list, mirroring `remove_asset`'s existing normalization (`items = x if isinstance(x, list) else [x]`). |
| `FrameApi.include_asset` | **New method, does not exist** | Mirror `exclude_asset`'s exact shape once the live spike confirms its path/payload. |
| `AssetApi.delete_asset` | Unchanged | Already fail-loud (Phase 8 WRITE-05); only needs a new reachable call site. |

**Installation:** None — `uv add` is not needed this phase.

**Version verification:** Not applicable (no new packages).

## Package Legitimacy Audit

**No new packages are introduced by this phase.** Every write primitive needed is already implemented in this codebase or a same-shape extension of an existing class. The Package Legitimacy Gate protocol does not apply — no registry check needed.

| Package | Registry | Disposition |
|---------|----------|-------------|
| (none) | — | No installs this phase |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
              aura-cli sync <dir> --frame <x> --apply [--yes] [--delete | --hard-delete]
                                      │
                       (CLI: cli.py, existing dry-run reused)
                                      ▼
     ┌──────────────────────────────────────────────────────────────────┐
     │ 1. login()  2. resolve_frame()  3. scan_directory                │
     │ 4. get_all_assets() -- NOW also carries each asset's hidden state│
     │ 5. compute_plan(local_hashes, frame_assets)                      │
     │      --> SyncPlan(to_upload, to_reshow[NEW], to_remove[renamed], │
     │                    unchanged, already_hidden[NEW counter])       │
     └──────────────────────────────┬───────────────────────────────---┘
                                     │ print counts + full lists, verb per mode (D-07/D-08)
                                     ▼
                     ┌─────────────────────────────────────┐
                     │ --apply gate (existing, D-01..D-04)  │
                     │  mode-aware wording; --hard-delete    │
                     │  gets a DISTINCT stronger gate (NEW)  │
                     └────────────────┬──────────────────---┘
                                      │ confirmed
                                      ▼
                ┌──────────────────────────────────────────────────┐
                │ execute_plan(plan, aura, frame_id,                │
                │              removal_mode='hide'|'delete'|'hard') │  <- sync.py, extended
                └───────────────────┬────────────────────────────--┘
                                    │
       ┌────────────────────────────┼─────────────────────────────────┐
       │  UPLOADS (unchanged)       │  RE-SHOW (NEW, always runs,      │
       │                            │  independent of removal_mode)    │
       ▼                            ▼
  existing upload loop     for chunk in to_reshow:
  (select_asset/S3/         include_asset(frame_id, [AssetPartialId(id=a.id) ...])  <- NEW primitive
   batch_update)                                        │
                                                          ▼
                              ┌───────────────────────────────────────────┐
                              │ REMOVAL (mode-selected, exactly one runs) │
                              │  hide       -> exclude_asset(...)  [NEW batch support]
                              │  delete     -> remove_asset(...)   [unchanged, today's default]
                              │  hard_delete-> delete_asset(...)   [existing primitive, NEWLY reachable]
                              └───────────────────────────────────────────┘
                                    │
                                    ▼
                   Print separated summary (verb per mode, D-07/D-08):
                     Uploads: N succeeded, M failed
                     Re-shown: N succeeded, M failed
                     Hidden|Removed|Hard-deleted: N succeeded, M failed
                   exit 1 if any failure

   (SEPARATE, one-time checkpoint -- HIDE-01, gates everything above)
   ┌─────────────────────────────────────────────────────────┐
   │ checkpoint:human-verify -- hide/show/hard-delete spike    │
   │ disposable asset -> raw-JSON baseline -> exclude_asset ->  │
   │ raw-JSON diff -> include_asset -> raw-JSON diff -> re-probe │
   │ delete_asset blast radius -> document; STOP if tripwire hit │
   │ NOT reachable from execute_plan()/--apply until confirmed  │
   └─────────────────────────────────────────────────────────┘
```

### Recommended Project Structure

No new files — extend existing modules exactly as Phase 8/9 did:

```
auraframes/
├── api/frameApi.py    # exclude_asset gains batch support (mirror remove_asset);
│                       #   NEW include_asset method, same shape as exclude_asset
├── models/asset.py     # EITHER: Asset gains `hidden: Optional[bool] = None`
│                       #   OR: a small FrameAsset(asset, hidden) wrapper is introduced
│                       #   in sync.py/aura.py -- decided by the live spike (see Pattern 2)
├── aura.py             # get_all_assets (or a new sibling) merges/attaches the hidden
│                       #   signal onto each returned asset before handing it to compute_plan
├── sync.py             # compute_plan: 4-way classification (Pattern 2)
│                       # execute_plan: removal_mode param + re-show chunk loop (Pattern 3)
├── cli.py              # sync subparser gains --delete/--hard-delete;
│                       #   run_sync: mode-aware plan/summary wording (D-07/D-08),
│                       #   escalated confirm gate for --hard-delete
```

### Pattern 1: Widen `exclude_asset` to Batch, Add `include_asset` as Its Mirror
**What:** Give `exclude_asset` the exact same single-or-list normalization `remove_asset` already has; add a new `include_asset` method that is a byte-for-byte structural copy of `exclude_asset` (same URL-shape decision, same fail-loud checks), targeting whatever path the live spike confirms.
**When to use:** Once HIDE-01 confirms the mechanism and its exact endpoint path/payload shape.
**Example:**
```python
# Source: pattern-matched from auraframes/api/frameApi.py's existing remove_asset (batch-refactored
# in quick task 260708-fyr) applied to exclude_asset's current single-item shape
def exclude_asset(self, frame_id: str, asset_partial_ids: AssetPartialId | list[AssetPartialId]) -> int:
    items = asset_partial_ids if isinstance(asset_partial_ids, list) else [asset_partial_ids]
    json_response = self._client.post(f'/frames/{frame_id}/exclude_asset',  # NOTE: no .json -- confirm via spike
                                      data={'assets': [item.to_request_format() for item in items]})
    if json_response.get('error'):
        raise RuntimeError(f"exclude_asset failed for frame {frame_id}: {json_response.get('error')}")
    number_failed = json_response.get('number_failed')
    if number_failed:
        raise RuntimeError(f"exclude_asset reported {number_failed} failure(s) for frame {frame_id}")
    return number_failed

def include_asset(self, frame_id: str, asset_partial_ids: AssetPartialId | list[AssetPartialId]) -> int:
    # Mirror of exclude_asset above -- path/payload confirmed by the live spike (HIDE-01).
    ...
```

### Pattern 2: Read-Side Visibility Signal — Two Candidate Shapes, Spike Decides

**Candidate A (lower blast radius, preferred if the spike confirms it): inline field on `Asset`.**
If step 2 of the live spike shows the raw per-asset dict already carries an inline `hidden` (or similarly-named) key that `Asset`'s current model silently drops, the fix is a one-line model addition:
```python
# auraframes/models/asset.py, Asset class
hidden: Optional[bool] = None  # populated once confirmed live (HIDE-01); None for any asset
                                # never touched by exclude_asset/hidden-state logic
```
`compute_plan` then reads `asset.hidden` directly — zero changes to `FrameApi.get_assets`'s return signature, zero changes to any of its three call sites (`Aura.get_all_assets`, `run_inspect`, `run_sync`).

**Candidate B (larger blast radius, only if the spike shows this is the real shape): parallel `asset_settings` array, mirroring `ActivityApi.get_activity_assets`.**
```python
# auraframes/api/activityApi.py:60-65 -- the EXISTING precedent this candidate would mirror
json_response = self._client.get(f'/activities/{activity_id}/assets.json', ...)
return (
    [Asset(**json_asset) for json_asset in json_response.get('assets')],
    [AssetSetting(**json_asset_setting) for json_asset_setting in json_response.get('asset_settings')]
)
```
If `FrameApi.get_assets` turns out to return the same shape, its signature must widen (`tuple[list[Asset], list[AssetSetting], str]`), which touches `Aura.get_all_assets`, `run_inspect`, and `run_sync` — a real, non-trivial blast-radius increase. **Recommendation to avoid this:** do the `AssetSetting`↔`Asset` merge-by-`asset_id` **inside** `Aura.get_all_assets` (or a new sibling method), zipping the two lists into a single enriched sequence *before* returning to any caller — e.g. attach the matching `AssetSetting.hidden` value onto each `Asset` via `asset.model_copy(update={'hidden': setting.hidden})` (requires Candidate A's field to also exist on the model) or via a small `FrameAsset` wrapper dataclass used only within `sync.py`. This keeps `get_assets`'s own signature and every existing call site byte-identical, confining the widening to one merge step.

**Recommendation:** Try Candidate A's raw-JSON check first (it's strictly cheaper to confirm and cheaper to implement); only fall back to Candidate B's merge-inside-`get_all_assets` approach if the spike shows the API genuinely returns a parallel `asset_settings` array on the frame-asset endpoint the way it does on the activity-asset endpoint.

### Pattern 3: `execute_plan`'s `removal_mode` Parameter + Always-On Re-show Loop

**What:** `execute_plan` gains one new parameter, `removal_mode: str = 'hide'`, selecting which single write primitive is applied to `plan.to_remove` (the existing `to_delete` list, semantically renamed since it now serves three possible actions); a **second, independent chunk loop** (new, always executed regardless of `removal_mode`) applies the confirmed re-show primitive to `plan.to_reshow`.
**When to use:** Inside `execute_plan`, following the exact chunking/throttle/budget/consecutive-failure machinery the existing upload and delete loops already use (`_chunked`, `throttle()`, `interchunk_pause()`, `budget.acquire(...)`, `note_failure(...)`) — this phase adds a third and fourth loop shaped identically to the existing delete loop, not a new execution model.
**Example:**
```python
# Source: pattern-extension of the existing delete loop (auraframes/sync.py:561-589),
# applied twice more (re-show always; removal mode-selected)
_REMOVAL_PRIMITIVE = {
    'hide': lambda aura, frame_id, ids: aura.frame_api.exclude_asset(frame_id, ids),
    'delete': lambda aura, frame_id, ids: aura.frame_api.remove_asset(frame_id, ids),
    'hard_delete': lambda aura, frame_id, ids: [aura.asset_api.delete_asset(a) for a in ids],  # asset-scoped, not batch (see Pitfall 3)
}

for chunk in _chunked(plan.to_reshow, batch_size):
    interchunk_pause()
    if budget is not None:
        budget.acquire(1, wait=wait_on_budget, max_wait=max_wait_seconds, now=clock(), sleep=sleep, on_wait=on_wait)
    try:
        throttle()
        aura.frame_api.include_asset(frame_id, [AssetPartialId(id=asset.id) for asset in chunk])
        for asset in chunk:
            result.reshow_succeeded += 1
            progress('reshow', asset.id, True)
    except RateLimitError:
        ...  # identical shape to the existing delete-chunk RateLimitError branch
    except Exception as e:
        for asset in chunk:
            result.reshow_failures.append((asset.id, str(e)))
            note_failure(str(e))

for chunk in _chunked(plan.to_remove, batch_size):
    ...  # identical shape, calling _REMOVAL_PRIMITIVE[removal_mode] instead of a hardcoded remove_asset
```
**Note on `--hard-delete`'s primitive:** `AssetApi.delete_asset` operates on a single `Asset` (`/assets/{id}.json`, asset-scoped, not `{"assets": [...]}` batch-shaped like `remove_asset`/`exclude_asset`) — it cannot be chunked the same batching way; a "chunk" of hard-deletes is still N individual `DELETE` calls even inside the chunk loop's outer structure (see Pitfall 3). Budget accounting must reflect N requests per hard-delete chunk, not 1.

### CLI Integration Pattern: Mode-Aware Wording + Escalated Confirm Gate

```python
# Source: pattern extension of run_sync's existing D-01..D-04/D-07/D-08 print block
mode = 'hard_delete' if args.hard_delete else ('delete' if args.delete else 'hide')
verb_noun = {'hide': 'hide', 'delete': 'delete', 'hard_delete': 'hard-delete'}[mode]
verb_past = {'hide': 'Hidden', 'delete': 'Removed', 'hard_delete': 'Hard-deleted'}[mode]

print(f'To {verb_noun}: {len(plan.to_remove)}')
print(f'To re-show: {len(plan.to_reshow)}')
...
if mode == 'hard_delete':
    print('WARNING: --hard-delete is IRREVERSIBLE -- affected photos cannot be recovered.')
    confirm = input(f'Type the number of photos ({len(plan.to_remove)}) to confirm hard-delete: ')
    if confirm.strip() != str(len(plan.to_remove)):
        print('Aborted.')
        return 0
elif not yes:
    answer = input(f'About to apply this plan to "{frame.name}" (id: {frame.id}). Proceed? [y/N] ')
    ...
```

### Anti-Patterns to Avoid
- **Branching on `mode` inside `compute_plan`:** `compute_plan` must stay mode-agnostic and pure — it only needs to know *whether* an asset is currently hidden (to classify), never *which* removal primitive will eventually run against a removal candidate. Mode selection belongs entirely in `execute_plan`/CLI, matching Phase 7's structural (not `if flag:`) separation precedent.
- **Silently keeping `Aura.upload_image()`-style duplicated logic for the new primitives:** reuse the existing chunk/throttle/budget/consecutive-failure scaffolding verbatim (Pattern 3) rather than writing a parallel, simpler-looking loop that skips Phase 9's anti-abuse protections.
- **Assuming `AssetSetting.hidden` can be written via `batch_update`:** `batch_update`'s payload allowlist (`auraframes/api/assetApi.py:37-52`) has no `hidden` key, and its own docstring disclaims frame-level effect — do not add `hidden` to that allowlist speculatively; the write side is `exclude_asset`/`include_asset`, not `batch_update`.
- **Treating `delete_asset`'s Phase 8 finding as still-valid without HIDE-07's re-verification:** the API has drifted before (Phase 2's asset-count field move) — re-probe before trusting `--hard-delete` on real photos.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Per-frame-asset visibility read signal | A custom "diff the app's exported JSON" heuristic, or a local manifest tracking hidden state client-side | The confirmed live read signal (inline `Asset.hidden` or merged `AssetSetting.hidden`, Pattern 2) | The server is the source of truth for what's actually hidden on the frame — a client-side manifest would drift the moment a second contributor or the mobile app itself changes visibility outside this CLI's control. |
| Batch-capable hide/show calls | A per-item loop issuing one `exclude_asset`/`include_asset` HTTP call per photo | The same chunk/batch pattern already proven for `select_asset`/`remove_asset`/`batch_update` (`WRITE_BATCH_SIZE`, `_chunked`) | Per-file calls are the documented root cause of the anti-abuse trip this project already suffered once (`pushd-batch-endpoints` memory) — the new hide/show calls must follow the same batch shape from day one, not be retrofitted after a second lockout. |
| Confirmation-gate escalation logic | A generic "danger level" enum/framework | A simple three-branch `if mode == 'hard_delete': ... elif not yes: ...` inline in `run_sync`, matching the existing single-gate code shape | This codebase's CLI layer has no framework anywhere else (argparse + print + input()) — a bespoke escalation abstraction would be the first of its kind and inconsistent with every other handler. |

**Key insight:** Every write primitive this phase needs (or needs to add) is a small, same-shape sibling of a primitive that already exists and is already live-verified or already tested offline. The only genuinely new invention is `include_asset` itself (no prior art in this codebase) and the read-side merge step (Pattern 2) — everything else is direct reuse of Phase 7/8/9's existing chunking, throttling, budget, and fail-loud conventions.

## Common Pitfalls

### Pitfall 1: `exclude_asset`'s missing `.json` suffix may or may not be a bug
**What goes wrong:** `FrameApi.exclude_asset` posts to `/frames/{frame_id}/exclude_asset` — every other write endpoint in this codebase (`select_asset.json`, `remove_asset.json`, `batch_update.json`) uses a `.json` suffix. A naive "fix" (adding `.json`) before live-testing the current form risks masking or altering genuinely correct-as-is API behavior.
**Why it happens:** This endpoint has never been exercised live (unlike `select_asset`/`remove_asset`, both confirmed in Phase 8). There is at least one **other** no-suffix precedent in this codebase (`ActivityApi.delete_activity`: `self._client.delete(f'/activities/{activity_id}')`, also no `.json`), so this is not necessarily a typo — some Pushd endpoints may genuinely lack the suffix.
**How to avoid:** Test the current no-suffix form FIRST during the live spike (step 3); only retry with `.json` appended if the no-suffix form 404s or errors. Do not "clean up" the URL before testing it as-is.
**Warning signs:** A 404 (not a JSON `error` envelope) on the first `exclude_asset` call during the spike.

### Pitfall 2: `AssetSetting` today has no known write path at all
**What goes wrong:** It's tempting to assume `AssetSetting.hidden` can simply be constructed and PUT/POSTed somewhere to flip visibility, mirroring how `FramePartial`/`AssetPartial` are used for other partial updates. **No such endpoint exists anywhere in this codebase** — `AssetSetting` is only ever constructed from a GET response (`ActivityApi.get_activity_assets`), never sent in a request body.
**Why it happens:** `AssetSetting`'s shape (a `frame_id`+`asset_id`+`added_by_id` join-record) *looks* like a natural write target, but this codebase has zero prior evidence that it's writable directly — the actual write mechanism (per the app's UI language: "exclude or include the selected items") is far more likely a frame-scoped action endpoint (`exclude_asset`/`include_asset`) that the *server* uses to update the underlying `AssetSetting` record, not a client-side direct write to that record.
**How to avoid:** Do not attempt a hypothetical `PUT /asset_settings/{id}` or similar invented endpoint. Confirm the read signal (Pattern 2) and write mechanism (`exclude_asset`/`include_asset`) independently; treat `AssetSetting` purely as a possible **read-side shape**, never as a write target, unless the spike specifically surfaces evidence otherwise.
**Warning signs:** Speculatively adding a new `AssetApi`/`ActivityApi` write method for `AssetSetting` without any live evidence it exists.

### Pitfall 3: `delete_asset` cannot be batched the way `exclude_asset`/`remove_asset` can
**What goes wrong:** `AssetApi.delete_asset(asset: Asset)` hits `/assets/{asset.id}.json` — one asset per call, no `{"assets": [...]}` batch shape (unlike every `FrameApi` write primitive touched this phase). Treating `--hard-delete` chunks as "1 network call per chunk" (like hide/show/soft-delete) will undercount both the actual HTTP call volume and the write-budget tokens consumed.
**Why it happens:** `delete_asset` is asset-scoped (`/assets/{id}.json`), structurally different from the frame-scoped batch endpoints (`/frames/{id}/remove_asset.json` etc.) that already support `{"assets": [...]}`.
**How to avoid:** When `removal_mode == 'hard_delete'`, `budget.acquire(len(chunk), ...)` (N tokens, one per asset), not `budget.acquire(1, ...)` as the hide/delete/re-show chunk loops do. Document this explicitly in `execute_plan`'s docstring, mirroring the existing "coarser than upload attribution" documentation style for `remove_asset`.
**Warning signs:** The write budget running out far sooner than expected during a `--hard-delete` run, or anti-abuse trips resurfacing specifically for hard-delete-heavy plans.

### Pitfall 4: Batch support for `exclude_asset`/`include_asset` is unverified — plan for the "single-item only" fallback
**What goes wrong:** If the live spike's batch check (step 8) shows `exclude_asset`/`include_asset` reject a multi-item `{"assets": [...]}` payload (unlike `select_asset`/`remove_asset`, which are confirmed native batch endpoints), a naive port of Pattern 3's chunk loop would send one oversized failing call per chunk instead of correctly falling back to N single-item calls.
**Why it happens:** `exclude_asset`'s only prior form in this codebase is explicitly single-item ("Typical use of this endpoint results in a single AssetPartialId being sent per call" — its own docstring, `auraframes/api/frameApi.py:145`), unlike `select_asset`/`remove_asset`, which were **already** batch-native before this project's own batch refactor (quick task 260708-fyr) formalized chunking around them.
**How to avoid:** Confirm batch support explicitly (spike step 8) before assuming it. If it fails, `execute_plan`'s hide/show loops should degrade to N single-item calls with per-call throttling — the existing `throttle_seconds`/`WRITE_THROTTLE_SECONDS` mechanism already exists for exactly this pacing need; do not skip it just because batching didn't pan out.
**Warning signs:** A batch `exclude_asset`/`include_asset` call returning `number_failed` equal to the whole chunk size, or an `error` envelope specifically on multi-item payloads that single-item payloads don't trigger.

### Pitfall 5: The confirmation-gate escalation removes Phase 8's full structural isolation of `delete_asset`
**What goes wrong:** Phase 8 D-06 kept `delete_asset` **completely absent** from any reachable code path in `sync.py`/`cli.py` (grep-verified). This phase deliberately reverses that (D-04 explicitly supersedes it) — `delete_asset` becomes reachable behind `--hard-delete`. This is a real, acknowledged reduction in the "physically unreachable" safety property Phase 8 established, not merely a flag-gated `if`.
**Why it happens:** The user explicitly chose to wire all three tiers now rather than defer `--hard-delete` to its own safety-reviewed phase (see Deferred Ideas — this was offered and declined).
**How to avoid:** Compensate with what CONTEXT.md's Claude's Discretion asks for: a **distinct, stronger** confirmation gate for `--hard-delete` specifically (not just a differently-worded version of the same y/N prompt) — e.g., requiring the exact count to be re-typed (see CLI Integration Pattern above) — plus HIDE-07's live re-verification immediately before shipping. Document this tradeoff explicitly in the phase's `10-SECURITY.md` as an accepted, deliberate risk (mirroring how Phase 8 documented the "no `--max-delete` circuit breaker" risk), not silently absorbed.
**Warning signs:** A plan that wires `--hard-delete` with the *same* confirmation wording as `--delete`/hide, or that omits `checkpoint:human-verify` before the `--hard-delete` code path is exercised against a real account.

## Code Examples

### Existing `remove_asset` batch pattern `exclude_asset` should mirror exactly
```python
# Source: auraframes/api/frameApi.py:157-186 (already live-verified, WRITE-02)
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

### Existing activity-assets parallel-array precedent (Candidate B's mirror target)
```python
# Source: auraframes/api/activityApi.py:48-65
def get_activity_assets(self, activity_id: str, limit: int = 1000, cursor: str = None):
    json_response = self._client.get(f'/activities/{activity_id}/assets.json',
                                     query_params={'limit': limit, 'cursor': cursor})
    return (
        [Asset(**json_asset) for json_asset in json_response.get('assets')],
        [AssetSetting(**json_asset_setting) for json_asset_setting in json_response.get('asset_settings')]
    )
```

### Existing pure-classification shape `compute_plan`'s 4-way logic extends
```python
# Source: auraframes/sync.py:212-252 (Phase 7, unchanged shape this phase extends)
def compute_plan(local_hashes: dict[str, list[Path]], frame_assets: list, skipped_non_image: int = 0) -> SyncPlan:
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
    return SyncPlan(to_upload=to_upload, to_delete=to_delete, unchanged=unchanged, ...)

# Phase 10 extension sketch (exact field name TBD by planner, e.g. asset.hidden per Pattern 2):
#   present_local = demand.get(asset.md5_hash, 0) > 0   (existing condition, renamed for clarity)
#   if present_local and asset.hidden:      to_reshow.append(asset)
#   elif present_local:                     unchanged += 1   (existing branch, unchanged)
#   elif not present_local and asset.hidden: already_hidden += 1   (NEW no-op counter, D-06)
#   else:                                   to_remove.append(asset)  (existing to_delete, renamed)
```

### Existing test convention for constructing test `Asset`s with new fields
```python
# Source: tests/test_sync_engine.py:12-13 -- Asset.model_construct bypasses full validation,
# so a new `hidden` field can be set directly in tests without populating all 60+ Asset fields
def _asset(id_, md5_hash, hidden=False, taken_at="2024-03-11T12:00:00.000Z"):
    return Asset.model_construct(id=id_, md5_hash=md5_hash, hidden=hidden, taken_at=taken_at)
```

## State of the Art

| Old Approach | Current/Proposed Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| `sync --apply`'s only removal primitive: `remove_asset` (frame disassociation) | Three selectable tiers: `exclude_asset` (default, hide) / `remove_asset` (`--delete`) / `delete_asset` (`--hard-delete`) | This phase (Phase 10) | The safe default shifts from "disassociate" to "hide," matching the user's stated rationale that the frame has no photo-count limit so preservation should be the default. |
| `delete_asset` structurally unreachable from any executable path (Phase 8 D-06) | Reachable behind `--hard-delete` with an escalated confirmation gate (Phase 10 D-04, supersedes 08 D-06) | This phase | A deliberate, acknowledged reduction in Phase 8's "physically impossible to trigger" safety property — compensated by a stronger gate and a live blast-radius re-verification, not removed silently. |
| `compute_plan` classifies frame assets on one dimension (present-local vs not) | Two dimensions (present-local × hidden-visible), 4-way classification | This phase | Requires a new read signal (`hidden`/visibility state) that no code path in this project currently fetches from the frame-asset endpoint. |

**Deprecated/outdated:** None beyond the general project-wide `.dict()`→`.model_dump()` pydantic v2 migration note already documented in Phase 8's research (still applies to any new `.dict(include={...})` calls this phase might add, if the read-side merge step needs one).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `exclude_asset` (and a symmetric `include_asset`) is the real hide/show mechanism, rather than a currently-unknown third mechanism | Summary / Live-Spike Protocol | If wrong, the spike's step 3-6 will fail cleanly (STOP tripwire) rather than silently ship incorrect behavior — this is the entire reason HIDE-01 is a gating checkpoint, not a research-time claim. |
| A2 | The frame-asset endpoint (`/frames/{id}/assets.json`) returns a parallel `asset_settings` array or an inline `hidden` key, mirroring the activity-asset endpoint's confirmed shape | Pattern 2 | If wrong, no read signal exists at all and `compute_plan`'s 4-way classification cannot be built — this is itself a STOP tripwire (see Live-Spike Protocol). |
| A3 | `exclude_asset`/`include_asset` are batch-capable like `select_asset`/`remove_asset`, not single-item-only like their current implementation | Pitfall 4 | If wrong, hide/show calls fall back to N single-item calls per removal-candidate/reshow-candidate, reintroducing some of the per-call anti-abuse risk Phase 9's batching specifically mitigated — degrades performance/safety margin but does not block shipping (not a STOP tripwire on its own). |
| A4 | The official Aura Help Center's "exclude or include the selected items" UI description (found via web search, not a raw page fetch — the page returned HTTP 403 to direct fetch) accurately describes the current app's actual behavior, not a stale/older UI flow | Summary, Pattern 1 | Low risk — this is corroborating context for why `exclude_asset`/`include_asset` is the most plausible mechanism, not load-bearing for any code decision; the live spike is the actual source of truth regardless. |
| A5 | `delete_asset`'s Phase 8 finding (asset-scoped, not frame-scoped, matches its docstring's worst case) still holds unchanged | Live-Spike Protocol step 7 / HIDE-07 | If the API drifted since Phase 8 (already happened once, Phase 2's asset-count field move), `--hard-delete` could be wired to something more destructive than documented — this is exactly why HIDE-07's re-verification is a required, not optional, step before `--hard-delete` ships. |

**If this table is empty:** N/A — five genuine unknowns exist, all gated behind this phase's own live-spike checkpoint (HIDE-01/HIDE-07), not resolvable from static research alone, consistent with Phase 8's precedent for this same undocumented API.

## Open Questions

1. **Does `exclude_asset`'s current no-`.json`-suffix form actually work, or does it need `.json` appended?**
   - What we know: Every other write endpoint in this codebase uses `.json`; one other no-suffix precedent exists (`delete_activity`).
   - What's unclear: Whether this is a latent bug (never caught because `exclude_asset` has never been called live) or a genuine API inconsistency.
   - Recommendation: Test as-is first during the spike (Pitfall 1); only add `.json` if the no-suffix form 404s.

2. **Is the hidden/visible signal per-account (global) or per-contributor (each contributor can independently hide an asset in their own view)?**
   - What we know: `AssetSetting` carries `added_by_id`, suggesting a per-user relationship; multi-contributor frames exist in this codebase's model (`Frame.contributors`).
   - What's unclear: Whether `compute_plan` (acting as the single authenticated account) sees a hidden state that's globally consistent for the frame, or only reflects what *this* account hid — if per-contributor, one user's `sync --apply` hide could be invisible to (or conflict with) another contributor's view.
   - Recommendation: The live spike's raw-JSON read (step 2) should reveal whether `asset_settings`/the hidden signal is a single value or a list keyed by contributor; if the latter, `compute_plan` should key on the currently-authenticated account's own `added_by_id` entry, and this ambiguity should be flagged explicitly in the plan/summary output if multiple contributors' hidden states could diverge.

3. **Does the official Aura app's "remove" action (the one described in the Help Center as irreversible, requiring re-upload) map to `remove_asset` or `delete_asset`?**
   - What we know: Phase 8 confirmed `remove_asset` disassociates without apparent S3/Glacier deletion (softer than the app's "can't be undone, must re-upload" wording suggests); `delete_asset` was confirmed asset-scoped and more thoroughly destructive.
   - What's unclear: The app's single "remove" button in its UI could be calling either primitive (or something else) — the Help Center's "can't undo it, must re-upload" language is arguably a closer match to `delete_asset`'s behavior than `remove_asset`'s (which merely disassociates; the underlying account asset likely still exists and, if a local/backup copy is re-synced, could conceivably re-associate without a fresh "upload" round-trip, though this project's own D-02/D-03 flag naming already commits `--delete` to `remove_asset` regardless).
   - Recommendation: Not blocking for this phase — D-02/D-03 already lock `--delete`→`remove_asset` and `--hard-delete`→`delete_asset` regardless of which one the app's own "remove" button calls; noted here only as residual uncertainty about how this project's flag names map to the app's own UI vocabulary, in case future user-facing documentation wants to reference the app's terms.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.14 / `uv` | Runtime | ✓ | 3.14.4 / — [ASSUMED: unchanged since Phase 8's local verification, not re-checked this session] | — |
| Live Aura account + a disposable/spare test asset | HIDE-01/HIDE-07 live spike | Likely ✓ — the project's standing live-verification frame ("Cadre de Fabrice") and disposable-asset convention already exist from Phase 8 | — | If credentials or the test frame are unavailable at execution time, the live-spike checkpoint cannot proceed and must block (same as Phase 8's WRITE-03 checkpoint gate). |
| Official Aura mobile/web app (for visual crossed-eye-icon confirmation) | Live-Spike Protocol step 4/6 (optional, corroborating only) | Unknown — not verified this session | — | If unavailable, rely entirely on the raw-JSON diff (steps 2/4/6) as the source of truth; the visual check is corroborating, not required, for HIDE-01 to pass. |

**Missing dependencies with no fallback:** None identified from static review — actual live-credential/test-frame availability can only be confirmed at execution time (this phase's own checkpoint task).

**Missing dependencies with fallback:** The visual in-app confirmation (see above) has a documented fallback (raw-JSON diff alone).

## Security Domain

`security_enforcement` is enabled (`.planning/config.json`: `security_asvs_level: 1`). This phase both introduces new destructive reach (`--hard-delete` reaching `delete_asset`, reversing part of Phase 8's structural isolation) and a new state-reading capability (per-asset visibility) — the posture shifts further from Phase 8's already-elevated write-path baseline.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V1 Architecture | yes | `compute_plan` stays pure/mode-agnostic (no mechanism-specific branching in the diff engine); `execute_plan`'s `removal_mode` parameter is the ONLY point where the three removal primitives diverge, keeping the "structural, not `if apply:`" separation Phase 7/8 established, adapted (not abandoned) for three tiers instead of one. |
| V4 Access Control | no | Single-user tool acting with the authenticated account's own permissions; no multi-tenant concern (see Open Question 2 re: per-contributor visibility, which is a correctness question, not an access-control one). |
| V5 Input Validation | yes | New `--delete`/`--hard-delete` CLI flags (mutually-exclusive with each other, argparse-level) plus the new escalated confirmation input (exact-count re-type for `--hard-delete`) are the new input surface. |
| V7 Error Handling & Logging | yes | The new `exclude_asset`/`include_asset` primitives must get the same fail-loud (`error` field + nonzero `number_failed` → raise) treatment `remove_asset`/`select_asset` already have (WRITE-05 precedent) — do not ship them un-hardened. `Client._redact()` already covers any new POST/PUT body generically; confirm no new logging statement in the re-show/hide loops prints raw asset content. |
| V9 Communications | no | No change — reuses the existing `httpx.Client(http2=True)` HTTPS transport. |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| `--hard-delete` reaching a previously-unreachable, irreversible primitive on the wrong frame or wrong asset set | Tampering | Distinct, stronger confirmation gate (exact-count re-type) + D-04's live re-verification (HIDE-07) before shipping; frame name+id echo (existing D-04 from Phase 8) retained for all three tiers. |
| Read-side visibility signal misread as global when it's actually per-contributor (or vice versa), causing `compute_plan` to hide/re-show assets based on a stale or wrong-scoped signal | Tampering / Repudiation | Live-spike step 2's raw-JSON inspection must explicitly check for a per-contributor shape (Open Question 2) before `compute_plan` is written to assume a single global value. |
| A mistaken `sync --apply` (default hide mode) still being effectively destructive if the hide mechanism turns out to secretly disassociate rather than merely hide (mechanism misidentified) | Tampering | This is precisely what HIDE-01's live spike (raw-JSON diff, asset must remain in `get_assets`'s listing) is designed to catch before any code ships — a STOP tripwire, not a runtime guard. |
| Anti-abuse trip re-triggered by un-batched hide/show calls if batch support turns out to be unavailable (Pitfall 4) | Denial of Service | Reuse the existing `WRITE_THROTTLE_SECONDS`/`WRITE_CHUNK_DELAY_SECONDS`/`WriteBudget` machinery unchanged for the single-item fallback path — do not skip pacing just because batching didn't pan out. |
| Secret/token leakage in any new logging added for the hide/re-show/hard-delete loops | Information Disclosure | `Client._redact()` already covers this generically at the HTTP layer; confirm no new `logger.debug`/`print` statement in the new chunk loops echoes raw asset/account data beyond what existing loops already print (asset id, filename, taken_at). |

## Sources

### Primary (HIGH confidence — direct codebase reads, this session)
- `auraframes/api/frameApi.py` — full read: `exclude_asset`, `remove_asset`, `select_asset`, `get_assets`, `get_frame` (full file)
- `auraframes/api/assetApi.py` — full read: `delete_asset`, `batch_update`, `crop_asset`
- `auraframes/api/activityApi.py` — full read: `get_activity_assets` (the `AssetSetting` parallel-array precedent)
- `auraframes/models/asset.py`, `auraframes/models/person.py` — full read: `Asset`, `AssetSetting`, `AssetPartialId`, `PersonAssetSetting`
- `auraframes/models/frame.py` — full read: `Frame` (confirmed no per-asset visibility field at the frame level)
- `auraframes/models/meta.py` — full read: `make_partial`
- `auraframes/sync.py`, `auraframes/cli.py` — full read: `compute_plan`, `execute_plan`, `run_sync`, CLI flag wiring
- `tests/test_sync_engine.py`, `tests/test_cli_apply.py` — full read: existing offline-test conventions (`Asset.model_construct`, monkeypatched `execute_plan`, `offline_aura` fixture)
- `grep -rn "AssetSetting|hidden|exclude_asset|include_asset|selected"` across the full source tree — direct confirmation that `AssetSetting`/`hidden` has zero write-path usage anywhere in this codebase today
- `.planning/phases/08-destructive-execution-upload-delete-verification/08-RESEARCH.md`, `08-LIVE-FINDINGS.md` — full read: `delete_asset`/`remove_asset` live-verification precedent and methodology this phase's spike directly extends
- `.planning/REQUIREMENTS.md`, `.planning/STATE.md`, `.planning/ROADMAP.md`, `.planning/config.json` — full read

### Secondary (MEDIUM confidence — cross-checked web search, official but not directly fetched)
- [Aura Help Center — "How can I remove Photos & Videos from my Frame?"](https://help.auraframes.com/hc/en-us/articles/218847447-How-can-I-remove-Photos-Videos-from-my-Frame) — confirms the official app presents "exclude or include the selected items into your slideshow" as a distinct action from "remove," and that removal is described as irreversible/requiring re-upload. Content retrieved via search synthesis, not a direct page fetch (direct fetch returned HTTP 403).
- [Aura Help Center — "Using the Frame Slideshow Feature"](https://help.auraframes.com/hc/en-us/articles/8418115014039-Using-the-Frame-Slideshow-Feature) — confirms excluded photos/videos display a crossed-eye icon and are not shown in the physical slideshow, corroborating D-01's exact semantic. Same retrieval caveat as above.

### Tertiary (LOW confidence — unverified/exploratory)
- [zmanowar/auraframes](https://github.com/zmanowar/auraframes), [bp1222/auraframes-api](https://github.com/bp1222/auraframes-api) — other unofficial Aura API clients found via search; neither's public README documents a hide/exclude mechanism beyond what this project's own code already has. Checked as a "does anyone else's reverse-engineering corroborate this" pass; yielded no additional field/endpoint evidence beyond this repo's own code.

## Metadata

**Confidence breakdown:**
- Standard stack / code mapping: HIGH — every candidate mechanism was traced to an exact file/line in this repository this session; no speculation about what code exists today.
- Hide/show mechanism identity and live behavior: LOW/unknown by design — this is precisely why HIDE-01 is a mandatory `checkpoint:human-verify` gating task, not a research-time claim; the ranking (exclude_asset/include_asset > AssetSetting-as-read-signal > selected/batch_update-rejected) is MEDIUM confidence, corroborated by official (if indirectly retrieved) help-center documentation.
- Architecture/classification threading (Pattern 2/3): HIGH for the *shape* of the change (extends existing, already-tested `compute_plan`/`execute_plan` patterns almost mechanically); LOW for the *exact field name/model shape*, which depends entirely on HIDE-01's outcome.
- Pitfalls: HIGH — every pitfall is grounded in a specific, cited line number, docstring quote, or grep result, not speculation.

**Research date:** 2026-07-09
**Valid until:** 2026-07-16 (7 days — mirrors Phase 8's precedent: any finding here that depends on live API behavior is provisional until this phase's own execution-time checkpoint (HIDE-01) confirms it, and the underlying API is undocumented/drift-prone).
