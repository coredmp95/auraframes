# Phase 10: Hide-instead-of-delete sync mode - Context

**Gathered:** 2026-07-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Change `sync --apply`'s removal path so that photos gone-locally are **hidden** on the
frame by default (kept on the frame, removed from the slideshow) instead of being removed.
Introduce two opt-in flags for stronger removal, and make the diff engine treat the local
directory as the source of truth for visibility (so a still-present local file re-shows a
previously-hidden frame photo).

**In scope:**
- Default `sync --apply` removal mode = **hide** (make invisible on the frame; the asset
  stays attached to the frame / visible in the app, just not shown in the rotation).
- Three-tier removal control on `sync --apply`:
  - default (no flag) → **hide**
  - `--delete` → `remove_asset` (disassociate the photo from the frame; asset survives in account/S3)
  - `--hard-delete` → `delete_asset` (irreversible, asset-scoped destroy)
- **Re-show**: a photo currently hidden on the frame whose file is still present locally is
  un-hidden on plain `--apply` (non-destructive), surfaced as its own plan line.
- Diff-engine change: read each frame asset's hidden/visibility state so hidden photos count
  as "present on the frame" for dedup (never re-uploaded) and can be classified for re-show.
- Plan/summary output labels the real action per mode; confirmation gate escalates by
  destructiveness.
- Offline test coverage for all new classification/execution paths, matching the existing
  injected-fake conventions.

**Out of scope / non-goals:**
- Any new subcommand (this is entirely within `sync --apply`; `push` is additive-only and
  untouched).
- A standalone "unhide/show everything" or bulk-visibility command (re-show is driven only
  by the diff against the local directory).
