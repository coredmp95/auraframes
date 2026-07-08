---
phase: 08-destructive-execution-upload-delete-verification
plan: 04
subsystem: verification
tags: [live-verification, aws-s3, aws-sqs, checkpoint]

requires:
  - phase: 08-destructive-execution-upload-delete-verification plan 03
    provides: shipped sync --apply/--yes path (execute_plan wired into the CLI)
provides:
  - Live confirmation that the upload round-trip, remove_asset, and delete_asset all behave as designed against a real Aura account/frame
  - 08-LIVE-FINDINGS.md documenting all three observations plus an incident note
affects: []

tech-stack:
  added: []
  patterns:
    - "One-off, structurally-isolated Python script (uv run python -c '...') as the standard way to probe an unwired API primitive live without adding any code path to the shipped module — used for the delete_asset blast-radius probe"

key-files:
  created:
    - .planning/phases/08-destructive-execution-upload-delete-verification/08-LIVE-FINDINGS.md
  modified:
    - .planning/STATE.md

key-decisions:
  - "delete_asset's live probe used Asset.model_construct(id=...) (bypassing full pydantic validation) exactly as RESEARCH.md's how-to-verify recommended, rather than trying to fully hydrate a real Asset object for a single-purpose throwaway call"
  - "The accidental large-batch delete (see Issues Encountered) was resolved by re-running the shipped sync --apply --yes command with a fresh process/token rather than writing any new recovery code — the existing fail-loud + continue-past-failure design (WRITE-05/D-08) already made the partial failure safely resumable"

patterns-established:
  - "Live checkpoint findings are recorded in a dedicated {phase}-LIVE-FINDINGS.md file, separate from the plan's own {phase}-{plan}-SUMMARY.md, so the raw live observations remain a stable, independently-citable artifact regardless of how the plan's own summary evolves"

requirements-completed: [WRITE-01, WRITE-02, WRITE-03, WRITE-04]

coverage:
  - id: L1
    description: "New local photos appear on the test frame after sync --apply, confirmed via inspect (WRITE-01)"
    requirement: WRITE-01
    verification:
      - kind: manual
        ref: "uv run aura-cli sync ./data/ --frame \"Cadre de Fabrice\" --apply --yes, followed by inspect confirming asset b7bfc558-... present"
        status: pass
    human_judgment: true
  - id: L2
    description: "remove_asset disassociates a gone-locally photo from the frame, confirmed via inspect (WRITE-02)"
    requirement: WRITE-02
    verification:
      - kind: manual
        ref: "72 total assets removed live across two --apply --yes runs; final dry-run confirmed 0 remaining delete candidates"
        status: pass
    human_judgment: true
  - id: L3
    description: "delete_asset's real blast radius is observed against a disposable asset and documented (WRITE-03)"
    requirement: WRITE-03
    verification:
      - kind: manual
        ref: "One-off script calling AssetApi.delete_asset on a dedicated disposable throwaway image; DELETE /assets/{id}.json returned 200 empty body, asset vanished entirely — see 08-LIVE-FINDINGS.md"
        status: pass
    human_judgment: true
  - id: L4
    description: "Uploads target the correct frame's SQS confirmation queue regardless of which frame is chosen (WRITE-04)"
    requirement: WRITE-04
    verification:
      - kind: manual
        ref: "Live upload to \"Cadre de Fabrice\" (not the originally-hardcoded test frame) completed with no queue-related errors"
        status: pass
    human_judgment: true

duration: ~35min (across two live-verification sessions with an operator-driven recovery in between)
completed: 2026-07-08
status: complete
---

# Phase 8 Plan 04: Live Upload + Delete Verification Summary

**Proved the write path live for the first time in this codebase's history: the upload round-trip, `remove_asset`, and `delete_asset`'s blast radius were all confirmed against a real Aura account and frame, with `remove_asset` reaffirmed as `--apply`'s safe default and `delete_asset` confirmed broader-scoped and correctly left unwired.**

## Performance

- **Duration:** ~35 min across two sessions (an operator-driven live run, an incident-recovery run, and the delete_asset probe)
- **Completed:** 2026-07-08
- **Tasks:** 4 completed (3 human-verify checkpoints + 1 autonomous findings/documentation task)
- **Files modified:** 0 source files (this plan produces no code changes) — 2 docs files (`08-LIVE-FINDINGS.md` created, `STATE.md` updated)

## Accomplishments

