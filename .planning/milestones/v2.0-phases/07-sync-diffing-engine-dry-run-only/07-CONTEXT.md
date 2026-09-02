# Phase 7: Sync-Diffing Engine (Dry-Run Only) - Context

**Gathered:** 2026-07-07
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers the **`sync <dir> --frame <name|id>` dry-run diff engine**: it
recursively scans a local directory for eligible image files, content-hashes them,
compares those hashes against the target frame's asset `md5_hash` values, and prints a
full plan of upload / delete / unchanged counts and items — executing nothing. There is
no `--apply`/`--yes` path in this phase; that destructive execution is Phase 8. This
phase also validates (once, live) that local hashing matches `S3Client.get_md5`'s
base64-MD5 convention, per SYNC-02.

In scope: directory scanning, content-hash computation, the diff/plan algorithm
(upload/delete/unchanged classification including duplicate handling), plan output
formatting, frame targeting (reusing Phase 6's `resolve_frame`), and the one-time live
hash-convention validation.

Out of scope: any write/mutating call (`select_asset`, `remove_asset`, `delete_asset`,
S3 upload) — Phase 8 entirely; video/non-image file diffing (Phase 6 confirmed
`md5_hash` is null for videos, so photos-only is sufficient per REQUIREMENTS.md); a
local-manifest fallback (only needed if video sync ever enters scope, which it doesn't
here).

</domain>

<decisions>
## Implementation Decisions

### Directory Scanning & File Eligibility
- **D-01:** Directory scan is **recursive** — walks all subdirectories, matching how
  people typically organize photo libraries (year/event folders) rather than requiring
  a flattened top-level directory.
- **D-02:** Only **image files (jpg/jpeg/png/heic)** are eligible for content-hash
  diffing. This matches Phase 6's live finding: `md5_hash` is populated only for photo
  assets on the frame, not videos — keeping the diff engine's core hash-matching
  assumption sound (no fallback needed, per REQUIREMENTS.md's Out of Scope note).
- **D-03:** Files found that aren't eligible (videos, `.DS_Store`, other non-image
  files) are **excluded from the plan but reported via a summary note** (e.g. "12
  non-photo files skipped") — not silently dropped, and not a hard error/abort. A real
  photo directory will likely contain stray non-image files; erroring on their presence
  would make the tool impractical.

### Content-Hash Matching & Duplicate Handling
- **D-04:** Matching between local files and frame assets is **content-hash-only** —
  there is no meaningful filename correlation to use. `S3Client.upload_file`
  (`auraframes/aws/s3client.py`) generates a random `{uuid4}{extension}` filename on
  upload, so `Asset.file_name` is never the original local filename. Any 1:1
  filename-based matching approach would be wrong by construction.
- **D-05:** Local files sharing an **identical content hash are deduped to one logical
  photo** before diffing. If two local files (e.g. copied into two folders) hash
  identically, they count as a single "want" for the plan — the tool does not propose
  uploading the same content twice just because it exists at two local paths.
- **D-06:** Frame-side assets are matched **count-for-count against local (multiset)**.
  If the frame already holds duplicate-content assets (same `md5_hash` on 2+ assets)
  and only one local file (post-dedupe, per D-05) justifies that hash, the surplus
  frame asset(s) become delete candidates. This is a deliberate asymmetry — local
  duplicates collapse to one "want," but frame duplicates are NOT automatically
  protected as a group; only as many copies as local demand survive the diff.

### Plan Output & Delete-List Identification
- **D-07:** The plan output lists **every planned upload/delete/unchanged item in
  full** — no truncation, unlike `inspect`'s first-N default (Phase 6 D-06). Rationale
  (explicit from discussion): Phase 8's `--apply` will execute exactly this plan, and
  deletions are irreversible, so the user must be able to review every item before that
  ever runs — a sampled/truncated view is unacceptable for a destructive preview.
- **D-08:** A delete candidate (a frame photo with no matching local file) is
  identified in the plan by **asset id + `taken_at` date** (e.g. `- abc123 (taken
  2024-03-11)`) — reusing fields `inspect` already prints (`asset.id`,
  `asset.taken_at_dt`). No hash prefix is shown; id + date is enough for the user to
  recognize/cross-reference the photo without exposing the meaningless UUID filename.

### Hash-Convention Validation (SYNC-02, success criterion 3)
- **D-09:** Validating that local base64-MD5 hashing matches `S3Client.get_md5`'s exact
  convention is a **one-time live check performed during build, documented afterward**
  — the same methodology as Phase 6's `md5_hash` live spike (06-CONTEXT.md D-12/D-13):
  download one real asset, hash its bytes locally, compare to `Asset.md5_hash`, confirm
  equality, and record the result (not a permanent automated regression test/fixture).

### Claude's Discretion
- Exact plan output line wording/formatting, following the full-listing requirement of
  D-07 and Phase 5's concise-summary-no-table style (D-05) for the surrounding counts.
- Whether the scan/hash/diff logic lives in a new helper module (e.g.
  `auraframes/sync.py`) or inline in `auraframes/cli.py` — small enough either way at
  this phase's scope, following the precedent set by `resolve_frame`'s placement.
- Exact image extension set if the test directory surfaces formats beyond
  jpg/jpeg/png/heic — as long as videos and other non-image types stay excluded per
  D-02/D-03.
- Where the one-time hash-validation live check gets documented (STATE.md/PROJECT.md
  per Phase 6's precedent, or a dedicated note in the phase's own artifacts).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project & milestone scope
- `.planning/PROJECT.md` — Current Milestone section (`sync` target features: full
  mirror, content-hash diffing, dry-run default); Context section's Phase 6 entry
  documents the live `md5_hash` finding (populated for photos, null for videos) that
  directly justifies D-02/D-03's images-only scope.
- `.planning/REQUIREMENTS.md` — **SYNC-01** (dry-run full-mirror plan via content-hash
  diffing) and **SYNC-02** (base64-MD5 convention matching `S3Client.get_md5`,
  validated against a real downloaded asset) are this phase's requirements. The Out of
  Scope table's "local manifest/state file" row stays inapplicable — `md5_hash` IS
  populated for the photos this phase diffs.
- `.planning/ROADMAP.md` §"Phase 7: Sync-Diffing Engine (Dry-Run Only)" — goal + the 3
  success criteria.
- `.planning/STATE.md` Blockers/Concerns — "Hash-format mismatch risk (Phase 7)" entry
  is the direct motivation for D-09's validation step.

### Prior phase context (patterns to follow)
- `.planning/phases/06-inspect-frame-resolution/06-CONTEXT.md` — D-12/D-13 (live spike
  methodology: piggyback on real usage, document in STATE.md/PROJECT.md, no throwaway
  script) is the direct precedent for D-09 here. D-06 (photo-list truncation) is
  explicitly **not** carried forward for `sync`'s plan output — see D-07's deliberate
  deviation and rationale.
- `.planning/phases/05-cli-skeleton-status/05-CONTEXT.md` — D-01 (argparse, no new
  runtime dependency), D-08 (fail-loud, non-zero exit convention) carry forward
  unchanged into this phase.

### Codebase analysis (structure/architecture already mapped)
- `.planning/codebase/ARCHITECTURE.md` — Image Upload Flow section documents
  `S3Client.upload_file`'s UUID-filename generation — the direct evidence behind D-04's
  content-hash-only matching decision; Facade pattern confirms new orchestration
  belongs at the CLI/Aura layer, not inside `*Api` classes.
- `.planning/codebase/STRUCTURE.md` — naming conventions, "Where to Add New Code"
  guidance.
- `.planning/codebase/STACK.md` — confirms no existing directory-scanning/hashing
  dependency; stdlib `hashlib`/`pathlib` is the natural fit, matching
  `S3Client.get_md5`'s existing `hashlib.md5` usage (no new runtime dependency needed).

### Files that will change
- `auraframes/cli.py` — add a `sync` subparser (positional `dir` + `--frame`, following
  `inspect`'s `--frame` pattern) and handler; likely a new diff/scan helper following
  `resolve_frame`'s pure-function shape.
- `auraframes/aws/s3client.py` — `get_md5(data)` is reused as-is
  (`base64.b64encode(hashlib.md5(data).digest()).decode('utf-8')`) for local hashing —
  no changes expected, just imported and called from the new sync code.
- `auraframes/models/asset.py` — `Asset.md5_hash: Optional[str]` reused as-is for the
  frame side of the diff — no changes expected.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `S3Client.get_md5(data)` (`auraframes/aws/s3client.py:14`) — the canonical
  base64-MD5 convention (`base64.b64encode(hashlib.md5(data).digest()).decode('utf-8')`).
  Local hashing must call this exact function (or byte-identical logic) per SYNC-02 —
  not reimplement it independently, to avoid subtle format drift.
- `Aura.get_all_assets(frame_id)` (`auraframes/aura.py`) — already paginates all frame
  assets; sync's frame-side of the diff reuses this exactly as `inspect` does.
- `resolve_frame()` / `FrameResolution` (`auraframes/cli.py`) — Phase 6's frame
  targeting by name/id is reused as-is for `sync --frame`; no new resolution logic
  needed.
- `run_status()`/`run_inspect()`'s `int`-return, never-`sys.exit`-directly pattern
  (`auraframes/cli.py`) — `run_sync()` should follow the same convention for offline
  testability via `capsys`.
- `Asset.md5_hash: Optional[str]` (`auraframes/models/asset.py:65`) — already modeled;
  the frame side of the diff reads this field directly, no schema change needed.

### Established Patterns
- Facade-only orchestration — new diff/scan logic is CLI-layer or a small helper
  module, not added to `*Api` classes (`STRUCTURE.md`).
- Pure-function pattern for resolution logic — `resolve_frame(target, frames) ->
  FrameResolution` takes data in, returns a result dataclass, no I/O. The hash-diff
  computation should follow the same shape (e.g. `compute_plan(local_hashes,
  frame_assets) -> SyncPlan`, no I/O) for offline testability — this also directly
  realizes PROJECT.md's key decision that dry-run is structurally enforced via separate
  `compute_plan()`/`execute_plan()` functions, not an `if apply:` flag.
- Fail-loud, non-zero exit convention (Phase 5 D-08, Phase 6 D-05) carries forward.

### Integration Points
- `auraframes/cli.py`'s `build_parser()` needs a new `sync` subparser (positional `dir`
  argument + `--frame`, following `inspect`'s `--frame` flag pattern) and a branch in
  `main()`.
- No existing local file scanning/hashing code exists anywhere in the codebase — net
  new for Phase 7, mirroring how Phase 6 noted frame-resolution was net-new there.

</code_context>

<specifics>
## Specific Ideas

- The user's explicit design split for duplicate handling: local-side duplicates
  dedupe to **one logical want** (never propose uploading identical content twice),
  while frame-side duplicates are matched **count-for-count (multiset)** so genuine
  extra copies on the frame become delete candidates. This is an intentional asymmetry,
  not an oversight — the planner/executor must not accidentally symmetrize it (e.g. by
  also deduping the frame side, which would hide real duplicate cleanup opportunities).
- The user's explicit rationale for the full (non-truncated) plan listing: Phase 8's
  `--apply` will execute exactly what Phase 7 prints, and deletions are irreversible —
  so a sampled/truncated view was rejected specifically on safety grounds, not just
  preference.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. No scope-creep items arose; all four
discussed areas were implementation decisions for `sync`'s dry-run diff engine itself.

### Reviewed Todos (not folded)
None — no pending todos matched Phase 7 (`todo.match-phase` returned zero matches).

</deferred>

---

*Phase: 7-Sync-Diffing Engine (Dry-Run Only)*
*Context gathered: 2026-07-07*