- Auto-detecting the app's hide mechanism without a live confirmation — the live spike must
  confirm behavior before the default ships (see Claude's Discretion below).

</domain>

<decisions>
## Implementation Decisions

### Hidden end-state (what "hide" means)
- **D-01:** "Hide" means **off the slideshow, kept on the frame** — the photo no longer
  displays in the rotation but remains attached to the frame and visible in the Aura app's
  frame view. This is the most-preserving option (a mistaken sync loses nothing) and matches
  the semantics documented on the existing `FrameApi.exclude_asset` endpoint ("Excludes an
  asset from displaying in the frame's slideshow. The asset will still show in the app.").
  This is the product intent that scopes which mechanism research/spike must target — NOT a
  lock on `exclude_asset` specifically if the live spike finds the real "make invisible"
  action is backed by something else (e.g. an `AssetSetting.hidden` write).

### Removal tiers / flag design
- **D-02:** The opt-in "actually remove it, don't just hide" flag is named **`--delete`**
  (matches the existing plan vocabulary; reads naturally against a hide default).
- **D-03:** **Three tiers** on `sync --apply`:
  - default (no flag) → **hide**
  - `--delete` → `remove_asset` (soft disassociate — today's `--apply` removal behavior)
  - `--hard-delete` → `delete_asset` (the broad, irreversible asset-scoped destroy)
- **D-04:** `--hard-delete → delete_asset` **supersedes Phase 8 D-06**, which deliberately
  left `delete_asset` with no reachable code path from `--apply` "not even behind an
  undocumented flag." Because `delete_asset` was only ever probed live against a single
  disposable asset (Phase 8 D-05, with D-07's "stop if more destructive than documented"
  caveat), wiring `--hard-delete` REQUIRES, before it is trusted on real user photos:
  (a) a stronger/explicit confirmation gate distinct from the hide/`--delete` gate, and
  (b) live re-verification of `delete_asset`'s blast radius (does it reach S3/Glacier, or
  only the frame association?). If that re-verification reveals broader destruction than
  documented, STOP and report (mirroring Phase 7/8 live-checkpoint precedent) before shipping.

### Re-show / diff behavior
- **D-05:** The **local directory is the source of truth for visibility.** A photo currently
  hidden on the frame whose file is still present locally is **un-hidden (re-shown)** on
  plain `sync --apply`, regardless of removal mode (un-hide is non-destructive). This requires
  an inverse "show/include" action — research must confirm one exists (`include_asset`? an
  `AssetSetting.hidden = false` write? a `batch_update`/`selected` toggle?).
- **D-06:** Hidden frame photos count as **"present on the frame"** for dedup — they are never
  re-uploaded. The diff engine must read each asset's hidden/visibility state so it can
  distinguish: present-local + hidden → re-show; present-local + visible → unchanged;
  gone-local + visible → hide (default) / delete / hard-delete; gone-local + already-hidden →
  no-op (already in desired removed-ish state; not re-removed, not counted as a change).

### Plan output & summary wording
- **D-07:** **Verb matches the mode.** The dry-run plan and end-of-run summary label the real
  action: `To hide: N` / `To delete: N` / `To hard-delete: N` (summary: `Hidden`, `Removed`,
  `Hard-deleted`). Preserves the Phase 7/8 separated-counts plan style (upload / <removal> /
  unchanged) rather than keeping a static "delete" label.
- **D-08:** Re-show gets its **own plan line** (e.g. `To re-show: N`) alongside
  upload / hide / unchanged — most transparent; a visibility change is never folded silently
  into "unchanged."

### Claude's Discretion
- **Confirmation gate design** (user: "you decide") — lean toward **escalating friction by
  destructiveness**: hide = normal `Proceed? [y/N]` (reversible); `--delete` = same gate with
  wording noting photos leave the frame; `--hard-delete` = a stronger, explicit gate (distinct
  warning line and/or a count re-type) since it is irreversible. Keep `--yes` skipping the
  prompt in all modes, and keep Phase 8's single-gate-covers-the-whole-plan model (D-02 there).
- **If a safe hide mechanism cannot be confirmed live** (user: "you decide") — follow the
  Phase 7/8 precedent: **STOP and report** rather than ship a "hide" default that silently does
  something else. Keep today's `remove_asset` behavior until a real, live-confirmed hide/show
  path exists. Planner may choose a clean alternative only if the spike surfaces one.
- Exact endpoint(s) backing hide and re-show, precise CLI wording, and how the visibility
  state is threaded through the plan dataclasses — all implementation detail for research/planning.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap / requirements
- `.planning/ROADMAP.md` §"Phase 10: Hide-instead-of-delete sync mode" — the goal statement
  and the open mechanism question this phase resolves.
- `.planning/REQUIREMENTS.md` — new requirement IDs for this phase are TBD; mint during
  planning and back-fill (same pattern as Phase 9's `ANTI-*`).

### Prior locked decisions this phase touches
- `.planning/phases/08-destructive-execution-upload-delete-verification/08-CONTEXT.md` —
  D-01/D-02/D-03/D-04 (two-flag apply + single confirmation gate + non-interactive fail-closed
  + frame-echo), and **D-05/D-06/D-07** (disposable-asset `delete_asset` probe; `delete_asset`
  left unreachable; STOP-and-report if the live probe surprises). Phase 10 D-04 explicitly
  supersedes 08 D-06.
- `.planning/phases/07-sync-diffing-engine-dry-run-only/07-CONTEXT.md` — the dry-run plan
  output conventions (separated upload/delete/unchanged counts, untruncated listing) that
  D-07/D-08 extend.

### Code seams to integrate with (existing)
- `auraframes/api/frameApi.py` — `exclude_asset` (line ~136, the hide candidate; **untested**,
  note it POSTs `/frames/{frame_id}/exclude_asset` with no `.json` suffix and is single-item
  today), `remove_asset` (line ~157, `--delete` maps here), `select_asset` (batch association).
- `auraframes/api/assetApi.py` — `delete_asset` (`--hard-delete` maps here; the primitive
  Phase 8 verified but left unwired), `batch_update` (writes `selected` and other per-asset
  fields — a candidate lever for visibility if `hidden`/`selected` is the real mechanism).
- `auraframes/models/asset.py` — `AssetSetting.hidden: bool` and `Asset.selected: bool` /
  `Asset` has no top-level `hidden` field; research must determine where the read-side
  visibility state actually lives on a frame's asset listing.
- `auraframes/sync.py` — `compute_plan` (~line 210, `SyncPlan` dataclass: `to_upload` /
  `to_delete` / `unchanged` — add hide / re-show / hard-delete classification here) and
  `execute_plan` (~line 304, the mutating engine + `ExecutionResult` summary — add the
  per-mode removal branch and the re-show call; the delete loop currently calls `remove_asset`
  exclusively per 08 D-06).
- `auraframes/cli.py` — `sync` subparser (~line 65: `--apply`/`--yes`; add `--delete` /
  `--hard-delete`) and `run_sync` (~line 299: plan print + confirmation gate + separated
  summary; note the existing `no_delete` additive-mode pattern as a model for a removal-mode
  toggle).

### Test analogs (existing offline-test conventions)
- `tests/test_cli_apply.py`, `tests/test_cli_sync.py`, `tests/test_sync.py` (or equivalent) —
  injected-fake style (fake `aura`/`s3`/`sqs`, injected `sleep`, offline). Mirror these for
  the hide / re-show / three-mode classification and execution tests.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `FrameApi.exclude_asset` — already present as the documented "hide from slideshow, still
  shows in app" endpoint; strongest hide candidate but never live-verified and currently
  single-item / no `.json` suffix. Likely needs batch support + live confirmation.
- `FrameApi.remove_asset` — the `--delete` target; already batch-capable and live-verified.
- `AssetApi.delete_asset` — the `--hard-delete` target; live-verified once on a disposable
  asset, fail-loud wrapper already added (Phase 8 WRITE-05).
- `SyncPlan` / `ExecutionResult` dataclasses in `auraframes/sync.py` — the classification and
  summary structures to extend with hide / re-show / hard-delete buckets.

### Established Patterns
- **Structural (not `if flag:`) separation of safety-critical paths** — Phase 7 kept the
  dry-run engine physically separate from any mutating call; Phase 8 kept `delete_asset`
  unreachable. Phase 10 introduces new destructive reach (`--hard-delete`) and must add its
  own explicit guardrails rather than relying on flag defaults alone.
- **Live-spike-via-real-usage then document** (Phase 6 `md5_hash`, Phase 7 hash convention,
  Phase 8 `delete_asset`) — the correct methodology for confirming the hide/show mechanism and
  re-verifying `delete_asset`'s blast radius.
- **Injectable seams + no-op-when-unconfigured** (Phase 8/9) — new removal-mode/visibility
  behavior should default to the safest mode and keep existing offline tests green.

### Integration Points
- The removal-mode branch lives in `execute_plan`; the classification (hide vs re-show vs
  delete vs unchanged) lives in `compute_plan` and depends on a new read of each frame asset's
  visibility state during `inspect`/`get_assets`.
- CLI flag parsing + confirmation gate + plan/summary printing in `cli.py`'s `run_sync`.

</code_context>

<specifics>
## Specific Ideas

- User rationale for the hide default: **the frame has no photo-count limit, so preserving
  photos is the safer default — a mistaken sync should never destroy photos.** Reversibility
  is the whole point of the hide default.
- Directory-as-source-of-truth extends to visibility, not just presence: putting a file back
  in the sync directory should bring its photo back into the rotation (re-show), symmetric
  with removing a file hiding it.
- Related memory: `[[pushd-batch-endpoints]]` (select_asset/remove_asset/batch_update are
  batch endpoints — the hide/show mechanism should follow the same batch shape),
  `[[pushd-write-geofence]]` and Phase 9's write budget/geo guard already gate `sync --apply`,
  so the new hide/show/hard-delete calls inherit that anti-abuse protection automatically.

</specifics>

<deferred>
## Deferred Ideas

- **Standalone bulk visibility command** (e.g. `show`/`hide` a frame's photos independent of a
  directory diff) — out of scope; re-show here is driven only by the local-directory diff.
- **`--hard-delete` as its own focused phase** was offered but the user chose to include all
  three tiers now; if the live `delete_asset` re-verification surfaces broader-than-documented
  destruction, splitting `--hard-delete` back out into a dedicated safety-reviewed phase is the
  fallback.

*None beyond the above — discussion stayed within phase scope.*

</deferred>

---

*Phase: 10-hide-instead-of-delete-sync-mode*
*Context gathered: 2026-07-09*
