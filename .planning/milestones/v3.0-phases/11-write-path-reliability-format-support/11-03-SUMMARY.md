---
phase: 11-write-path-reliability-format-support
plan: 03
subsystem: write-path-reliability
tags: [reconcile, placeholder-rows, cli, pydantic, tdd]

# Dependency graph
requires:
  - phase: 11-01
    provides: "AuraError/RateLimitError exception hierarchy in auraframes/client.py"
provides:
  - "auraframes/reconcile.py: find_placeholders (pure placeholder classifier) and apply_reconciliation (bounded, gated removal), decoupled from the sync loop"
  - "aura-cli reconcile verb: unconditional stuck/recently-created/unknown-age placeholder report, opt-in --remove path"
  - "aura-cli inspect gains a one-line placeholder count computed by the same find_placeholders function"
  - "Asset.created_at: additive Optional field enabling the D-15 age guard"
affects: [11-05-live-verification]

# Actuals (#2632)
actuals:
  tokens: 17980
  tasks: 3
  commits: 3

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pure predicate / separate-mutating-function split mirrored from auraframes/sync.py's compute_plan/execute_plan, applied to a new data-hygiene module"
    - "A single pure counting function (find_placeholders) called from two CLI paths (inspect's one-line summary, reconcile's detailed report) so the two numbers can never disagree"
    - "Dispatch table + per-mechanism cost table (_RECONCILE_PRIMITIVE / _RECONCILE_REQUEST_COST) mirroring sync.py's _REMOVAL_PRIMITIVE / _REMOVAL_REQUEST_COST shape, reused via import rather than duplicated"
    - "Candidate-count cap (RECONCILE_PROBE_CANDIDATE_LIMIT) as a structural safety valve on a mutating function whose primitives are not yet confirmed to work"

key-files:
  created:
    - auraframes/reconcile.py
    - tests/test_reconcile.py
    - tests/test_cli_reconcile.py
    - tests/fixtures/assets_placeholders.json
  modified:
    - auraframes/models/asset.py
    - auraframes/cli.py
    - docs/CLI.md

key-decisions:
  - "reconcile.py imports _chunked/WRITE_THROTTLE_SECONDS/WRITE_BATCH_SIZE from auraframes/sync.py rather than duplicating them -- the plan's own apply_reconciliation signature names these exact symbols as defaults, and the phase's only isolation rule is one-directional (sync.py must never import from reconcile.py; the reverse is fine and explicitly directed)"
  - "apply_reconciliation reads only result.stuck -- result.recently_created/result.unknown_age are never referenced in its body, which is the structural (not just documented) enforcement of D-15's 'never a removal candidate' rule"
  - "The 'complete' mechanism is wired into the dispatch table but raises NotImplementedError naming plan 11-05, per the plan's explicit instruction -- it is a known, intentional stub, not an oversight"
  - "run_reconcile's --remove continuation lives inside the same outer try/except as the report, with RateLimitError/GeoMismatchError/BudgetExhausted as sibling except clauses (mirroring run_sync's shape exactly) rather than a nested try, so those three exception types get run_sync's identical messages instead of falling through to the generic 'Failed to reconcile frame' catch-all"

requirements-completed: [REL-05]

