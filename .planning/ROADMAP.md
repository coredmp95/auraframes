# Roadmap: Aura Frames Python Client — Revive & Verify

## Milestones

- ✅ **v1.0 Revive & Verify** — Phases 1-3 (shipped 2026-06-30)
- ✅ **v1.1 Client Transport Seam** — Phase 4 (shipped 2026-07-05)
- 🚧 **v2.0 Directory-to-Frame Sync** — Phases 5-8 (in progress) — a `sync`/`inspect`/`status` CLI that mirrors a local photo directory to a live Aura frame, verifying the write/delete path live for the first time

## Phases

<details>
<summary>✅ v1.0 Revive & Verify (Phases 1-3) — SHIPPED 2026-06-30</summary>

Full detail archived in [`milestones/v1.0-ROADMAP.md`](./milestones/v1.0-ROADMAP.md).

- [x] Phase 1: Toolchain Revival (2/2 plans) — completed 2026-06-29 — installs/imports on Python 3.14 via `uv`, model layer on pydantic v2
- [x] Phase 2: Live Read-Path Verification (2/2 plans) — completed 2026-06-29 — login, list frames, paginated asset fetch, image download with EXIF verified live
- [x] Phase 3: Run Docs & Verification Report (1/1 plan) — completed 2026-06-29 — documented `uv` setup/run + repo-root VERIFICATION-REPORT.md

</details>

<details>
<summary>✅ v1.1 Client Transport Seam (Phase 4) — SHIPPED 2026-07-05</summary>

Full detail archived in [`milestones/v1.1-ROADMAP.md`](./milestones/v1.1-ROADMAP.md).

- [x] Phase 4: Client Transport Seam for Offline Testability (3/3 plans) — completed 2026-07-05 — additive `Client(transport=...)`/`Aura(client=...)` DI seam, reusable offline `httpx.MockTransport` harness + sanitized fixtures, lifting most of `test_read_path.py` off the live network

</details>

### 🚧 v2.0 Directory-to-Frame Sync (Phases 5-8)

Safety-first, read-before-write: every phase before Phase 8 touches only already-live-verified read endpoints, sequencing all genuine new write-path risk into a single, well-prepared final phase.

- [x] **Phase 5: CLI Skeleton + Status** — Runnable CLI entrypoint whose `status` command reports auth/config health and account frames (zero API risk) (completed 2026-07-06)
- [x] **Phase 6: Inspect + Frame Resolution** — `inspect --frame <name|id>` lists a frame's photos + metadata, resolves frames by name or ID, and answers the live `md5_hash`-on-read question that shapes Phase 7 (zero write risk) (completed 2026-07-07)
- [x] **Phase 7: Sync-Diffing Engine (Dry-Run Only)** — `sync <dir> --frame <name|id>` computes and prints an upload/delete/unchanged plan from content-hash diffing, executing nothing (no destructive path exists yet) (completed 2026-07-07)
- [x] **Phase 8: Destructive Execution (Upload + Delete Verification)** — `sync ... --apply`/`--yes` runs the plan for real, proving the upload and delete write paths live for the first time (completed 2026-07-08)

## Phase Details

### Phase 5: CLI Skeleton + Status

**Goal**: Users have a runnable CLI whose `status` command reports whether they are configured and authenticated, exercising only the already-live-verified login/list path.
**Depends on**: Nothing (first phase of the milestone; builds on shipped read path)
**Requirements**: CLI-01, CLI-02
**Success Criteria** (what must be TRUE):

  1. User can invoke the CLI as a packaged command distinct from `main.py` and see usage/help output
  2. Running `status` reports whether `AURA_EMAIL`/`AURA_PASSWORD` are set
  3. Running `status` attempts login and reports success/failure plus which account authenticated
  4. `status` lists the frames on the authenticated account

**Plans**: 2/2 plans complete

- [x] 05-01-PLAN.md — Packaged `aura-cli` entrypoint + argparse skeleton + `status` command (config health, login, frame listing) with offline tests
- [x] 05-02-PLAN.md — Gap closure: suppress verbose loguru stderr in `status` by default, add opt-in `--debug` flag, add stderr assertions to tests

### Phase 6: Inspect + Frame Resolution

**Goal**: Users can inspect a specific frame's contents and metadata by name or ID, and the diff engine's core `md5_hash` assumption is confirmed against the live API before Phase 7 is designed.
**Depends on**: Phase 5
**Requirements**: CLI-03, CLI-04
**Success Criteria** (what must be TRUE):

  1. User can run `inspect --frame <name>` or `--frame <id>` and see the frame's photos (id / filename / date)
  2. `inspect` shows frame metadata: name, owner, contributor count, and asset count
  3. Targeting a frame by an ambiguous name produces a clear error directing the user to use the ID instead
  4. It is confirmed live whether `md5_hash` is populated on read for pre-existing (non-client-uploaded) assets, documented as the input to Phase 7's design

**Plans**: 2/2 plans complete
**Wave 1**

