---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Directory-to-Frame Sync
status: planning
last_updated: "2026-07-05T19:15:00.000Z"
last_activity: 2026-07-05
progress:
  total_phases: 4
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-05)

**Core value (v2.0):** Prove the write path the same way v1.0/v1.1 proved the read path, and turn that proof into a real usable capability — mirroring a local photo directory to an Aura frame.
**Current focus:** v2.0 Directory-to-Frame Sync — Phase 5 (CLI Skeleton + Status) ready to plan

## Current Position

Phase: 5 of 8 (CLI Skeleton + Status) — first phase of the v2.0 milestone
Plan: — (not yet planned)
Status: Ready to plan
Last activity: 2026-07-05 — Roadmap created; 13 v1 requirements mapped to Phases 5-8

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**

- Total plans completed: 8 (across v1.0 + v1.1)
- Average duration: — min
- Total execution time: — hours

**By Phase (shipped milestones):**

| Phase | Milestone | Plans | Status |
|-------|-----------|-------|--------|
| 1-3 | v1.0 | 5 | Complete |
| 4 | v1.1 | 3 | Complete |
| 5-8 | v2.0 | TBD | Not started |

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table. Recent decisions affecting current work:

- Done bar shifts to the **write path** for v2.0 — upload + delete verified live, delivered as a real `sync`/`inspect`/`status` CLI (not another internal-only pass)
- Safety-first roadmap ordering: Phases 5-7 touch only already-live-verified read endpoints; all new write-path risk is sequenced into Phase 8
- Dry-run is a structural default (separate `compute_plan()`/`execute_plan()`), not an `if apply:` flag — decided at research time, to be enforced in Phase 7
- Additive `Client(transport=...)` / `Aura(client=...)` DI seam (from v1.1) is available to drive the CLI/sync stack offline in tests

### Pending Todos

None yet.

### Blockers/Concerns

- **Phase 6 live spike (hard dependency for Phase 7 design):** unverified whether `md5_hash` is populated on read for pre-existing (non-client-uploaded) assets — if not, Phase 7 needs a local-manifest fallback
- **Hash-format mismatch risk (Phase 7):** local hashing must match `S3Client.get_md5`'s base64-MD5 exactly, or every file looks "changed" forever → mass unwanted uploads/deletes
- **Delete-primitive ambiguity (Phase 8):** `remove_asset` (soft, frame-scoped) vs `delete_asset` (hard, unverified S3/Glacier scope) — both must be live-verified before locking the safe default
- **Hardcoded SQS frame ID (Phase 8, WRITE-04):** `get_sqs()` listens on the original test frame's queue; must be parameterized before sync can upload to an arbitrary frame
- API is undocumented and may have drifted since April 2023; the write path has never been exercised live in three years

### Quick Tasks Completed

| # | Description | Date | Commit |
|---|-------------|------|--------|
| 260630-qs8 | main.py loads a local .env at startup so the read-path demo picks up creds without exporting them; python-dotenv promoted to a runtime dep | 2026-06-30 | cd9ab6b |

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Testing | Lift-tests-off-network candidates #2 (authenticated value) + #4 (injected config) → TEST-01 (v2) | Deferred | v1.1 close |
| Hardening | MOD-01 async, MOD-02 config-ize AWS pool IDs/bucket, MOD-03 typed exceptions, MOD-04 loguru sink leak | Deferred | v1.1 close |

## Session Continuity

Last session: 2026-07-05 19:15
Stopped at: ROADMAP.md created for v2.0 — Phases 5-8, 13/13 requirements mapped
Resume file: None

## Operator Next Steps

- Run `/gsd-discuss-phase 5` (or `/gsd-plan-phase 5`) to begin Phase 5: CLI Skeleton + Status
