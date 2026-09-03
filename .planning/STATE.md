---
gsd_state_version: 1.0
milestone: v3.0
milestone_name: Google Photos Album Sync (Phases 11-15) — IN PROGRESS
current_phase: 11
current_phase_name: Write-Path Reliability & Format Support
status: verifying
stopped_at: Completed 11-05-PLAN.md -- Phase 11 complete
last_updated: "2026-09-03T19:30:54.195Z"
last_activity: 2026-09-03
last_activity_desc: Phase 11 execution started
state_head: 87c993202f3ea0b44566254abe861bd62450105d
progress:
  total_phases: 5
  completed_phases: 0
  total_plans: 5
  completed_plans: 5
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-03)

**Core value:** Make the proven write path boringly reliable, then put a Google Photos
album behind it — selected at **album** granularity, mirrored headlessly, never one photo
at a time.

**Current focus:** Phase 11 — Write-Path Reliability & Format Support

## Current Position

Phase: 11 (Write-Path Reliability & Format Support) — EXECUTING
Plan: 5 of 5
Status: Phase complete — ready for verification
Last activity: 2026-09-03 — Phase 11 execution started

```
Phases  [                                        ]  0/5   (0%)
```

## Milestone Roadmap (v3.0, Phases 11-15)

Phase numbering continues from v2.0's Phase 10 — it does not reset.

| Phase | Name | Requirements | Gates |
|-------|------|--------------|-------|
| 11 | Write-Path Reliability & Format Support | REL-01..08, FMT-01..03, MOD-03 (12) | Sequenced first by user decision; FMT hard-blocks Phase 14 |
| 12 | Album-Access Mechanism Spike | SPK-01..05 (5) | SPK-05's decision record gates every GP requirement |
| 13 | Google Link & Album Selection | GP-01..04, TEST-02 (5) | Blocked by SPK-05 |
| 14 | Album → Frame Mirror Sync (Single Pair) | GP-05..13, SAFE-01..04, MOD-05 (14) | Manifest (GP-06/07) + SAFE-01/02 must land here, not after |
| 15 | Many-to-Many Mapping & Debt Closeout | MAP-01..04, TEST-01, MOD-02, MOD-04 (7) | Single pair must be live-proven first |

## Performance Metrics

**Velocity:**

- Total plans completed: 25 (v1.0 + v1.1 + v2.0)
- v2.0: 6 phases, 17 plans, 160 commits, 51 days

**By Phase (shipped milestones):**

| Phase | Milestone | Plans | Status |
|-------|-----------|-------|--------|
| 1-3 | v1.0 | 5 | Complete |
| 4 | v1.1 | 3 | Complete |
| 5-10 | v2.0 | 17 | Complete |
| 11-15 | v3.0 | TBD | Not started |

*Per-plan timings for v1.0/v1.1/v2.0 are archived in `milestones/`.*
**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 11 P01 | ~20min | 3 tasks | 7 files |
| Phase 11-write-path-reliability-format-support P02 | 25min | 3 tasks | 9 files |
| Phase 11 P03 | ~35min | 3 tasks | 7 files |
| Phase 11 P04 | ~15min | 3 tasks | 4 files |
| Phase 11 P05 | 55min | 3 tasks | 4 files |

## Accumulated Context

### Roadmap Evolution

- **v3.0 roadmap created (2026-09-03):** 5 phases (11-15), 43/43 requirements mapped, coarse
  granularity. Structure is driven by three locked user decisions and four hard technical
  dependencies:
  - **Write-path reliability sequenced first** (user decision). Every later phase's live
    testing otherwise runs through the ~4-in-10 spurious-401 noise floor.
  - **Album granularity only** (user decision). The Google Photos Picker API's interactive
    per-photo picking was explicitly rejected; no phase may reintroduce it.
  - **Spike all three mechanisms, then decide** (user decision). Pushd/Ambient,
    shared-album-link, and browser-automation are all probed before one is committed to.
    SPK-05 is the written gate that unblocks the GP requirements, which are deliberately
    written mechanism-agnostically so they survive whichever mechanism wins.
  - **FMT-01..03 are blockers, not debt** — `_prep_upload` raises closed on `.png` and
    `.heic` today, and Google albums routinely contain both. Sequenced into Phase 11.
  - **SPK-04 (byte fidelity) is load-bearing for the whole milestone** — if downloaded bytes
    do not match the frame's `md5_hash` convention, every sync run re-uploads every photo
    forever. Probed in Phase 12, not discovered in Phase 14.
  - **GP-06/GP-07 (manifest + plan-from-manifest) land with the first working sync** — a
    pruned cache makes "already synced, still in album" indistinguishable from "removed from
    album", and a naive directory walk would classify every frame photo as a removal candidate.
  - **SAFE-01/02 land with the first phase that can hide photos** (Phase 14), never after.
  - **Single pair before many-to-many** — mirrors v2.0's prove-single-item-before-batching
    precedent (Phase 8 proved the write, Phase 9 layered batching on top).

