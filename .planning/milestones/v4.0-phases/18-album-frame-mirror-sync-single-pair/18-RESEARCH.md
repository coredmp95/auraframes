# Phase 18 Research: Album → Frame Mirror Sync (Single Pair)

**Researched:** 2026-09-28 (inline research pass; no subagent runtime available —
per the established project convention from phases 16-17)
**Confidence:** high for reuse mapping (all primitives read in-tree), medium for
new-code specifics (concurrency + manifest details are agent-designed, flagged below).

## Summary

Phase 18's risk is NOT the frame write path — v2.0 already shipped and live-proved
the entire `compute_plan`/`execute_plan` engine (hide-by-default, WriteBudget, SQS
confirmations, 401 retry, chunked batched writes). The risk is the **pruned cache +
manifest invariant**: the moment steady-state disk drops below "whole album", the
directory walk becomes a lie (criterion 3), and everything hinges on rebuilding
demand from `enumerate_album` + a persisted manifest instead. The research below
maps every existing primitive Phase 18 reuses unchanged, designs the three new
pieces (cache, manifest, concurrent downloader) against REQUIREMENTS verbatim, and
flags the two genuine unknowns (write-confirmation latency, truncation detection).

## Validation Architecture

### 1. Reuse map — what exists and is proven (do NOT re-implement)

| Primitive | Where | Proof | Phase 18 use |
|---|---|---|---|
| `SyncPlan` (to_upload/to_delete/to_reshow/unchanged/already_hidden/frame_no_hash) | `auraframes/sync.py:287` | v2.0 phases 7-10, live | THE plan dataclass — no fork |
| `compute_plan(local_hashes, frame_assets, skipped_non_image)` | `sync.py:305` | pure, 2×2 table (present/gone × visible/hidden), offline-tested | Diff engine — fed a demand map built from listing+manifest, **never** a dir walk (CSE-03) |
| `execute_plan(plan, aura, frame_id, *, s3_client, sqs_client, removal_mode='hide', budget, progress, ...)` | `sync.py:469` | live, phases 8-11 | The only mutating call; `removal_mode='hide'` = CSE-06; WriteBudget pacing = CSE-01 |
| `_REMOVAL_PRIMITIVE['hide']` → `frame_api.exclude_asset` batch | `sync.py:398` | live phase 10 | Hide semantics unchanged |
| `WriteBudget(capacity, refill_per_min, path)` token bucket | `ratelimit.py:64` | live phase 9 | Same env-configured budget, same acquire-per-chunk |
| `S3Client.upload_file(data, extension) -> (filename, md5)` + `get_md5` | `aws/s3client.py:25` | live | The frame's md5 convention (base64 MD5) — cache files hashed with the SAME function |
| `enumerate_album(session, album_id, page_key=...)` → `AlbumListing` | `google/enumerate.py` | live phase 17 (24/24 + 1094 paginated + null-payload retry) | The Google read side; items carry `id/base_url/width/height/ts_ms` |
| `list_shared_albums` / `resolve_album` / `resolve_frame` | `google/enumerate.py`, `cli.py` | live phase 17 / v2.0 phase 6 | Resolution UX for the new verb (D-01) |
| `offline_aura` + `make_router` (`tests/offline.py`) | harness | phases 4-11 | Aura-side offline testing (frame assets, exclude_asset, batch_update, SQS) |
| `_GoogleRouter` (`tests/test_google_enumerate.py`) | harness | phase 17 | Google-side offline testing (batchexecute, Range GETs) — extended with `=d` FULL-download routes |
| CLI gates: `--apply` + `--yes` fail-closed non-interactive, tqdm on stderr, exit codes 0/1/2 | `cli.py:905` | v2.0 phase 8 | `google-sync --apply` inherits the exact gate shape (SAFE-02 gate joins it) |

### 2. New code — the three pieces (designed, not yet built)

**a) `auraframes/google/cache.py` (Google-side staging; downloads may be concurrent)**

- `download_to_cache(session, listing, cache_dir, *, workers=4, progress=None) -> CacheOutcome`
  — for every listing item **without a manifest entry** (D-07: manifest members skip
  entirely — steady state = zero downloads), fetch `{base_url}=d` and write the exact
  bytes to `<cache_dir>/<google_media_id>`; compute base64-MD5 **after** a
  length-verified download (Content-Length / expected-size check → SAFE-04: a failed
  or partial download is recorded failed, never hashed, never staged as good bytes).
- Bounded `concurrent.futures.ThreadPoolExecutor(max_workers=4)` (D-06) over the
  GoogleSession's httpx client (thread-safe per httpx docs; single connection pool).
  The function never touches the Aura client — concurrency structurally cannot reach
  frame writes (CSE-01).
- `prune_cache(cache_dir, manifest, keep_ids) -> int` — delete staged files whose
  `google_media_id` has a manifest entry after a confirmed apply (CSE-04); failed
  downloads are NOT pruned (next run retries them). Returns count for the report.
- Failure model: per-item try/except collecting `(google_media_id, error)` into
  `CacheOutcome.failed` — one bad download never blocks the album; the plan refuses
  to include failed items (SAFE-04) and reports them.

**b) `auraframes/google/manifest.py` (the sole memory that survives pruning)**

