# Project Research Summary

**Project:** Aura Frames Python Client — v2.0 Directory-to-Frame Sync
**Domain:** Directory-to-cloud-device sync CLI (photo-frame integration)
**Researched:** 2026-07-05
**Confidence:** HIGH for recommended approach and phase structure; MEDIUM on execution details until the Phase 2 live spike confirms diff design

## Executive Summary

This milestone adds a `sync` CLI that mirrors a local directory to an Aura frame. The core finding across all four research dimensions: the codebase **already has the necessary infrastructure** — `Asset.md5_hash`, `S3Client.get_md5()`, `FrameApi.get_assets()`, `FrameApi.remove_asset()` — so this isn't a build-from-scratch problem. The real challenge is that the write path (`select_asset → S3 → SQS confirm → batch_update`) and the delete primitive (`remove_asset`/`delete_asset`) have **never been exercised against the live API** in three years of this codebase's existence, unlike the read path which two prior milestones already proved live.

The recommended approach is safety-first, read-before-write: build the CLI skeleton and read-only commands (`status`, `inspect`) before touching any write path, use those read-only commands to live-verify assumptions the diff engine depends on (especially whether `md5_hash` is populated on read for pre-existing assets), then build the sync diff engine as pure dry-run logic before wiring up any destructive `--apply` execution. Dry-run should be a structural default (separate `compute_plan()`/`execute_plan()` functions), not an `if apply:` flag sprinkled through shared code.

The biggest risk is silent data loss through several compounding pitfalls: a base64-vs-hex MD5 hash-format mismatch would make every file look "changed" forever and trigger mass unwanted deletes; the two delete primitives (`remove_asset` soft vs. `delete_asset` hard) have very different blast radii and picking the wrong default is genuinely destructive; and a hardcoded frame ID baked into the existing SQS confirmation lookup means uploads to any frame other than the original author's test frame listen on the wrong queue. All three are addressed in the phase structure below before the destructive path is wired up.

## Key Findings

### Recommended Stack

No new runtime dependencies are required for the MVP. The codebase's existing minimal-dependency, pragmatic-modernization philosophy points toward stdlib tools over new frameworks; the two credible CLI options (stdlib `argparse` vs. `click`) are both defensible and can be settled at plan time rather than research time.

**Core technologies:**
- `argparse` (stdlib) or `click` (~8.4.2): CLI argument parsing and subcommand dispatch — argparse for zero new deps given only 3 flat subcommands; click if the group/subcommand ergonomics and `CliRunner`-based offline testing are valued enough to justify the one new dependency.
- `hashlib.md5` (stdlib): Content-hash comparison key — must match the existing `S3Client.get_md5()` convention exactly (base64-encoded MD5, not hex, not sha256).
- `FrameApi.get_assets()` (existing): Source of truth for the remote side of the diff — cursor-paginated, already hydrated into `Asset` models.
- `json` (stdlib, fallback only): A flat local manifest file (e.g. `.aura-sync/<frame_id>.json`) is needed **only if** live testing shows `md5_hash` is not populated on read for pre-existing (non-client-uploaded) assets.

**What NOT to add:** click/typer as an unquestioned default, sqlite or any database, shelling out to rsync/rclone, an async rewrite, a size/partial-hash proxy (no cheap remote byte-size field exists to make this worthwhile), or a second logging/config mechanism alongside the existing loguru/env-var setup.

### Expected Features

Dry-run-by-default, an explicit apply/confirm flag, a three-bucket plan output (upload/delete/unchanged), and non-zero exit codes on failure are universal conventions across rclone, aws s3 sync, rsync --delete, and gsutil — table stakes, not novel design. Content-hash-based matching (rather than filename or mtime) is both standard industry practice and, more importantly, **already how this specific API is built** — filenames get UUID-randomized on S3 upload, making filename-matching a dead end regardless of external convention.

**Must have (table stakes):**
- `status` — auth/config health check; zero new API risk since it only exercises the already-live-verified login/list path
- `inspect --frame <name|id>` — frame listing + metadata; same zero-new-risk profile as `status`
- `sync <dir> --frame <name|id>` dry-run mode — content-hash diff plan (upload/delete/unchanged), no mutation
- `sync ... --apply`/`--yes` — real execution; this is where the milestone's actual, never-before-verified write-path risk lives
- Per-action plan output and meaningful exit codes
- Frame targeting by name or ID, with explicit handling if a name isn't unique

**Should have (v2.0, lower priority):**
- Delete-count circuit breaker (`--max-delete`) once real usage patterns are understood

**Defer (v1.x or later):**
- `--json` machine-readable output (no scripting demand yet)
- Watch mode / background daemon sync (too risky to run unattended against an unverified write path)
- Bidirectional sync (explicitly out of scope per PROJECT.md)
- Storage/quota reporting in `status`/`inspect` — confirmed absent from both `Frame` and `User` models; report `Frame.num_assets` and `contributors` instead of fabricating a quota concept

