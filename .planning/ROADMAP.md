# Roadmap: Aura Frames Python Client — Revive & Verify

## Milestones

- ✅ **v1.0 Revive & Verify** — Phases 1-3 (shipped 2026-06-30) — the ~3-year-old codebase runs again on Python 3.14/`uv`/pydantic v2, read path proven live
- ✅ **v1.1 Client Transport Seam** — Phase 4 (shipped 2026-07-05) — additive DI seam + offline `httpx.MockTransport` harness, lifting most read-path tests off the live network
- ✅ **v2.0 Directory-to-Frame Sync** — Phases 5-10 (shipped 2026-09-02) — a real `status`/`inspect`/`sync`/`push` CLI that mirrors a local photo directory to a live Aura frame, with the write path proven live for the first time and hide-by-default removal
- 🔵 **v3.0 Google Photos Album Sync** — Phases 11-15 (in progress, started 2026-09-03) — make the proven write path boringly reliable, then put a Google Photos album behind it, selected at album granularity and mirrored headlessly

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

<details>
<summary>✅ v2.0 Directory-to-Frame Sync (Phases 5-10) — SHIPPED 2026-09-02</summary>

Full detail archived in [`milestones/v2.0-ROADMAP.md`](./milestones/v2.0-ROADMAP.md).
Requirements archived in [`milestones/v2.0-REQUIREMENTS.md`](./milestones/v2.0-REQUIREMENTS.md).

Safety-first, read-before-write: every phase before Phase 8 touched only already-live-verified read endpoints, sequencing all genuine new write-path risk into a single, well-prepared phase.

- [x] Phase 5: CLI Skeleton + Status (2/2 plans) — completed 2026-07-06 — packaged `aura-cli` entrypoint, `status` reports config/auth health and account frames, quiet by default with opt-in `--debug`
- [x] Phase 6: Inspect + Frame Resolution (2/2 plans) — completed 2026-07-07 — `inspect --frame <name|id>` with name-substring/exact-ID resolution; live spike answered the `md5_hash`-on-read question that shaped Phase 7
- [x] Phase 7: Sync-Diffing Engine (Dry-Run Only) (3/3 plans) — completed 2026-07-07 — `compute_plan()` content-hash diffing with structurally no reachable mutating primitive; hash format confirmed byte-identical live
- [x] Phase 8: Destructive Execution (Upload + Delete Verification) (4/4 plans) — completed 2026-07-08 — `--apply`/`--yes` runs the plan for real; upload round-trip, `remove_asset` and `delete_asset` blast radius all proven live for the first time
- [x] Phase 9: Proactive Write Rate-Limiter & Geo Guard (2/2 plans) — completed 2026-07-09 — `auraframes/ratelimit.py`: persisted `WriteBudget` token bucket + fail-open `check_geo` pre-flight, wired as the default for every `--apply`
- [x] Phase 10: Hide-instead-of-delete sync mode (4/4 plans) — completed 2026-08-25 — `sync --apply` hides removed photos via `exclude_asset` and re-shows restored ones; the two destructive tiers are opt-in and count-gated

**Milestone outcome:** 28/28 requirements complete, all 6 phases verified, closed as a verified closeout with 0 open artifacts. Live evidence corrected two working theories along the way: the visibility flag lives in `asset_settings[asset_id].selected` (not `Asset.selected`), and the write "geofence" was disproven — the 401 lockout is transient auth-token expiry.

**Known defects carried forward (open, non-blocking):** intermittent write 401s clearing on retry (~4 in 10 live runs); 58 unremovable placeholder rows from incomplete `select_asset` calls; `test_read_03_pagination` asserting `drained == num_assets`, two counts the server does not keep consistent.

</details>

### 🔵 v3.0 Google Photos Album Sync (Phases 11-15) — IN PROGRESS

Requirements: [`REQUIREMENTS.md`](./REQUIREMENTS.md) — 43 requirements, all mapped below.
Research: [`research/`](./research/) — `SUMMARY.md`, `ARCHITECTURE.md`, `ALBUM-ACCESS.md`, `BROWSER-AUTOMATION.md`, `PITFALLS.md`.

