# Requirements: Aura Frames Python Client — v3.0 Google Photos Album Sync

**Defined:** 2026-09-03
**Core Value:** Make the proven write path boringly reliable, then put a Google Photos album behind it — selected at **album** granularity, mirrored headlessly, never one photo at a time.

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

- [ ] **REL-01**: `sync --apply` retries once with a fresh login when a write returns HTTP 401, before attributing the item as failed
- [ ] **REL-02**: A 401 retry cannot create a duplicate frame asset — an upload that actually succeeded but whose response was lost must not be re-uploaded blindly
- [ ] **REL-03**: Retry accounting against `WriteBudget` is explicit and documented — a retry's token consumption is a deliberate decision, not an accident
- [ ] **REL-04**: A genuine authentication failure is still reported as one; the retry must not mask it as transient
- [ ] **REL-05**: `aura-cli` detects and reports the stuck placeholder rows (no `uploaded_at`/`file_name`/`md5_hash`), and removes them if a working mechanism is found
- [ ] **REL-06**: `AssetPartialId`'s cross-field validator actually validates on the common construction path
- [ ] **REL-07**: `batch_update`'s partial-success response is validated against the requested id list
- [ ] **REL-08**: `test_read_03_pagination` no longer asserts equality between two counts the server does not keep consistent

### Image Format Support (FMT)

<!-- Promoted from debt to blocker: Google albums routinely contain PNG and HEIC. -->

- [ ] **FMT-01**: `data_uti` is derived from the actual file type instead of the hardcoded `public.jpeg`
- [ ] **FMT-02**: `.png` files upload end-to-end and are verified live on a real frame
- [ ] **FMT-03**: `.heic` is either supported via a decoder dependency or refused with a clear, actionable message — decided explicitly, never a silent failure

### Mechanism Spikes (SPK)

<!-- Decision-producing, not feature-producing. Gates every GP requirement below. -->

- [ ] **SPK-01**: Pushd API inspected for Google-album-linking endpoints behind Aura's Ambient API integration; findings recorded
- [ ] **SPK-02**: Shared-album-link mechanism probed live, including the pagination ceiling and the real size of the user's target albums
- [ ] **SPK-03**: Browser-automation path probed — one-time cookie bootstrap from a real Chrome profile plus an internal `batchexecute` album listing
- [ ] **SPK-04**: Byte-fidelity confirmed — the account's Original-quality vs Storage-Saver setting checked, and a downloaded photo's base64-MD5 compared against the frame's reported `md5_hash`
- [ ] **SPK-05**: A written decision record selects one mechanism, with the evidence and the rejected alternatives' reasons

### Google Photos Album Sync (GP)

<!-- Written mechanism-agnostically wherever possible so SPK-05's outcome does not invalidate them. -->

- [ ] **GP-01**: The user authorizes/links Google once; the credential or session is persisted, kept out of version control, and re-linking is a single documented command
- [ ] **GP-02**: `aura-cli status` reports Google link state without leaking the credential
- [ ] **GP-03**: An album is selected at **album granularity** — never by picking individual photos
- [ ] **GP-04**: All photos in a selected album can be enumerated, including albums larger than one page
- [ ] **GP-05**: Album photos download to a local cache directory, with concurrency on the Google side only
- [ ] **GP-06**: A persisted manifest maps `google_media_id` to `md5_hash` and survives cache pruning
- [ ] **GP-07**: The sync plan is reconstructed from the album listing plus the manifest, never from a directory walk of a pruned cache
- [ ] **GP-08**: Google album sync is dry-run by default, structurally — the plan-computing path contains no mutating call
- [ ] **GP-09**: A photo removed from the Google album is **hidden** on the frame, not deleted
- [ ] **GP-10**: A photo re-added to the Google album is re-shown without re-uploading
- [ ] **GP-11**: Videos are skipped with a reported count, never silently dropped
- [ ] **GP-12**: The cache is pruned after uploads confirm, without breaking the next run's correctness
- [ ] **GP-13**: Progress is reported for long-running album downloads and uploads

### Mirror Safety (SAFE)

<!-- The catastrophic failure mode of every mirror-mode sync tool. First-class requirements. -->

