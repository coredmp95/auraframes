---
phase: 09-proactive-write-rate-limiter-geo-guard
plan: 01
subsystem: infra
tags: [rate-limiting, token-bucket, geo-guard, httpx, dataclass, tdd]

# Dependency graph
requires: []
provides:
  - "auraframes/ratelimit.py: WriteBudget (token bucket, JSON persistence), check_geo (geo pre-flight guard), BudgetExhausted, GeoMismatchError, _default_resolver"
  - "100%-offline unit test suite (tests/test_ratelimit.py) covering the whole module"
affects: [09-02-execute-plan-cli-integration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Injected clock/sleep/resolver seam (mirrors execute_plan's sleep=time.sleep convention) -- module never calls datetime.utcnow(), time.sleep(), or httpx directly on any tested path"
    - "Plain @dataclass for internal domain objects (WriteBudget), pydantic reserved for API DTOs only"
    - "Fail-open-by-default external pre-flight check (check_geo) mirroring execute_plan's best-effort SQS poll precedent"

key-files:
  created:
    - auraframes/ratelimit.py
    - tests/test_ratelimit.py
  modified: []

key-decisions:
  - "check_geo's resolver parameter defaults to _default_resolver (production callers need no explicit wiring); every test still injects a fake explicitly per the 100%-offline requirement"
  - "WriteBudget.save() takes no path argument -- it always writes to self.path set at construction, enabling a bare budget.save() call from 09-02's execute_plan integration"
  - "TDD gate applied per task (not per plan): Task 1 (WriteBudget) got its own RED/GREEN commit pair, then Task 2 (check_geo) got a second RED/GREEN commit pair on top, rather than one combined RED covering both tasks"

patterns-established:
  - "Pattern: Injected-clock token bucket -- any future time-dependent bookkeeping in this codebase should take now/sleep as caller-supplied values, never read the clock internally"
  - "Pattern: Fail-open external pre-flight check with an injected resolver -- any future third-party-backed pre-flight check should default to fail-open with an explicit fail_open=False escape hatch"

requirements-completed: [ANTI-01, ANTI-02, ANTI-07]

coverage:
  - id: D1
    description: "WriteBudget.acquire refills by elapsed minutes (clamped to >=0, handling backward-clock and None-updated_at edge cases), caps at capacity, and consumes n tokens when available"
    requirement: "ANTI-01"
    verification:
      - kind: unit
        ref: "tests/test_ratelimit.py#test_acquire_refills_by_elapsed_minutes_then_consumes"
        status: pass
      - kind: unit
        ref: "tests/test_ratelimit.py#test_acquire_refill_never_pushes_tokens_above_capacity"
        status: pass
      - kind: unit
        ref: "tests/test_ratelimit.py#test_acquire_elapsed_clamp_backward_clock_adds_zero_tokens"
        status: pass
      - kind: unit
        ref: "tests/test_ratelimit.py#test_acquire_elapsed_clamp_same_instant_adds_zero_tokens"
        status: pass
      - kind: unit
        ref: "tests/test_ratelimit.py#test_acquire_fresh_bucket_none_updated_at_does_not_crash"
        status: pass
      - kind: unit
        ref: "tests/test_ratelimit.py#test_acquire_consumes_and_returns_none_when_enough_tokens"
        status: pass
    human_judgment: false
  - id: D2
    description: "acquire in wait mode sleeps the computed wait_seconds in 1s steps via injected sleep, surfacing on_wait each second, then consumes; in stop mode raises BudgetExhausted with wait_seconds"
    requirement: "ANTI-01"
    verification:
      - kind: unit
        ref: "tests/test_ratelimit.py#test_acquire_wait_mode_sleeps_in_1s_steps_calls_on_wait_then_consumes"
        status: pass
      - kind: unit
        ref: "tests/test_ratelimit.py#test_acquire_wait_mode_works_without_on_wait_callback"
        status: pass
      - kind: unit
        ref: "tests/test_ratelimit.py#test_acquire_stop_mode_raises_budget_exhausted_when_wait_false"
        status: pass
      - kind: unit
        ref: "tests/test_ratelimit.py#test_acquire_stop_mode_raises_when_wait_seconds_exceeds_max_wait"
        status: pass
    human_judgment: false
  - id: D3
    description: "reconcile_tripped(now) forces tokens=0 and updated_at=now; save()/load() round-trip tokens + updated_at through JSON with no drift, persisting no credential material, and load() of a missing path returns a fresh bucket"
    requirement: "ANTI-01"
    verification:
      - kind: unit
        ref: "tests/test_ratelimit.py#test_reconcile_tripped_zeroes_tokens_and_sets_updated_at"
        status: pass
      - kind: unit
        ref: "tests/test_ratelimit.py#test_save_then_load_round_trips_tokens_and_updated_at"
        status: pass
      - kind: unit
        ref: "tests/test_ratelimit.py#test_load_of_missing_path_returns_fresh_bucket_without_raising"
        status: pass
      - kind: unit
        ref: "tests/test_ratelimit.py#test_save_writes_no_credential_material_only_tokens_and_updated_at"
        status: pass
    human_judgment: false
  - id: D4
    description: "check_geo skips on falsy expected_country, returns None on case-insensitive match, raises GeoMismatchError(found, expected) on mismatch, fails open by default on resolver error, and fails closed when fail_open=False"
    requirement: "ANTI-02"
    verification:
      - kind: unit
        ref: "tests/test_ratelimit.py#test_check_geo_skips_and_does_not_call_resolver_when_expected_country_falsy"
        status: pass
      - kind: unit
        ref: "tests/test_ratelimit.py#test_check_geo_returns_none_on_case_insensitive_match"
        status: pass
      - kind: unit
        ref: "tests/test_ratelimit.py#test_check_geo_raises_geo_mismatch_error_on_country_mismatch"
        status: pass
      - kind: unit
        ref: "tests/test_ratelimit.py#test_check_geo_fails_open_by_default_when_resolver_raises"
        status: pass
      - kind: unit
        ref: "tests/test_ratelimit.py#test_check_geo_fails_closed_when_fail_open_false"
        status: pass
    human_judgment: false
  - id: D5
    description: "Whole existing test suite (120 tests) stays green untouched -- this plan adds a new file and modifies no existing source"
    verification:
      - kind: unit
        ref: "uv run pytest -q (119 passed, 1 pre-existing unrelated failure: test_read_03_pagination)"
        status: pass
    human_judgment: false

duration: 12min
completed: 2026-07-09
status: complete
---

# Phase 09 Plan 01: WriteBudget Token Bucket + Geo Guard Module Summary

**New standalone `auraframes/ratelimit.py` module — injected-clock `WriteBudget` token bucket with JSON persistence, and a fail-open `check_geo` pre-flight guard — fully offline-tested (19 new tests), zero existing source touched.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-09T~10:58Z (per plan file timestamp)
- **Completed:** 2026-07-09
- **Tasks:** 2 completed (TDD: 4 commits each task-pair, 2 test + 2 feat)
- **Files modified:** 2 (both new: `auraframes/ratelimit.py`, `tests/test_ratelimit.py`)

## Accomplishments
- `WriteBudget` token bucket: injected-clock refill math (with the clock-skew/None-updated_at
  clamp), consume/wait/stop `acquire()` semantics matching the locked keyword-only signature,
  `reconcile_tripped()`, and a stdlib-only JSON `save()`/`load()` round-trip that persists no
  credential material
- `check_geo` pre-flight guard: skip-on-falsy-country, case-insensitive country match,
  `GeoMismatchError` on mismatch, and a fail-open-by-default (fail-closed opt-in) resolver
  failure policy
- `BudgetExhausted` and `GeoMismatchError` exceptions carrying the exact fields (`wait_seconds`;
  `found`/`expected`) the CLI (Plan 09-02) needs for its user-facing messages
- `_default_resolver`: bare short-timeout `httpx.get` to `ipinfo.io/json`, deliberately not
  routed through the Pushd-specific `Client` class, never exercised by the test suite
- 19 new offline unit tests (`tests/test_ratelimit.py`) — zero real network calls, zero real
  `~/.config` disk access, zero real `datetime.utcnow()`/`time.sleep()` calls
- Entire pre-existing 120-test suite stays green (only the one pre-existing, unrelated
  `test_read_03_pagination` failure persists — out of scope for this plan)

## Task Commits

Each task followed the plan's `tdd="true"` RED/GREEN cycle, with two independent gate pairs
(Task 1 for `WriteBudget`, Task 2 for `check_geo`) since both target the same two files:

1. **Task 1: WriteBudget token bucket + JSON persistence + exceptions**
   - `dd2ff60` — `test(09-01): add failing test for WriteBudget token bucket` (RED)
   - `d4336d7` — `feat(09-01): implement WriteBudget token bucket + JSON persistence` (GREEN)
2. **Task 2: check_geo pre-flight guard + default ipinfo resolver + GeoMismatchError**
   - `74a6f9e` — `test(09-01): add failing test for check_geo pre-flight guard` (RED)
   - `25c8f0e` — `feat(09-01): implement check_geo pre-flight guard + default resolver` (GREEN)

**Plan metadata:** (this commit, docs: complete plan)

## Files Created/Modified
- `auraframes/ratelimit.py` - New module: `WriteBudget`, `check_geo`, `_default_resolver`,
  `GeoMismatchError`, `BudgetExhausted`
- `tests/test_ratelimit.py` - New 100%-offline unit test suite for the whole module (19 tests)

## Decisions Made
- `check_geo`'s `resolver` keyword defaults to `_default_resolver` (per the plan's Task 2 action
  block) so Plan 09-02's production wiring needs no explicit resolver argument, while every test
  in this plan still injects a fake explicitly — the default is never exercised in the suite.
- `WriteBudget.save()` takes no path argument by design (uses `self.path` from construction),
  matching the plan's stated rationale that Plan 09-02's `execute_plan` integration can call a
  bare `budget.save()` after each chunk.
- Applied the TDD RED/GREEN gate per task rather than once for the whole plan: Task 1's test file
  initially covered only `WriteBudget`-related behavior (RED against a nonexistent module, then
  GREEN with `BudgetExhausted`/`WriteBudget` only); Task 2 then extended the same test file with
  `check_geo` coverage (RED against the still-missing symbols, then GREEN adding
  `GeoMismatchError`/`check_geo`/`_default_resolver`). This keeps each task's RED phase failing
  for a reason specific to that task, not a leftover import error from the other task.

## Deviations from Plan

None - plan executed exactly as written. Every method signature, refill formula, wait-mode
countdown behavior, persistence contract, and `check_geo` behavior matches the plan's `<behavior>`
and `<action>` blocks and the verbatim code examples in `09-RESEARCH.md:826-881` and
`09-RESEARCH.md:690-702`.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. `_default_resolver` requires no API key
(ipinfo.io's unauthenticated legacy endpoint) and is not invoked by anything in this plan.

## Next Phase Readiness

- `auraframes/ratelimit.py` exports everything Plan 09-02 needs to wire into `execute_plan`,
  `settings.py`, and `cli.py`: `WriteBudget` (with its locked `acquire()` signature),
  `check_geo`, `BudgetExhausted`, `GeoMismatchError`.
- No blockers. The module is fully self-contained and untested-integration-wise only in the
  sense that Plan 09-02 has not yet wired it into the write path — that wiring, plus the
  `settings.py`/`cli.py` surface and the REQUIREMENTS.md back-fill, is explicitly deferred to
  09-02 per this plan's `<artifacts_this_phase_produces>` note.

---
*Phase: 09-proactive-write-rate-limiter-geo-guard*
*Completed: 2026-07-09*

## Self-Check: PASSED

- FOUND: auraframes/ratelimit.py
- FOUND: tests/test_ratelimit.py
- FOUND: .planning/phases/09-proactive-write-rate-limiter-geo-guard/09-01-SUMMARY.md
- FOUND commit: dd2ff60 (test: WriteBudget RED)
- FOUND commit: d4336d7 (feat: WriteBudget GREEN)
- FOUND commit: 74a6f9e (test: check_geo RED)
- FOUND commit: 25c8f0e (feat: check_geo GREEN)