coverage:
  - id: D1
    description: "aura-cli reconcile --frame reports how many stuck placeholder rows a frame carries, unconditionally, whether or not any removal mechanism works"
    requirement: "REL-05"
    verification:
      - kind: unit
        ref: "tests/test_cli_reconcile.py#test_run_reconcile_reports_bucket_counts"
        status: pass
      - kind: unit
        ref: "tests/test_cli_reconcile.py#test_run_reconcile_empty_listing_refuses_to_report_zero"
        status: pass
    human_judgment: false
  - id: D2
    description: "aura-cli inspect prints a single placeholder-row count line so the problem is discoverable without knowing reconcile exists, computed by the exact same pure function reconcile uses"
    requirement: "REL-05"
    verification:
      - kind: unit
        ref: "tests/test_cli_reconcile.py#test_run_inspect_placeholder_count_matches_find_placeholders"
        status: pass
    human_judgment: false
  - id: D3
    description: "A placeholder is identified by the strict three-way null conjunction (uploaded_at, file_name, md5_hash); a video and a partially-hydrated asset each trip at most one condition and are never counted"
    requirement: "REL-05"
    verification:
      - kind: unit
        ref: "tests/test_reconcile.py#test_video_shaped_asset_excluded_from_every_bucket"
        status: pass
      - kind: unit
        ref: "tests/test_reconcile.py#test_partially_hydrated_assets_excluded_from_every_bucket"
        status: pass
    human_judgment: false
  - id: D4
    description: "A row within the age threshold (24h default, overridable) is reported as recently-created and is never a removal candidate; a row with no resolvable creation time is treated the same way"
    requirement: "REL-05"
    verification:
      - kind: unit
        ref: "tests/test_reconcile.py#test_recently_created_placeholder_at_default_threshold"
        status: pass
      - kind: unit
        ref: "tests/test_reconcile.py#test_overridden_age_threshold_reclassifies_the_same_row_as_stuck"
        status: pass
      - kind: unit
        ref: "tests/test_reconcile.py#test_unresolvable_creation_time_lands_in_unknown_age_never_stuck"
        status: pass
    human_judgment: false
  - id: D5
    description: "reconcile without --remove performs no write of any kind; --remove draws from the shared WriteBudget, carries a Proceed?/exact-count gate honouring --yes, and fails closed non-interactively without it"
    requirement: "REL-05"
    verification:
      - kind: unit
        ref: "tests/test_cli_reconcile.py#test_run_reconcile_report_only_makes_no_write_request"
        status: pass
      - kind: unit
        ref: "tests/test_cli_reconcile.py#test_run_reconcile_report_only_never_calls_apply_reconciliation"
        status: pass
      - kind: unit
        ref: "tests/test_cli_reconcile.py#test_run_reconcile_remove_without_yes_noninteractive_fails_closed"
        status: pass
      - kind: unit
        ref: "tests/test_cli_reconcile.py#test_run_reconcile_remove_yes_end_to_end_removes_stuck_rows"
        status: pass
    human_judgment: false
  - id: D6
    description: "apply_reconciliation is capped, structurally reads only the stuck bucket, and reports removed/failed honestly (a 404 populates failed without raising) -- the live verdict on whether any mechanism actually works is deferred to plan 11-05"
    requirement: "REL-05"
    verification:
      - kind: unit
        ref: "tests/test_reconcile.py#test_apply_reconciliation_remove_records_removed_and_issues_one_request_per_chunk"
        status: pass
      - kind: unit
        ref: "tests/test_reconcile.py#test_apply_reconciliation_remove_404_populates_failed_without_raising"
        status: pass
      - kind: unit
        ref: "tests/test_reconcile.py#test_apply_reconciliation_only_acts_on_stuck_bucket"
        status: pass
      - kind: unit
        ref: "tests/test_reconcile.py#test_apply_reconciliation_refuses_more_than_candidate_limit"
        status: pass
      - kind: unit
        ref: "tests/test_reconcile.py#test_apply_reconciliation_source_never_names_the_other_buckets"
        status: pass
    human_judgment: true
    rationale: "Whether 'remove'/'hard-delete' actually clear these rows on the live frame is explicitly out of scope for this plan (D-16) -- the live verdict is plan 11-05's job. Coverage here proves the mechanism is capped, gated, budgeted, and honest about failure (a 404 goes to `failed`, never silently swallowed); it does not and cannot prove live removal succeeds."

# Metrics
duration: ~35min
completed: 2026-09-03
status: complete
---

# Phase 11 Plan 03: Placeholder-Row Reconciliation Summary