- [ ] **SAFE-01**: An empty or partial album listing is treated as an error, never as an instruction to hide the whole frame
- [ ] **SAFE-02**: A plan whose removals exceed a threshold fraction of the frame is gated behind an explicit confirmation
- [ ] **SAFE-03**: Real deletion stays opt-in and exact-count-gated, exactly as v2.0 shipped it
- [ ] **SAFE-04**: A failed or partial download never results in junk bytes being uploaded to the frame

### Album-to-Frame Mapping (MAP)

- [ ] **MAP-01**: A TOML config maps N Google albums to N Aura frames
- [ ] **MAP-02**: One run reconciles every configured pair, with a failing pair not aborting the rest
- [ ] **MAP-03**: A single `WriteBudget` is shared across all pairs in a run, since the anti-abuse surface is account-wide
- [ ] **MAP-04**: The config file holds no secrets

### Testing (TEST)

- [ ] **TEST-01**: Lift-tests-off-network candidates #2 (authenticated value) and #4 (injected config), carried since v1.1
- [ ] **TEST-02**: The Google source is offline-testable through an injected transport or fixture-backed fake — no component may be testable only against live Google

### Hardening (MOD)

<!-- Existing IDs retained from the v1.1-era debt register. -->

- [ ] **MOD-02**: AWS pool IDs and bucket name moved out of hardcoded constants into config
- [ ] **MOD-03**: Typed exception hierarchy replacing bare `RuntimeError`/status discriminators where it pays
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
| REL-01 | Phase 11 | Pending |
| REL-02 | Phase 11 | Pending |
| REL-03 | Phase 11 | Pending |
| REL-04 | Phase 11 | Pending |
| REL-05 | Phase 11 | Pending |
| REL-06 | Phase 11 | Pending |
| REL-07 | Phase 11 | Pending |
| REL-08 | Phase 11 | Pending |
| FMT-01 | Phase 11 | Pending |
| FMT-02 | Phase 11 | Pending |
| FMT-03 | Phase 11 | Pending |
| SPK-01 | Phase 12 | Pending |
| SPK-02 | Phase 12 | Pending |
| SPK-03 | Phase 12 | Pending |
| SPK-04 | Phase 12 | Pending |
| SPK-05 | Phase 12 | Pending |
| GP-01 | Phase 13 | Pending |
| GP-02 | Phase 13 | Pending |
| GP-03 | Phase 13 | Pending |
| GP-04 | Phase 13 | Pending |
| GP-05 | Phase 14 | Pending |
| GP-06 | Phase 14 | Pending |
| GP-07 | Phase 14 | Pending |
| GP-08 | Phase 14 | Pending |
| GP-09 | Phase 14 | Pending |
| GP-10 | Phase 14 | Pending |
| GP-11 | Phase 14 | Pending |
| GP-12 | Phase 14 | Pending |
| GP-13 | Phase 14 | Pending |
| SAFE-01 | Phase 14 | Pending |
| SAFE-02 | Phase 14 | Pending |
| SAFE-03 | Phase 14 | Pending |
| SAFE-04 | Phase 14 | Pending |
| MAP-01 | Phase 15 | Pending |
| MAP-02 | Phase 15 | Pending |
| MAP-03 | Phase 15 | Pending |
| MAP-04 | Phase 15 | Pending |
| TEST-01 | Phase 15 | Pending |
| TEST-02 | Phase 13 | Pending |
| MOD-02 | Phase 15 | Pending |
| MOD-03 | Phase 11 | Pending |
| MOD-04 | Phase 15 | Pending |
| MOD-05 | Phase 14 | Pending |

**Coverage:**
- v3.0 requirements: 43 total
- Mapped to phases: 43 ✓ (100% — no orphans, no duplicates)

| Phase | Requirements | Count |
|-------|--------------|-------|
| Phase 11 — Write-Path Reliability & Format Support | REL-01..08, FMT-01..03, MOD-03 | 12 |
| Phase 12 — Album-Access Mechanism Spike | SPK-01..05 | 5 |
| Phase 13 — Google Link & Album Selection | GP-01..04, TEST-02 | 5 |
| Phase 14 — Album → Frame Mirror Sync (Single Pair) | GP-05..13, SAFE-01..04, MOD-05 | 14 |
| Phase 15 — Many-to-Many Mapping & Debt Closeout | MAP-01..04, TEST-01, MOD-02, MOD-04 | 7 |

---
*Requirements defined: 2026-09-03*
*Last updated: 2026-09-03 — traceability populated by the roadmapper (phases 11-15)*
