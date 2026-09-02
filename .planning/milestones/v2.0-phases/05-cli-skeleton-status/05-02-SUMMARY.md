---
phase: 05-cli-skeleton-status
plan: 02
subsystem: cli
tags: [loguru, argparse, logging, cli, stderr]

# Dependency graph
requires:
  - phase: 05-cli-skeleton-status (plan 01)
    provides: aura-cli status command, offline test harness, run_status()/build_parser() DI seam
provides:
  - Quiet-by-default aura-cli status (no loguru INFO/DEBUG request/response noise on stderr)
  - Opt-in --debug flag on the status subcommand restoring full loguru verbosity
  - Offline stderr-assertion tests locking in the fix
affects: [06-inspect-frame-resolution, 07-sync-dry-run, 08-sync-write-path]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "CLI-side loguru sink re-initialization after Aura() construction (compensates for the frozen aura.py's commented-out logger.remove())"
    - "argparse subcommand-level boolean flags (--debug) threaded through run_status(debug=...) keyword, defaulting to quiet"

key-files:
  created: []
  modified:
    - auraframes/cli.py
    - tests/test_cli_status.py

key-decisions:
  - "The fix lands entirely in auraframes/cli.py (a _configure_cli_logging() helper called after Aura() construction, before login) rather than in aura.py, honoring the D-04 freeze"
  - "Quiet mode doesn't go fully silent on stderr: it re-adds a level=WARNING sys.stderr sink so genuine warnings/errors still surface, while suppressing INFO/DEBUG request/response spam (T-05-05 mitigation)"
  - "Tests use an autouse logger.remove()-before/after fixture to keep stderr assertions deterministic against loguru's process-global sink accumulation"

patterns-established:
  - "Pattern: CLI-boundary logging reconfiguration — when an upstream facade construction accumulates unwanted sinks/state and can't be edited, neutralize/re-init from the calling boundary right after construction and before the first side-effecting call"

requirements-completed: [CLI-02]

coverage:
  - id: D1
    description: "aura-cli status (default) suppresses loguru INFO/DEBUG request/response stderr output while keeping the concise config/login/frame lines"
    requirement: "CLI-02"
    verification:
      - kind: unit
        ref: "tests/test_cli_status.py#test_status_quiet_by_default_suppresses_verbose_stderr"
        status: pass
    human_judgment: false
  - id: D2
    description: "aura-cli status --debug restores full loguru verbose stderr output (opt-in)"
    requirement: "CLI-02"
    verification:
      - kind: unit
        ref: "tests/test_cli_status.py#test_status_debug_flag_restores_verbose_stderr"
        status: pass
    human_judgment: false
  - id: D3
    description: "On-disk logs/file_*.log logging continues in both quiet and --debug modes"
    verification:
      - kind: unit
        ref: "auraframes/cli.py#_configure_cli_logging (re-adds logs/file_{time}.log sink in quiet mode; leaves it untouched in debug mode since Aura._init_logger() already added it)"
        status: pass
    human_judgment: true
    rationale: "No automated test asserts the file sink actually writes to disk (offline tests don't inspect logs/); this is inferred from the sink-registration code path, not directly observed. A human running the live/manual verification step can confirm a logs/file_*.log file is created/appended in both modes."
  - id: D4
    description: "auraframes/aura.py and main.py remain byte-for-byte unchanged (D-04)"
    verification:
      - kind: other
        ref: "git diff --name-only -- auraframes/aura.py main.py (empty output)"
        status: pass
    human_judgment: false

duration: 21min
completed: 2026-07-06
status: complete
---

# Phase 5 Plan 2: Quiet-by-Default CLI Logging Summary

**Added a `--debug` flag to `aura-cli status` and a CLI-side loguru re-initialization helper that suppresses the two overlapping stderr sinks `Aura._init_logger()` accumulates, closing the only diagnosed UAT gap for Phase 5 without touching the frozen `aura.py`/`main.py`.**

## Performance