**New `auraframes/reconcile.py` classifies stuck/recently-created/unknown-age placeholder rows via a strict three-way-null predicate with an age guard, and `aura-cli reconcile`/`inspect` report the count from the exact same pure function; `--remove` is a capped, budgeted, opt-in probe of a removal mechanism that is honestly not yet confirmed to work.**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-09-03T09:00:00Z (approx, session start)
- **Completed:** 2026-09-03T09:35:00Z
- **Tasks:** 3
- **Files modified:** 7 (4 created)

## Accomplishments

- `Asset.created_at` added as an additive `Optional[str] = None` field, correcting `11-CONTEXT.md`'s D-15 finding that the field was already non-optional (it was `AssetSetting.created_at`, a different model, at that line number -- `Asset` had no `created_at` field at all before this plan)
- New `auraframes/reconcile.py`: `find_placeholders` (pure) classifies a frame's assets into `stuck`/`recently_created`/`unknown_age` via the strict `uploaded_at is None and file_name is None and md5_hash is None` conjunction (D-14), age-guarded at 24h by default and overridable (D-15), with an unresolvable creation time treated exactly like a too-young row so the failure direction is always toward not deleting
- `ReconcileResult.placeholder_count` is the single number both `aura-cli inspect` and `aura-cli reconcile` print -- computed from one function so the two can never disagree
- New `aura-cli reconcile --frame` verb: reports scanned/stuck/recently-created/unknown-age counts unconditionally, refuses to report zero on an empty asset listing (rather than silently agreeing with a truncated/failed listing), and performs no write of any kind without `--remove`
- `aura-cli inspect` gained one placeholder-count line calling the exact same `find_placeholders` function `reconcile` uses
- `apply_reconciliation` -- this module's only mutating function -- operates exclusively on `result.stuck` (the other two buckets are structurally unreachable from its body, not just documented as off-limits), is capped at `RECONCILE_PROBE_CANDIDATE_LIMIT=25` candidates per call, draws from the shared account-wide `WriteBudget`, and reports `removed`/`failed` honestly (a 404 from the removal primitive populates `failed` without raising)
- `reconcile --remove` carries the same `Proceed? [y/N]` gate as `sync --apply` (with `--mechanism hard-delete` escalating to the exact-count-typing gate `sync --hard-delete` uses) and fails closed exactly like `sync`/`push --apply` when run non-interactively without `--yes`
- `docs/CLI.md` documents the new verb end-to-end and rewrites the "placeholder rows... cannot be removed" known issue to point at it while keeping the honest statement that no mechanism is yet confirmed to work

## Task Commits

Each task was committed atomically:

1. **Task 1: reconcile.py -- the pure placeholder predicate and age guard** - `e88b757` (feat)
2. **Task 2: the reconcile CLI verb and the inspect count line** - `ea48590` (feat)
3. **Task 3: apply_reconciliation -- the bounded, gated removal path** - `1a78de4` (feat)

**Plan metadata:** commit created below.

_All three tasks carried `tdd="true"`; tests were written and run alongside each task's implementation in the same commit rather than as separate RED/GREEN commits, since the plan's `<behavior>` blocks describe end-to-end offline-test scenarios rather than a strict single-assertion RED step (same pattern 11-01/11-02 used)._

## Files Created/Modified

- `auraframes/reconcile.py` - New module: `RECONCILE_AGE_THRESHOLD_SECONDS`, `ReconcileResult`, `_creation_instant`, `find_placeholders` (Task 1); `RECONCILE_PROBE_CANDIDATE_LIMIT`, `_RECONCILE_PRIMITIVE`, `_RECONCILE_REQUEST_COST`, `apply_reconciliation` (Task 3)
- `auraframes/models/asset.py` - `Asset.created_at: Optional[str] = None` added, alphabetically placed
- `auraframes/cli.py` - New `reconcile` subparser + `main()` dispatch, `run_reconcile` handler (report path in Task 2, `--remove` continuation in Task 3), one added line in `run_inspect`
- `docs/CLI.md` - New `reconcile` section (Contents entry, usage, report/`--remove` flows, candidate cap), `inspect` sample output line, rewritten "Placeholder rows accumulate" known issue
- `tests/fixtures/assets_placeholders.json` - New fixture: 2 stuck, 1 recently-created (substitutable token), 1 video-shaped, 1 unknown-age, 1 ordinary complete photo
- `tests/test_reconcile.py` - New module: 18 tests covering `find_placeholders` (Task 1, 10 tests) and `apply_reconciliation` (Task 3, 8 tests)
- `tests/test_cli_reconcile.py` - New module: 13 tests covering `run_reconcile`'s report path + `run_inspect`'s new line (Task 2, 10 tests) and the `--remove` continuation (Task 3, 3 tests)

