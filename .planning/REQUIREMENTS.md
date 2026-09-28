# Requirements: Aura Frames Python Client — v3.0 Google Photos Album Sync

**Defined:** 2026-09-03
**Core Value:** Make the proven write path boringly reliable, then put a Google Photos
album behind it — selected at **album** granularity, mirrored headlessly, never one photo
at a time.

> **2026-09-28 — SCOPE CHANGE:** the Google-sync goal is **abandoned** (user decision).
> Aura's restored server-side Google sync does not work in practice and will not be used
> or imitated; any future Google album sync will be a **local** sync built from scratch
> (own mechanism, local cache, disk minimisation, periodic re-auth accepted), replanned in
> a fresh milestone. Phases 12-15 are cancelled; the SPK/GP/SAFE/MAP requirements below
> and TEST-02 are marked **cancelled** (their mechanism-independent content is expected
> to be re-requiremented, not silently dropped — see the cancelled-item notes). The
> carried debt items **MOD-02, MOD-04, TEST-01 are carried forward** to the replan.
> REL/FMT/MOD-03 remain **Complete** — Phase 11 delivered them, verified 2026-09-03.

## Context for this milestone

Research (`.planning/research/`, commits `075af43` + `1adf385`) settled the milestone's gating unknown:
Google permanently withdrew the broad `photoslibrary.readonly` scope on 2025-03-31 (VERIFIED), and the
replacement Picker API is interactive and per-photo — **rejected by the user as not meeting the requirement**.

Three album-level mechanisms survive, and the user has chosen to **spike all three before committing**:

1. **Pushd/Ambient** — Aura restored Google Photos sync in their own app (June 2026) via Google's
   partner-gated Ambient API. If Pushd exposes the endpoints, the frame pulls from Google server-side
   and this client never touches Google's API.
2. **Shared album link** — VERIFIED LIVE during research: plain `curl` from a Paris egress IP returned
   HTTP 200 with no consent wall, `AF_initDataCallback` parsed, full-resolution original downloaded with
   EXIF intact. Open risk: a ~500-item practical ceiling.
3. **Browser automation** — one-time cookie harvest from a real logged-in Chrome profile, then the
   internal `batchexecute` RPC. Local-only forever; never CI-able.