Two locked sequencing decisions shape this roadmap. **Reliability comes first** (user decision): every later phase's live testing otherwise runs through a ~4-in-10 spurious-401 noise floor that did not need to be there. **The mechanism spike gates every Google implementation phase**: Google permanently withdrew `photoslibrary.readonly` on 2025-03-31 and the replacement Picker API is interactive and per-photo (rejected by the user — album granularity is the requirement), so three album-level mechanisms are probed live before one is committed to.

- [ ] **Phase 11: Write-Path Reliability & Format Support** - Kill the spurious 401 failures, reconcile the stuck placeholder rows, and accept the file types a Google album actually contains
- [ ] **Phase 12: Album-Access Mechanism Spike** - Probe all three album-level mechanisms live and record a written decision that selects one — gates every phase below
- [ ] **Phase 13: Google Link & Album Selection** - Link Google once, name an album by album (never photo by photo), and list every photo in it
- [ ] **Phase 14: Album → Frame Mirror Sync (Single Pair)** - Mirror one Google album onto one Aura frame — correct on the second run, safe when the listing lies
- [ ] **Phase 15: Many-to-Many Mapping & Debt Closeout** - Reconcile every configured album↔frame pair in one run, and close the carried testing/hardening debt

## Phase Details

### Phase 11: Write-Path Reliability & Format Support
**Goal**: `sync --apply` stops failing spuriously, the frame's stuck data is accounted for, and uploads accept the file types Google albums routinely contain
**Depends on**: Nothing (first phase of v3.0; builds on shipped v2.0)
**Requirements**: REL-01, REL-02, REL-03, REL-04, REL-05, REL-06, REL-07, REL-08, FMT-01, FMT-02, FMT-03, MOD-03
**Success Criteria** (what must be TRUE):
  1. A `sync --apply` run that hits a transient HTTP 401 completes without operator intervention and creates no duplicate frame asset for the retried item; the retry's `WriteBudget` cost is a stated, documented decision rather than an accident.
  2. Write failures are attributed honestly: a genuine authentication failure is still reported as one (never masked as transient), a `batch_update` response that silently drops ids is reported as a failure, and an asset identity carrying neither `id` nor `local_id` is rejected at construction instead of being sent.
  3. A directory containing `.png` files uploads end-to-end and is verified on a real frame; `.heic` either uploads for real or is refused with a message naming the missing decoder and what to do about it — decided explicitly, never a silent failure.
  4. `aura-cli` reports how many stuck placeholder rows the frame carries (no `uploaded_at`/`file_name`/`md5_hash`), and removes them if a working mechanism is found — reporting the count either way.
  5. The default test suite passes with zero failures — `test_read_03_pagination` no longer asserts equality between two counts the server itself does not keep consistent.
**Plans**: 5 plans

Plans:
- [ ] 11-01-PLAN.md — 401 verify-then-retry in `execute_plan` plus the `AuraError` hierarchy (REL-01..04, MOD-03) — wave 1
- [ ] 11-02-PLAN.md — `batch_update`'s unacknowledged-id set, inbound tolerance, and the honest pagination assertions (REL-06..08) — wave 2
- [ ] 11-03-PLAN.md — `auraframes/reconcile.py` plus the `reconcile` CLI verb and the `inspect` count line (REL-05) — wave 2
- [ ] 11-04-PLAN.md — `pillow-heif` and content-derived `data_uti` for JPEG/PNG/HEIF (FMT-01, FMT-03) — wave 3
- [ ] 11-05-PLAN.md — live PNG/HEIC verification, the D-10 branch decision, and the placeholder-removal probe (FMT-02, FMT-03, REL-05, REL-08) — wave 4

**Notes**: `data_uti` is derived from the actual file type instead of the hardcoded `public.jpeg` — this is a hard blocker for Phase 14, not debt, because `_prep_upload` currently raises closed on both `.png` and `.heic`. MOD-03's typed exceptions land here because the 401 classification (`AuthExpiredError`) is what makes REL-01 and REL-04 distinguishable in the first place. Placeholder reconciliation stays outside the sync loop (data hygiene on existing bad state, per `research/ARCHITECTURE.md`).

