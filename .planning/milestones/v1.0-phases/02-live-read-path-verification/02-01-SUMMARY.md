---
phase: 02-live-read-path-verification
plan: 01
subsystem: testing
tags: [pytest, httpx, loguru, security, redaction, live-api, aura, pushd]

# Dependency graph
requires:
  - phase: 01-toolchain-revival
    provides: "Python 3.14 + uv env, pydantic v2 models, pytest dev extra, import smoke tests"
provides:
  - "raise_for_status guard in all 4 Client request methods (failed HTTP can no longer return green)"
  - "_redact() secret-masking helper applied to every request/response body log line"
  - "accountApi.login raises RuntimeError on error/empty result instead of silent pass"
  - "logs/ auto-created at logger init; logs/, cache/, asset_images/ gitignored"
  - "live pytest marker + session aura login fixture (credential-gated, auto-skip)"
  - "READ-01 login + READ-02 frame-listing live tests"
affects: [live-read-path-verification, phase-3-verification-report]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Credential-gated live tests via @pytest.mark.live + session fixture that pytest.skip()s when env vars unset"
    - "Centralized log redaction: recursive _redact() over dict/list masking secret-bearing keys"
    - "Fail-loud transport: raise_for_status after history.append, before .json()"

key-files:
  created:
    - tests/conftest.py
    - tests/test_read_path.py
  modified:
    - auraframes/client.py
    - auraframes/api/accountApi.py
    - auraframes/aura.py
    - .gitignore
    - pyproject.toml

key-decisions:
  - "Redaction keys limited to password/auth_token/x-token-auth, recursing into nested user dict and lists; stdlib copy only, no new deps"
  - "login raises plain RuntimeError (not a typed exception hierarchy — MOD-03 out of scope)"
  - "history.append kept BEFORE raise_for_status so a failed response stays inspectable in Client.history"

patterns-established:
  - "Live-API tests are credential-gated and skip cleanly so default `uv run pytest` stays green on a credential-less checkout"
  - "All request/response bodies pass through _redact() before reaching loguru sinks"

requirements-completed: [READ-01, READ-02]

# Metrics
duration: 12min
completed: 2026-06-29
---

# Phase 2 Plan 01: Live Read-Path Trust Foundation + Login/Frame-Listing Summary

**Credential-gated pytest harness with fail-loud transport (raise_for_status) and on-disk secret redaction, plus READ-01 login and READ-02 frame-listing live tests that skip cleanly without credentials.**

## Performance

- **Duration:** ~12 min
- **Completed:** 2026-06-29
- **Tasks:** 3
- **Files modified:** 7 (2 created, 5 modified)

## Accomplishments
- Transport now fails loudly: `response.raise_for_status()` runs in all four `Client` methods before any JSON parse, so a 4xx/5xx can no longer masquerade as success (D-06). The failed response is still appended to `Client.history` first, so it remains inspectable.
- HIGH-severity security item closed: a recursive `_redact()` helper masks `password`/`auth_token`/`x-token-auth` (including the nested login `user` dict) in every request- and response-body log line (D-07); runtime output dirs `logs/`, `cache/`, `asset_images/` are gitignored (D-08).
- `accountApi.login` raises `RuntimeError` (with the API's `message`/`error`) on an error or empty-result response instead of silently hydrating a model from nothing (D-06).
- `_init_logger` now `os.makedirs('logs/', exist_ok=True)` so the first live instantiation does not crash on a missing dir (D-08).
- Live harness landed: `live` pytest marker registered (D-01), session-scoped `aura` fixture that auto-skips credential-less and logs in when creds are present (D-02/D-03), and the READ-01/READ-02 live tests.

## Task Commits

Each task was committed atomically:

1. **Task 1: Transport trust + secret redaction (client + login)** - `2a2314e` (feat)
2. **Task 2: Runtime-dir fix, gitignore, live pytest harness scaffold** - `73ecc24` (feat)
3. **Task 3: READ-01 login + READ-02 frame-listing live tests** - `3ff45ab` (test)

## Files Created/Modified
- `auraframes/client.py` - Added `_redact()` helper; `raise_for_status()` + redacted body logging in get/post/delete/put.
- `auraframes/api/accountApi.py` - `login` raises `RuntimeError` on error/empty result (no bare `pass`); `register`/`delete` untouched.
- `auraframes/aura.py` - `_init_logger` creates `logs/` before adding the loguru file sink.
- `.gitignore` - Added `logs/`, `cache/`, `asset_images/`.
- `pyproject.toml` - Added `[tool.pytest.ini_options]` registering the `live` marker.
- `tests/conftest.py` - Session-scoped `aura` fixture (skip credential-less, else `Aura().login()`).
- `tests/test_read_path.py` - `test_read_01_login` (asserts auth headers) and `test_read_02_list_frames` (asserts non-empty `list[Frame]`, prints name+id), both `@pytest.mark.live`.

## Decisions Made
- Redaction key set kept minimal (`password`/`auth_token`/`x-token-auth`) and recursive over dict/list; used stdlib `copy` so no new dependency is introduced.
- `login` raises a plain `RuntimeError` rather than a typed exception hierarchy — MOD-03 is explicitly out of scope for this revive milestone.
- `Client.history.append(response)` is intentionally kept before `raise_for_status()` so the offending response stays available for post-mortem inspection.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None. Baseline was 9 import tests green; after the plan the default credential-less run is `9 passed, 2 skipped` and `uv run pytest -m live --collect-only` lists exactly the two READ tests.

## Verification Evidence
- `uv run python -c "import auraframes.client, auraframes.api.accountApi"` — clean.
- `grep -c raise_for_status auraframes/client.py` → 4.
- `_redact` applied in both `logger.info(... data=...)` calls and all four `logger.debug(... body ...)` lines.
- `uv run pytest -q` (no creds) → `9 passed, 2 skipped`.
- `uv run pytest -q -m live --collect-only` → exactly `test_read_01_login`, `test_read_02_list_frames`.

## Known Stubs
None.

## Next Phase Readiness
- READ-01/READ-02 are wired and credential-gated; the live PASS evidence + log-redaction grep is the deferred human-check gathered as Phase 3 verification evidence (per plan, not run here without real credentials).
- READ-03 (fetch a frame's assets) and READ-04 (download one image with EXIF) remain for the next slice; they will reuse the same session `aura` fixture and `live` marker.

## Self-Check: PASSED

---
*Phase: 02-live-read-path-verification*
*Completed: 2026-06-29*
