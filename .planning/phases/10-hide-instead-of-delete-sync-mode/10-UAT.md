---
status: testing
phase: 10-hide-instead-of-delete-sync-mode
source: [10-01-SUMMARY.md, 10-02-SUMMARY.md, 10-03-SUMMARY.md, 10-04-SUMMARY.md]
started: 2026-08-25T08:15:11Z
updated: 2026-08-25T08:15:11Z
---

## Current Test

number: 13
name: Confirm the auto-covered deliverables and the residual gaps
expected: |
  All 12 coverage entries across the four plan summaries are automatically
  covered by passing tests or recorded live probes, so none is presented as a
  manual checkpoint. What needs a human is confirming that the auto-pass is
  trustworthy and accepting (or rejecting) the three residual gaps listed in
  Tests 13-15 below.
awaiting: user response

## Tests

### 1. exclude_asset hides an asset non-destructively — asset remains in get_assets?filter=all with asset_settings.selected flipped to false
expected: exclude_asset hides an asset non-destructively — asset remains in get_assets?filter=all with asset_settings.selected flipped to false
result: pass
source: automated
coverage_id: D1
covering: live probe against frame c063b384-…, raw JSON recorded in 10-LIVE-FINDINGS.md

### 2. select_asset re-shows a hidden asset (D-05 inverse)
expected: select_asset re-shows a hidden asset (D-05 inverse)
result: pass
source: automated
coverage_id: D2
covering: live probe, settings.selected false->true recorded in 10-LIVE-FINDINGS.md

### 3. delete_asset blast radius re-confirmed asset-scoped via a full before/after inventory diff (158 -> 157, exactly the target)
expected: delete_asset blast radius re-confirmed asset-scoped via a full before/after inventory diff
result: pass
source: automated
coverage_id: D3
covering: live probe with inventory diff, recorded in 10-LIVE-FINDINGS.md

### 4. get_assets sends filter=all so hidden assets stay in the listing
expected: get_assets sends filter=all so hidden assets stay in the listing
result: pass
source: automated
coverage_id: D1
covering: tests/test_offline_read_path.py::test_offline_get_assets_requests_filter_all

### 5. Asset.selected carries this frame's visibility, joined from asset_settings
expected: Asset.selected carries this frame's visibility, joined from asset_settings
result: pass
source: automated
coverage_id: D2
covering: tests/test_offline_read_path.py::test_offline_get_assets_joins_per_frame_visibility_from_asset_settings + live read (3 known-hidden assets read selected=False)

### 6. compute_plan classifies frame assets 4 ways and never re-uploads a hidden match
expected: compute_plan classifies frame assets 4 ways and never re-uploads a hidden match
result: pass
source: automated
coverage_id: D3
covering: tests/test_sync_engine.py (6 classification tests)

### 7. removal_mode selects exactly one primitive and leaves the other two untouched
expected: removal_mode selects exactly one primitive and leaves the other two untouched
result: pass
source: automated
coverage_id: D1
covering: tests/test_execute_plan.py::test_hide_mode_excludes_and_never_removes_or_deletes (+ delete/hard_delete siblings)

### 8. The re-show loop runs under every removal mode and precedes removals
expected: The re-show loop runs under every removal mode and precedes removals
result: pass
source: automated
coverage_id: D2
covering: tests/test_execute_plan.py::test_reshow_loop_runs_under_every_removal_mode, ::test_reshow_precedes_removal

### 9. hard_delete charges the write budget per asset; batch modes charge per chunk
expected: hard_delete charges the write budget per asset; batch modes charge per chunk
result: pass
source: automated
coverage_id: D3
covering: tests/test_execute_plan_budget_geo.py::test_hard_delete_acquires_one_token_per_asset_not_per_chunk

### 10. sync defaults to hide; --delete and --hard-delete are mutually exclusive and select their mode
expected: sync defaults to hide; --delete and --hard-delete are mutually exclusive and select their mode
result: pass
source: automated
coverage_id: D1
covering: tests/test_cli_sync.py::test_delete_and_hard_delete_are_mutually_exclusive; tests/test_cli_apply.py::test_default_mode_is_hide_and_says_so + live dry-run

### 11. --hard-delete requires re-typing the exact removal count; a wrong answer aborts before any write
expected: --hard-delete requires re-typing the exact removal count; a wrong answer aborts before any write
result: pass
source: automated
coverage_id: D2
covering: tests/test_cli_apply.py::test_hard_delete_requires_typing_the_exact_count (+ siblings)

### 12. Re-shows are reported in plan and summary and affect the exit code; push never re-shows
expected: Re-shows are reported in plan and summary and affect the exit code; push never re-shows
result: pass
source: automated
coverage_id: D3
covering: tests/test_cli_apply.py::test_reshow_is_reported_in_plan_and_summary, ::test_reshow_failures_make_the_run_exit_nonzero, ::test_push_never_reshows_even_with_reshow_candidates

### 13. Residual gap — --delete and --hard-delete never exercised end-to-end against a real frame
expected: |
  Only the hide path ran live end-to-end. The --delete and --hard-delete CLI
  paths are covered offline, and their underlying primitives (remove_asset,
  delete_asset) were live-verified in Plans 10-01/Phase 8 — but no one has run
  `sync --apply --delete` or `--hard-delete` through the CLI against a real
  frame. Accept as known, or ask for a live disposable-asset test.
result: [pending]

### 14. Residual gap — probe residue left on "Cadre de Fabrice"
expected: |
  Three hidden 8x8 disposable JPEGs and five placeholder asset rows remain on
  the frame from Plan 10-01's probe. All are hidden or non-displaying, so the
  frame looks correct. Bulk deletion was refused by the environment's
  permission classifier and was not worked around. Accept, or request cleanup.
result: [pending]

### 15. Residual gap — one pre-existing test failure (num_assets vs drained pages)
expected: |
  tests/test_read_path.py::test_read_03_pagination fails: get_frame reports
  num_assets=171 while draining every page returns 157. 58 of 157 assets are
  placeholder rows with no image, created by select_asset calls whose upload
  never completed. Pre-existing, unrelated to Phase 10, logged in STATE.md.
  Accept as out-of-scope, or request investigation before shipping.
result: [pending]

## Summary

total: 15
passed: 12
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps

[none yet]
