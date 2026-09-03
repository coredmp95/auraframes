# Research Summary: v3.0 Google Photos Album Sync

**Project:** Aura Frames Python Client — v3.0 Google Photos Album Sync  
**Domain:** Photo cloud-sync CLI with content-hash diffing and write-path reliability hardening  
**Researched:** 2026-09-03  
**Confidence:** MEDIUM-HIGH overall (HIGH on Google API restrictions and existing codebase; MEDIUM on Google Picker API edge cases requiring live spike confirmation)

---

## Executive Summary

**Critical Finding: The milestone's "discover and sync albums" requirement is already broken by Google's permanent March 2025 API change.** The `photoslibrary.readonly` and `albums.list` scopes that this project assumed would remain available for reading a user's own photo library no longer work for general apps (VERIFIED, effective 2025-03-31, no documented allowlist path to restore access). The only remaining route is the **Picker API** — an interactive, session-based, browser-driven selection interface with no scriptable "list my albums" capability and no "select this whole album" one-click affordance. **This reshapes the requirement from "unattended, many-album reconciliation in one CLI run" to "user-interactive, re-pick-per-album, single CLI invocation."** The requirement language must change: `aura-cli google-sync` can reconcile N album→frame pairs in one run, but each pair's album discovery step requires the user to open a browser and re-select the photos they want.

**A second foundation problem surfaces simultaneously: Google's download mechanism does not guarantee byte-identical originals.** VERIFIED reports across multiple independent sources (including a mature, now-archived Google Photos backup tool) show that the `=d` "original quality" parameter strips EXIF GPS, re-encodes in some cases, and returns non-original bytes for some file types. This breaks the core assumption of v2.0's proven content-hash diff engine — if `md5_hash` of downloaded bytes ≠ frame's reported `md5_hash`, every sync run will re-upload every photo forever, burning the anti-abuse budget on ordinary usage. **Prevention is a cheap, high-confidence live spike before any Google integration ships** — the project has already proven (Phases 6, 7, 10) that live probes are the most reliable design-redirect mechanism in this codebase's history.

**The third non-obvious correctness trap is cache pruning.** Pruning the local cache directory immediately after uploads confirm is appealing (bounded disk usage), but it breaks the diff engine's ability to distinguish "already synced, still in album" from "removed from album" on the second run — both look like "file absent." The fix is a **persisted `google_media_id → md5_hash` manifest** that survives pruning and lets the diff engine rebuild its demand dict from the manifest plus the current album listing, not from a directory walk. This manifest is the load-bearing design point that makes "reuse the v2.0 pipeline unchanged" actually true.

**Recommendation:** Build to the Picker-API model (Option A in STACK.md research), with explicit requirements language changes, two critical live spikes before Phase 1 integration work starts, and a manifest-backed cache design that makes pruning safe.

---

## Key Findings

### Recommended Stack (from STACK.md)

Google Photos authentication and album access require only two new direct dependencies:

**Core libraries:**
- `google-auth` (2.57.0) — OAuth credential object and token refresh (`Credentials.refresh()`) with Python 3.10–3.14 support via pure-Python wheels
- `google-auth-oauthlib` (1.4.1) — `InstalledAppFlow.run_local_server()` for loopback-redirect OAuth, PKCE handled internally, matching installed-app flow conventions

**Support libraries:**
- `tomli-w` (1.2.0) — TOML config file writes for the album↔frame mapping (optional but recommended for human-editable config persistence)
- Hand-rolled single 401-retry logic — one 12-line helper inside `execute_plan`, not `tenacity` (the retry requirement is narrow: exactly once, only on 401, only after fresh login)
- `concurrent.futures.ThreadPoolExecutor` (stdlib) — concurrent Google media-item downloads to the local cache, strictly upstream of the Aura write path (concurrency is Google-side only, per MOD-01 scope carveout)