- [x] 06-01-PLAN.md — `inspect` subcommand: frame resolution (name substring + id fallback), photo + metadata display, root-level `--debug` promotion, full offline test coverage

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 06-02-PLAN.md — Live `md5_hash` spike via `inspect --debug`; document the Phase 7 design input in STATE.md/PROJECT.md; close the folded `--debug` todo

### Phase 7: Sync-Diffing Engine (Dry-Run Only)

**Goal**: Users can preview a full-mirror sync plan for a directory against a frame, with zero possibility of a write.
**Depends on**: Phase 6 (its live `md5_hash` finding determines whether a local-manifest fallback is needed)
**Requirements**: SYNC-01, SYNC-02
**Success Criteria** (what must be TRUE):

  1. Running `sync <dir> --frame <name|id>` prints a plan of upload / delete / unchanged with counts and executes nothing (dry-run is the default, structurally enforced)
  2. The plan correctly classifies files by comparing local content-hashes to frame asset `md5_hash` values
  3. Local hashing uses the same base64-MD5 convention as `S3Client.get_md5`, validated equal against a real downloaded asset before diffing is trusted

**Plans**: 3/3 plans complete

**Wave 1**

- [x] 07-01-PLAN.md — Pure sync engine (`auraframes/sync.py`): recursive image scanner + local base64-MD5 hashing + `compute_plan` diff (upload/delete/unchanged, local-dedup vs frame-multiset, video-safety) with offline unit tests

**Wave 2** *(blocked on Wave 1)*

- [x] 07-02-PLAN.md — CLI `sync <dir> --frame <name|id>` subcommand + `run_sync` handler + full untruncated dry-run plan output (D-07/D-08) with offline CLI tests

**Wave 3** *(blocked on Wave 2)*

- [x] 07-03-PLAN.md — One-time LIVE hash-convention validation (SYNC-02, D-09): confirm local `get_md5` equals frame `md5_hash`, documented in STATE.md/PROJECT.md

### Phase 8: Destructive Execution (Upload + Delete Verification)

**Goal**: Users can apply a sync plan for real — uploading new photos and removing gone-locally photos — with the upload and delete write paths proven live against a test frame for the first time.
**Depends on**: Phase 7
**Requirements**: SYNC-03, SYNC-04, WRITE-01, WRITE-02, WRITE-03, WRITE-04, WRITE-05
**Success Criteria** (what must be TRUE):

  1. `sync ... --apply`/`--yes` uploads new local files to the targeted frame, verified visually and via `inspect` (the `select_asset → S3 → SQS → batch_update` round-trip works live)
  2. `sync ... --apply` removes frame photos no longer present locally via `remove_asset`, with both `remove_asset` and `delete_asset` real behavior confirmed live to lock in the safe default
  3. Uploads target the correct frame's SQS confirmation queue regardless of which frame is chosen (the hardcoded frame ID in `get_sqs` is fixed)
  4. Write/delete API errors raise loudly and are attributable to a specific file, and the CLI exits non-zero on any execution failure
  5. Plan output lists upload / delete / unchanged counts before applying

**Plans**: 4/4 plans complete

**Wave 1**

- [x] 08-01-PLAN.md — Foundations: AssetPartial model + fail-loud write/delete endpoints (WRITE-05) + get_sqs(frame_id) parameterization (WRITE-04)

**Wave 2** *(blocked on Wave 1)*

- [x] 08-02-PLAN.md — `execute_plan()` mutating engine in sync.py: upload round-trip + remove_asset deletes, continue-past-failure, injected AWS clients (SYNC-03/04)

**Wave 3** *(blocked on Wave 2)*

- [x] 08-03-PLAN.md — CLI `sync --apply`/`--yes` confirmation gate (D-01–D-04) + execute wiring + separated summary + non-zero exit (SYNC-03/04)

**Wave 4** *(blocked on Wave 3)*

- [x] 08-04-PLAN.md — Live verification checkpoints: upload round-trip (WRITE-01), remove_asset (WRITE-02), delete_asset blast-radius probe on a disposable asset (WRITE-03)

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Toolchain Revival | v1.0 | 2/2 | Complete | 2026-06-29 |
| 2. Live Read-Path Verification | v1.0 | 2/2 | Complete | 2026-06-29 |
| 3. Run Docs & Verification Report | v1.0 | 1/1 | Complete | 2026-06-29 |
| 4. Client Transport Seam for Offline Testability | v1.1 | 3/3 | Complete | 2026-07-05 |
| 5. CLI Skeleton + Status | v2.0 | 2/2 | Complete    | 2026-07-06 |
| 6. Inspect + Frame Resolution | v2.0 | 2/2 | Complete    | 2026-07-07 |
| 7. Sync-Diffing Engine (Dry-Run Only) | v2.0 | 3/3 | Complete    | 2026-07-07 |
| 8. Destructive Execution (Upload + Delete Verification) | v2.0 | 4/4 | Complete   | 2026-07-08 |

## Backlog

_No items currently in backlog._