### Architecture Approach

The CLI should be added as a new layer alongside — not inside — the existing `Aura` facade, keeping `main.py`'s existing facade-demo role untouched per PROJECT.md. Three new pieces: a CLI entrypoint, a pure sync-diffing engine, and small stateless utilities for frame resolution and hashing.

**Major components:**
1. `auraframes/cli.py` — CLI entrypoint (new `[project.scripts]` binary), owns argument parsing, output formatting, confirmation UX, and exit codes; dispatches into `Aura` and the sync engine.
2. `auraframes/sync.py` — sync-diffing engine as a `SyncPlan` dataclass plus a pure `compute_plan()` (no writes, consumes `FrameApi.get_assets()` + local directory hashes) and a separate `execute_plan()` (the only function allowed to call `Aura.upload_image`/`FrameApi.remove_asset`) — structurally enforces dry-run-by-default.
3. `auraframes/utils/frames.py` + `auraframes/utils/hashing.py` — pure helpers for "resolve a frame by name or ID" (client-side lookup over `FrameApi.get_frames()`, no new endpoint needed) and base64-MD5 hashing matching `S3Client.get_md5()`.

**Build order (safety-first, read-before-write):**
1. CLI skeleton + `status` (zero API risk)
2. `inspect` + frame resolution + **live spike: is `md5_hash` populated on read for pre-existing assets?** (zero write risk; this answer determines whether Phase 3 needs a local manifest fallback)
3. Sync-diffing engine, dry-run only — proves the diff algorithm against real frame data with no possibility of a write
4. Destructive execution path (`--apply`/`--yes` gated) — the only phase that touches `upload_image`/`remove_asset` for real

### Critical Pitfalls

1. **Hash-format mismatch (base64 vs. hex MD5)** — if the local hash isn't computed in the same base64 form as `Asset.md5_hash`, every file looks "changed" forever, triggering mass unwanted uploads/deletes. Avoid by standardizing on base64 explicitly and unit-testing hash equality against a real downloaded asset before the first live dry-run.
2. **`remove_asset` (soft, frame-scoped) vs. `delete_asset` (hard, unverified, possibly touches S3/Glacier) ambiguity** — defaulting to the wrong one is either falsely safe or genuinely destructive against the least-verified endpoint in the codebase. Avoid by defaulting sync's delete leg to `remove_asset` and live-verifying both before locking the choice.
3. **Hardcoded SQS frame ID in the existing upload confirmation path** — uploads to any frame other than the one hardcoded in `get_sqs()` listen on the wrong queue. Must be parameterized before sync can upload to an arbitrary frame.
4. **No transaction boundary across the 4-step upload pipeline** (`select_asset → S3 PUT → SQS confirm → batch_update`) — partial failures leave orphaned S3 objects or ghost asset stubs with no cleanup path. Avoid with a persisted manifest of steps reached and a reconciliation pass on restart.
5. **Non-deterministic `local_identifier`** (rolled fresh per attempt via `uuid.uuid4()`) breaks upload idempotency — a retried upload after a partial failure can't recognize its own prior attempt. Avoid by deriving the identifier deterministically from file path/content instead.

Full detail on all 8 identified pitfalls, including EXIF-rewrite-breaks-hash-matching and silent discarding of server-side comments/reactions on delete+recreate, is in `PITFALLS.md`.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: CLI Skeleton + Status
**Rationale:** Establishes packaging/entrypoint and exercises only the already-live-verified login/config path — zero new API risk, a safe place to shake out CLI plumbing.
**Delivers:** Working `status` command reporting config/auth health and account info.
**Addresses:** `status` from FEATURES.md.
**Avoids:** All pitfalls (read-only, no write path touched).

### Phase 2: Inspect + Frame Resolution + md5_hash Spike
**Rationale:** Extends the read-only CLI and is where the diff engine's core open question gets answered against the live API before Phase 3 is planned in detail.
**Delivers:** Working `inspect --frame <name|id>` command; a confirmed answer to whether `md5_hash` is populated on read for pre-existing assets.
**Uses:** `FrameApi.get_frames()`, `FrameApi.get_assets()` (existing, already live-verified read calls).
**Implements:** Frame-resolution-by-name-or-id utility.
**Research flags:** Critical live spike — if `md5_hash` isn't populated, Phase 3's design pivots to include a local manifest fallback.

### Phase 3: Sync-Diffing Engine (Dry-Run Only)
**Rationale:** Proves the diff algorithm against real frame data with zero possibility of a write — a safe playground to validate hash-format and EXIF-rewrite assumptions before anything destructive exists.
**Delivers:** Working `sync <dir> --frame <name|id>` that computes and prints a plan (upload/delete/unchanged) but never executes it.
**Implements:** `compute_plan()` pure function, `local_content_hash()` utility, `SyncPlan` dataclass.
**Research flags:** Validate hash format against a real downloaded asset (base64 MD5) and confirm whether `ExifWriter`'s own EXIF rewrite on download breaks hash matching for round-tripped files; add this as an explicit unit/live test before Phase 4.

