# Roadmap: Aura Frames Python Client — Revive & Verify

## Milestones

- ✅ **v1.0 Revive & Verify** — Phases 1-3 (shipped 2026-06-30) — the ~3-year-old codebase runs again on Python 3.14/`uv`/pydantic v2, read path proven live
- ✅ **v1.1 Client Transport Seam** — Phase 4 (shipped 2026-07-05) — additive DI seam + offline `httpx.MockTransport` harness, lifting most read-path tests off the live network
- ✅ **v2.0 Directory-to-Frame Sync** — Phases 5-10 (shipped 2026-09-02) — a real `status`/`inspect`/`sync`/`push` CLI that mirrors a local photo directory to a live Aura frame, with the write path proven live for the first time and hide-by-default removal
- ✅ **v3.0 Write-Path Reliability** — Phase 11 (delivered 2026-09-03; phases 12-15 cancelled 2026-09-28 when the Google-sync goal was abandoned — Aura's own server-side sync does not work in practice) — spurious 401s killed, placeholder rows reconciled, PNG/HEIC accepted
- 🚧 **v4.0 Local Google Photos Album Sync** — Phases 16-19 (in progress, started 2026-09-28) — sync a Google Photos album to a frame through this project's **own** local pipeline: live-probed mechanism, pruned cache with a persistent manifest, album granularity, hide-by-default mirror semantics

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

- [x] Phase 5: CLI Skeleton + Status (2/2 plans) — completed 2026-07-06
- [x] Phase 6: Inspect + Frame Resolution (2/2 plans) — completed 2026-07-07
- [x] Phase 7: Sync-Diffing Engine, Dry-Run Only (3/3 plans) — completed 2026-07-07
- [x] Phase 8: Destructive Execution (4/4 plans) — completed 2026-07-08
- [x] Phase 9: Proactive Write Rate-Limiter & Geo Guard (2/2 plans) — completed 2026-07-09
- [x] Phase 10: Hide-instead-of-delete sync mode (4/4 plans) — completed 2026-08-25

</details>

<details>
<summary>✅ v3.0 Write-Path Reliability (Phase 11 delivered; 12-15 cancelled) — 2026-09-03/28</summary>

Full detail archived in [`milestones/v3.0-ROADMAP.md`](./milestones/v3.0-ROADMAP.md); requirements in [`milestones/v3.0-REQUIREMENTS.md`](./milestones/v3.0-REQUIREMENTS.md).

- [x] Phase 11: Write-Path Reliability & Format Support (6/6 plans) — completed 2026-09-03 — 401 verify-then-retry, `batch_update` unacknowledged-id validation, placeholder reconciliation (`reconcile` verb, live-verified removal), content-derived `data_uti` with PNG/HEIC live-proven, honest pagination assertions
- [x] Phase 12: Album-Access Mechanism Spike — **CANCELLED 2026-09-28** before any planning (Google-sync goal abandoned)
- [x] Phase 13: Google Link & Album Selection — **CANCELLED 2026-09-28**
- [x] Phase 14: Album → Frame Mirror Sync (Single Pair) — **CANCELLED 2026-09-28**
- [x] Phase 15: Many-to-Many Mapping & Debt Closeout — **CANCELLED 2026-09-28** (debt carried into v4.0)

</details>

### 🚧 v4.0 Local Google Photos Album Sync (Phases 16-19) — IN PROGRESS

Requirements: [`REQUIREMENTS.md`](./REQUIREMENTS.md) — 22 requirements, all mapped below.
Research: [`research/ALBUM-ACCESS.md`](./research/ALBUM-ACCESS.md) §1-§4 (shared-link, browser automation, dead ends — §5 Pushd/Ambient obsolete), [`research/BROWSER-AUTOMATION.md`](./research/BROWSER-AUTOMATION.md), [`research/ALBUM-ACCESS-V4-ADDENDUM.md`](./research/ALBUM-ACCESS-V4-ADDENDUM.md) (targeted 2026-09-28), [`research/PITFALLS.md`](./research/PITFALLS.md).

Three locked user decisions shape this roadmap. **Own mechanism, not Aura's** (2026-09-28): Aura's restored server-side Google sync does not work in practice, so nothing probes or imitates it — the sync is local, built from this project's own primitives. **Both surviving mechanisms are probed live before one is committed**: the shared-album link (no auth, live-verified in research, suspected ~500-item ceiling) and browser automation via a dedicated-Chrome-profile cookie bootstrap plus the internal `batchexecute` RPC (public reference implementation exists). **Disk minimisation is a design requirement, not a preference**: a pruned cache plus a persistent `google_media_id → md5_hash` manifest keeps steady-state disk proportional to new photos, with "keep everything locally" the accepted fallback. Periodic re-authentication is accepted as an operational cost; its cadence is an accepted unknown. The proven v2.0 pipeline (structural dry-run, hide-by-default, exact-count-gated deletion, `WriteBudget`) is reused unchanged — almost all the risky code is already live-verified.

- [ ] **Phase 16: Local Mechanism Spike & Decision** - Probe both surviving mechanisms live, settle byte fidelity, and record the decision that gates everything below
- [ ] **Phase 17: Google Link & Album Selection** - Link Google once through the chosen mechanism, select an album at album granularity, enumerate every photo in it
- [ ] **Phase 18: Album → Frame Mirror Sync (Single Pair)** - Mirror one Google album onto one Aura frame through the pruned-cache local pipeline — correct on the second run, safe when the listing lies
- [ ] **Phase 19: Debt Closeout** - Close the carried testing/hardening debt so the milestone ships clean

## Phase Details

### Phase 16: Local Mechanism Spike & Decision

**Goal**: Know — from live evidence, not assumption — which album-level mechanism this milestone builds on, and whether its bytes are diffable at all
**Depends on**: Nothing (first phase of v4.0; builds on shipped Phase 11)
**Requirements**: LGS-01, LGS-06
**Success Criteria** (what must be TRUE):

  1. A written decision record names one selected mechanism, the live evidence behind it, and the reason the rejected alternative was rejected — this document gates every later phase.
  2. The shared-album-link path has been probed against the user's own real target albums, with their actual item counts recorded against the suspected ~500-item ceiling (a 600+ synthetic album is built only if the real albums cannot measure it).
  3. The browser-automation path has been probed end-to-end once — a one-time cookie bootstrap from a dedicated Chrome profile plus one internal `batchexecute` album listing — with its permanent local-only, never-CI-able cost stated plainly rather than discovered mid-build.
  4. Byte fidelity is settled: the account's Original-quality vs Storage-Saver setting is checked, and a photo already on the frame is downloaded back through the candidate mechanism and its base64-MD5 compared directly against the frame's reported `md5_hash` — a mechanism that cannot match is rejected outright.

**Plans**: 3 plans

Plans:
**Wave 1**

- [ ] 16-01-PLAN.md — shared-album-link probe: fetch/parse/count real albums, =d fidelity hash (LGS-01, LGS-06)
- [ ] 16-02-PLAN.md — browser-automation probe: cookie vault + denylist, Playwright bootstrap (gated), batchexecute listing (LGS-01)

**Wave 2** *(blocked on Wave 1 completion)*

- [ ] 16-03-PLAN.md — byte-fidelity comparison + 16-DECISION-RECORD.md with the operator's signed selection (LGS-01, LGS-06)

**Notes**: Decision-producing, not feature-producing. SPK-01/Pushd-probing from v3.0 is dead and stays dead — Aura's server-side sync does not work and nothing is built on it. Byte fidelity (success criterion 4) is load-bearing for the whole milestone: if downloaded bytes do not match the frame's `md5_hash` convention, every sync run re-uploads every photo forever. Cookie-expiry cadence is an accepted unknown (user decision 2026-09-28) — the re-bootstrap command's existence is required by LGS-02, not the cadence measurement. Closed dead ends are not re-opened: Picker per-photo picking, app-created albums, Takeout, Data Portability API, restricted-scope allowlist, Aura's server-side mechanism.

### Phase 17: Google Link & Album Selection

**Goal**: The user links Google once through the chosen mechanism, names an album at album granularity, and the CLI can enumerate every photo inside it
**Depends on**: Phase 16 (the decision record determines the mechanism)
**Requirements**: LGS-02, LGS-03, LGS-04, LGS-05, TEST-02
**Success Criteria** (what must be TRUE):

  1. The user runs one documented command to link/authorize Google; the credential or session persists across runs, stays out of version control, and re-running that same command re-links when the session expires (periodic re-auth is an accepted cost, never a redesign).
  2. `aura-cli status` reports whether Google is linked and for which account, and whether the session is usable, without ever printing the credential, cookie, or token.
  3. An album is selected at **album granularity** — by share link, id, or name — with no step anywhere that asks the user to pick individual photos.
  4. Listing a selected album returns every photo in it, including albums larger than one page of the mechanism's listing surface, and the returned count matches what the user sees in Google Photos.
  5. Every Google-facing component above is exercised by the offline test suite through an injected transport or fixture-backed fake — no component is testable only against live Google.

**Plans**: TBD

**Notes**: Built on whichever mechanism Phase 16 selects. If browser automation wins, the browser dependency sits behind a leaf module that never appears in a test-suite import graph (per `research/BROWSER-AUTOMATION.md`), and the shared-link parser behind the same seam if the link mechanism wins. TEST-02 lands here rather than later because a component testable only against live Google would be a regression against the v1.1 DI seam.

### Phase 18: Album → Frame Mirror Sync (Single Pair)

**Goal**: One Google album mirrors onto one Aura frame through the local pipeline — still correct on the second run after the cache is pruned, and safe when the album listing lies
**Depends on**: Phase 17
**Requirements**: CSE-01, CSE-02, CSE-03, CSE-04, CSE-05, CSE-06, CSE-07, CSE-08, SAFE-01, SAFE-02, SAFE-03, SAFE-04
**Success Criteria** (what must be TRUE):

  1. `aura-cli` prints a full upload / re-show / unchanged / hide plan for one album→frame pair without touching the frame at all, with skipped videos counted and named rather than silently dropped, and progress reported while the album downloads.
  2. Album photos download concurrently into a local cache while every write to the frame stays sequential and paced by the existing `WriteBudget` — concurrency never reaches the Aura write client.
  3. Running the same sync twice against an unchanged album reports zero to upload on the second run **even though the cache was pruned after the first**, because the plan is rebuilt from the album listing plus a persisted `google_media_id → md5_hash` manifest, never from a directory walk of the pruned cache — and steady-state disk usage after pruning stays proportional to in-flight photos, not the whole album.
  4. Removing a photo from the Google album and re-running **hides** it on the frame; re-adding it to the album and re-running re-shows it without re-uploading a byte.
  5. An empty or truncated album listing aborts with an error instead of producing a plan; a plan whose removals exceed a threshold share of the frame requires explicit confirmation; real deletion stays opt-in and exact-count-gated exactly as v2.0 shipped it; and a failed or partial download is reported as failed rather than uploaded as junk bytes.

**Plans**: TBD

**Notes**: The crux of the milestone. Dry-run stays a **structural** default — the plan-computing path contains no mutating call, as in Phase 7. Success criterion 3 is the load-bearing correctness point: a pruned cache makes "already synced, still in album" indistinguishable from "removed from album", and a naive directory walk on the pruned cache would classify every photo on the frame as a removal candidate — the manifest is what makes disk minimisation safe. Success criterion 5 is the catastrophic failure mode of every mirror-mode sync tool and ships **with** the hide capability, never after it. Criterion 4 only manifests over two runs, which makes it the single most important live UAT in the milestone. The v2.0 content-hash diff/upload pipeline is reused unchanged underneath.

### Phase 19: Debt Closeout

**Goal**: The carried testing/hardening debt is closed so the milestone ships clean
**Depends on**: Phase 18 (the single pair must be proven live before the cleanup layer lands on a moving codebase)
**Requirements**: TEST-01, MOD-02, MOD-04
**Success Criteria** (what must be TRUE):

  1. The default test suite runs green with no credentials and no network, including the two lift-tests-off-network candidates carried since v1.1 (authenticated value, injected config).
  2. AWS pool IDs and the bucket name come from configuration rather than hardcoded constants, with no behavior change when the config is unset.
  3. Repeatedly constructing `Aura()` in one process no longer accumulates duplicate loguru sinks or log files.

**Plans**: TBD

**Notes**: Mirrors v3.0 Phase 15's original intent, minus everything Google-shaped: the debt items are folded into a thin closeout phase rather than given their own milestone. MOD-01's full async migration stays out of scope.

## Progress

**Execution Order:** 16 → 17 → 18 → 19

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 16. Local Mechanism Spike & Decision | 0/? | Not started | - |
| 17. Google Link & Album Selection | 0/? | Not started | - |
| 18. Album → Frame Mirror Sync (Single Pair) | 0/? | Not started | - |
| 19. Debt Closeout | 0/? | Not started | - |

## Requirement Coverage (v4.0)

| Phase | Requirements | Count |
|-------|--------------|-------|
| 16 | LGS-01, LGS-06 | 2 |
| 17 | LGS-02, LGS-03, LGS-04, LGS-05, TEST-02 | 5 |
| 18 | CSE-01..08, SAFE-01..04 | 12 |
| 19 | TEST-01, MOD-02, MOD-04 | 3 |
| **Total** | | **22 / 22** |

No orphaned requirements; no requirement mapped to more than one phase.

## Backlog

_No items currently in backlog._

---
*Roadmap last updated: 2026-09-28 — v4.0 phases 16-19 created (phase numbering continues from v3.0's Phase 11). v3.0's Google-sync phases 12-15 were cancelled 2026-09-28; the local-sync goal replaces them.*