**What NOT to use:**
- `google-api-python-client` — the Picker API postdates its bundled discovery cache, adding integration complexity without payoff; raw `httpx` through the existing `Client`/DI seam is simpler
- Any async rewrite of the Aura client (MOD-01 deferred; concurrency scoped to downloads only, which run synchronously into a local directory before the sequential write pipeline starts)

**VERIFIED confidence:** Library versions and Python 3.14 wheel availability confirmed via PyPI. Google Photos API access model (scope removal, Picker API mechanics) verified against current (dated 2026-08-28) developers.google.com pages and independent tools' archived decisions (`gphotos-sync` maintainers' closeout rationale). **INFERRED confidence (MEDIUM):** Exact Picker API edge cases (session expiry duration, `baseUrl` 60-min window, pagination completeness guarantees) not yet live-validated by this project.

### Expected Features (from FEATURES.md)

**Must have (table stakes, MVP for "sync an album once"):**
- OAuth loopback link/status/unlink — matches existing credential-handling posture, required by every other feature
- Single album → single frame sync via reused v2.0 pipeline (download cache → content-hash diff → hide/upload execution) — the architecture decision that bounds risk
- Hide-by-default mirror semantics, reusing the Phase 10 classifier — matches established safety posture; real deletion remains opt-in and count-gated
- Photos only, videos reported — frame-side `md5_hash` null for all video; cannot be diffed
- Dry-run plan visible before any execute — matches project's core convention

**Should have after MVP validation (v1.x, competitive):**
- N-album ↔ N-frame persisted mapping, reconciled in one CLI invocation
- Plan preview without a fresh Picker session every time (cached last-known-picked-items diff) — turns an interactive-only API into something feeling repeatable
- Disk-space sanity check before bulk download

**Not in scope, documented as limitations (v2+):**
- "Live" auto-syncing (Picker API has no webhook/change-feed primitive — design assumes user-invoked `sync` runs, not unattended scheduled sync)
- Video sync (would need alternate hashing strategy, out of scope pending future design)
- Streaming Google bytes to S3 without local cache (rejected; reusing the proven v2.0 pipeline is the safety bet)

### Architecture Approach (from ARCHITECTURE.md)

Add a `auraframes/google/` package that mirrors the existing `Client`/`BaseApi` dependency-injection seam exactly, maintaining the offline-testable `httpx.MockTransport` harness. The Google side is **structurally separate** from the Aura write side: concurrent downloads happen in `auraframes/google/download.py`, producing local cache files; those files feed into the unchanged `compute_plan()` + `execute_plan()` pipeline, which has never changed since v2.0.

**Load-bearing design decision:** Do NOT call `scan_directory()` directly on the pruned Google cache dir. Instead, write a new `build_wanted_hashes()` function that iterates the **album's current listing** (not the filesystem) and reconstructs the demand dict by: (1) pulling known hashes from a persisted `google_media_id → md5_hash` manifest for items still in the album, (2) downloading and hashing items the manifest has never seen. This produces the exact `(local_hashes, skipped_count)` shape `compute_plan()` expects, reusing it **verbatim**, and makes cache pruning safe: absent files no longer break correctness because absence is resolved by manifest lookup, not directory walk.

**Major components:**
1. `GoogleClient` — `httpx`-based, mirroring `auraframes/client.py:Client`, with token injected per-request (since Google tokens are short-lived and can refresh mid-run)
2. `GooglePhotosApi` — thin REST wrapper (`list_album_items()`, etc.), mirrors `auraframes/api/frameApi.py`, zero business logic
3. `AlbumManifest` — persisted `google_media_id → md5_hash` mapping, uses `WriteBudget`'s atomic-write-with-corrupt-fallback pattern
4. `build_wanted_hashes()` — source abstraction producer; the one place cache pruning is reconciled with correctness
5. Shared `WriteBudget` instance — one per run, not per pair (anti-abuse surface is account-wide, keyed by email, confirmed in existing `cli.py:284-300`)
6. `_with_relogin_retry()` helper in `execute_plan()` — catches 401, calls `aura.login()` to mutate shared `Client` headers in place, retries once

