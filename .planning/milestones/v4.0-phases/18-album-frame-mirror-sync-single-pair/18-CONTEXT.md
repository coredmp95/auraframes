# Phase 18: Album → Frame Mirror Sync (Single Pair) - Context

**Gathered:** 2026-09-28
**Status:** Ready for planning
**Provenance:** compiled by the planning agent from ROADMAP §Phase 18, REQUIREMENTS
CSE-01..08/SAFE-01..04 verbatim, the signed `16-DECISION-RECORD.md`, and the
`17-CONTEXT.md` deferred items (cache/manifest/mirror were explicitly pushed here).
The operator chose "compile without a discuss session" at the 2026-09-28 planning
checkpoint; every decision below traces to one of those sources or is marked
agent-default.

<domain>
## Phase Boundary

One Google album (selected via Phase 17's `google-album` surface) mirrors onto one
Aura frame through the **local pipeline**: concurrent Google-side downloads into a
pruned local cache, a persistent `google_media_id → md5_hash` manifest that survives
pruning, a structurally-dry-run plan, and hide-by-default mirror execution reusing
v2.0's `compute_plan`/`execute_plan` unchanged underneath.

Delivers: the cache+manifest layer, the concurrent downloader, the plan-computing
engine, the `google-sync` CLI verb (dry-run default, `--apply` gated), mirror safety
gates (SAFE-01/02/03/04), video-skip accounting, progress reporting. Does NOT
deliver: many-to-many mapping (GSF-01), scheduled/unattended sync (GSF-02),
real-deletion exposure on the Google verb (v2.0's `sync` keeps those gates), video
sync (out of scope, carried replan decision).

</domain>

<decisions>
## Implementation Decisions

### CLI surface
- **D-01:** Dedicated verb **`aura-cli google-sync <album> --frame <frame>`** —
  album resolved via Phase 17's `resolve_album` (name/link/id, numbered ambiguity),
  frame via the existing `resolve_frame` (same UX). Mirrors 17-CONTEXT D-01's
  "separate from `sync` for readability" reasoning. Dry-run by default; `--apply`
  executes; `--yes` skips confirmation (fail closed non-interactive without it,
  v2.0 convention). — *Reversibility: reversible — new subcommand.*
- **D-02:** Real deletion is **not exposed** on `google-sync` this phase: the only
  removal mode wired is `hide` (CSE-06's exact requirement). SAFE-03 stays
  satisfied because v2.0's `sync` keeps its `--delete`/`--hard-delete`
  exact-count-gated surface untouched, and the Google verb adds no deletion
  surface. Exposing delete tiers on google-sync is a future decision, not an
  omission. — *agent-default from CSE-06 verbatim text.*

### Cache & manifest
- **D-03:** Cache root **`~/.config/auraframes/google-cache/<album_share_token>/<google_media_id>`**;
  file content is the **exact `=d` bytes** (never re-encoded — LGS-06/Phase-11
  data_uti lessons: the bytes decide). The cache is a *staging area*: entries are
  pruned after upload confirmation; nothing in the pipeline ever diffs by walking
  it (CSE-03). — *agent-default on the exact path (mirrors the vault's
  `~/.config/auraframes/` home); the no-walk rule is REQUIREMENTS verbatim.*
- **D-04:** Manifest **`~/.config/auraframes/google-manifest.json`**: a JSON map
  `google_media_id → {md5_hash, size_bytes, album_share_token, first_synced}`.
  Contains **no secrets** (ids + hashes only — the cookie vault's denylist is not
  implicated). Entries are written **only after execute_plan confirms the upload**
  (SQS-backed), so a manifest entry means "this photo lives on the frame". The
  manifest is the sole memory that survives pruning (CSE-02/CSE-04). — *agent-default
  on single-file-per-account (mono-account, 17-CONTEXT D-04); per-album sharding
  deferred with GSF-01.*

### Sync engine shape
- **D-05:** The mirror engine lives in **`auraframes/gsync.py`** (mirrors
  `sync.py`'s module shape); Google-side storage lives in
  **`auraframes/google/cache.py`** + **`auraframes/google/manifest.py`**. The plan
  is computed by building the `local_hashes` demand map from **album listing +
  manifest** and calling v2.0's **`compute_plan` unchanged**; execution calls
  **`execute_plan` unchanged** (`removal_mode='hide'`, WriteBudget wired). No fork
  of the diff logic. — *agent-default on module placement; reuse-not-fork is
  ROADMAP Notes verbatim.*
- **D-06:** Google-side downloads run on a **bounded thread pool (4 workers,
  injectable)** over the Phase-17 session's httpx client; every write to the frame
  stays inside synchronous, WriteBudget-paced `execute_plan` (CSE-01 verbatim).
  Concurrency never crosses the Aura client seam. — *agent-default on worker count.*
- **D-07:** md5 values enter the manifest **only from verified bytes**: a cache
  file's md5 is computed after a complete, length-verified download (SAFE-04);
  items already in the manifest skip download entirely (steady state = zero
  downloads, zero cache residency). Frame-side `md5_hash` equality remains the
  only diff key (v2.0 convention). — *REQUIREMENTS CSE/SAFE verbatim + LGS-06
  fidelity proof.*

### Safety gates
- **D-08:** SAFE-01 aborts (named error, exit 1, no plan emitted) on: empty
  `listing.items`; `exhausted_cleanly=False`; **or an empty frame asset listing**
  (the get_assets drift observed live in 16-03 — same lesson as reconcile's
  T-11-11). — *ROADMAP criterion 5 verbatim + 16-LIVE-FINDINGS evidence.*
- **D-09:** SAFE-02 threshold: a plan whose hide/removal count exceeds **20% of
  the frame's hash-bearing assets** (constant
  `GOOGLE_SYNC_REMOVAL_THRESHOLD = 0.2`, env-overridable
  `AURA_GOOGLE_SYNC_REMOVAL_THRESHOLD`) requires an explicit y/N confirmation
  echoing the frame name+id and both counts; non-interactive without `--yes`
  fails closed. — *agent-default on the 20% number; the gate itself is criterion 5
  verbatim.*

### Videos
- **D-10:** Skipped videos are **counted and named via the metadata delta**:
  `videos_skipped = album_metadata_item_count − enumerated_photo_count` (the
  live-proven interpretation: "Nous" 1096 metadata vs 1094 photos = 2 videos).
  No video walker is built (replan decision: videos out of scope). The plan print
  reports the count explicitly, never silently (CSE-07). — *17-LIVE-FINDINGS
  evidence; agent-default on the delta method.*

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `.planning/phases/16-local-mechanism-spike-decision/16-DECISION-RECORD.md` — the
  mechanism gate + LGS-06 fidelity MATCH (md5 diffability is Phase 18's foundation)
- `.planning/REQUIREMENTS.md` — CSE-01..08, SAFE-01..04 verbatim (the phase's contract)
- `.planning/ROADMAP.md` §Phase 18 — success criteria 1-5 (criterion 3 is load-bearing)
- `auraframes/sync.py` — `compute_plan` (pure 2×2 classifier), `execute_plan`
  (single mutating entry, `removal_mode='hide'` default, WriteBudget/SQS/401-retry),
  `SyncPlan`/`ExecutionResult` dataclasses, `_prep_upload` (md5 = base64 MD5 of bytes)
- `auraframes/ratelimit.py` — `WriteBudget(capacity, refill_per_min, path)` persisted token bucket
- `auraframes/google/enumerate.py` — `enumerate_album` (AlbumListing items carry
  id/base_url/width/height/ts_ms; fail-loud; the null-payload bounded retry)
- `auraframes/google/client.py` — `GoogleSession.from_vault()`, httpx client seam
- `auraframes/cli.py` — `run_sync` (--apply/--yes fail-closed gate, tqdm on stderr,
  exit codes), `resolve_frame`, `run_google_album`/`resolve_album` (Phase 17)
- `tests/offline.py` — `offline_aura`/`make_router` harness; `tests/test_google_enumerate.py`
  `_GoogleRouter` — the two offline harnesses TEST-02 requires combining

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `compute_plan(local_hashes, frame_assets, skipped_non_image)` — the whole 2×2
  mirror classification (upload/reshow/hide/already-hidden) exists and is pure;
  Phase 18 feeds it a demand map built from listing+manifest instead of a dir walk
- `execute_plan` — uploads→reshows→hides ordering, chunked batched writes,
  WriteBudget/geo gates, 401 verify-then-retry, consecutive-failure abort,
  `progress(kind, identifier, ok)` reporter — all already live-proven
- `S3Client.upload_file(data, extension) -> (filename, md5)` + `get_md5` — the
  frame's md5 convention (base64 MD5), reused for cache-file hashing
- `enumerate_album`/`measure_disk_weight`/`list_shared_albums` — the entire
  Google read side, offline-tested over `_GoogleRouter`
- `resolve_frame`/`resolve_album` — both resolution UXes for the new verb

### Established Patterns
- Dry-run structural default: pure compute, mutating path only in execute_plan
- Content-hash diffing on `md5_hash`, never filename; videos have null frame hashes
- Fail-loud + redaction (`redact_link`) at every Google print site
- pytest offline: MockTransport routers, injectable sleep/clock/budget seams
- CLI exit codes: 0 (dry-run/aborted confirm), 1 (failure), 2 (usage/ambiguity)

### Integration Points
- `google-sync` composes: GoogleSession.from_vault → enumerate_album →
  cache/manifest → compute_plan → print → (--apply) execute_plan → prune+persist
- The manifest write happens after execute_plan returns; its per-item attribution
  (upload_succeeded/failed) drives which entries are safe to persist

</code_context>

<specifics>
## Specific Ideas

- Steady-state run (nothing new, nothing removed): zero Google downloads, zero
  cache bytes, one enumerate_album + one get_all_assets — that is criterion 3's
  proof shape.
- The plan print should reuse `run_google_album`'s table style for the item list
  and run_sync's plan summary style for counts (muscle memory).
- Prune = delete cache files whose google_media_id has a manifest entry after a
  confirmed apply; in-flight failures are kept for the next run's retry.
- Cache directory keyed by album share token keeps two albums' stagings isolated
  ahead of GSF-01 without building mapping now.

</specifics>

<deferred>
## Deferred Ideas

- `--delete`/`--hard-delete` exposure on google-sync (SAFE-03 keeps them v2.0-only)
- Many-to-many album↔frame TOML mapping, shared account-wide WriteBudget (GSF-01)
- Scheduled/unattended sync (GSF-02); periodic re-auth cadence measurement
- Video sync (`=dv` walk) — out of scope by replan decision
- Manifest compaction/orphan GC (entries for photos no longer in any synced album)

</deferred>

---

*Phase: 18-Album → Frame Mirror Sync (Single Pair)*
*Context gathered: 2026-09-28*
