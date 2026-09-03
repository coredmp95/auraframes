# Phase 6: Inspect + Frame Resolution - Context

**Gathered:** 2026-07-06
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers the **`inspect --frame <name|id>` command**: it lists a frame's
photos (id/filename/date) plus frame metadata (name, owner, contributor count, asset
count), resolves frames by human-readable name or opaque ID, and produces a clear error
when a name is ambiguous. It also answers a live research question — whether `md5_hash`
is populated on read for pre-existing (non-client-uploaded) assets — whose answer
determines whether Phase 7's diff engine needs a local-manifest fallback. Zero new write
risk: `inspect` only reads (`get_frame`, `get_all_assets`), same as `status` in Phase 5.

In scope: frame name/ID resolution logic (new — no existing helper), the `inspect`
subcommand and its output formatting, and running/documenting the `md5_hash` live check.

Out of scope: `sync` (Phases 7-8), any write/mutating calls, machine-readable output
formats for `inspect` (see Deferred), promoting `--debug` beyond what's folded in below.

</domain>

<decisions>
## Implementation Decisions

### Frame Resolution (CLI-04)
- **D-01:** Matching is **case-insensitive substring match on `Frame.name`**, tried
  first. `"kitchen"` matches a frame named `"Kitchen"` (exact case-folded) and also
  `"Kitchen 2 Upstairs"` (substring) — both count toward the same match set.
- **D-02:** If the substring-name match set has **exactly one** result, use it. If it has
  **zero** results, fall back to treating the value as a **frame `id`** (exact match
  against `Frame.id`).
- **D-03:** If the substring-name match set has **more than one** result, that's
  ambiguous: print an error directing the user to `--frame <id>` and **list the
  matching frames' names + ids** so the user can copy one directly. Do not attempt the
  ID fallback in this case — multiple name matches wins over trying it as an id.
- **D-04:** If neither the name-match nor the id-match resolves to a frame, print a
  not-found error **and list the account's available frame names** as a hint (reuses the
  same `frame_api.get_frames()` call `status` already makes).
- **D-05:** All resolution failure paths (ambiguous, not-found) follow the Phase 5 D-08
  fail-loud convention: print what's wrong, exit non-zero.

### Photo Listing (CLI-03)
- **D-06:** Default output is a **summary count plus the first N photos** (id / filename
  / date), not the full list unconditionally — real frames can hold 77+ assets (Phase 2
  finding) and dumping thousands of lines to a terminal by default isn't useful. Exact
  value of N is Claude's discretion (e.g. 10); document the choice in the plan.
- **D-07:** Photos are listed in the **API's natural order** — no client-side re-sorting
  by `taken_at` or otherwise. Simplest, and avoids assuming a stable/meaningful field
  ordering from an undocumented API.
- **D-08 [informational]:** A `--format json`/`--format csv` full-export flag is
  **deferred**, not built in this phase — see Deferred Ideas. It duplicates the
  already-deferred `SYNC-06` ("--json machine-readable output for scripting") and should
  be designed once, for both `inspect` and `sync`, not half-built here. Scope-exclusion
  decision only — no plan action required; both Phase 6 plans correctly omit it.

### Frame Metadata Display
- **D-09:** Owner is shown as **both name and email** (`Frame.user.name` +
  `Frame.user.email` — both fields already exist on the `User` model, no new mapping
  needed).
- **D-10:** Contributors are shown as **count plus each contributor's name/email**
  (`Frame.contributors` is already a hydrated `list[User]` — no new API call needed,
  just formatting).
- **D-11:** Asset count uses `Frame.num_assets` (same field `status`'s sibling `get_frame`
  already prefers per the Phase 2 live-drift fix in `frameApi.get_frame`).