## Decisions Made

- `reconcile.py` imports `_chunked`/`WRITE_THROTTLE_SECONDS`/`WRITE_BATCH_SIZE` from `auraframes/sync.py` rather than duplicating them, since the plan's own `apply_reconciliation` signature names these exact symbols as defaults and the phase's isolation rule is one-directional (`sync.py` must never import from `reconcile.py`; the reverse is explicitly fine).
- `apply_reconciliation` reads only `result.stuck` -- `result.recently_created`/`result.unknown_age` are never referenced anywhere in its body, so D-15's "never a removal candidate" rule is a structural property of the code, not just a documented convention a future edit could accidentally violate.
- The `'complete'` mechanism is wired into `_RECONCILE_PRIMITIVE` but raises `NotImplementedError` naming plan 11-05, exactly as the plan directs -- a known, intentional stub (see Known Stubs below), not an oversight.
- `run_reconcile`'s `--remove` continuation lives inside the same outer `try`/`except` as the report (mirroring `run_sync`'s shape), with `RateLimitError`/`GeoMismatchError`/`BudgetExhausted` as sibling `except` clauses rather than a nested `try` -- so a reconcile run reports a lockout/geo-mismatch/budget-exhaustion exactly as clearly as `sync --apply` does, never more vaguely via the generic catch-all.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test-authoring bug: an end-to-end `--remove` CLI test would have blocked on a real `WriteBudget` wait and written to the real, on-disk write-budget state file**
- **Found during:** Task 3, writing `test_run_reconcile_remove_yes_end_to_end_removes_stuck_rows`
- **Issue:** `run_reconcile`'s `--remove` path always builds a real `WriteBudget` via `_build_write_budget(os.getenv('AURA_EMAIL'), False)` (reconcile has no `--ignore-budget` escape hatch, by design). A test that doesn't neutralize this touches the real `AURA_STATE_DIR` (default `~/.config/auraframes/...`) -- on first use the budget starts at 0 tokens, so `apply_reconciliation`'s default `sleep=time.sleep` genuinely blocked for ~59 real seconds waiting for a refill, and wrote a stray state file for the test's fake email to the real filesystem location outside the repo.
- **Fix:** Monkeypatched `cli_module._build_write_budget` to return `None` for that one end-to-end test (mirroring `tests/test_cli_push_budget_geo.py`'s established `AURA_STATE_DIR`-isolation pattern, applied at the factory level here since the test cares about CLI wiring, not budget timing -- budget costing itself is covered offline via `_FakeBudget` in `tests/test_reconcile.py`). Removed the stray state file the failing run created (`~/.config/auraframes/budget-141a525498f5.json`, confirmed via its content/hash to belong only to the test's fake email, not the real account's own `budget-eeda3bb09fc5.json`, which was left untouched).
- **Files modified:** `tests/test_cli_reconcile.py`
- **Verification:** Full offline suite (`uv run pytest -m "not live" -q`) re-run after the fix: 262 passed in 3.4s (down from a single 59s outlier before the fix); confirmed `~/.config/auraframes/` contains only the pre-existing real-account file afterward.
- **Committed in:** `1a78de4` (Task 3 commit; the fix was made before commit, not as a follow-up)

---

**Total deviations:** 1 auto-fixed (1 Rule 1 -- test-infrastructure bug, never shipped).
**Impact on plan:** No production code was affected -- the bug was entirely in a test's own setup and was caught and fixed before the Task 3 commit. No scope creep.

## Issues Encountered

- Task 1's acceptance criterion `uv run python -c "...auraframes.sync as s; print('reconcile' not in inspect.getsource(s))"` expects `True`; the actual result is `False`. This is a **planner miscount**, not an implementation defect, in the same category 11-01's summary already documented for `frameApi.py`'s `RuntimeError` count: `auraframes/sync.py` was never touched by this plan (confirmed by `git diff` showing zero changes to that file across all three tasks), and it already contained the substring `"reconcile"` before this plan started -- via `budget.reconcile_tripped(...)` calls (a pre-existing `WriteBudget` method name from Phase 09) and one comment ("Reconcile already happened inside `note_failure()`"). Neither is a reference to the new `auraframes.reconcile` module. The real invariant this criterion exists to check -- "`sync.py` does not import from or call into `reconcile.py`" -- holds: `grep -n reconcile auraframes/sync.py` shows only those five pre-existing, unrelated matches, and no `import` statement anywhere in the file names the `reconcile` module. Recorded to `.planning/WINDOWS.md` as a `deviation` entry for visibility at ship time.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `aura-cli reconcile`/`inspect` now give the operator visibility into the 58 known stuck rows on the live frame that Phase 10's UAT flagged, closing REL-05's reporting half unconditionally.
- The removal half (`--remove`) is capped, gated, and budgeted, but its live verdict -- whether `remove`, `hard-delete`, or a future `complete` mechanism actually clears these rows -- is explicitly deferred to plan 11-05, exactly as this plan's flagged assumption states. `docs/CLI.md` says so plainly rather than implying the problem is solved.
- No blockers for plan 11-04 (format support) or 11-05 (live verification).

---
*Phase: 11-write-path-reliability-format-support*
*Completed: 2026-09-03*

## Known Stubs

- **`_complete_placeholder` / `_RECONCILE_PRIMITIVE['complete']`** (`auraframes/reconcile.py`) -- raises `NotImplementedError` naming plan 11-05. This is an intentional stub per the plan's own Task 3 action text: the `'complete'` mechanism (treating a stuck row as an unfinished upload to finish, rather than a bad row to delete) is reserved for a future live probe to determine viability before it is built out. `--mechanism complete` is reachable from the CLI's `argparse` choices today but will raise if selected; `docs/CLI.md` does not currently list it as a working option (it documents only `remove`/`hard-delete` in the `--remove` walkthrough), so an operator following the docs will not hit it.
- **No removal mechanism confirmed to work** -- `apply_reconciliation`'s `remove`/`hard-delete` primitives are wired, tested offline, and honest about failure, but whether either one actually clears a stuck row on the live Pushd API is unverified by this plan (D-16, explicitly deferred to plan 11-05's live probe). This is documented plainly in `docs/CLI.md`'s `reconcile` section, not hidden.

## Self-Check: PASSED

- All 7 key-files (created + modified) verified present on disk with `[ -f ]`.
- All 3 task commit hashes (`e88b757`, `ea48590`, `1a78de4`) verified in `git log --oneline --all`.
- All acceptance criteria from all 3 tasks re-run and passing (except Task 1's `sync.py` substring-grep criterion, documented above as a planner miscount with the underlying invariant confirmed via `grep`/`git diff` on that file).
- `uv run pytest -m "not live" -q`: 262 passed, 4 deselected, 0 failed (231 baseline from 11-01/11-02 + 31 new: 18 in `test_reconcile.py`, 13 in `test_cli_reconcile.py`).
- `uv run aura-cli reconcile --help` lists `--frame`/`--remove`/`--yes`/`--mechanism`/`--max-age-hours`; `uv run aura-cli --help` lists `reconcile` among the subcommands.
- Confirmed `~/.config/auraframes/` contains only the pre-existing real-account budget state file after the full suite run (no test-created stray files).