### Critical Pitfalls (from PITFALLS.md)

1. **Album discovery mechanism is broken as scoped** — `albums.list` no longer works for a user's pre-existing albums (VERIFIED, permanent since 2025-03-31). Picker API requires interactive user selection each sync run, no headless re-enumeration. **Prevention:** Live spike before Phase 1 integration — call `albums.list` against a real non-app-created album and verify it 403s; run one full Picker session round-trip; rewrite the requirement language based on findings.

2. **Content-hash identity mismatch on Google downloads** — `=d` downloads do not reliably return byte-identical originals; GPS EXIF stripped, possible re-encoding (VERIFIED across 3+ independent sources including archived `gphotos-sync` tool). If `md5_hash(downloaded_bytes) ≠ frame.md5_hash`, every run re-uploads everything forever and burns WriteBudget on normal usage. **Prevention:** Cheap live spike — pick one photo already on the frame, download it back via Picker API `=d`, compute `get_md5()` on bytes, compare directly to frame's `md5_hash`.

3. **Empty/partial listing triggers mass-hide** — Mirror semantics as "album is source of truth" naturally becomes "remove what's no longer in the listing," but if the listing is truncated by a transient API failure, the diff engine cannot distinguish "user genuinely emptied album" from "listing failed partway." Every already-synced photo would be classified as removal candidate and hidden in one run. **Prevention:** (1) Treat empty source listing as an error. (2) Cap removals at a fraction threshold with explicit confirmation. (3) Verify listing completeness.

4. **401-retry duplicates writes and mutates shared client mid-batch** — Retrying a failed write by re-logging in mutates the shared `Client` headers while other batch items are in flight. A naive retry of `select_asset` creates a duplicate placeholder row if the retry succeeds. **Prevention:** Scope retry narrowly, check idempotency before retry, distinguish terminal failures, consume second WriteBudget token.

5. **Pruned-cache correctness trap** — Cache pruning breaks the diff engine's ability to distinguish "already synced" from "removed from album" on the second run. **Prevention:** Use the manifest-backed `build_wanted_hashes()` function that iterates the album's current listing (not the filesystem).

---

## Implications for Roadmap

The research strongly suggests a specific 9-phase sequence driven by hard technical dependencies and the user's explicit "write-path reliability first" decision:

### Phase Sequence

1. **Spike: Google Photos API Mechanism** — Verify Picker API is the only viable path; confirm hash mismatch is real on Google downloads. Gates all subsequent phases.

2. **Reliability Part 1** — 401-retry with relogin, `.png` upload support, HEIC decode decision. Reduces noise in Google integration UAT.

3. **Reliability Part 2** — Placeholder-row reconciliation (independent, unblocks `test_read_03_pagination`).

4. **Google Client Plumbing** — OAuth loopback, token persistence, `aura-cli status` + `google login` verbs. Infrastructure only, no album logic.

5. **Album Discovery** — Determined by Spike results. If Picker API: documented manual-pick workflow + config verb.

6. **Manifest + Download** — `AlbumManifest` persistence, `build_wanted_hashes()` function, concurrent downloads. The load-bearing design.

7. **Single Album → Frame MVP** — End-to-end single-pair sync. Reuses v2.0 `compute_plan()`/`execute_plan()` unchanged. Live UAT: two-run test with removal/re-add.

8. **Many-to-Many Config** — N-pair per-pair loop, shared `WriteBudget`, continue-past-failure, account-level lockout handling.

9. **Polish** — Status extension, disk-space pre-flight, bounded-batch download, cache lockfiles.

### Phase Ordering Rationale

