---
phase: 07-sync-diffing-engine-dry-run-only
fixed_at: 2026-07-07T11:34:00Z
review_path: .planning/phases/07-sync-diffing-engine-dry-run-only/07-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 07: Code Review Fix Report

**Fixed at:** 2026-07-07T11:34:00Z
**Source review:** .planning/phases/07-sync-diffing-engine-dry-run-only/07-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 5 (critical_warning scope: CR-01, WR-01..WR-04; IN-01..IN-03 excluded per scope)
- Fixed: 5
- Skipped: 0

## Fixed Issues

### CR-01: Nonexistent/invalid `dir` argument is silently treated as an empty directory, producing a "delete everything" dry-run plan with exit code 0

**Files modified:** `auraframes/sync.py`
**Commit:** `bdc7327`
**Applied fix:** Added an upfront `root.is_dir()` guard at the top of `scan_directory` that raises `NotADirectoryError` when `root` does not exist or is not a directory, instead of silently walking an empty `rglob` result. `run_sync`'s existing broad `except Exception` in `auraframes/cli.py` already catches this and returns exit code 1 with a message, so the "delete everything" plan with exit 0 can no longer occur. (WR-02, fixed next, further narrows this specific path to a clearer local-scan error message.)

### WR-01: `scan_directory` follows symlinks to files outside the scanned directory, contradicting its own docstring

**Files modified:** `auraframes/sync.py`
**Commit:** `2522383`
**Applied fix:** Changed the traversal filter from `if not p.is_file(): continue` to `if p.is_symlink() or not p.is_file(): continue`, so symlinked files (which `is_file()` would otherwise follow and read) are excluded from hashing. Updated the docstring to accurately describe the bounding behavior instead of the previous inaccurate claim. Manually reproduced the review's exact repro (symlink inside scan root pointing outside it) after the fix and confirmed the linked file is no longer hashed/included.

### WR-02: Overly broad `except Exception` collapses distinct failure modes into one misleading message

**Files modified:** `auraframes/cli.py`
**Commit:** `cd77a39`
**Applied fix:** Wrapped the `scan_directory(Path(dir_arg))` call in `run_sync` with a nested `try/except OSError` that prints `Failed to scan {dir_arg}: {e}` and returns 1, before the remaining frame/API logic (still under the original outer `except Exception` for remote/API failures). Local filesystem errors (including the `NotADirectoryError` from CR-01) are now reported distinctly from live API/auth failures. Scoped strictly to `run_sync`, matching the finding's cited Fix snippet (the finding only noted `run_inspect` shares the broad-catch pattern in passing; `run_inspect` has no local filesystem operation to split out).

### WR-03: `to_upload` ordering is filesystem-traversal-order-dependent, making dry-run output non-reproducible

**Files modified:** `auraframes/cli.py`
**Commit:** `d7fcead`
**Applied fix:** Changed `for path in plan.to_upload:` to `for path in sorted(plan.to_upload):` in `run_sync`'s print loop, so dry-run "To upload" output is deterministically ordered regardless of filesystem traversal order.

### WR-04: `_configure_cli_logging`'s default path writes real files to `<cwd>/logs/` during every offline test run, an unisolated shared side effect

**Files modified:** `tests/test_cli_sync.py`
**Commit:** `a5bcd9c`
**Applied fix:** Updated the autouse `_reset_loguru` fixture to `monkeypatch.chdir()` into a dedicated scratch directory obtained via `tmp_path_factory.mktemp('cli-logging-cwd')` before each test. Deliberately did **not** chdir into the test's own `tmp_path` — several tests in this file pass `tmp_path` directly as `dir_arg` to `run_sync`, and a `logs/` directory created inside it would be picked up by `scan_directory`'s recursive walk and inflate `skipped_non_image` counts (discovered this via a real test failure during verification and corrected before committing). Confirmed via `pytest tests/test_cli_sync.py` and the full offline suite (`pytest -q -m "not live"`, 49 passed) that no `logs/` directory is created in the repo/worktree root anymore.

## Skipped Issues

None — all in-scope findings were fixed.

---

_Fixed: 2026-07-07T11:34:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