### md5_hash Live Spike (Success Criterion 4)
- **D-12:** The spike is **not a separate throwaway script** — it piggybacks on
  `inspect`'s own live verification pass. When `inspect` is tested/UATed against the
  real account/frame during this phase's build-out, check the real `Asset.md5_hash`
  values returned for pre-existing assets as part of that same live pass.
- **D-13:** The finding is documented in **two existing canonical locations**, not a new
  file: update the "Phase 6 live spike" entry in `STATE.md`'s Blockers/Concerns with the
  actual answer, and add a dated note to `PROJECT.md`'s Context section. Both are already
  where Phase 7 planning reads from — no new artifact convention introduced.
- Per `REQUIREMENTS.md` Out of Scope, a local-manifest fallback for Phase 7 is added
  **only if** this spike shows `md5_hash` is NOT populated for pre-existing assets — that
  decision stays conditional and is not pre-built here.

### Folded Todos
- **"Promote `--debug` flag to a global CLI convention"**
  (`.planning/todos/pending/2026-07-06-promote-debug-flag-to-a-global-cli-convention.md`,
  score 0.9) — folded into this phase's scope. `--debug` moves from a `status`-only
  subparser flag to a **root `aura-cli --debug <subcommand> ...` flag**, parsed once in
  `main()` before dispatching to any subcommand, so `_configure_cli_logging()` is called
  once regardless of which subcommand runs. `inspect` (this phase) is the first
  subcommand to benefit; `sync`/`upload` (Phases 7-8) inherit it for free. Requires
  updating `build_parser()` (root-level `--debug` arg instead of per-subparser) and
  `main()` (call `_configure_cli_logging` before subcommand dispatch) in
  `auraframes/cli.py`.

### Claude's Discretion
- Exact value of N for the default "first N photos" truncation (D-06).
- Exact wording of ambiguous/not-found error messages, as long as they follow D-03/D-04's
  content requirements (list matches or available frame names) and never leak the
  password (carried forward from Phase 5 D-07).
- Whether frame resolution lives in a new helper module (e.g. `auraframes/cli.py` or a
  small `frame_resolver.py`) or inline in the CLI handler — small enough either way at
  this phase's scope.
- Exact terminal formatting of the photo list / metadata block, following Phase 5's D-05
  concise-summary-no-table precedent.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project & milestone scope
- `.planning/PROJECT.md` — Current Milestone section (target features for `inspect`),
  Context section (will be updated with the md5_hash spike finding per D-13).
- `.planning/REQUIREMENTS.md` — **CLI-03** (`inspect` command) and **CLI-04** (frame
  targeting by name or ID) are this phase's requirements. Out of Scope table's
  conditional local-manifest-fallback note is the direct consumer of D-12/D-13's finding.
  v2 Requirements' **SYNC-06** is the reason D-08 defers `--format json/csv`.
- `.planning/ROADMAP.md` §"Phase 6: Inspect + Frame Resolution" — goal + the 4 success
  criteria.
- `.planning/STATE.md` Blockers/Concerns — "Phase 6 live spike" entry to be updated with
  the actual md5_hash finding per D-13.
- `.planning/todos/pending/2026-07-06-promote-debug-flag-to-a-global-cli-convention.md`
  — folded todo; superseded by D-\* above once this phase ships (mark resolved).

### Prior phase context (patterns to follow)
- `.planning/phases/05-cli-skeleton-status/05-CONTEXT.md` — D-01/D-02 (argparse,
  subcommand structure), D-05 (concise summary, no table), D-08/D-09 (fail-loud,
  non-zero exit convention) all carry forward unchanged into this phase.

### Codebase analysis (structure/architecture already mapped)
- `.planning/codebase/STRUCTURE.md` — naming conventions, "Where to Add New Code"
  guidance.
- `.planning/codebase/ARCHITECTURE.md` — Facade pattern; confirms `login()` must run
  before any other method.

### Files that will change
- `auraframes/cli.py` — add `inspect` subparser + handler; move `--debug` from the
  `status` subparser to the root parser (folded todo); wire frame resolution.