- **Spike first:** Determines whether the entire architecture survives (Picker API mechanics, hash mismatch reality). Cheap relative to cost of discovering assumptions were wrong mid-Phase 7.
- **Reliability before Google:** Reduces Phase 7 UAT noise. The existing ~4-in-10 spurious 401 failures would mask new Google integration bugs.
- **Plumbing before logic:** OAuth (Phase 4) before album discovery (Phase 5) — natural dependency order.
- **Manifest design before single-pair MVP:** Phases 5-6 build infrastructure; Phase 7 proves correctness with real end-to-end run.
- **Single-pair before N-pair:** MVP is the hard risk; many-to-many is additive.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 1 (Spike):** This is the research. Returns findings that either confirm or reshape Phases 5-7.
- **Phase 5 (Album Discovery):** Picker API session lifecycle in a multi-pair run — may surface orchestration challenges.

Phases with well-documented patterns (standard execution, no research needed):
- **Phase 4 (Client Plumbing):** OAuth loopback is an established pattern; `google-auth-oauthlib` is the official library.
- **Phase 7-8 (Sync Logic):** Mirrors v2.0 `compute_plan`/`execute_plan`, which is already proven live.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| **Stack** | HIGH | Library versions and Python 3.14 compatibility verified via PyPI. Google API scope restriction verified against current developers.google.com pages. Recommended libraries follow project's existing patterns. |
| **Features** | HIGH | Table-stakes features reuse v2.0 conventions. Differentiators grounded in comparable tools' design (rclone, immich-go). Anti-features validated by project's Phase 8 incident history. |
| **Architecture** | MEDIUM-HIGH | All recommendations grounded in direct source code inspection. Manifest-backed cache is novel — design is sound, but edge cases require live testing. Mirrors existing proven patterns (v1.1+ DI seam, offline harness). |
| **Pitfalls** | MEDIUM | Pitfalls 1-2 are VERIFIED against Google sources but not yet live-tested by this project (Phase 1 spike). Pitfalls 3-6 are architectural or pattern-based. |

**Overall Confidence:** MEDIUM-HIGH

Success depends on Phase 1 spike confirming or correcting the Google API assumptions. The roadmap can proceed with Phases 2-3 in parallel while Phase 1 runs.

### Gaps to Address

1. **Picker API edge cases** — Session lifecycle, pagination, multi-pair orchestration require live testing beyond the single-session spike.
2. **HEIC decode strategy** — No Pillow HEIC support in this environment. Phase 2 must decide: add dependency, document as unsupported, or use conversion workaround.
3. **Hash mismatch confirmation** — If Phase 1 confirms hash mismatch, the manifest becomes non-optional design decision.
4. **`WriteBudget` accounting under retry** — Phase 2 tests must verify retried calls consume two tokens, not one.
5. **Google token refresh in Testing mode** — 7-day expiry is MEDIUM-confidence. Phase 4 must decide: document, move to Production, or implement auto-re-consent flow.

---

## Sources

**Official Google Documentation (HIGH confidence, verified 2026-09-03):**
- developers.google.com/photos/support/updates (scope removal effective 2025-03-31, page dated 2026-08-28)
- developers.google.com/photos/overview/authorization (scope table, Library API limitations)
- developers.google.com/photos/picker/* (session lifecycle, 60-min baseUrl window)
- Google Developers Blog — "Updates to the Google Photos APIs"

**Project Documentation (HIGH confidence):**
- `.planning/PROJECT.md` (v3.0 scope, v2.0 achievements, Phases 6-10 findings)
- Direct codebase inspection: `sync.py`, `client.py`, `aura.py`, `cli.py`, `ratelimit.py`

**Community Reports (MEDIUM confidence):**
- `github.com/gilesknap/gphotos-sync` (archived 2024-10-24, byte-identity issue documentation)
- rclone Google Photos backend (Picker API migration, forum discussion)
- `github.com/simulot/immich-go` (Takeout workaround approach)
- Multiple independent 2026-dated sources on 7-day Testing-status token expiry

---

*Research completed: 2026-09-03*  
*Ready for roadmap design: Yes, with Phase 1 spike as immediate prerequisite*
