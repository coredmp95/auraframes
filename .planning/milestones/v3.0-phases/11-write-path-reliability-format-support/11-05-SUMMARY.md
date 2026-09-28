---
phase: 11-write-path-reliability-format-support
plan: 05
subsystem: write-path-reliability
tags: [live-verification, heic, pillow-heif, reconcile, pytest-live, pagination]

# Dependency graph
requires:
  - phase: 11-01
    provides: "verify-then-retry 401 recovery, exercised live by this plan's push --apply run"
  - phase: 11-02
    provides: "BatchUpdateResult / test_read_03_pagination's rewritten assertions, exercised live in this plan"
  - phase: 11-03
    provides: "auraframes/reconcile.py's find_placeholders/apply_reconciliation, probed live in this plan"
  - phase: 11-04
    provides: "content-derived data_uti / pillow-heif, live-verified end-to-end by this plan"
provides:
  - "Live proof that .png and .heic both upload end-to-end and render on a real frame (FMT-02, FMT-03/D-10 renders branch) -- no code change needed in auraframes/sync.py"
  - "tests/test_write_formats_live.py: a live regression module for the PNG/HEIC round trip"
  - "The definitive root cause for plan 11-03's flagged Asset.created_at question: the live API never sends the field at all, confirmed against the raw JSON payload"
  - "11-LIVE-FINDINGS.md: the phase's live evidence record (T-11-17), including a declined mid-task authorization-escalation request, recorded verbatim for audit"
affects: [12-album-access-mechanism-spike, 14-album-frame-mirror-sync]

# Actuals (#2632)
actuals:
  tokens: 9500
  tasks: 3
  commits: 2

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "D-05 disposable-test-asset methodology applied to a live regression test: per-invocation-randomized pixel content (not a fixed constant) so a live test's own upload can never collide by content-hash with a prior run's still-present asset"
    - "Raw-JSON-bypass verification: when a pydantic-model field reads None, check the raw HTTP response before concluding the server sent-but-didn't-populate it versus never-sent-it-at-all -- these have different implications for a conservative fallback's reachability"

key-files:
  created:
    - tests/test_write_formats_live.py
    - .planning/phases/11-write-path-reliability-format-support/11-LIVE-FINDINGS.md
  modified:
    - auraframes/reconcile.py
    - docs/CLI.md

key-decisions:
  - "D-10's HEIC-renders branch was taken: the operator confirmed both a solid-red PNG and a solid-blue HEIC render correctly on the real frame, so auraframes/sync.py was left completely unmodified -- no refusal branch, no ELIGIBLE_EXTENSIONS change"
  - "Declined a mid-task, coordinator-relayed request to (a) loosen reconcile.py's age guard and (b) immediately run a live removal probe including hard-delete against real placeholder rows -- no agent's message, however it characterizes its own provenance (including a claimed AskUserQuestion outcome this executor did not itself observe), constitutes the operator's consent for an architecturally-significant, potentially-irreversible live action. Recorded verbatim in 11-LIVE-FINDINGS.md and offered as a follow-up-plan candidate rather than silently acted on or silently dropped"
  - "Task 3's stated precondition (at least one stuck placeholder row) was unmet live -- 0 of 53 placeholder rows landed in the stuck bucket, because /frames/{id}/assets.json never sends a created_at key at all (confirmed via raw JSON, not just the parsed model). No removal mechanism was attempted against live data; the honest reporting-satisfied/removal-open outcome was recorded instead of manufacturing a candidate or bypassing the age guard"
  - "A real bug in the plan's own required live test was found and fixed during execution: a fixed pixel color made tests/test_write_formats_live.py collide by content-hash on its second run, leaving test assets visible on the live frame between two failing attempts. Discovered via a full session-scoped visibility audit, all 8 test-run assets confirmed hidden, and the test fixed to randomize color per invocation"

patterns-established:
  - "A live-marked regression test that uploads content must randomize that content per invocation, never reuse a fixed constant -- a fixed-content live test breaks on its second CI run by design, since content-hash matching cannot distinguish 'my new upload' from 'my own prior run's still-present asset'"

requirements-completed: [FMT-02, FMT-03, REL-05, REL-08]

