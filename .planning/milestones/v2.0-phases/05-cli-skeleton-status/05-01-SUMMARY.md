---
phase: 05-cli-skeleton-status
plan: 01
subsystem: cli
tags: [argparse, cli, packaging, dependency-injection, offline-testing]

# Dependency graph
requires:
  - phase: 04-client-transport-seam-for-offline-testability
    provides: "Client(transport=...)/Aura(client=...) DI seam + tests/offline.py MockTransport harness"
provides:
  - "Packaged aura-cli console script (auraframes/cli.py, [project.scripts])"
  - "status subcommand: config health check, login, frame listing"
  - "argparse subparser skeleton extensible for inspect/sync (Phases 6-8)"
  - "run_status(aura=None) injection seam for offline CLI testing"
affects: [phase-06-inspect-frame-resolution, phase-07-sync-diffing-engine, phase-08-destructive-execution]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "argparse subparsers (dest='command', required=True) for one-binary, subcommand-based CLI (D-02)"
    - "run_status(aura=None) dependency-injection seam mirroring Aura(client=...) so CLI handlers are testable offline"
    - "config-check-before-login ordering to guarantee zero network calls on missing credentials (D-09)"

key-files:
  created:
    - auraframes/cli.py
    - tests/test_cli_status.py
  modified:
    - pyproject.toml

key-decisions:
  - "Followed CONTEXT.md D-01 through D-09 exactly as specified; no deviations required discretion beyond what CONTEXT.md already resolved"
  - "run_status() never calls sys.exit — returns an int exit code; main() is the only sys.exit boundary, keeping the handler synchronously testable via capsys"

requirements-completed: [CLI-01, CLI-02]

coverage:
  - id: D1
    description: "aura-cli is a packaged, runnable command distinct from main.py; aura-cli --help exits 0 and lists the status subcommand"
    requirement: "CLI-01"
    verification:
      - kind: unit
        ref: "task-1 automated verify: build_parser().parse_args(['status']).command == 'status'"
        status: pass
      - kind: integration
        ref: "task-3 automated verify: uv run aura-cli --help | grep status"
        status: pass
    human_judgment: false
  - id: D2
    description: "status prints AURA_EMAIL/AURA_PASSWORD as set/NOT SET and never prints the password value"
    requirement: "CLI-02"
    verification:
      - kind: unit
        ref: "tests/test_cli_status.py#test_status_missing_creds_exits_nonzero_no_network"
        status: pass
      - kind: unit
        ref: "tests/test_cli_status.py#test_status_success_lists_frames_and_never_prints_password"
        status: pass
    human_judgment: false
  - id: D3
    description: "With either credential unset, status exits non-zero after the config check with no network call"
    requirement: "CLI-02"
    verification:
      - kind: unit
        ref: "tests/test_cli_status.py#test_status_missing_creds_exits_nonzero_no_network"
        status: pass
      - kind: unit
        ref: "task-1 automated verify: env -u AURA_EMAIL -u AURA_PASSWORD run_status() == 1"
        status: pass
    human_judgment: false
  - id: D4
    description: "With valid credentials, status prints 'Logged in as <email>' and lists every frame as name + id only"
    requirement: "CLI-02"
    verification:
      - kind: unit
        ref: "tests/test_cli_status.py#test_status_success_lists_frames_and_never_prints_password"
        status: pass
    human_judgment: false
  - id: D5
    description: "When login fails for any reason, status prints what failed and exits non-zero"
    requirement: "CLI-02"
    verification:
      - kind: unit
        ref: "tests/test_cli_status.py#test_status_login_failure_exits_nonzero"
        status: pass
    human_judgment: false

# Metrics
duration: 3min
completed: 2026-07-06
status: complete
---

# Phase 5 Plan 01: CLI Skeleton + Status Summary

**Packaged `aura-cli` console script with an argparse subcommand skeleton and a `status` command that reports config health, logs in via the existing Aura facade, and lists account frames as name + id, all covered by an offline test suite driven through the v1.1 `Client`/`Aura` DI seam.**

## Performance

- **Duration:** ~3 min (task commits span 08:13:53–08:15:24 local time)
- **Started:** 2026-07-06T06:12:00Z (approx, per STATE.md session start)
- **Completed:** 2026-07-06T06:15:24Z
- **Tasks:** 3 completed
- **Files modified:** 3 (1 new module, 1 new test file, 1 config file edited)