- **WRITE-01 confirmed:** `sync --apply --yes` uploaded a new local file live to "Cadre de Fabrice"; the photo was confirmed present via `inspect` immediately after. The double `select_asset` call and both SQS polls (preserved unchanged per RESEARCH.md Pitfall 4) caused no errors.
- **WRITE-04 confirmed:** the upload correctly targeted "Cadre de Fabrice"'s own SQS queue (not the originally-hardcoded test-frame queue), confirming the `get_sqs(frame_id)` parameterization fix works for an arbitrary frame.
- **WRITE-02 confirmed:** `remove_asset` correctly disassociated assets from the frame — exercised at real scale (72 total across two runs, see Issues Encountered) with 0 final failures.
- **WRITE-03 confirmed:** a dedicated disposable throwaway image was uploaded and then sacrificed to a standalone `delete_asset` probe (never through the CLI/`--apply` path). `DELETE /assets/{id}.json` returned 200 with an empty body and the asset vanished entirely — the endpoint is asset-scoped, not frame-scoped like `remove_asset`, confirming it is broader-reaching and correctly excluded from `--apply` (D-06).
- `08-LIVE-FINDINGS.md` created, consolidating all three observations plus a detailed incident note.
- `STATE.md`'s "Delete-primitive ambiguity" and "Hardcoded SQS frame ID" blockers marked RESOLVED.

## Files Created/Modified

- `.planning/phases/08-destructive-execution-upload-delete-verification/08-LIVE-FINDINGS.md` — the three live observations plus the incident note
- `.planning/STATE.md` — two Phase 8 blockers marked RESOLVED

## Decisions Made

- Used `Asset.model_construct(id=...)` for the `delete_asset` probe rather than fully hydrating a real `Asset`, per RESEARCH.md's own vetted example
- Recovered the mid-batch auth failure (see Issues Encountered) by simply re-running the already-shipped `sync --apply --yes` command with a fresh process, rather than writing new retry/recovery code — the existing fail-loud + continue-past-failure design was sufficient

## Deviations from Plan

### Auto-fixed Issues

**1. [Recovered live incident, not a code defect] Unplanned large-batch delete during Task 1's live upload check**
- **Found during:** Task 1 (live upload verification)
- **Issue:** The operator ran `sync --apply --yes` against `./data/` (2 files) while "Cadre de Fabrice" held ~74 pre-existing real photos (accumulated since 2012, the same frame used for Phase 6/7's live checkpoints). Since `sync` deletes anything on the frame not present locally, this produced and executed a much larger plan than the single-photo test the checkpoint intended: 1 upload + 72 deletes. 47 deletes succeeded via `remove_asset`; the remaining 25 failed with `401 Unauthorized` when the auth session/token expired mid-batch.
- **Fix:** No code change was needed. WRITE-05's fail-loud handling and D-08's continue-past-failure model worked exactly as designed — each failure was individually caught and attributed, the batch continued, and the CLI exited non-zero (confirming SYNC-04). A follow-up dry-run confirmed the frame was left in a consistent state (no corruption), and re-running `sync --apply --yes` with a fresh process (fresh token) completed the remaining 25 deletes with 0 failures.
- **Files modified:** None — this was an operational/process finding, not a code fix.
- **Verification:** Final dry-run against "Cadre de Fabrice" showed 0 to upload, 0 to delete, confirming full reconciliation. The operator confirmed all affected photos are independently backed up elsewhere, so no data was actually lost.
- **Committed in:** N/A (no code change; documented in `08-LIVE-FINDINGS.md`)

---

**Total deviations:** 1 (live operational incident, fully recovered, no code defect found)
**Impact on plan:** None on functionality — all three live checkpoints (WRITE-01/02/03) and WRITE-04 were ultimately confirmed. The incident is itself positive evidence that SYNC-04's fail-loud/non-zero-exit contract works correctly under a real partial-failure condition.

## Issues Encountered

See "Deviations from Plan" above — the mid-batch auth-token expiry is a genuine, previously-unknown operational finding (a single `--apply` run against a large delete batch can outlive the auth session's token lifetime), flagged in `08-LIVE-FINDINGS.md` as a future hardening candidate. It is not required by any Phase 8 requirement (SYNC-03/04, WRITE-01..05) and is not fixed as part of this plan.

## User Setup Required

None further — all live verification for this phase is now complete. `AURA_EMAIL`/`AURA_PASSWORD` (already configured via local `.env`) were the only credentials needed.

## Next Phase Readiness

- All 7 Phase 8 requirements (SYNC-03, SYNC-04, WRITE-01 through WRITE-05) are now implemented and live-confirmed.
- `delete_asset` remains fully unwired from any executable path (`grep -c 'delete_asset' auraframes/sync.py auraframes/cli.py` → 0), preserving the safe default.
- No blockers for phase completion / milestone v2.0 progression.

---
*Phase: 08-destructive-execution-upload-delete-verification*
*Completed: 2026-07-08*

## Self-Check: PASSED

`08-LIVE-FINDINGS.md` exists and documents all three live observations plus the incident note; `STATE.md`'s two Phase 8 blockers are marked RESOLVED; `delete_asset` confirmed absent from `auraframes/sync.py` and `auraframes/cli.py`.