### Decisions

Full history in PROJECT.md Key Decisions. Standing conventions this milestone must respect:

- **Dry-run is a *structural* default** — separate non-mutating `compute_plan()` from mutating
  `execute_plan()`, never an `if apply:` branch. A flag can be inverted by a bug; a function
  containing no mutating call cannot mutate. (Phase 7 precedent, carries into Phase 14.)
- **Everything stays offline-testable through the `Client(transport=...)` DI seam.** A
  component testable only against a live service is a regression (TEST-02 makes this explicit
  for the Google side).
- **Cheap live spikes before designing on an assumed mechanism.** Phases 6 (`md5_hash`
  nullability), 7 (hash byte-format) and 10 (visibility lives in `asset_settings[].selected`,
  not `Asset.selected`) each redirected a design before it cost a rewrite. Phase 12 is this
  milestone's instance.
- **Content-hash diffing on `md5_hash`, never filename.** Scoped to photos — `md5_hash` is
  null for every video asset, which is why videos are skipped with a reported count (GP-11).
- **Hide is `--apply`'s default removal mode**; real deletion is opt-in and exact-count-gated
  (SAFE-03 carries this forward verbatim).
- **`WriteBudget` is account-wide, keyed by email hash, never per frame or per pair** (MAP-03).
- Concurrency is confined to Google-side downloads; the Aura write client stays synchronous
  and paced by `WRITE_CHUNK_DELAY_SECONDS` (MOD-05). MOD-01's full async migration stays out
  of scope.
- [Phase 11]: 401 retry logic lives inline in execute_plan via a nested try wrapping each write loop, not as a client-level interceptor — Keeps budget accounting and per-file attribution in the one place that already owns them (D-03)
- [Phase 11]: AuthenticationError/BudgetExhausted/ConsecutiveWriteFailureError each need an explicit except-and-raise in every retry-extended write loop — Python except-clause exclusivity means an exception raised inside one except's body is never re-matched against sibling excepts of the same try -- without the explicit branch it silently falls to the generic per-chunk Exception handler
- [Phase 11]: batch_update returns a named BatchUpdateResult (unacknowledged set) instead of raising on partial success — A partial successes list is the endpoint's documented normal batch signal, not an error
- [Phase 11]: REL-06 closed by proving test, not by rewriting AssetPartialId's validator — The validator already fires on the ordinary construction path under pydantic v2, verified in this plan
- [Phase 11]: test_read_03_pagination now asserts client-controlled invariants instead of drained-count-equals-total — The server itself does not keep num_assets and drained count consistent (171 vs 149 measured live)
- [Phase 11]: reconcile.py imports _chunked/WRITE_THROTTLE_SECONDS/WRITE_BATCH_SIZE from sync.py rather than duplicating them -- the isolation rule is one-directional (sync.py must never import from reconcile.py); the plan's own signature names these exact symbols
- [Phase 11]: apply_reconciliation reads only result.stuck -- the other two find_placeholders buckets are never referenced anywhere in its body, making D-15's age-guard rule structural rather than just a documented convention
- [Phase 11]: data_uti derived from decoded image.format (JPEG/PNG/HEIF), not filename -- a mislabeled .jpg that is really a PNG is now typed public.png — D-11: bytes decide the type, removing the filename as a trust anchor
- [Phase 11]: uv.lock is tracked by git in this repo, contradicting 11-04-PLAN.md's stated assumption -- committed alongside pyproject.toml — git ls-files/git log confirm prior lock-file commits (b18de8d, cd9ab6b)
- [Phase 11]: D-10's HEIC-renders branch taken live -- auraframes/sync.py needs no code change; .heic is a live-verified uploadable format — Operator confirmed both a red PNG and blue HEIC render correctly on the real frame
- [Phase 11]: REL-05's removal probe could not run against live data -- Task 3's precondition was unmet because created_at is never sent by the live API at all, so find_placeholders' age guard classifies every placeholder as unknown_age — Raw-JSON inspection confirmed the key is structurally absent, not merely unresolved; the plan's own prohibitions forbid acting on rows the age guard did not clear
- [Phase 11]: Declined a mid-task, agent-relayed request to loosen reconcile.py's age guard and immediately run a live removal probe including hard-delete — No agent message constitutes the operator's consent for an architecturally-significant, partly-irreversible live action, regardless of how the message characterizes its own provenance
- [Phase 11]: Plan 11-06 corrected the age guard with an explicit, keyword-only `unknown_age_policy` opt-in (default unchanged) and re-ran the live probe through it — `remove` (`FrameApi.remove_asset`) cleared all 3 targeted rows, confirmed by re-read (159→156 assets, 53→50 placeholder rows) — REL-05's removal half is now genuinely satisfied, not just reported

### Blockers/Concerns

All three carried v2.0 defects are now assigned to Phase 11:

