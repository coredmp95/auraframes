---
phase: 01-toolchain-revival
plan: 01
subsystem: infra
tags: [uv, pyproject, python3.14, packaging, dependencies, hatchling, pydantic, httpx, boto3]

# Dependency graph
requires: []
provides:
  - "uv-managed pyproject.toml as the sole dependency manifest (replaces UTF-16 requirements.txt)"
  - "Committed uv.lock resolving 37 packages on Python 3.14 (all cp314 wheels)"
  - ".python-version pinning the interpreter to 3.14"
  - ".venv with all runtime deps + pytest installed, ready for the 01-02 smoke test"
affects: [01-02, pydantic-v2-migration, smoke-test]

# Tech tracking
tech-stack:
  added: [uv, hatchling, pytest]
  patterns: ["uv project with flat-layout package", ">= floor pins + committed lockfile (D-01/D-02)"]

key-files:
  created: [pyproject.toml, uv.lock, .python-version]
  modified: [.gitignore]

key-decisions:
  - "Use >= floors in pyproject.toml and rely on committed uv.lock for reproducibility (D-01/D-02)"
  - "hatchling build backend with flat-layout auto-detection (no [tool.hatch] config needed)"
  - "pytest>=8 in [project.optional-dependencies] dev extra rather than PEP 735 dependency-groups (portability)"
  - "Un-ignore .python-version in .gitignore so the uv interpreter pin is committed"

patterns-established:
  - "Pattern 1: uv project for an existing flat-layout package (pyproject + uv.lock + .python-version)"

requirements-completed: [ENV-01, ENV-02]

# Metrics
duration: 6min
completed: 2026-06-29
---

# Phase 01 Plan 01: Toolchain Revival (uv packaging seam) Summary

**Migrated the broken UTF-16 requirements.txt to a uv-managed pyproject.toml, resolved 37 packages on Python 3.14 (all cp314 wheels, no sdist builds), and committed uv.lock for reproducible installs.**

## Performance

- **Duration:** ~6 min
- **Completed:** 2026-06-29
- **Tasks:** 2
- **Files modified:** 4 (pyproject.toml, uv.lock, .python-version created; .gitignore modified; requirements.txt deleted)

## Accomplishments
- Authored `pyproject.toml` with `[project]` (name `auraframes`, `requires-python = ">=3.14"`), 11 runtime deps at `>=` floors (D-01), a `dev` extra with `pytest>=8`, and a hatchling `[build-system]`.
- Deleted the legacy UTF-16 `requirements.txt` (D-03) — `pyproject.toml` + `uv.lock` are now the sole manifest (ENV-01).
- `uv lock --python 3.14` resolved 37 packages and `uv sync --extra dev` installed them into `.venv` from prebuilt cp314 wheels with zero build failures (ENV-02, ROADMAP SC#1).
- Committed `uv.lock` (D-02) — hash-pinned, tamper-evident supply-chain mitigation (T-01-SC).
- Verified the managed env imports every runtime dep (pydantic 2.13.4, Pillow 12.2.0, h2 4.3.0, boto3 1.43.36, httpx 0.28.1, geopy, loguru, tqdm) plus pytest 9.1.1.

## Task Commits

Each task was committed atomically:

1. **Task 1: Author pyproject.toml, pin interpreter, delete legacy requirements.txt** - `2b6ad51` (feat)
2. **Task 2: Resolve and install on Python 3.14, commit uv.lock** - `b18de8d` (chore)

## Files Created/Modified
- `pyproject.toml` - Single dependency manifest: `[project]` with `>=`-floored runtime deps, `dev` extra (pytest), hatchling build backend.
- `uv.lock` - Hash-pinned resolved tree (37 pkgs) for Python 3.14; `version = 1`.
- `.python-version` - Pins interpreter to `3.14` so bare `uv run` selects the right CPython.
- `.gitignore` - Un-ignored `.python-version` (negation entry) so the pin is tracked.
- `requirements.txt` - Deleted (legacy UTF-16 manifest, D-03).

## Decisions Made
- Followed RESEARCH Pattern 1 verbatim for `pyproject.toml`; floors not re-derived.
- Kept `requests>=2.31` for parity even though unused in active source (scope: revive what's there).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Un-ignored .python-version in .gitignore**
- **Found during:** Task 1 (committing artifacts)
- **Issue:** The project's `.gitignore` carries the default pyenv rule `.python-version`, which blocked committing the interpreter pin. The plan's must_haves require `.python-version` as a committed artifact, and for a uv-managed project the pin must be tracked for reproducibility (D-02).
- **Fix:** Added a `!.python-version` negation entry with an explanatory comment.
- **Files modified:** `.gitignore`
- **Verification:** `git add .python-version` succeeds; file is tracked in commit `2b6ad51`.
- **Committed in:** `2b6ad51` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary to satisfy the plan's required `.python-version` artifact. No scope creep.

## Issues Encountered
None beyond the gitignore deviation above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `.venv` with runtime deps + pytest is ready for the pydantic v1→v2 migration and `uv run pytest` smoke test in plan 01-02.
- Note for 01-02: httpx resolved to 0.28.1, which dropped some legacy constructor args; `client.py` only uses `Client(http2=True)`, `Timeout`, `Response`, so any runtime fallout is a 01-02/Phase 2 concern.

## Self-Check: PASSED

All created files present (pyproject.toml, uv.lock, .python-version, 01-01-SUMMARY.md), requirements.txt confirmed deleted, both task commits (2b6ad51, b18de8d) exist in git history.

---
*Phase: 01-toolchain-revival*
*Completed: 2026-06-29*
