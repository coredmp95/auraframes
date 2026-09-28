# Requirements: Aura Frames Python Client — v4.0 Local Google Photos Album Sync

**Defined:** 2026-09-28
**Core Value:** Put a Google Photos album on an Aura frame through the project's **own**
local pipeline — album selected at album granularity, mirrored headlessly, with a cache
that minimises disk usage — on a write path that is already boringly reliable.

> **v4.0 context:** v3.0 delivered write-path reliability (Phase 11: 401 retry,
> placeholder reconciliation, PNG/HEIC support) and was then **re-scoped** (2026-09-28):
> Aura's restored server-side Google sync does not work in practice, so v3.0's
> Aura-mechanism spike (old Phase 12) and the server-shaped plan were cancelled. v4.0
> rebuilds album sync as a **local** sync using only this project's own mechanisms.
> Carried debt from v3.0: MOD-02, MOD-04, TEST-01.
> Research: `research/ALBUM-ACCESS.md` §1 (shared-link, live-verified) + §2/§3
> (browser automation) + `research/BROWSER-AUTOMATION.md` + `research/ALBUM-ACCESS-V4-ADDENDUM.md`.
> Aura's system is explicitly **not a reference**.

## v4.0 Requirements

### Mechanism & Album Selection (LGS — local Google sync)

<!-- Decision-producing first, then the selection surface the mechanism allows. -->

- [ ] **LGS-01**: Both surviving mechanisms are probed live against the user's real albums and one written decision record selects one, with the evidence and the rejected alternative's reason — the shared-album-link probe measures the real albums' item counts against the suspected ~500-item ceiling (a 600+ synthetic album is built only if the real albums can't measure it), and the browser-automation probe completes one cookie bootstrap plus one internal-RPC album listing
- [ ] **LGS-02**: The Google credential/session is linked once via a single documented command, persisted out of version control, and re-linking is that same command — periodic re-authentication is an accepted operational cost, never a design blocker
- [ ] **LGS-03**: `aura-cli status` reports the Google link/session state (linked, which account, session usable) without ever printing the credential or session token
- [ ] **LGS-04**: An album is selected at **album granularity** — by share link, id, or name — never by picking individual photos (Picker-API per-photo selection remains rejected)
- [ ] **LGS-05**: All photos in a selected album can be enumerated, including albums larger than one page of whatever mechanism provides
- [ ] **LGS-06**: Byte fidelity is settled once in the spike and guarded after: the account's Original-quality vs Storage-Saver setting is checked, and a photo already on the frame downloaded back through the chosen mechanism base64-MD5-matches the frame's reported `md5_hash` — a mechanism that cannot achieve this is rejected outright

### Local Cache & Sync Engine (CSE)

<!-- The disk-minimisation architecture: pruned cache + persistent manifest. -->

