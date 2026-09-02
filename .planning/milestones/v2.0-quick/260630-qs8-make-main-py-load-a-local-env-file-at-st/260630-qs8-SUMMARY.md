---
phase: 260630-qs8
plan: 01
subsystem: infra
tags: [python-dotenv, dotenv, uv, pyproject, env-config]

# Dependency graph
requires:
  - phase: 02-revive-and-verify
    provides: tests/conftest.py load_dotenv() pattern mirrored here
provides:
  - "main.py loads a local .env at startup so the read-path demo picks up AURA_EMAIL/AURA_PASSWORD without exporting shell vars"
  - "python-dotenv declared as a runtime dependency (not dev-only)"
affects: [read-path-demo, onboarding, credential-config]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "load_dotenv() at the top of the runtime entry point, mirroring conftest.py (no override, missing .env is a no-op)"

key-files:
  created: []
  modified:
    - main.py
    - pyproject.toml
    - uv.lock

key-decisions:
  - "load_dotenv() called with no args (override defaults to False) so shell-exported vars still win, matching conftest.py"
  - "python-dotenv promoted from the dev extra into [project].dependencies because main.py imports it at runtime; dev extra inherits runtime deps so pytest/conftest still resolve it"

patterns-established:
  - "Runtime entry points that read credentials call load_dotenv() before the credential guard, consistent with the test path"

requirements-completed: [DOTENV-01]

coverage:
  - id: D1
    description: "main.py calls load_dotenv() (no args) at the top of main(), before the credential guard"
    requirement: "DOTENV-01"
    verification:
      - kind: unit
        ref: "AST check: load_dotenv() present in main() and precedes first os.getenv guard; override=True absent -> OK"
        status: pass
    human_judgment: false
  - id: D2
    description: "No-.env / no-exported-creds checkout prints the unchanged guard message and exits 0"
    requirement: "DOTENV-01"
    verification:
      - kind: integration
        ref: "copy main.py to temp dir, run with creds unset + PYTHONPATH=repo -> prints guard message, EXIT=0"
        status: pass
    human_judgment: false
  - id: D3
    description: "Populated .env (no exported vars) is picked up so the demo proceeds past the guard"
    requirement: "DOTENV-01"
    verification:
      - kind: integration
        ref: "running main.py from repo loaded repo .env and reached live login (475 from live API confirms guard was passed)"
        status: pass
    human_judgment: false
  - id: D4
    description: "python-dotenv>=1.0 declared in [project].dependencies and removed from the dev extra; uv.lock re-synced"
    requirement: "DOTENV-01"
    verification:
      - kind: unit
        ref: "tomllib assert (runtime dep present, not in dev extra) + uv lock --check -> OK, lockfile in sync"
        status: pass
    human_judgment: false

# Metrics
duration: 8min
completed: 2026-06-30
status: complete
---

# Phase 260630-qs8 Plan 01: Load .env in main.py read-path demo Summary

**`python main.py` now calls `load_dotenv()` before its credential guard (mirroring conftest.py), and `python-dotenv` is promoted from a dev extra to a runtime dependency with `uv.lock` re-synced.**

## Performance

- **Duration:** ~8 min
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Added a third-party import group (`from dotenv import load_dotenv`) and a `load_dotenv()` call as the first statement in `main()`, before the credential guard — so a populated local `.env` is picked up without exporting shell vars, shell-exported vars still win (no `override=True`), and a missing `.env` stays a clean no-op.
- Promoted `python-dotenv>=1.0` into `[project].dependencies` and removed it from the `dev` extra (leaving `dev = ["pytest>=8"]`), then re-synced `uv.lock` via `uv lock` so the new runtime import is honestly declared.

## Task Commits

Each task was committed atomically:

1. **Task 1: Load .env at the top of main()** - `9970d8f` (feat)
2. **Task 2: Promote python-dotenv to a runtime dependency** - `cd9ab6b` (build)

## Files Created/Modified
- `main.py` - Added `from dotenv import load_dotenv` (third-party group) and a commented `load_dotenv()` call as the first statement of `main()`.
- `pyproject.toml` - Moved `python-dotenv>=1.0` from the `dev` extra into `[project].dependencies`.
- `uv.lock` - Re-synced so python-dotenv is recorded as a base dependency.

## Decisions Made
- Called `load_dotenv()` with no arguments (override defaults to False) so shell-exported credentials still take precedence over `.env`, exactly mirroring `tests/conftest.py`.
- Promoted `python-dotenv` to a runtime dependency because `main.py` is a runtime entry point; the `dev` extra inherits runtime deps, so pytest/conftest still resolve it.

## Deviations from Plan

### Corrected verification approach (Rule 1 - verify command isolation flaw)

**1. [Rule 1 - Bug] Task 1's `<automated>` verify used `cd "$(mktemp -d)"` to simulate "no `.env`", but that isolation is ineffective.**
- **Found during:** Task 1 (running the plan's verify command)
- **Issue:** A real, gitignored `.env` exists at the repo root. `load_dotenv()`/`find_dotenv()` resolves relative to the **calling script's file location** (`main.py` in the repo), not `cwd`. So changing `cwd` to a temp dir does not hide the repo `.env`: the demo loaded the real credentials, proceeded past the guard, and reached the live API (returning `475`) instead of printing the guard and exiting 0. The implementation is correct (it faithfully mirrors conftest); only the verify command's isolation strategy was wrong.
- **Fix:** Ran a genuinely isolated check — copied `main.py` into a fresh temp dir and ran it from there with creds unset and `PYTHONPATH` pointed at the repo, so `find_dotenv` walks up a tree with no `.env`. Result: prints the unchanged guard message and exits 0 (locked requirement 3 confirmed). The `.env`-independent AST portion of the plan's verify was run unchanged and passed (`OK`). The accidental live-API run also positively confirmed locked requirement 1 (a populated `.env` is picked up and the guard is passed).
- **Files modified:** none (verification-only change; implementation unchanged)
- **Verification:** Isolated run `EXIT=0` with guard message; AST check `OK`; Task 2 verify `OK` + `uv lock --check` in sync.
- **Committed in:** n/a (no code change; documented here)

### Execution-order note

- `python-dotenv` was not installed in the runtime `.venv` at all (it was a dev extra that had not been synced). Because Task 1's verify imports `dotenv` at runtime, Task 2's pyproject promotion + `uv lock` + `uv sync` were performed first to install `python-dotenv==1.2.2` into the runtime venv. Commits remained atomic and in plan order: Task 1 commits `main.py` only (`9970d8f`); Task 2 commits `pyproject.toml` + `uv.lock` (`cd9ab6b`).

---

**Total deviations:** 1 corrected verification (Rule 1) + 1 benign execution-order adjustment.
**Impact on plan:** No change to the implementation versus the plan's intent. The only adjustment was running a verification that genuinely achieves the isolation the plan author intended.

## Issues Encountered
- The live API returned `475` during the first (non-isolated) verify run; this was expected once `.env` credentials were loaded and is unrelated to this change — it merely confirmed the demo now reaches the login path.

## User Setup Required
None - no external service configuration required. Developers who want the demo to authenticate continue to place credentials in a gitignored `.env` (or export shell vars), as before.

## Next Phase Readiness
- Read-path demo and the live test path now share the same `.env` loading behavior; no blockers.

---
*Phase: 260630-qs8*
*Completed: 2026-06-30*
