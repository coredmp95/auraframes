---
phase: 06-inspect-frame-resolution
plan: 02
subsystem: cli
tags: [live-verification, md5_hash, aura-cli, inspect, spike]

requires:
  - phase: 06-inspect-frame-resolution
    provides: "aura-cli inspect --frame <name|id> (Plan 06-01), root-level --debug flag"
provides:
  - "Live-confirmed answer to the hard Phase 7 design dependency: is Asset.md5_hash populated on read for pre-existing (non-client-uploaded) assets?"
  - "Documented finding in the two canonical locations Phase 7 planning reads: STATE.md Blockers/Concerns 'Phase 6 live spike' entry and PROJECT.md Context dated note (D-13)"
  - "Folded '--debug promotion' todo confirmed resolved/closed under .planning/todos/completed/ (no re-work needed — already shipped in Plan 06-01)"
affects: ["Phase 7 (diff-engine design) — content-hash diffing strategy for sync"]

tech-stack:
  added: []
  patterns:
    - "Live spikes piggyback on an already-shipped CLI command with --debug rather than throwaway scripts (D-12)"
    - "Findings that gate a future phase's design are recorded directly in STATE.md/PROJECT.md, not a new artifact file (D-13)"

key-files:
  created: []
  modified:
    - .planning/STATE.md
    - .planning/PROJECT.md

key-decisions:
  - "md5_hash is populated for photos but not videos — Phase 7's content-hash diffing is scoped to photos only; a local-manifest/alternate-hash fallback becomes required scope only if video sync enters Phase 7/8 scope"

patterns-established: []

requirements-completed: [CLI-03]

coverage:
  - id: D1
    description: "Live confirmation of whether Asset.md5_hash is populated on read for pre-existing assets (Success Criterion 4, D-12)"
    requirement: "CLI-03"
    verification:
      - kind: manual_procedural
        ref: "uv run aura-cli --debug inspect --frame \"Cadre de Fabrice\" — logged asset JSON inspected across 106 paginated assets (101 photos, 5 videos)"
        status: pass
    human_judgment: true
    rationale: "Requires a live account/frame and human observation of --debug log output; not automatable via a unit/integration test."
  - id: D2
    description: "Finding documented in STATE.md Blockers/Concerns and PROJECT.md Context (the two canonical Phase 7 read locations, D-13)"
    requirement: "CLI-03"
    verification:
      - kind: other
        ref: "grep -rInq md5_hash .planning/PROJECT.md && grep -rIniq 'phase 6 live spike' .planning/STATE.md"
        status: pass
    human_judgment: false
  - id: D3
    description: "Folded --debug promotion todo closed (moved to .planning/todos/completed/)"
    requirement: ""
    verification:
      - kind: other
        ref: "test -f .planning/todos/completed/2026-07-06-promote-debug-flag-to-a-global-cli-convention.md"
        status: pass
    human_judgment: false

duration: 8min
completed: 2026-07-07
status: complete
---

# Phase 6 Plan 2: Live md5_hash Spike Summary

**Confirmed live that `md5_hash` is populated for all 101 pre-existing photo assets but null for all 5 video assets on a real frame — content-hash diffing is viable for Phase 7's photo sync with no fallback needed, but videos would need a local-manifest fallback if they ever enter scope.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-07-07T00:10:00Z
- **Completed:** 2026-07-07T00:18:00Z
- **Tasks:** 2 (Task 1: checkpoint:human-verify live spike, observation-only; Task 2: auto, documentation)
- **Files modified:** 2

## Accomplishments
- Ran `uv run aura-cli --debug inspect --frame "Cadre de Fabrice"` live against the real account/frame and parsed the `--debug`-logged asset JSON across all 106 paginated assets.
- Confirmed: 101/101 photo assets (`.jpg`) have `md5_hash` populated (non-null base64) — 100%. 5/5 video assets (`.mp4`, identified via a `duration` field) have `md5_hash` NOT populated (`None`) — 0%.
- Noted expected drift (not a defect, per RESEARCH Pitfall 4): `inspect`'s displayed `Assets: 77` (from `Frame.num_assets`) differs from the actual paginated total (106) — consistent with a previously-documented Phase 2 finding.
- Resolved the hard Phase 7 design dependency (does the diff engine need a local-manifest fallback?): no, for photos; only conditionally, for videos.
- Documented the finding verbatim in STATE.md's "Phase 6 live spike" Blockers/Concerns entry and as a dated Context note in PROJECT.md, the two canonical locations Phase 7 planning reads from (D-13).
- Verified the folded `--debug`-promotion todo was already closed by Plan 06-01 (present under `.planning/todos/completed/`, absent from `.planning/todos/pending/`) — no re-work required.

## Task Commits

Task 1 was a live observation-only checkpoint (`gate="blocking"`) — no code change, no commit expected, per the plan's artifact list ("No code artifact and no new file (D-13)").

1. **Task 2: Document the md5_hash finding and resolve the folded todo** - `904faf0` (docs)

**Plan metadata:** (this commit) `docs(06-02): complete inspect frame resolution plan`

## Files Created/Modified
- `.planning/STATE.md` - "Phase 6 live spike" Blockers/Concerns entry rewritten from "unverified" to the confirmed answer + Phase 7 consequence
- `.planning/PROJECT.md` - dated 2026-07-06 Context note under the Phase 6 entry recording the same finding as canonical project history

## Decisions Made
- The Phase 7 diff-engine consequence is scoped precisely: md5_hash content-diffing is viable for photos with zero additional work; a local-manifest/alternate-hash fallback is deferred and only becomes required scope if video sync is ever pulled into Phase 7/8 (it currently is not — sync scope is photos-first per PROJECT.md's v2.0 target features).

## Deviations from Plan

None - plan executed exactly as written. The one anticipated conditional step ("skip todo move if already done") applied: the `--debug` promotion todo was confirmed already resolved by Plan 06-01 (commit `55c256a`), so Task 2 only performed the STATE.md/PROJECT.md documentation half of its file list — no todo file operation was needed.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 7's diff-engine design now has its hard live-verification dependency resolved: md5_hash-based content diffing is safe to build for photos; video handling (if ever in scope) needs an explicit fallback decision at that time.
- All Phase 6 requirements (CLI-03) validated; Phase 6 is complete pending final STATE/ROADMAP bookkeeping.

---
*Phase: 06-inspect-frame-resolution*
*Completed: 2026-07-07*

## Self-Check: PASSED

- FOUND: `.planning/phases/06-inspect-frame-resolution/06-02-SUMMARY.md`
- FOUND: commit `904faf0` (Task 2 docs commit)
- FOUND: `.planning/todos/completed/2026-07-06-promote-debug-flag-to-a-global-cli-convention.md`
- CONFIRMED: absent from `.planning/todos/pending/`
