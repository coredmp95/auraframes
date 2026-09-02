---
status: complete
phase: 10-hide-instead-of-delete-sync-mode
source: [10-01-SUMMARY.md, 10-02-SUMMARY.md, 10-03-SUMMARY.md, 10-04-SUMMARY.md]
started: 2026-08-25T08:15:11Z
updated: 2026-08-25T08:35:00Z
---

## Current Test

[testing complete]

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
result: pass
reported: "accept all, and the current frame is a test one, so you can run what you want on it"
note: |
  Accepted AND then closed. The user's authorization allowed running the real
  thing, so all three removal modes plus re-show were exercised end-to-end
  through the CLI against "Cadre de Fabrice" — see tests 16-20. The gap no
  longer exists.

### 14. Residual gap — probe residue left on "Cadre de Fabrice"
expected: |
  Three hidden 8x8 disposable JPEGs and five placeholder asset rows remain on
  the frame from Plan 10-01's probe. All are hidden or non-displaying, so the
  frame looks correct. Bulk deletion was refused by the environment's
  permission classifier and was not worked around. Accept, or request cleanup.
result: pass
reported: "accept all, and the current frame is a test one, so you can run what you want on it"
note: |
  Accepted, then cleaned up as far as the API allows. All 4 uploaded
  disposables destroyed and the one real photo hidden for testing was
  restored (hidden=False, selected=True). The 5 placeholder rows could NOT be
  removed — see the new gap below: they are unremovable through the API.
  Frame is 154 assets vs 149 at session start = the 5 permanent placeholders.

### 15. Residual gap — one pre-existing test failure (num_assets vs drained pages)
expected: |
  tests/test_read_path.py::test_read_03_pagination fails: get_frame reports
  num_assets=171 while draining every page returns 157. 58 of 157 assets are
  placeholder rows with no image, created by select_asset calls whose upload
  never completed. Pre-existing, unrelated to Phase 10, logged in STATE.md.
  Accept as out-of-scope, or request investigation before shipping.
result: pass
reported: "accept all, and the current frame is a test one, so you can run what you want on it"
note: |
  Accepted as out of scope. Partially explained as a side effect of this
  session: placeholder rows cannot be deleted (delete_asset returns 200 and
  does nothing; remove_asset returns 404), so they accumulate permanently.
  That is very likely why 58 exist and why num_assets disagrees with the
  drained page count.

### 16. Hide path end-to-end through `sync --apply` (default mode)
expected: Default `sync --apply` hides gone-local photos and reports "Hidden: N succeeded"
result: pass
note: "Hidden: 1 succeeded, 0 failed" against the live frame; asset stayed in filter=all

### 17. Re-show path end-to-end through `sync --apply`
expected: A locally-restored photo that is hidden on the frame is re-shown, not re-uploaded
result: pass
note: |
  "To re-show: 1 / Re-shown: 1 succeeded" with "To upload: 0" — the D-06 dedup
  guarantee holding end-to-end, not just in unit tests.

### 18. `--delete` end-to-end (remove_asset)
expected: `sync --apply --delete` removes the gone-local asset and reports "Removed: N succeeded"
result: pass
note: First attempt failed with a transient 401; the retry reported "Removed: 1 succeeded, 0 failed". See gap 1.

### 19. `--hard-delete` exact-count gate on a real TTY
expected: Typing anything other than the exact count aborts before any write; the correct count proceeds
result: pass
note: |
  Driven through a real pty. Typing "y" — the answer a normal y/N gate would
  accept — printed "IRREVERSIBLE: 1 photo(s) will be permanently destroyed
  account-wide" then "Aborted."; the asset was verified still present
  afterwards. Typing "1" proceeded. Also confirmed the non-interactive path
  still fails closed ("--apply requires --yes when running non-interactively").

### 20. `--hard-delete` irreversibly destroys, end-to-end
expected: The asset is permanently gone from the frame
result: pass
note: Frame 157 -> 156, target absent on re-read. A later run destroyed 2 more in one batch. First attempt failed 401; retry succeeded. See gap 1.

## Summary

total: 20
passed: 20
issues: 2
pending: 0
skipped: 0
blocked: 0

## Gaps

- truth: "A write issued by `sync --apply` succeeds on the first attempt"
  status: failed
  reason: "Observed live: roughly 4 of ~10 CLI write runs failed with a transient HTTP 401 and succeeded on an immediate re-run, with no config, geo or credential change. Seen on select_asset, remove_asset and delete_asset alike, so it is not endpoint-specific. The client has no retry, so the user sees a spurious failure and a non-zero exit and must re-run by hand."
  severity: major
  test: 18
  root_cause: ""
  artifacts: []
  missing: []
  debug_session: ""

- truth: "An asset created on a frame can be removed from it again"
  status: failed
  reason: "Placeholder rows — assets created by a select_asset call whose upload never completed (no uploaded_at, no file_name, no md5) — cannot be removed by any wrapped primitive. delete_asset returns HTTP 200 and removes nothing; remove_asset returns 404 Not found. 58 such rows have accumulated on the live frame and are permanently stuck, which also explains the num_assets (171) vs drained-pages (154) mismatch in test 15."
  severity: minor
  test: 14
  root_cause: ""
  artifacts: []
  missing: []
  debug_session: ""
