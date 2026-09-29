---
phase: 18-album-frame-mirror-sync-single-pair
plan: 02
subsystem: sync-engine
tags: [gsync, compute-plan, safe-01, offline-tested]
requires:
  - auraframes/sync.py (compute_plan — reused unchanged; SyncPlan shape)
  - auraframes/google/manifest.py (GoogleManifest — 18-01)
  - auraframes/google/cache.py (CacheOutcome — 18-01)
  - auraframes/google/redaction.py (redact_link)
provides:
  - auraframes/gsync.py (build_demand, SafeSyncError, run_google_sync_plan, format_plan_report, SENTINEL_SUFFIX)
affects: [18-03 (run_google_sync composes the mutating half around these)]
tech-stack:
  added: []
  patterns:
    - demand-map reconstruction (scan_directory-shaped) fed to compute_plan unchanged
    - sentinel-path demand entries for manifest members with pruned cache files, structurally barred from to_upload by a drift guard
key-files:
  created:
    - auraframes/gsync.py
    - tests/test_gsync_engine.py
  modified: []
key-decisions:
  - "Manifest members with pruned cache files assert their manifest md5 via a <id>.absent sentinel demand path — if it ever reaches to_upload the frame disputes the confirmed-upload claim and run_google_sync_plan raises manifest_drift instead of uploading a fictional path"
  - "SAFE-01 empty-frame-listing abort covers the live-observed get_assets drift (16-LIVE-FINDINGS) — same lesson as reconcile's T-11-11"
  - "failed/absent downloads are excluded from demand and reported, never planned from (SAFE-04 continuity)"
requirements-completed: [CSE-03, CSE-05, SAFE-01]
coverage:
  - deliverable: Demand rebuilt from listing+manifest, never a cache walk (CSE-03)
    verification:
      - kind: test
        ref: tests/test_gsync_engine.py#test_manifest_member_with_pruned_cache_asserts_md5_via_sentinel
        status: pass
      - kind: command
        ref: "! grep -nE \"rglob\\(|iterdir\\(\" auraframes/gsync.py (plan verify — passed)"
      - kind: test
        ref: tests/test_gsync_engine.py#test_second_run_zero_upload_with_pruned_cache
        status: pass
    human_judgment: false
  - deliverable: Structural dry-run — plan-computing half is pure (CSE-05)
    verification:
      - kind: test
        ref: tests/test_gsync_engine.py#test_compute_plan_imported_not_forked
        status: pass
      - kind: command
        ref: "gsync.py contains no mutating call: staged outcome is a parameter, execute_plan is not imported (source review)"
    human_judgment: false
  - deliverable: SAFE-01 named aborts before any plan output
    verification:
      - kind: test
        ref: tests/test_gsync_engine.py#test_safe01_empty_listing_aborts
        status: pass
      - kind: test
        ref: tests/test_gsync_engine.py#test_safe01_truncated_listing_aborts
        status: pass
      - kind: test
        ref: tests/test_gsync_engine.py#test_safe01_empty_frame_listing_aborts
        status: pass
    human_judgment: false
  - deliverable: Videos skipped counted and named via metadata delta (CSE-07 support)
    verification:
      - kind: test
        ref: tests/test_gsync_engine.py#test_video_delta_reported_through_the_plan
        status: pass
      - kind: test
        ref: tests/test_gsync_engine.py#test_format_plan_report_counts_videos_and_redacts
        status: pass
    human_judgment: false
duration: 20 min
completed: 2026-09-28
---

# Phase 18 Plan 02: gsync Plan-Computing Half Summary

The pure mirror-planning engine: demand from listing+manifest (sentinel paths
for pruned manifest members), v2.0's `compute_plan` reused unchanged, named
SAFE-01 aborts, manifest-drift fail-loud, redacted plan report. The roadmap's
load-bearing criterion 3 is proven offline: full manifest + pruned cache →
`to_upload == []`, `unchanged == N`.

## Accomplishments

- `auraframes/gsync.py`: `build_demand` (scan_directory-shaped demand map from
  listing+manifest; failed downloads excluded and reported),
  `run_google_sync_plan` (SAFE-01 gates → demand → compute_plan → drift
  guard), `SafeSyncError` with five named constructors, `format_plan_report`
  (counts + redacted candidates), `SENTINEL_SUFFIX`.
- 13 offline engine tests; suite 383 passing offline (was 370).

## Deviations from Plan

None - plan executed exactly as written. (Test-authoring fix mid-task: the
report-formatting test initially asserted an item line in a zero-upload plan;
corrected to assert their ABSENCE — the formatter was right, the test was not.)

## Issues Encountered

None

## Self-Check: PASSED