- `auraframes/frameApi.py` / `auraframes/aura.py` — reused as-is (`get_frames`,
  `get_frame`, `get_all_assets`); no changes expected unless a small resolution helper is
  added here instead of in `cli.py` (Claude's discretion).
- `.planning/STATE.md`, `.planning/PROJECT.md` — updated with the md5_hash spike finding
  (D-13) once confirmed live.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `FrameApi.get_frames()` (`auraframes/api/frameApi.py`) — already used by `status`;
  `inspect`'s resolution step reuses the same call to build the name/id match set.
- `FrameApi.get_frame(frame_id)` (`auraframes/api/frameApi.py`) — returns
  `(Frame, total_asset_count)`, already prefers `Frame.num_assets` as the live-corrected
  asset-count field (Phase 2 drift fix) — reuse directly for D-11.
- `Aura.get_all_assets(frame_id)` (`auraframes/aura.py:59`) — already handles cursor
  pagination; `inspect`'s photo listing calls this directly, same as `dump_frame` does.
- `Frame.contributors: Optional[list[User]]` and `Frame.user: User` (`auraframes/models/frame.py`)
  — already hydrated `User` objects with `.name`/`.email`; D-09/D-10 need no new API
  calls or model changes.
- `Asset.md5_hash: Optional[str]` (`auraframes/models/asset.py`) — already modeled; the
  live spike (D-12) just needs to inspect this field on real fetched assets, no schema
  change required.
- `Client`/`Aura` DI transport seam (v1.1) + `tests/offline.py` harness — `inspect`'s
  offline tests follow the same `Aura(client=...)` pattern Phase 5 established for
  `status`.

### Established Patterns
- Facade-only orchestration: `inspect`'s handler calls `Aura`/`FrameApi` methods
  directly; no new business logic belongs in `*Api` classes (`STRUCTURE.md`).
- Fail-loud, non-zero exit on any failure — carried forward from Phase 5 D-08 to D-05 in
  this phase.
- `run_status()`'s pattern of returning an int exit code (never calling `sys.exit`
  directly) should be mirrored by an equivalent `run_inspect()` for the same offline
  testability via `capsys`.

### Integration Points
- `auraframes/cli.py`'s `build_parser()` currently wires `--debug` on the `status`
  subparser only (`auraframes/cli.py:18-23`) — this phase's folded todo moves it to the
  root parser, and `main()` (`auraframes/cli.py:97-103`) currently dispatches only
  `status` — both need updating to add the `inspect` branch alongside relocating
  `--debug`.
- No existing frame name/id resolution code exists anywhere in the codebase — this is
  net-new logic for Phase 6 (unlike Phase 5, which only reused already-live-verified
  read calls).

</code_context>

<specifics>
## Specific Ideas

- The user's exact framing for photo listing: "there is no point to print 2000 line[s]
  on screen for any user" — drove D-06's summary-plus-first-N default over listing
  everything unconditionally.
- The user wants the eventual export-format flag to cover multiple formats (JSON *and*
  CSV explicitly mentioned), not just JSON — noted for whichever future phase designs
  `SYNC-06`/the deferred `--format` flag, so it isn't narrowed to JSON-only when built.

</specifics>

<deferred>
## Deferred Ideas

- **`--format json`/`--format csv` full photo-list export** — raised during the photo
  listing discussion; explicitly deferred per D-08 because it duplicates the
  already-deferred v2 requirement `SYNC-06` ("--json machine-readable output for
  scripting"). Should be designed once, covering both `inspect` and `sync`, in whichever
  future phase picks up `SYNC-06` — not half-built for `inspect` alone in Phase 6.

### Reviewed Todos (not folded)
None — the one matching todo (`--debug` global promotion) was folded in, not deferred.

</deferred>

---

*Phase: 6-Inspect + Frame Resolution*
*Context gathered: 2026-07-06*