- [ ] **CSE-01**: Album photos download to a local cache directory, with concurrency on the Google side only — the Aura write client stays synchronous and paced by `WriteBudget` (MOD-05's rule)
- [ ] **CSE-02**: A persisted manifest maps `google_media_id` to `md5_hash` and survives cache pruning
- [ ] **CSE-03**: The sync plan is reconstructed from the album listing plus the manifest, never from a directory walk of the (pruned) cache
- [ ] **CSE-04**: The cache is pruned after uploads confirm, so steady-state disk usage stays proportional to new/unchanged-in-flight photos, not to the whole album — and pruning never breaks the next run's correctness
- [ ] **CSE-05**: Google album sync is dry-run by default, structurally — the plan-computing path contains no mutating call (v2.0 Phase 7 convention)
- [ ] **CSE-06**: A photo removed from the Google album is **hidden** on the frame (`exclude_asset`), never deleted by default; a photo re-added is re-shown without re-uploading
- [ ] **CSE-07**: Videos are skipped with a reported count, never silently dropped
- [ ] **CSE-08**: Progress is reported for long-running album downloads and uploads

### Mirror Safety (SAFE)

<!-- The catastrophic failure mode of every mirror-mode sync tool. First-class. -->

- [ ] **SAFE-01**: An empty or partial album listing is treated as an error, never as an instruction to hide the whole frame
- [ ] **SAFE-02**: A plan whose removals exceed a threshold fraction of the frame is gated behind an explicit confirmation
- [ ] **SAFE-03**: Real deletion stays opt-in and exact-count-gated, exactly as v2.0 shipped it
- [ ] **SAFE-04**: A failed or partial download never results in junk bytes being uploaded to the frame

### Offline Testability (TEST)

<!-- TEST-02's convention, re-stated for the local mechanisms; TEST-01's carried debt. -->

- [ ] **TEST-01**: Lift-tests-off-network candidates #2 (authenticated value) and #4 (injected config), carried since v1.1, are closed
- [ ] **TEST-02**: Every Google-facing component is offline-testable through an injected transport or fixture-backed fake — no component may be testable only against live Google

### Hardening (MOD)

<!-- Carried from the v1.1-era debt register; re-scoped from v3.0's Phase 15. -->

- [ ] **MOD-02**: AWS pool IDs and bucket name moved out of hardcoded constants into config
- [ ] **MOD-04**: `Aura._init_logger()` no longer leaks loguru sinks on repeated construction

## Future Requirements

Deferred, tracked, not in this roadmap.

### Google Photos

- **GSF-01**: Many-to-many album↔frame mapping (TOML config, N albums ↔ N frames, one reconciling run, shared account-wide `WriteBudget`, secrets-free config) — the v3.0 MAP requirements re-scoped; sequenced after a single pair is proven live
- **GSF-02**: Unattended/scheduled sync — requires whichever mechanism permits headless re-auth; re-evaluated after LGS-01's decision record
- **GSF-03**: Live/auto-updating album propagation (Dropbox-style) — explicit non-goal carried from v3.0

## Out of Scope

| Feature | Reason |
|---------|--------|
| Aura/Pushd server-side Google sync (SPK-01) | Abandoned 2026-09-28: Aura's own restored sync does not work in practice; not a reference for anything |
| Picker API per-photo selection | Rejected by the user — album-level selection is the requirement (carried from v3.0) |
| App-created-album workaround | VERIFIED dead end (v3.0 research §3) — do not re-open |
| Google Takeout as the sync mechanism | No programmatic trigger (v3.0 research §2) — do not re-open |
| Data Portability API / restricted-scope allowlist | VERIFIED dead ends (v3.0 research) — do not re-open |
| Video sync | Frame reports null `md5_hash` for every video asset; content-hash diffing cannot see them — skipped with a reported count (carried from v3.0) |
| Streaming Google → S3 without disk | Rejected in favour of the local cache (CSE-01/04) so the live-verified v2.0 pipeline is reused unchanged |
| CI coverage of the browser-automation path | Structurally impossible — Google blocks unattended login from untrusted environments (if the browser mechanism is chosen) |
| Async migration of the Aura client (MOD-01) | Writes are deliberately paced; concurrency only pays on the Google download side (carried from v3.0) |

## Traceability

Populated during roadmap creation. Every v4.0 requirement maps to exactly one phase;
phase numbering continues from v3.0's Phase 11.

| Requirement | Phase | Status |
|-------------|-------|--------|
| LGS-01 | TBD | Pending |
| LGS-02 | TBD | Pending |
| LGS-03 | TBD | Pending |
| LGS-04 | TBD | Pending |
| LGS-05 | TBD | Pending |
| LGS-06 | TBD | Pending |
| CSE-01 | TBD | Pending |
| CSE-02 | TBD | Pending |
| CSE-03 | TBD | Pending |
| CSE-04 | TBD | Pending |
| CSE-05 | TBD | Pending |
| CSE-06 | TBD | Pending |
| CSE-07 | TBD | Pending |
| CSE-08 | TBD | Pending |
| SAFE-01 | TBD | Pending |
| SAFE-02 | TBD | Pending |
| SAFE-03 | TBD | Pending |
| SAFE-04 | TBD | Pending |
| TEST-01 | TBD | Pending |
| TEST-02 | TBD | Pending |
| MOD-02 | TBD | Pending |
| MOD-04 | TBD | Pending |

**Coverage:**

- v4.0 requirements: 22 total
- Mapped to phases: TBD (roadmapper fills)

---
*Requirements defined: 2026-09-28*
*Last updated: 2026-09-28 — v4.0 scope defined after v3.0 Google-sync abandonment; carried debt TEST-01/MOD-02/MOD-04 included*