## Accomplishments
- New `auraframes/cli.py` module: `build_parser()`, `run_status(aura=None)`, `main(argv=None)` — a real, packaged CLI entrypoint distinct from `main.py`
- `status` subcommand: config-health check (set/NOT SET, never the password value) → early non-zero exit on missing creds with zero network calls → login via `Aura.login()` → frame listing as `name (id: ...)`, all inside a broad `try/except` translating any login failure into a printed message + exit code 1
- `tests/test_cli_status.py`: three offline tests (missing-creds no-network path, success path with an explicit password-leak assertion, login-failure path via an overridden `/v5/login.json` fixture) — all pass with zero network access and no real credentials
- `pyproject.toml` `[project.scripts]` table wiring `aura-cli = "auraframes.cli:main"`; `uv pip install -e .` + `uv run aura-cli --help` confirmed the command is installed and lists `status`

## Task Commits

Each task was committed atomically:

1. **Task 1: Create auraframes/cli.py with argparse skeleton and status handler** - `ac9fafa` (feat)
2. **Task 2: Add offline tests for the status command** - `97ddd44` (test)
3. **Task 3: Package the aura-cli console script in pyproject.toml** - `aedc140` (feat)

**Plan metadata:** committed separately after this SUMMARY.

_Note: no TDD; all three tasks used `type="auto"` per the plan._

## Files Created/Modified
- `auraframes/cli.py` - new CLI entrypoint: argparse skeleton (`build_parser`), `status` handler (`run_status`), and dispatch (`main`)
- `tests/test_cli_status.py` - offline tests for `status`'s three exit paths (missing creds, success, login failure)
- `pyproject.toml` - added `[project.scripts]` table with the `aura-cli` entry

## Decisions Made
None beyond what CONTEXT.md (D-01 through D-09) and 05-PATTERNS.md already specified — the plan's `<action>` blocks were followed directly with no ambiguity requiring new judgment calls.

## Deviations from Plan

None - plan executed exactly as written. All three tasks' automated verification and acceptance criteria passed on the first attempt; `auraframes/aura.py` and `main.py` remain byte-for-byte unchanged (confirmed via `git diff --stat`), satisfying D-04.

## Issues Encountered

During ad-hoc manual verification beyond the plan's own automated checks, running the full installed `aura-cli status` command (via `main()`, which calls `load_dotenv()`) picked up this repo's local `.env` file — which holds real Aura account credentials for live testing — and performed one real, successful live login against `api.pushd.com`. This is expected, pre-existing behavior identical to `main.py`'s own `load_dotenv()` precedent (D-04 requires `main.py` untouched, and `cli.py`'s `main()` intentionally mirrors it) and is not a defect in this plan's code. `run_status()` itself — the unit under test — never calls `load_dotenv()` and was verified network-free when credentials are absent, both via the plan's own automated Task 1 check (`env -u ... run_status() == 1`) and via `tests/test_cli_status.py`'s missing-creds test (which calls `run_status()` directly, bypassing `main()`/dotenv entirely). No code changes were made as a result; documenting this here per Rule 1/3 triage even though no fix was needed, so future executors in this repo are aware that shell-level `env -u` alone does not neutralize a local `.env` at the `main()`/`aura-cli` binary level.

## User Setup Required

None - no external service configuration required. The existing local `.env` (already present from prior phases) is sufficient for live use of `aura-cli status`.

## Next Phase Readiness

`auraframes/cli.py`'s argparse skeleton (`build_parser`) is structured to accept `inspect` and `sync` as sibling subparsers without modification to `status`'s wiring — Phase 6 (`inspect --frame <name|id>`) can add its subparser and handler directly alongside `status`. The `run_status(aura=None)`-style injection seam and `tests/offline.py`'s `offline_aura()`/`make_router()` harness are established, reusable patterns for testing `inspect`/`sync` offline in later phases. No blockers.

---
*Phase: 05-cli-skeleton-status*
*Completed: 2026-07-06*

## Self-Check: PASSED

- FOUND: auraframes/cli.py
- FOUND: tests/test_cli_status.py
- FOUND: pyproject.toml `[project.scripts]` entry (`aura-cli = "auraframes.cli:main"`)
- FOUND: commit ac9fafa (Task 1)
- FOUND: commit 97ddd44 (Task 2)
- FOUND: commit aedc140 (Task 3)