- `GoogleManifest` — JSON at `~/.config/auraframes/google-manifest.json` (D-04),
  `{google_media_id: {md5_hash, size_bytes, album_share_token, first_synced}}`.
  `load(path)`, `save(path)` (atomic temp+rename, 0600 like the vault's file
  discipline), `entry_for(google_media_id)`.
- Write timing (the load-bearing invariant): entries enter the manifest **only after
  `execute_plan` reports the upload confirmed** — the CLI maps
  `ExecutionResult.upload_succeeded` items (via `progress(kind, identifier, ok)` or
  the returned attribution) to their `google_media_id`s and persists post-apply.
  A manifest entry MEANS "this photo lives on the frame" (criterion 3's foundation).
  In a dry run, nothing is written anywhere.
- Privacy: ids + hashes + sizes only — no URLs with unguessable tokens, no cookies;
  the vault denylist is untouched.

**c) `auraframes/gsync.py` (the mirror engine — thin by design)**

- `build_demand(listing, manifest, cache_dir) -> tuple[dict[str, list[Path]], list[dict], int]`
  — returns the `local_hashes`-shaped demand map `{md5: [cache_path]}` built from
  listing+manifest (CSE-03: no cache walk), the skip list (manifest members with
  empty `CacheOutcome.downloads`), and the video count (D-10: metadata − photo
  count). Items whose md5 already exists in demand but whose file is not staged
  (manifest member, cache pruned) map to the manifest's recorded md5 with a
  **sentinel path absent** — `compute_plan` consumes the demand dict's KEYS, so
  demand is expressible without re-downloading: pass `local_hashes` with the md5
  keys and a path placeholder that `execute_plan` never touches because those items
  never appear in `to_upload` (frame already has the hash → unchanged/reshow only).
  ⚠ This detail is the subtlest new code; its test (second-run zero-upload with a
  pruned cache) is the plan's must_have truth.
- `run_google_sync(album_target, frame_arg, *, apply=False, yes=False, debug=False,
  session=None, aura=None, ...) -> int` — compose: resolve album+frame → SAFE-01
  checks → download (skip manifest members) → build demand → `compute_plan` → print
  plan → SAFE-02 gate → `--apply`+`--yes` fail-closed → `execute_plan` → persist
  manifest → prune → report. Dry-run default is structural (no mutating call exists
  before the gate).
- **Open unknown W1 — write confirmation latency:** `execute_plan` awaits SQS
  upload-confirmation signals (v2.0 design); the Google path uses the same
  `sqs_client` seam, so offline tests fake it and live behavior is already
  proven by v2.0. No new mechanism — but the plan print must show upload→confirm
  progress distinctly (CSE-08). **Open unknown W2 — truncation detection:** a
  "300-items-and-no-continuation" response on a 1000+ album would exhaust cleanly
  while lying. Mitigations planned: (a) cross-check `album_metadata_item_count`
  vs enumerated photo count and warn when metadata < photos (impossible shape),
  (b) SAFE-02's threshold catches the resulting mass-hide, (c) the null-payload
  retry already covers the observed transient. A cryptographic listing-count
  proof does not exist on Google's surface; SAFE-02 is the backstop (recorded
  as such, per fail-loud honesty).

**d) CLI verb — `aura-cli google-sync <album> --frame <frame>` (`run_google_sync`)**

- Flags: `--apply`, `--yes`, `--frame` (required — single pair), `--debug`.
  Reuses `resolve_album` (numbered ambiguity exit 2) + `resolve_frame`.
- Plan print: counts summary (`N to upload, N to re-show, N unchanged, N to hide,
  M already hidden, V videos skipped named via delta`) + per-item table in
  `run_google_album`'s redacted style.
- Exit codes: 0 (dry-run or aborted confirmation), 1 (failure/SAFE-01 abort),
  2 (usage/ambiguity) — v2.0 conventions.

### 3. Test strategy (TEST-02 everywhere; zero live network)

- Aura side: `offline_aura`/`make_router` — frame assets page, `exclude_asset`
  capture, `batch_update` acknowledgement, SQS confirmation fake (existing fakes
  cover all of it — no new Aura-side harness work beyond wiring).
- Google side: extend `_GoogleRouter` with `=d` full-download routes (bytes +
  Content-Length + a failure route for SAFE-04), and a metadata-count injection
  for the video delta.
- End-to-end offline: two-run proof (run 1: 3 uploads; prune cache; run 2: zero
  uploads, zero downloads) — criterion 3's exact shape, fully offline.
- Live UAT (operator-gated, after execution): criterion 4's two-run re-add/remove
  scenario on the real pair (the milestone's single most important live check).

### 4. Risks & flags

- **R1 (medium):** the `build_demand` sentinel-path subtlety above — mitigated by
  making the two-run test the tracer slice's acceptance, not a later task.
- **R2 (low):** httpx client thread-safety under 4 workers — standard usage
  (httpx.Client is thread-safe); workers injectable to 1 if live evidence ever
  says otherwise.
- **R3 (low):** manifest corruption mid-write — atomic temp+rename + 0600.
- **R4 (recorded):** W2 truncation has no cryptographic proof; SAFE-01/02 are the
  designed backstops, honestly labeled as such.

## RESEARCH COMPLETE