- **Duration:** 21 min
- **Started:** 2026-07-06T15:21:22+02:00 (prior commit baseline)
- **Completed:** 2026-07-06T15:42:07+02:00
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- `aura-cli status` now runs quiet by default — no loguru INFO/DEBUG request/response bodies, headers, or cookies leak to stderr; only the concise config/login/frame lines print.
- `aura-cli status --debug` is a new opt-in flag that leaves loguru's sinks untouched, reproducing the full verbose output for troubleshooting.
- A stricter `sys.stderr` sink at level WARNING is added in quiet mode so genuine warnings/errors still surface — quiet mode isn't silent, just non-spammy.
- On-disk `logs/file_{time}.log` logging is preserved in both modes.
- `tests/test_cli_status.py` now asserts on captured stderr (not just stdout) via two new tests plus an autouse loguru-reset fixture, locking in the regression fix for CI.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add --debug flag and a quiet-by-default logging helper to cli.py** - `7313a85` (feat)
2. **Task 2: Extend tests/test_cli_status.py with stderr assertions** - `5bfab50` (test)

**Plan metadata:** (pending — this commit)

## Files Created/Modified
- `auraframes/cli.py` - Added `from loguru import logger` import, `--debug` argparse flag on the `status` subparser, `_configure_cli_logging(debug)` helper (drops all loguru handlers and re-adds a file sink + WARNING-level stderr sink in quiet mode; no-op in debug mode), `run_status(aura=None, debug=False)` now calls the helper after `Aura()` construction and before `aura.login()`, and `main()` passes `args.debug` through to `run_status()`.
- `tests/test_cli_status.py` - Added `from loguru import logger` import, an autouse `_reset_loguru` fixture (`logger.remove()` before and after each test), `test_status_quiet_by_default_suppresses_verbose_stderr` (asserts absence of `'request to'` / `'Response ('` markers in `.err`), and `test_status_debug_flag_restores_verbose_stderr` (asserts presence of the request marker in `.err` when `debug=True`). The three pre-existing tests are unchanged and still pass.

## Decisions Made
- Because `auraframes/aura.py` is frozen (D-04) and its `logger.remove()` call is commented out, the fix cannot live there — `_configure_cli_logging()` compensates from the CLI boundary by calling `logger.remove()` itself (clearing both the loguru library-default handler and `_init_logger()`'s INFO handler) and then re-adding the file sink plus a WARNING-level stderr sink.
- Quiet mode re-adds a WARNING-level stderr sink rather than removing all stderr output entirely, per the T-05-05 mitigation plan in the plan's threat model (avoid quiet mode accidentally hiding genuine errors).
- The helper must run after `aura = aura or Aura()` (which is what registers the noisy sinks) and before `aura.login()` (the first HTTP call) — this ordering is load-bearing and was verified via the offline harness.

## Deviations from Plan

None - plan executed exactly as written. Both tasks matched their `<action>` specs; no Rule 1-4 fixes were needed, no architectural changes, no auth gates encountered (offline harness used throughout, no live credentials needed for this plan).

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 5's single diagnosed UAT gap is closed: `aura-cli status` is quiet by default with an opt-in `--debug` flag, verified offline (5/5 tests in `tests/test_cli_status.py`, 24/24 in the full `not live` suite) and manually verified via a direct offline `run_status()` call.
- `auraframes/aura.py` and `main.py` remain byte-for-byte unchanged (D-04 preserved) — confirmed via `git diff --name-only`.
- Phase 5 is now ready for `/gsd-verify-work 5` re-run (or equivalent phase closure) to confirm the gap is resolved, then `/gsd-discuss-phase 6` to begin Phase 6: Inspect + Frame Resolution.
- The known deferred item MOD-04 (loguru sink leak on repeated `Aura()` construction) is now partially mitigated for the CLI's own use case (status quiet mode explicitly clears accumulated sinks) but the underlying `Aura._init_logger()` behavior itself remains unchanged and still applies to any other caller that constructs multiple `Aura()` instances in-process (e.g. tests) — still tracked as deferred debt, not resolved by this plan.

---
*Phase: 05-cli-skeleton-status*
*Completed: 2026-07-06*

## Self-Check: PASSED

All created/modified files and task commits verified present on disk and in git history.