Closed dead ends (do not re-open): app-created albums cannot read back user-added existing photos
(Google's scope filter is a media-item property, not album membership); Google Takeout has no
programmatic trigger.

## v3.0 Requirements

### Write-Path Reliability (REL)

- [x] **REL-01**: `sync --apply` retries once with a fresh login when a write returns HTTP 401, before attributing the item as failed
- [x] **REL-02**: A 401 retry cannot create a duplicate frame asset — an upload that actually succeeded but whose response was lost must not be re-uploaded blindly
- [x] **REL-03**: Retry accounting against `WriteBudget` is explicit and documented — a retry's token consumption is a deliberate decision, not an accident
- [x] **REL-04**: A genuine authentication failure is still reported as one; the retry must not mask it as transient
- [x] **REL-05**: `aura-cli` detects and reports the stuck placeholder rows (no `uploaded_at`/`file_name`/`md5_hash`), and removes them if a working mechanism is found. **Both halves evaluated and satisfied, live, 2026-09-03 (plan 11-06):** reporting is unconditional (`reconcile`/`inspect`, verified against 156 real assets / 50 placeholder rows); a working removal mechanism was found and confirmed by re-read, not by HTTP status alone — `--remove --include-unknown-age` (default `--mechanism remove`, i.e. `FrameApi.remove_asset`) removed all 3 rows targeted in a bounded live probe. `--include-unknown-age` is required to reach eligible rows on this account because `/frames/{id}/assets.json` never sends `created_at` at all (plan 11-05's finding); the flag's default keeps every pre-11-06 guarantee unchanged. Full command, raw HTTP evidence and mechanism table: `.planning/phases/11-write-path-reliability-format-support/11-LIVE-FINDINGS.md`, "Plan 11-06" section.
- [x] **REL-06**: `AssetPartialId`'s cross-field validator actually validates on the common construction path
- [x] **REL-07**: `batch_update`'s partial-success response is validated against the requested id list
- [x] **REL-08**: `test_read_03_pagination` no longer asserts equality between two counts the server does not keep consistent

### Image Format Support (FMT)

<!-- Promoted from debt to blocker: Google albums routinely contain PNG and HEIC. -->

- [x] **FMT-01**: `data_uti` is derived from the actual file type instead of the hardcoded `public.jpeg`
- [x] **FMT-02**: `.png` files upload end-to-end and are verified live on a real frame
- [x] **FMT-03**: `.heic` is either supported via a decoder dependency or refused with a clear, actionable message — decided explicitly, never a silent failure

### Mechanism Spikes (SPK) — CANCELLED 2026-09-28

<!-- Cancelled with the Google-sync goal: Aura's server-side sync does not work in
     practice, so probing how it works (SPK-01) has no value, and no mechanism will be
     selected for a build that is no longer planned against this milestone's shape.
     SPK-02/03/04's substance (shared-album-link viability, browser-automation bootstrap,
     byte fidelity vs the frame's md5_hash) is expected to be re-requiremented in the
     fresh local-sync milestone — byte fidelity (SPK-04) remains the load-bearing unknown
     regardless of mechanism. -->

- [x] **SPK-01**: ~~Pushd API inspected for Google-album-linking endpoints behind Aura's Ambient API integration; findings recorded~~ **CANCELLED 2026-09-28 — obsolete: Aura's server-side sync does not work; not a reference**
- [x] **SPK-02**: ~~Shared-album-link mechanism probed live, including the pagination ceiling and the real size of the user's target albums~~ **CANCELLED with the goal; substance carried to the local-sync replan**
- [x] **SPK-03**: ~~Browser-automation path probed — one-time cookie bootstrap from a real Chrome profile plus an internal `batchexecute` album listing~~ **CANCELLED with the goal; substance carried to the local-sync replan**
- [x] **SPK-04**: ~~Byte-fidelity confirmed — the account's Original-quality vs Storage-Saver setting checked, and a downloaded photo's base64-MD5 compared against the frame's reported `md5_hash`~~ **CANCELLED with the goal; byte fidelity carries over as the replan's load-bearing unknown**
- [x] **SPK-05**: ~~A written decision record selects one mechanism, with the evidence and the rejected alternatives' reasons~~ **CANCELLED with the goal; re-requiremented against the two surviving local mechanisms**

### Google Photos Album Sync (GP) — CANCELLED 2026-09-28

<!-- Cancelled with the Google-sync goal. Mechanism-independent substance expected to be
     re-requiremented in the fresh local-sync milestone, largely unchanged: GP-05
     (concurrent Google-side downloads), GP-06/07 (manifest + plan-from-listing over a
     pruned cache — the pruned-cache correctness trap), GP-08 (structural dry-run),
     GP-09/10 (hide/re-show mirror semantics), GP-11 (videos skipped with a count),
     GP-12 (cache pruning), GP-13 (progress). GP-01..04 will be re-shaped around the
     local mechanisms (shared-album link / browser automation). -->

- [x] **GP-01**: ~~The user authorizes/links Google once; the credential or session is persisted, kept out of version control, and re-linking is a single documented command~~ **CANCELLED with the goal; re-shaped in the replan**
- [x] **GP-02**: ~~`aura-cli status` reports Google link state without leaking the credential~~ **CANCELLED with the goal; re-shaped in the replan**
- [x] **GP-03**: ~~An album is selected at **album granularity** — never by picking individual photos~~ **CANCELLED with the goal; album granularity remains a locked user decision for the replan**
- [x] **GP-04**: ~~All photos in a selected album can be enumerated, including albums larger than one page~~ **CANCELLED with the goal; pagination-ceiling measurement carries to the replan**
- [x] **GP-05**: ~~Album photos download to a local cache directory, with concurrency on the Google side only~~ **CANCELLED with the goal; substance re-requiremented in the replan**
- [x] **GP-06**: ~~A persisted manifest maps `google_media_id` to `md5_hash` and survives cache pruning~~ **CANCELLED with the goal; substance re-requiremented in the replan**
- [x] **GP-07**: ~~The sync plan is reconstructed from the album listing plus the manifest, never from a directory walk of a pruned cache~~ **CANCELLED with the goal; substance re-requiremented in the replan**
- [x] **GP-08**: ~~Google album sync is dry-run by default, structurally — the plan-computing path contains no mutating call~~ **CANCELLED with the goal; substance re-requiremented in the replan**
- [x] **GP-09**: ~~A photo removed from the Google album is **hidden** on the frame, not deleted~~ **CANCELLED with the goal; hide-by-default remains the locked removal semantics for the replan**
- [x] **GP-10**: ~~A photo re-added to the Google album is re-shown without re-uploading~~ **CANCELLED with the goal; substance re-requiremented in the replan**
- [x] **GP-11**: ~~Videos are skipped with a reported count, never silently dropped~~ **CANCELLED with the goal; substance re-requiremented in the replan**
- [x] **GP-12**: ~~The cache is pruned after uploads confirm, without breaking the next run's correctness~~ **CANCELLED with the goal; substance re-requiremented in the replan**
- [x] **GP-13**: ~~Progress is reported for long-running album downloads and uploads~~ **CANCELLED with the goal; substance re-requiremented in the replan**

### Mirror Safety (SAFE) — CANCELLED 2026-09-28

<!-- Cancelled with the Google-sync goal. The catastrophic-failure-mode requirements are
     mechanism-independent and expected to be re-requiremented essentially unchanged in
     the fresh local-sync milestone. -->

- [x] **SAFE-01**: ~~An empty or partial album listing is treated as an error, never as an instruction to hide the whole frame~~ **CANCELLED with the goal; substance re-requiremented in the replan**
- [x] **SAFE-02**: ~~A plan whose removals exceed a threshold fraction of the frame is gated behind an explicit confirmation~~ **CANCELLED with the goal; substance re-requiremented in the replan**
- [x] **SAFE-03**: ~~Real deletion stays opt-in and exact-count-gated, exactly as v2.0 shipped it~~ **CANCELLED with the goal; v2.0's gating itself is unaffected and stays shipped**
- [x] **SAFE-04**: ~~A failed or partial download never results in junk bytes being uploaded to the frame~~ **CANCELLED with the goal; substance re-requiremented in the replan**

### Album-to-Frame Mapping (MAP) — CANCELLED 2026-09-28

<!-- Cancelled with the Google-sync goal; the TOML mapping layer will be re-scoped in the
     fresh milestone against whatever album-selection mechanism the local sync adopts.
     MAP-03's account-wide WriteBudget rule stays a standing convention regardless. -->

- [x] **MAP-01**: ~~A TOML config maps N Google albums to N Aura frames~~ **CANCELLED with the goal; re-scoped in the replan**
- [x] **MAP-02**: ~~One run reconciles every configured pair, with a failing pair not aborting the rest~~ **CANCELLED with the goal; re-scoped in the replan**
- [x] **MAP-03**: ~~A single `WriteBudget` is shared across all pairs in a run, since the anti-abuse surface is account-wide~~ **CANCELLED with the goal; the account-wide-budget convention itself stands**
- [x] **MAP-04**: ~~The config file holds no secrets~~ **CANCELLED with the goal; secrets-out-of-VCS remains a standing constraint**

### Testing (TEST)

- [x] **TEST-01**: ~~Lift-tests-off-network candidates #2 (authenticated value) and #4 (injected config), carried since v1.1~~ **CARRIED FORWARD to the fresh milestone's replan**
- [x] **TEST-02**: ~~The Google source is offline-testable through an injected transport or fixture-backed fake — no component may be testable only against live Google~~ **CANCELLED with the goal; the offline-testability convention itself stands (v1.1 DI seam) and will apply to whatever the replan builds**

### Hardening (MOD)

<!-- Existing IDs retained from the v1.1-era debt register. -->

- [ ] **MOD-02**: AWS pool IDs and bucket name moved out of hardcoded constants into config
- [x] **MOD-03**: Typed exception hierarchy replacing bare `RuntimeError`/status discriminators where it pays
- [ ] **MOD-04**: `Aura._init_logger()` no longer leaks loguru sinks on repeated construction
- [ ] **MOD-05**: Concurrency confined to Google-side downloads; the Aura write client stays synchronous

## Future Requirements

Deferred, tracked, not in this roadmap.

### Google Photos

- **GPF-01**: Unattended/scheduled sync without any human step — only becomes possible if SPK-01 finds a server-side Pushd mechanism
- **GPF-02**: Albums beyond the shared-link pagination ceiling, if the shared-link mechanism is chosen and the ceiling proves real
- **GPF-03**: Live/auto-updating album propagation (Dropbox-style), explicitly a non-goal for v3.0

### Hardening

- **MOD-01**: Async migration of the Aura HTTP client — still not required; writes are deliberately paced

## Out of Scope

| Feature | Reason |
|---------|--------|
| Picker API per-photo selection | Rejected by the user — album-level selection is the requirement |
| App-created-album workaround | VERIFIED dead end: `readonly.appcreateddata` filters on media-item origin, not album membership |
| Google Takeout as the sync mechanism | No programmatic trigger exists; scheduled export runs on a 2-month cadence |
| Applying for Google's restricted-scope allowlist | VERIFIED: no allowlist path back to `photoslibrary.readonly` for a general app |
| Video sync | Frame reports null `md5_hash` for every video asset; content-hash diffing cannot see them |
| Streaming Google → S3 without disk | Rejected in favour of a pruned cache so the live-verified v2.0 pipeline is reused unchanged |
| CI coverage of the browser-automation path | Structurally impossible — Google blocks unattended login from untrusted environments |
| Async migration of the Aura client (MOD-01) | Writes are deliberately paced; concurrency only pays on the Google download side |

## Traceability

Populated during roadmap creation (2026-09-03). Every v3.0 requirement maps to exactly
one phase; phase numbering continues from v2.0's Phase 10.

| Requirement | Phase | Status |
|-------------|-------|--------|
| REL-01 | Phase 11 | Complete |
| REL-02 | Phase 11 | Complete |
| REL-03 | Phase 11 | Complete |
| REL-04 | Phase 11 | Complete |
| REL-05 | Phase 11 | Complete |
| REL-06 | Phase 11 | Complete |
| REL-07 | Phase 11 | Complete |
| REL-08 | Phase 11 | Complete |
| FMT-01 | Phase 11 | Complete |
| FMT-02 | Phase 11 | Complete |
| FMT-03 | Phase 11 | Complete |
| SPK-01 | Phase 12 | ~~Pending~~ Cancelled 2026-09-28 |
| SPK-02 | Phase 12 | ~~Pending~~ Cancelled 2026-09-28 |
| SPK-03 | Phase 12 | ~~Pending~~ Cancelled 2026-09-28 |
| SPK-04 | Phase 12 | ~~Pending~~ Cancelled 2026-09-28 |
| SPK-05 | Phase 12 | ~~Pending~~ Cancelled 2026-09-28 |
| GP-01 | Phase 13 | ~~Pending~~ Cancelled 2026-09-28 |
| GP-02 | Phase 13 | ~~Pending~~ Cancelled 2026-09-28 |
| GP-03 | Phase 13 | ~~Pending~~ Cancelled 2026-09-28 |
| GP-04 | Phase 13 | ~~Pending~~ Cancelled 2026-09-28 |
| GP-05 | Phase 14 | ~~Pending~~ Cancelled 2026-09-28 |
| GP-06 | Phase 14 | ~~Pending~~ Cancelled 2026-09-28 |
| GP-07 | Phase 14 | ~~Pending~~ Cancelled 2026-09-28 |
| GP-08 | Phase 14 | ~~Pending~~ Cancelled 2026-09-28 |
| GP-09 | Phase 14 | ~~Pending~~ Cancelled 2026-09-28 |
| GP-10 | Phase 14 | ~~Pending~~ Cancelled 2026-09-28 |
| GP-11 | Phase 14 | ~~Pending~~ Cancelled 2026-09-28 |
| GP-12 | Phase 14 | ~~Pending~~ Cancelled 2026-09-28 |
| GP-13 | Phase 14 | ~~Pending~~ Cancelled 2026-09-28 |
| SAFE-01 | Phase 14 | ~~Pending~~ Cancelled 2026-09-28 |
| SAFE-02 | Phase 14 | ~~Pending~~ Cancelled 2026-09-28 |
| SAFE-03 | Phase 14 | ~~Pending~~ Cancelled 2026-09-28 |
| SAFE-04 | Phase 14 | ~~Pending~~ Cancelled 2026-09-28 |
| MAP-01 | Phase 15 | ~~Pending~~ Cancelled 2026-09-28 |
| MAP-02 | Phase 15 | ~~Pending~~ Cancelled 2026-09-28 |
| MAP-03 | Phase 15 | ~~Pending~~ Cancelled 2026-09-28 |
| MAP-04 | Phase 15 | ~~Pending~~ Cancelled 2026-09-28 |
| TEST-01 | Phase 15 | ~~Pending~~ Carried forward to replan |
| TEST-02 | Phase 13 | ~~Pending~~ Cancelled 2026-09-28 |
| MOD-02 | Phase 15 | ~~Pending~~ Carried forward to replan |
| MOD-03 | Phase 11 | Complete |
| MOD-04 | Phase 15 | ~~Pending~~ Carried forward to replan |
| MOD-05 | Phase 14 | ~~Pending~~ Cancelled 2026-09-28 |

**Coverage:**

- v3.0 requirements: 43 total
- Mapped to phases: 43 ✓ (100% — no orphans, no duplicates)
- **2026-09-28:** 27 cancelled with the Google-sync goal; 3 carried forward to the fresh
  local-sync milestone (TEST-01, MOD-02, MOD-04); 13 Complete (Phase 11's REL/FMT/MOD-03)

| Phase | Requirements | Count |
|-------|--------------|-------|
| Phase 11 — Write-Path Reliability & Format Support | REL-01..08, FMT-01..03, MOD-03 | 12 |
| Phase 12 — Album-Access Mechanism Spike | SPK-01..05 | 5 |
| Phase 13 — Google Link & Album Selection | GP-01..04, TEST-02 | 5 |
| Phase 14 — Album → Frame Mirror Sync (Single Pair) | GP-05..13, SAFE-01..04, MOD-05 | 14 |
| Phase 15 — Many-to-Many Mapping & Debt Closeout | MAP-01..04, TEST-01, MOD-02, MOD-04 | 7 |

*(Phases 12-15 and their requirements are cancelled as of 2026-09-28 — tables kept for
the record. The fresh local-sync milestone will re-requirement the carried debt plus the
mechanism-independent substance noted in each cancelled section.)*

---
*Requirements defined: 2026-09-03*
*Last updated: 2026-09-28 — Google-sync goal abandoned (user decision): SPK/GP/SAFE/MAP + TEST-02 cancelled with phases 12-15; TEST-01, MOD-02, MOD-04 carried forward; mechanism-independent substance to be re-requiremented in a fresh local-sync milestone.*