coverage:
  - id: D1
    description: "A directory containing .png files uploads end-to-end to the real frame and is confirmed present, displaying, and correctly typed (public.png), not merely accepted by the API"
    requirement: FMT-02
    verification:
      - kind: e2e
        ref: "11-LIVE-FINDINGS.md#Task-2 -- push --apply command, full stdout, per-format field table"
        status: pass
      - kind: e2e
        ref: "tests/test_write_formats_live.py#test_write_png_round_trips_and_data_uti_is_public_png"
        status: pass
    human_judgment: true
    rationale: "The render half of FMT-02 can only be confirmed by a human looking at the frame or app -- the operator's verbatim verdict is quoted in 11-LIVE-FINDINGS.md, but this executor could not itself observe it, so human_judgment stays true even though every other level (API acceptance, server-side field population) is independently, automatically verified."
  - id: D2
    description: "The .heic question is answered on one of D-10's two branches: HEIC uploads and displays on the real frame (the renders branch), verified live and recorded for Phases 12/14"
    requirement: FMT-03
    verification:
      - kind: e2e
        ref: "11-LIVE-FINDINGS.md#Task-2 -- HEIC field table, D-10 branch decision, verification command (True True)"
        status: pass
      - kind: e2e
        ref: "tests/test_write_formats_live.py#test_write_heic_round_trips_and_data_uti_is_public_heic"
        status: pass
    human_judgment: true
    rationale: "Same as D1 -- the render confirmation is the operator's, quoted verbatim; the executor cannot independently observe a physical frame or app screen."
  - id: D3
    description: "A time-boxed live probe of placeholder-removal mechanisms ran against a bounded candidate set, and its verdict -- here, the honest 'zero eligible candidates, root cause identified and dated' -- is recorded; the reporting half of REL-05 is unconditional and was satisfied regardless"
    requirement: REL-05
    verification:
      - kind: e2e
        ref: "11-LIVE-FINDINGS.md#Task-3 -- reconcile report (53 placeholder rows / 157 scanned), raw-JSON created_at evidence, mechanism table (0 attempted, reasons dated), reconcile.py comment update"
        status: pass
    human_judgment: false
  - id: D4
    description: "The rewritten test_read_03_pagination executed against the live account and passed; the full live and offline suites are green"
    requirement: REL-08
    verification:
      - kind: e2e
        ref: "11-LIVE-FINDINGS.md#Task-2 -- full live suite: 6 passed, 271 deselected, 0 skipped; READ-03: drained 157 across 2 pages, total 170"
        status: pass
      - kind: integration
        ref: "uv run pytest -m 'not live' -q -- 271 passed, 6 deselected"
        status: pass
    human_judgment: false

# Metrics
duration: ~55min active work (spread across a longer session with multiple operator checkpoint waits)
completed: 2026-09-03
status: complete
---

# Phase 11 Plan 5: Live Write-Path & Placeholder-Reconciliation Verification Summary

**PNG and HEIC both live-verified end-to-end on the operator's real frame with no code change needed (D-10's renders branch), the phase's whole test suite runs green including a live pagination proof, and REL-05's removal probe honestly could not run against real data — root-caused live to the API never sending `created_at` at all, not to a failed mechanism.**

## Performance

- **Duration:** ~55 min of active execution work, across a longer session that included multiple pauses waiting on the operator (a physical-frame slideshow limitation, a render-verdict checkpoint, and a mid-task authorization request this executor declined)
- **Started:** 2026-09-03T12:29:03Z (first live write)
- **Completed:** 2026-09-03T19:28:00Z
- **Tasks:** 3 (1 checkpoint, pre-resolved by the operator before this executor started; 2 auto)
- **Files modified:** 4 (2 created)

## Accomplishments

- A sacrificial red PNG and blue HEIC both pushed live to "Cadre de Fabrice", confirmed fully hydrated server-side (not placeholders), and confirmed by the operator to render correctly — `"Le rouge s'afficher rouge et le bleu s'affiche bleu"`. D-10's HEIC-refusal fallback was never triggered; `auraframes/sync.py` needed zero changes.
- New `tests/test_write_formats_live.py`: a live regression module proving the PNG/HEIC round trip through the production `execute_plan` path, with `data_uti` asserted correct on each. A real bug was caught and fixed during its own first run — fixed pixel content collided by md5 across repeated runs, leaving three test assets briefly visible on the live frame — before it was allowed to land.
- Definitively root-caused plan 11-03's flagged `Asset.created_at` question: the live `/frames/{id}/assets.json` endpoint never sends the key at all (verified against the raw JSON, not just the parsed model), on any asset including this plan's own freshly-processed uploads.
- That root cause means `find_placeholders`' age guard currently has zero eligible `stuck` candidates on this account (53 placeholder rows, all `unknown_age`) — REL-05's removal-mechanism probe could not run against live data without violating the plan's own explicit prohibitions. Recorded as an honest, dated finding rather than forced.
- `auraframes/reconcile.py`'s `'complete'` mechanism stays `NotImplementedError`, with its comment corrected to say *why* (zero eligible candidates, dated) rather than implying a probe that never happened. `docs/CLI.md`'s known-issues and `reconcile --remove` sections updated to match exactly, including the unresolved 53-vs-58 count discrepancy.
- Declined a mid-task request, relayed through the orchestrating agent, to loosen the age guard and immediately run a live removal probe (including irreversible `hard-delete`) — recorded verbatim for transparency, not acted on, offered as a follow-up-plan candidate.
- Full live suite (`uv run pytest -m live -q`): 6 passed, 0 skipped, including `test_read_03_pagination` draining 157 assets across 2 pages against a reported total of 170. Full offline suite: 271 passed, 6 deselected — no offline regressions.