### Phase 4: Destructive Execution (Upload + Delete Verification)
**Rationale:** The first live use of the write path — the actual, never-before-proven core value of this milestone — and must sequence last, after every read-only assumption above has been validated.
**Delivers:** Working `sync <dir> --frame <name|id> --apply`/`--yes`, with real upload and delete against a live test frame.
**Implements:** `execute_plan()`, parameterized `get_sqs(frame_id)`, deterministic `local_identifier` derivation.
**Research flags:** Critical spikes — single-file upload end-to-end (select_asset → S3 → batch_update → reconciliation), confirm SQS queue targeting is correct for a non-hardcoded frame, live-verify both `remove_asset` and `delete_asset` real behavior to lock in the safe default, verify partial-failure recovery (interrupt mid-sync, restart, confirm no duplicates/orphans), and extend the existing fail-loud error-checking pattern (already used on `get_assets`) to every write/delete call so failures are attributable to a specific file rather than a bare `number_failed` count.

### Phase Ordering Rationale

- Every phase before Phase 4 touches only already-live-verified read endpoints — this sequences all genuine new risk into a single, well-prepared final phase rather than spreading it across the milestone.
- Phase 2's live spike is a hard dependency for Phase 3's design (manifest-file fallback or not), so it must run before Phase 3 is planned in detail, not just before it's built.
- Phase 3's dry-run-only scope means the diff engine can be fully validated against real frame data with zero risk of the destructive pitfalls (hash mismatch, wrong delete primitive, hardcoded queue ID) actually firing — those get fixed as prerequisites to Phase 4, not discovered during it.

### Research Flags

Phases likely needing deeper research/live verification during planning:
- **Phase 2:** Whether `md5_hash` is populated on read for pre-existing assets — unverified from static code alone, directly shapes Phase 3's design.
- **Phase 4:** The real behavior of `remove_asset` vs. `delete_asset`, SQS queue parameterization, and partial-failure recovery — all touch the codebase's least-verified, highest-risk endpoints.

Phases with standard patterns (skip deep research during planning):
- **Phase 1:** Standard CLI skeleton/argument-parsing patterns, well-documented regardless of argparse/click choice.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Existing infrastructure (`md5_hash`, `get_md5()`) confirmed directly from source; CLI framework choice is a judgment call between two defensible options, not a gap. |
| Features | HIGH | Sync conventions (dry-run, apply-flag, exit codes, hash-matching) corroborated across rclone/AWS CLI/rsync/gsutil docs; Aura-specific findings (no quota field, UUID-randomized filenames) verified directly against source. |
| Architecture | HIGH | Integration points identified with concrete file:line references; build order explicitly sequences read-only work before the destructive path. |
| Pitfalls | HIGH | Codebase-derived findings (hardcoded SQS frame ID, non-deterministic identifiers, no write-path fail-loud checking) read directly from source; general destructive-sync conventions cross-checked against rclone/AWS CLI issues (MEDIUM, corroborating only). |

**Overall confidence:** HIGH for the recommended approach and phase structure; MEDIUM on execution specifics until the Phase 2 live spike confirms the diffing design.

### Gaps to Address

- **`md5_hash` population on read:** Unverified whether `GET /frames/{id}/assets.json` returns it for assets not uploaded by this client — resolve with a live query in Phase 2 before finalizing Phase 3's design.
- **`remove_asset` real behavior:** The docstring claiming it doesn't touch S3/Glacier is a 3-year-old, never-tested guess by the original author — resolve with a live test against a disposable asset in Phase 4.
- **Frame name uniqueness:** Cannot be verified without live API access; code defensively (treat a non-unique name match as an error requiring the ID instead).

## Sources

### Primary (HIGH confidence)
- This repository's source — `auraframes/models/asset.py`, `auraframes/models/frame.py`, `auraframes/models/user.py`, `auraframes/aura.py`, `auraframes/client.py`, `auraframes/api/frameApi.py`, `auraframes/api/assetApi.py`, `auraframes/aws/s3client.py`, `auraframes/aws/sqsclient.py`, `main.py`, `tests/offline.py` — read directly, not inferred.

### Secondary (MEDIUM confidence)
- rclone documentation and GitHub issues — dry-run/sync/delete conventions
- AWS CLI (`aws s3 sync`) documentation and issues — `--dryrun` conventions, partial-failure/idempotency guidance
- rsync man page — `--delete` semantics
- gsutil documentation — mirror/sync conventions

### Tertiary (LOW confidence)
- General click vs. typer comparison articles (web-sourced, cross-checked across two sources but not project-specific) — informs the CLI-framework judgment call only, not load-bearing for any other recommendation

---
*Research completed: 2026-07-05*
*Ready for roadmap: yes*