### Phase 12: Album-Access Mechanism Spike
**Goal**: Know — from live evidence, not assumption — which album-level mechanism this milestone builds on, and whether its bytes are diffable at all
**Depends on**: Phase 11 (user decision: reliability is sequenced first)
**Requirements**: SPK-01, SPK-02, SPK-03, SPK-04, SPK-05
**Success Criteria** (what must be TRUE):
  1. A written decision record names one selected mechanism, the live evidence behind it, and the reason each rejected alternative was rejected — this document is the gate that unblocks every GP requirement.
  2. The Pushd/Ambient path has been probed against the live API with its verdict recorded: either Pushd exposes Google-album-linking endpoints (which dissolves the entire Google-side problem, since the frame would pull server-side) or it demonstrably does not.
  3. The shared-album-link path has been probed against the user's own real target albums, with their actual item counts recorded against the suspected ~500-item lazy-load ceiling.
  4. The browser-automation path has been probed end-to-end once — a one-time cookie bootstrap from a real logged-in Chrome profile plus one internal `batchexecute` album listing — with its permanent local-only, never-CI-able cost stated plainly rather than discovered mid-build.
  5. Byte fidelity is settled: the account's Original-quality vs Storage-Saver setting is checked, and a photo already on the frame is downloaded back through the candidate mechanism and its base64-MD5 compared directly against the frame's reported `md5_hash`.
**Plans**: TBD

**Notes**: Decision-producing, not feature-producing. Success Criterion 5 is load-bearing for the whole milestone: if downloaded bytes do not match the frame's `md5_hash` convention, every sync run re-uploads every photo forever and burns the anti-abuse budget on ordinary usage — that must be known here, not discovered in Phase 14. Follows this project's three-times-vindicated precedent (Phase 6 `md5_hash`, Phase 7 hash format, Phase 10 visibility flag) of letting a cheap live probe redirect a design before it costs a rewrite. Closed dead ends are not to be re-opened: Picker API per-photo picking (user-rejected), app-created albums, Takeout as the mechanism, and the restricted-scope allowlist.

### Phase 13: Google Link & Album Selection
**Goal**: The user links Google once, names an album at album granularity, and the CLI can enumerate every photo inside it
**Depends on**: Phase 12 (SPK-05's decision record determines this phase's mechanism), Phase 11
**Requirements**: GP-01, GP-02, GP-03, GP-04, TEST-02
**Success Criteria** (what must be TRUE):
  1. The user runs one documented command to authorize/link Google; the credential or session persists across runs, stays out of version control, and re-linking is that same single command.
  2. `aura-cli status` reports whether Google is linked and for which account, without ever printing the credential or session token.
  3. An album is selected at **album granularity** — by link, id, or name — with no step anywhere that asks the user to pick individual photos.
  4. Listing a selected album returns every photo in it, including albums larger than one page, and the returned count matches what the user sees in Google Photos.
  5. Every Google-side component above is exercised by the offline test suite through an injected transport or fixture-backed fake — no component is testable only against live Google.
**Plans**: TBD

**Notes**: Written mechanism-agnostically on purpose so SPK-05's outcome does not invalidate it. If SPK-05 selects the browser-automation path, the browser dependency is isolated behind a leaf module that never appears in an import graph the test suite touches (per `research/BROWSER-AUTOMATION.md`), and its live correctness becomes a documented recurring manual check rather than a solvable CI gap. TEST-02 lands here rather than later because a component that is only testable against live Google would be a regression against the v1.1 DI seam.

### Phase 14: Album → Frame Mirror Sync (Single Pair)
**Goal**: One Google album mirrors onto one Aura frame — still correct on the second run after the cache is pruned, and safe when the album listing lies
**Depends on**: Phase 13
**Requirements**: GP-05, GP-06, GP-07, GP-08, GP-09, GP-10, GP-11, GP-12, GP-13, SAFE-01, SAFE-02, SAFE-03, SAFE-04, MOD-05
**Success Criteria** (what must be TRUE):
  1. `aura-cli` prints a full upload / re-show / unchanged / hide plan for one album→frame pair without touching the frame at all, with skipped videos counted and named rather than silently dropped, and progress reported while the album downloads.
  2. Album photos download concurrently into a local cache while every write to the frame stays sequential and paced by the existing `WriteBudget` — concurrency never reaches the Aura write client.
  3. Running the same sync twice against an unchanged album reports zero to upload on the second run **even though the cache was pruned after the first**, because the plan is rebuilt from the album listing plus a persisted `google_media_id → md5_hash` manifest, never from a directory walk of the pruned cache.
  4. Removing a photo from the Google album and re-running **hides** it on the frame; re-adding it to the album and re-running re-shows it without re-uploading a byte.
  5. An empty or truncated album listing aborts with an error instead of producing a plan; a plan whose removals exceed a threshold share of the frame requires explicit confirmation; real deletion stays opt-in and exact-count-gated exactly as v2.0 shipped it; and a failed or partial download is reported as failed rather than uploaded as junk bytes.