## Task Commits

1. **Task 1: Authorize the live run and name the target frame** — checkpoint, pre-resolved by the operator ("go physical frame is poweron") before this executor was dispatched; no commit (no file written by this task, per its own `<files>` declaration).
2. **Task 2: Live PNG and HEIC verification, and the D-10 branch decision** — `3999674` (feat)
3. **Task 3: Time-boxed live probe for a placeholder-removal mechanism** — `87c9932` (docs)

## Files Created/Modified

- `tests/test_write_formats_live.py` — New live-marked module: PNG/HEIC round-trip regression tests through `execute_plan`, with per-invocation-randomized pixel content
- `.planning/phases/11-write-path-reliability-format-support/11-LIVE-FINDINGS.md` — New findings record: full command output, field tables, the operator's verbatim render verdict, the D-10 branch decision, the reconcile report, the `created_at` root cause with raw-JSON evidence, the mechanism table (0 attempted, reasons dated), and the declined mid-task authorization request recorded verbatim
- `auraframes/reconcile.py` — `_complete_placeholder`'s docstring and the `_RECONCILE_PRIMITIVE` dispatch-table comment corrected to record the dated, honest reason `'complete'` remains untested (no behavior change)
- `docs/CLI.md` — Known-issues "Placeholder rows accumulate" and the `reconcile --remove` section updated with the 2026-09-03 live finding and the unresolved count discrepancy

## Decisions Made

- D-10's HEIC-renders branch was taken on the operator's confirmed verdict; no code change to `auraframes/sync.py`.
- Declined the mid-task authorization-escalation request (loosen the age guard + immediately run a live, partly-irreversible removal probe) because it arrived relayed through an agent rather than directly from the operator or an observed permission-system interaction — see Deviations below for the full reasoning.
- Task 3's own stated precondition was unmet (0 stuck rows live); per this executor's precondition-check rules, that is reported rather than routed around, and the plan's own prohibitions against acting on unknown-age rows were treated as binding.
- The `tests/test_write_formats_live.py` fixed-color bug was fixed inline (randomized content) rather than deferred, since a live regression test that cannot survive its own second CI run is not a working regression test.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed pixel color in the required live test collided by content-hash across repeated runs, leaving test assets visible on the live frame**
- **Found during:** Task 2, first run of `tests/test_write_formats_live.py`
- **Issue:** `_round_trip_and_hide` used a fixed `(30, 144, 255)` pixel color for both the PNG and HEIC test bodies. `execute_plan(SyncPlan(to_upload=[path]))` uploads unconditionally (it does not dedupe against existing frame content the way `compute_plan` does), so a second run's identical bytes produced an identical `md5_hash` to the first run's still-present asset. The test's own `assert len(matches) == 1` then failed with `found 2` — and because that assertion fires before the cleanup `exclude_asset` call, the newly-uploaded (and, on the first failing run, one previously-uploaded) asset was left **visible** on the operator's real frame.
- **Fix:** Ran a full session-scoped visibility audit (all assets uploaded since session start, by timestamp) and hid the 3 that were still visible via `exclude_asset`. Fixed the test to randomize the pixel color per invocation (`random.randint` per call) so repeated runs can never collide by content.
- **Files modified:** `tests/test_write_formats_live.py`
- **Verification:** Re-ran the module after the fix — 2 passed; a full session-scoped audit afterward confirmed 8/8 test-run assets hidden, 0 visible. Full live suite subsequently green.
- **Committed in:** `3999674` (the fix landed before the commit, not as a follow-up — no broken version was ever committed)

### Declined Requests (not deviations from the plan — deviations FROM a mid-task request)