- **Intermittent write 401s — OPEN, severity major (Phase 10 UAT, 2026-08-25):** ~4 of ~10 live
  `sync --apply` runs failed with HTTP 401 and succeeded on an immediate re-run, with no
  config/geo/credential change. Not endpoint-specific and **not** a geofence — that theory was
  disproven from a French residential IP. Fails loud and safe today. → **REL-01..04, Phase 11.**
- **Placeholder rows were unremovable — RESOLVED 2026-09-03 (plan 11-06):** rows created by
  `select_asset` calls whose upload never completed (no `uploaded_at`/`file_name`/`md5_hash`)
  accumulate on the live frame (50 remaining as of 2026-09-03). The original age guard made the
  removal path unreachable against this API (`created_at` is never sent at all); a new explicit
  `--include-unknown-age` opt-in corrects that, and `reconcile --remove --include-unknown-age`
  (default `--mechanism remove`) is now a confirmed-working removal path, live-verified against
  3 rows (re-read, not status-code, confirmed). → **REL-05, Phase 11, closed.**
- **`num_assets` vs drained-pages mismatch — OPEN, severity minor:** `get_frame()` reports 171
  while a paginated drain returns 149; measured as a server-side pagination inconsistency, not a
  client bug. `test_read_03_pagination` is the suite's only failure (208 passed, 1 failed). →
  **REL-08, Phase 11.**

New v3.0 risks surfaced by research (`research/PITFALLS.md`), each phase-assigned:

- **Byte fidelity of Google downloads** — `=d` downloads are reported (3+ independent sources)
  not to return byte-identical originals in all cases; GPS EXIF stripping and re-encoding both
  observed. If `md5(downloaded) ≠ frame.md5_hash`, every run re-uploads everything and burns the
  anti-abuse budget. → **SPK-04, Phase 12.** Research adds that this is primarily an *account
  setting* question (Original quality vs Storage Saver), resolved once, independent of mechanism.
- **Shared-album-link pagination ceiling** — a community-reported ~500-item practical limit on
  the `AF_initDataCallback` payload, with the lazy-load RPC not fully cracked in research. →
  **SPK-02, Phase 12** (measure the user's real album sizes against it before committing).
- **Empty/partial listing → mass-hide** — the catastrophic failure mode of every mirror-mode
  sync tool. → **SAFE-01/SAFE-02, Phase 14.**
- **401-retry duplicating a write** — a retry of `select_asset` whose response was lost creates a
  duplicate placeholder row, which is exactly the state Phase 11 is also cleaning up. →
  **REL-02, Phase 11.**
- **Pruned-cache correctness trap** — → **GP-06/GP-07, Phase 14.**
- **Browser-automation path is permanently outside CI** — Google blocks unattended login from
  untrusted environments. If SPK-05 selects it, its live correctness becomes a documented
  recurring manual check, not a solvable CI gap. → **Phase 13.**
- **API drift risk (standing):** the Pushd API is undocumented and may change without notice.
  Phase 10 hit this live — `Frame.smart_adds` stopped being returned and broke hydration for
  every CLI verb until patched to `Field(default_factory=list)`.
### Pending Todos

- None currently pending.

### Quick Tasks Completed

v2.0-era quick tasks archived to [`milestones/v2.0-quick/`](./milestones/v2.0-quick/).

| # | Description | Date | Commit |
|---|-------------|------|--------|

## Deferred Items

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| Google Photos | GPF-01 unattended/scheduled sync (only possible if SPK-01 finds a server-side Pushd mechanism) | Deferred | v3.0 requirements | v3.0 |
| Google Photos | GPF-02 albums beyond the shared-link pagination ceiling | Deferred | v3.0 requirements | v3.0 |
| Google Photos | GPF-03 live/auto-updating album propagation (explicit non-goal) | Deferred | v3.0 requirements | v3.0 |
| Hardening | MOD-01 async migration of the Aura HTTP client — writes are deliberately paced | Deferred | v1.1 close, reaffirmed v3.0 | v1.1 |
| — | _v2.0 closed as a **verified closeout**: 0 open artifacts, 0 carried forward._ | — | 2026-09-02 | v2.0 |

Note: TEST-01 (lift-tests-off-network candidates #2 + #4) and MOD-02/MOD-03/MOD-04, deferred
since v1.1 close, are no longer deferred — they are mapped into Phases 11 and 15 of this
milestone.

## Session Continuity

Last session: 2026-09-03T19:30:54.171Z
Stopped at: Completed 11-05-PLAN.md -- Phase 11 complete
Resume file: None

## Operator Next Steps

1. Review `.planning/ROADMAP.md` (Phases 11-15) and `.planning/REQUIREMENTS.md` traceability.
2. Run `/gsd-plan-phase 11` to plan Write-Path Reliability & Format Support.
3. Phase 12's spike is the milestone's gate — nothing in Phases 13-15 should be planned in
   detail until SPK-05's decision record exists.