**Plans**: TBD

**Notes**: The crux of the milestone. Dry-run stays a **structural** default — the plan-computing path contains no mutating call, as in Phase 7 — rather than an `if apply:` branch. Success Criterion 3 is the load-bearing correctness point from `research/ARCHITECTURE.md`: a pruned cache makes "already synced, still in album" indistinguishable from "removed from album", and a naive `scan_directory()` on the pruned cache dir would classify every photo on the frame as a removal candidate. Success Criterion 5 is the catastrophic failure mode of every mirror-mode sync tool and ships **with** the hide capability, never after it. Criterion 4 only manifests over two runs, which makes it the single most important live UAT in the milestone.

### Phase 15: Many-to-Many Mapping & Debt Closeout
**Goal**: One run reconciles every configured album↔frame pair, and the carried testing/hardening debt is closed so the milestone ships clean
**Depends on**: Phase 14 (the single pair must be proven live before the layer that multiplies it)
**Requirements**: MAP-01, MAP-02, MAP-03, MAP-04, TEST-01, MOD-02, MOD-04
**Success Criteria** (what must be TRUE):
  1. A TOML config file maps N Google albums to N Aura frames, holds no secrets, and is safe to commit.
  2. One `aura-cli` run reconciles every configured pair; a pair that fails is reported and the remaining pairs still run to completion.
  3. Every pair in a run draws from a single shared `WriteBudget`, so the account-wide anti-abuse surface is respected no matter how many pairs are configured.
  4. The default test suite runs green with no credentials and no network, including the two lift-tests-off-network candidates carried since v1.1 (authenticated value, injected config).
  5. AWS pool IDs and the bucket name come from configuration rather than hardcoded constants, and repeatedly constructing `Aura()` in one process no longer accumulates duplicate loguru sinks or log files.
**Plans**: TBD

**Notes**: Mirrors v2.0's own precedent — Phase 8 proved single-item write, Phase 9 added the batching/anti-abuse layer on top. Many-to-many is additive risk, not foundational risk, and must not be built before the foundation it multiplies is trusted. The debt items (TEST-01, MOD-02, MOD-04) are folded here rather than given a thin standalone maintenance phase; MOD-01's full async migration stays out of scope, MOD-05 having already confined concurrency to the Google download side in Phase 14.

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 11. Write-Path Reliability & Format Support | 0/? | Not started | - |
| 12. Album-Access Mechanism Spike | 0/? | Not started | - |
| 13. Google Link & Album Selection | 0/? | Not started | - |
| 14. Album → Frame Mirror Sync (Single Pair) | 0/? | Not started | - |
| 15. Many-to-Many Mapping & Debt Closeout | 0/? | Not started | - |

## Requirement Coverage (v3.0)

| Phase | Requirements | Count |
|-------|--------------|-------|
| 11 | REL-01..08, FMT-01..03, MOD-03 | 12 |
| 12 | SPK-01..05 | 5 |
| 13 | GP-01, GP-02, GP-03, GP-04, TEST-02 | 5 |
| 14 | GP-05..13, SAFE-01..04, MOD-05 | 14 |
| 15 | MAP-01..04, TEST-01, MOD-02, MOD-04 | 7 |
| **Total** | | **43 / 43** |

No orphaned requirements; no requirement mapped to more than one phase.

## Backlog

_No items currently in backlog._

---
*Roadmap last updated: 2026-09-03 — v3.0 phases 11-15 added (phase numbering continues from v2.0's Phase 10).*