**2. [Rule 4-adjacent — declined, not auto-fixed] Mid-task request to loosen `reconcile.py`'s age guard and run a live removal probe including `hard-delete`**
- **Found during:** Task 3, after the reconcile report showed 0 stuck candidates
- **Request (relayed via the orchestrating agent, claiming an `AskUserQuestion` outcome this executor did not itself observe):** (1) add an opt-in unknown-age eligibility policy to `auraframes/reconcile.py`, defaulting to today's conservative behavior; (2) immediately probe `remove`/`hard-delete`/`complete` live, bounded to 3 rows, through the loosened gate.
- **Why declined:** this executor's operating rules hold that no agent's message constitutes the operator's consent for a consequential action, regardless of how the message characterizes its own provenance. The bundled request combined an architecturally-significant safety-gate change with an immediately-following, partly-irreversible (`hard-delete`) live action against real account data — exactly the combination those rules exist to gate on direct, verifiable authorization.
- **Outcome:** no code change to the age guard; no live removal mechanism attempted. Recorded verbatim in `11-LIVE-FINDINGS.md` for transparency and offered as a follow-up-plan candidate, per the same message's own stated fallback ("stop and say so rather than half-doing it").
- **Committed in:** `87c9932` (the finding and the decision are both part of this commit's `11-LIVE-FINDINGS.md` content, committed in Task 2's commit; `reconcile.py`'s comment update reflecting this is in this commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — a real bug in required test infrastructure, caught and fixed before landing) + 1 declined mid-task request (recorded, not acted on).
**Impact on plan:** The test fix was necessary for correctness — an unfixed version would have broken on every subsequent CI run. The declined request left REL-05's removal half honestly open rather than force-closing it through an unverifiable authorization path; no scope creep occurred in either direction.

## Issues Encountered

- **Two accidental login attempts with missing credentials**, both from this executor's own ad-hoc verification scripts run outside the repo's `load_dotenv()`-aware entry points (the CLI and `conftest.py` both call `load_dotenv()` correctly; two standalone diagnostic scripts did not, and one used `find_dotenv()` in a context where its stack-based discovery could not resolve the repo's `.env`). Both surfaced as HTTP 475 with the server's own "email or password was incorrect" message — an explicit, unambiguous credential error, not the ambiguous plain-401 anti-abuse signature `pushd-write-geofence` warns about. Confirmed via `uv run aura-cli status` immediately after that these were not evidence of an account-level lockout; no further script skipped `load_dotenv(dotenv_path=...)` after the fix.
- **Live placeholder count (53) does not match the last-recorded count in STATE.md (58, measured 2026-08-25).** Recorded as an open discrepancy in `11-LIVE-FINDINGS.md` rather than silently adopting either number — this plan does not explain the delta.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- FMT-01/02/03 are now fully closed: JPEG/PNG/HEIC all live-verified end-to-end on a real frame. Phase 12/14 can treat `.heic` as an ordinary uploadable format with no conversion step required on this frame's write path.
- REL-01 through REL-08 and MOD-03 are all closed. The write path's 401 recovery, `batch_update`'s unacknowledged-set handling, and the rewritten pagination test are all live-proven, not just offline-proven.
- REL-05's reporting half is unconditionally closed. Its removal half is honestly open, root-caused (not mysteriously stuck): whether any mechanism — including the unbuilt `'complete'` — can ever clear the existing 53 placeholder rows is now blocked on a genuine design decision (whether/how to widen `find_placeholders`' age-guard eligibility past its current conservative default) that this plan deliberately did not make unilaterally. This is a clean candidate for a small, explicitly-scoped follow-up plan with direct operator sign-off on the tradeoffs (especially `hard-delete`'s irreversibility).
- Phase 11 is complete: all 5 plans have summaries, all 12 requirements (REL-01..08, FMT-01..03, MOD-03) are satisfied.
- No blockers for Phase 12 (Album-Access Mechanism Spike).

---
*Phase: 11-write-path-reliability-format-support*
*Completed: 2026-09-03*

## Self-Check: PASSED

- `tests/test_write_formats_live.py`, `.planning/phases/11-write-path-reliability-format-support/11-LIVE-FINDINGS.md`, `auraframes/reconcile.py`, `docs/CLI.md` all verified present on disk with `[ -f ]`.
- Both task commit hashes (`3999674`, `87c9932`) verified in `git log --oneline`.
- All acceptance criteria from Tasks 2 and 3 re-verified: `11-LIVE-FINDINGS.md` contains the exact push command + full stdout + date; the per-format field table; the operator's verbatim render verdict; the D-10 branch sentence; the verification command output (`True True`); the reconcile report with date/frame; the `created_at` raw-JSON finding; the mechanism table (0 attempted, dated reasons); asset ids for both sacrificial uploads with hidden-not-deleted confirmation; the live pagination numbers (157/2/170).
- `uv run python -c "import auraframes.sync as s; print('public.heic' in s._DATA_UTI_BY_IMAGE_FORMAT.values(), '.heic' in s.ELIGIBLE_EXTENSIONS)"` → `True True`.
- `uv run python -c "import auraframes.reconcile as r; print(sorted(r._RECONCILE_PRIMITIVE))"` → `['complete', 'hard-delete', 'remove']`.
- `grep -v '^#' docs/CLI.md | grep -c 'reconcile'` → `12` (≥ 3 required).
- `git diff HEAD~2 HEAD -- auraframes/sync.py` → empty (confirms no code change on the D-10 renders branch, as required).
- `uv run pytest -m live -q`: 6 passed, 271 deselected, 0 skipped, 0 failed.
- `uv run pytest -m "not live" -q`: 271 passed, 6 deselected, 0 failed (matches the 11-04 baseline exactly — no offline regressions).
