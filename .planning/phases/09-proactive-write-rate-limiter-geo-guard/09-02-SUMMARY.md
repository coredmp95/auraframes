---
phase: 09-proactive-write-rate-limiter-geo-guard
plan: 02
subsystem: infra
tags: [rate-limiting, token-bucket, geo-guard, cli, argparse, settings]

# Dependency graph
requires:
  - phase: 09-proactive-write-rate-limiter-geo-guard (Plan 09-01)
    provides: "auraframes/ratelimit.py: WriteBudget, check_geo, GeoMismatchError, BudgetExhausted, _default_resolver"
provides:
  - "settings.py: AURA_WRITE_BUDGET_CAPACITY/REFILL_PER_MIN/WAIT/MAX_WAIT, AURA_COUNTRY, AURA_GEO_FAIL_OPEN, AURA_STATE_DIR + _bool_env helper"
  - "execute_plan(): budget/geo_check/wait_on_budget/max_wait_seconds/clock params -- proactive write-budget + geo pre-flight guard wired into the live write path, no-op when unused"
  - "push CLI flags: --max-wait/--no-wait/--country/--ignore-budget; run_sync builds budget+geo_check for both push --apply and sync --apply by default"
  - "GeoMismatchError/BudgetExhausted CLI exception branches with clean user-facing messages and exit code 1"
  - "ANTI-01..ANTI-07 requirement IDs minted and traced in REQUIREMENTS.md"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Injected clock=get_utc_now (mirrors sleep=time.sleep) so execute_plan's time-dependent budget calls stay offline-testable"
    - "CLI-boundary factory functions (_build_write_budget/_build_geo_check) constructing guard objects only on confirmed --apply, mirroring the existing S3Client()/SQSClient() construction-at-boundary convention"
    - "exec_kwargs additive-forwarding idiom extended: budget/geo_check forwarded whenever built (both verbs, by default); override kwargs (wait_on_budget/max_wait_seconds) forwarded only when their CLI flag was explicitly supplied"

key-files:
  created:
    - tests/test_settings_budget.py
    - tests/test_execute_plan_budget_geo.py
    - tests/test_cli_push_budget_geo.py
  modified:
    - auraframes/utils/settings.py
    - auraframes/sync.py
    - auraframes/cli.py
    - tests/test_cli_apply.py
    - .planning/REQUIREMENTS.md

key-decisions:
  - "settings.py: bare float(os.getenv(...)) for the four numeric budget settings (no helper needed); only the two booleans (AURA_WRITE_BUDGET_WAIT, AURA_GEO_FAIL_OPEN) need the new _bool_env helper, since Python's bool('false') is True"
  - "execute_plan's save() placement: budget.save() runs as the last statement inside each for-chunk loop body, after the try/except -- covers success AND ordinary caught per-item/per-chunk failures, but NOT the upload loop's 'if not prepped: continue' early-exit (no write was attempted for that chunk, so no acquire-vs-save drift accrues to persist)"
  - "reconcile_tripped()+save() fires from exactly 2 RateLimitError except-branches (upload + delete) plus once inside note_failure()'s ConsecutiveWriteFailureError raise-site -- when a ConsecutiveWriteFailureError trips on the Nth chunk, prior chunks' own normal-path save() calls already ran, so total save_calls = (N-1 normal) + 1 reconcile-save, not just 1"
  - "budget/geo_check are constructed and forwarded for BOTH push --apply and sync --apply by default (built in run_sync from settings env) -- sync gets the same anti-abuse protection as push with zero new sync-only flags, matching the plan's locked must_haves truth"
  - "Rule 3 auto-fix: tests/test_cli_apply.py's pre-existing execute_plan fakes (_patch_execute_plan, and two standalone fakes in the RateLimitError/ConsecutiveWriteFailureError tests) needed **kwargs added to their signatures -- run_sync now always forwards budget/geo_check by default, which broke the old fakes' fixed keyword-only parameter lists with a TypeError; none of the pre-existing assertions changed"

patterns-established:
  - "Pattern: CLI-boundary guard-object factories (_build_write_budget/_build_geo_check) return None to signal 'omit from exec_kwargs' -- any future optional execute_plan extra should follow the same None-means-omit contract rather than always forwarding a sentinel"

requirements-completed: [ANTI-03, ANTI-04, ANTI-05, ANTI-06, ANTI-07]

coverage:
  - id: D1
    description: "settings.py exposes AURA_WRITE_BUDGET_CAPACITY/REFILL_PER_MIN/WAIT/MAX_WAIT, AURA_COUNTRY, AURA_GEO_FAIL_OPEN, AURA_STATE_DIR with correct defaults, parsed defensively via a new _bool_env helper; AURA_COUNTRY unset -> None; AURA_STATE_DIR expands ~"
    requirement: "ANTI-05"
    verification:
      - kind: unit
        ref: "tests/test_settings_budget.py#test_defaults_when_no_env_vars_set"
        status: pass
      - kind: unit
        ref: "tests/test_settings_budget.py#test_numeric_env_vars_are_parsed_as_floats"
        status: pass
      - kind: unit
        ref: "tests/test_settings_budget.py#test_aura_state_dir_expands_tilde"
        status: pass
      - kind: unit
        ref: "tests/test_settings_budget.py#test_bool_env_parses_common_string_forms"
        status: pass
      - kind: unit
        ref: "tests/test_settings_budget.py#test_write_budget_wait_and_geo_fail_open_parse_via_bool_env"
        status: pass
    human_judgment: false
  - id: D2
    description: "execute_plan gains budget/geo_check/wait_on_budget/max_wait_seconds/clock keyword-only params, acquiring 2 tokens per upload chunk and 1 per delete chunk, saving after each normally-returning chunk, geo-checking exactly once before any write (including delete-only plans), and reconciling+saving the budget on both the RateLimitError and ConsecutiveWriteFailureError trip paths"
    requirement: "ANTI-03"
    verification:
      - kind: unit
        ref: "tests/test_execute_plan_budget_geo.py#test_upload_only_plan_acquires_2_per_chunk_and_saves_after_each_chunk"
        status: pass
      - kind: unit
        ref: "tests/test_execute_plan_budget_geo.py#test_delete_only_plan_acquires_1_per_chunk"
        status: pass
      - kind: unit
        ref: "tests/test_execute_plan_budget_geo.py#test_geo_check_called_exactly_once_before_any_write_including_delete_only"
        status: pass
      - kind: unit
        ref: "tests/test_execute_plan_budget_geo.py#test_geo_mismatch_aborts_before_any_write_call"
        status: pass
    human_judgment: false
  - id: D3
    description: "budget.reconcile_tripped()+save() fire on both the upload-loop and delete-loop RateLimitError branches, and inside note_failure()'s ConsecutiveWriteFailureError raise-site, before propagating"
    requirement: "ANTI-04"
    verification:
      - kind: unit
        ref: "tests/test_execute_plan_budget_geo.py#test_rate_limit_error_upload_chunk_reconciles_and_saves_before_raising"
        status: pass
      - kind: unit
        ref: "tests/test_execute_plan_budget_geo.py#test_rate_limit_error_delete_chunk_reconciles_and_saves_before_raising"
        status: pass
      - kind: unit
        ref: "tests/test_execute_plan_budget_geo.py#test_consecutive_write_failure_reconciles_and_saves_before_raising"
        status: pass
    human_judgment: false
  - id: D4
    description: "execute_plan(budget=None, geo_check=None) -- its pre-Phase-09 default -- behaves byte-identically to before: the pre-existing test_execute_plan.py and test_write_throttling.py suites pass with ZERO modification"
    requirement: "ANTI-03"
    verification:
      - kind: unit
        ref: "tests/test_execute_plan_budget_geo.py#test_backward_compat_no_budget_no_geo_check_touches_nothing_new"
        status: pass
      - kind: unit
        ref: "uv run pytest tests/test_execute_plan.py tests/test_write_throttling.py -q (23 passed, unmodified files)"
        status: pass
    human_judgment: false
  - id: D5
    description: "push exposes --max-wait/--no-wait/--country/--ignore-budget (sync does not); run_sync constructs budget+geo_check for BOTH push --apply and sync --apply by default, forwarding budget only when not --ignore-budget and geo_check only when a country is configured; override kwargs (wait_on_budget/max_wait_seconds) forwarded only when their flag is explicitly supplied"
    requirement: "ANTI-06"
    verification:
      - kind: unit
        ref: "tests/test_cli_push_budget_geo.py#test_push_apply_forwards_budget_and_geo_check_by_default"
        status: pass
      - kind: unit
        ref: "tests/test_cli_push_budget_geo.py#test_push_apply_ignore_budget_forwards_no_budget_kwarg"
        status: pass
      - kind: unit
        ref: "tests/test_cli_push_budget_geo.py#test_push_no_wait_forwards_wait_on_budget_false"
        status: pass
      - kind: unit
        ref: "tests/test_cli_push_budget_geo.py#test_push_max_wait_forwards_max_wait_seconds"
        status: pass
      - kind: unit
        ref: "tests/test_cli_push_budget_geo.py#test_push_country_flag_builds_geo_check"
        status: pass
      - kind: unit
        ref: "tests/test_cli_push_budget_geo.py#test_sync_apply_no_new_flags_still_forwards_default_budget_and_geo_check"
        status: pass
      - kind: unit
        ref: "tests/test_cli_push_budget_geo.py#test_build_parser_push_exposes_new_flags_sync_does_not"
        status: pass
    human_judgment: false
  - id: D6
    description: "GeoMismatchError and BudgetExhausted produce clean, distinct user-facing CLI messages and exit code 1, ordered before the generic Exception catch-all"
    requirement: "ANTI-06"
    verification:
      - kind: unit
        ref: "tests/test_cli_push_budget_geo.py#test_geo_mismatch_error_produces_clean_message_and_exit_1"
        status: pass
      - kind: unit
        ref: "tests/test_cli_push_budget_geo.py#test_budget_exhausted_produces_clean_message_and_exit_1"
        status: pass
    human_judgment: false
  - id: D7
    description: "The state-file path derives from sha1(email)[:12] (non-cryptographic filename-uniqueness hash, not a security boundary per T-09-02) under AURA_STATE_DIR, and the persisted JSON body never contains the email or password"
    requirement: "ANTI-06"
    verification:
      - kind: unit
        ref: "tests/test_cli_push_budget_geo.py#test_state_file_path_derives_from_sha1_email_and_body_has_no_email"
        status: pass
    human_judgment: false
  - id: D8
    description: "REQUIREMENTS.md defines ANTI-01..ANTI-07 under a new Anti-Abuse Hardening (v2.x) subsection and traces every ID to Phase 9 with plan numbers"
    requirement: "ANTI-05"
    verification:
      - kind: manual_procedural
        ref: ".planning/REQUIREMENTS.md Anti-Abuse Hardening (v2.x) subsection + Traceability table"
        status: pass
    human_judgment: false
  - id: D9
    description: "Full pre-existing + new offline test suite passes (only the pre-existing, unrelated test_read_03_pagination failure persists, documented in 09-01-SUMMARY.md as out of scope)"
    verification:
      - kind: unit
        ref: "uv run pytest -q (175 passed, 1 pre-existing unrelated failure)"
        status: pass
    human_judgment: false

duration: ~12min
completed: 2026-07-09
status: complete
---

# Phase 09 Plan 02: Wire Write-Rate-Budget + Geo Guard into the Live Write Path Summary

**`WriteBudget`/`check_geo` (from Plan 09-01) wired into `execute_plan` and the CLI as the default protection for both `push --apply` and `sync --apply` — env config, four `push` override flags, and two new clean-message exception branches, with the whole 120+ test pre-existing suite staying green.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-07-09T~11:15Z (approximate, from first commit timestamp minus setup)
- **Completed:** 2026-07-09T11:27:29+02:00 (final task commit)
- **Tasks:** 3 completed
- **Files modified:** 8 (3 new test files, 3 modified source files, 1 modified pre-existing test file, REQUIREMENTS.md)

## Accomplishments
- `settings.py`: seven new env-config constants (`AURA_WRITE_BUDGET_CAPACITY`/`REFILL_PER_MIN`/`WAIT`/`MAX_WAIT`, `AURA_COUNTRY`, `AURA_GEO_FAIL_OPEN`, `AURA_STATE_DIR`) parsed defensively at import time, plus the first `_bool_env` helper in this codebase
- `execute_plan()` (`auraframes/sync.py`) gains `budget`/`geo_check`/`wait_on_budget`/`max_wait_seconds`/`clock` keyword-only params: a geo pre-flight fires once before any write (including delete-only plans), `budget.acquire(2)`/`acquire(1)` gate each upload/delete chunk, `budget.save()` runs after every normally-returning chunk, and `budget.reconcile_tripped()+save()` fires on both the `RateLimitError` and `ConsecutiveWriteFailureError` trip paths — a true no-op (byte-identical to pre-Phase-09 behavior) when `budget`/`geo_check` are `None`
- `cli.py`: `push` gains `--max-wait`/`--no-wait`/`--country`/`--ignore-budget`; `run_sync` builds `WriteBudget`/`geo_check` for **both** `push --apply` and `sync --apply` by default via new `_build_write_budget`/`_build_geo_check` factory functions at the CLI boundary (mirroring the existing `S3Client()`/`SQSClient()` construction site); two new exception branches (`GeoMismatchError`, `BudgetExhausted`) print clean, distinct back-off messages and return exit code 1, ordered before the generic `Exception` catch-all
- The per-account state-file path is `AURA_STATE_DIR/budget-{sha1(email)[:12]}.json` — the email itself never appears in the persisted JSON body (only `tokens`/`updated_at`)
- 3 new offline test files (settings, execute_plan integration, CLI wiring) — zero real network calls, zero real `~/.config` disk access, zero real time
- `.planning/REQUIREMENTS.md` minted and traced ANTI-01…ANTI-07 (ANTI-01/02/07 → Plan 09-01, ANTI-03/04/05/06/07 → Plan 09-02) under a new "Anti-Abuse Hardening (v2.x)" subsection
- Full suite: 175 passed, only the pre-existing unrelated `test_read_03_pagination` failure persists (documented in `09-01-SUMMARY.md` as out of scope)

## Task Commits

1. **Task 1: settings.py env config + REQUIREMENTS.md back-fill** - `0abdb71` (feat)
2. **Task 2: execute_plan integration — geo pre-flight, budget.acquire, save, reconcile-on-trip** - `a75f07e` (feat)
3. **Task 3: cli.py wiring — push flags, budget/geo_check factories, forwarding, exception branches** - `dc9c759` (feat)

**Plan metadata:** (this commit, docs: complete plan)

## Files Created/Modified
- `auraframes/utils/settings.py` - `_bool_env` helper + seven write-budget/geo-guard env-config constants
- `auraframes/sync.py` - `execute_plan` gains the budget/geo_check integration (5 new params, geo pre-flight, acquire/save/reconcile call sites)
- `auraframes/cli.py` - `push` flags, `_build_write_budget`/`_build_geo_check` factories, `exec_kwargs` forwarding, `GeoMismatchError`/`BudgetExhausted` branches
- `tests/test_settings_budget.py` - New: settings defaults/overrides/`_bool_env`/`~`-expansion coverage
- `tests/test_execute_plan_budget_geo.py` - New: fake-budget call-sequencing coverage for the `execute_plan` integration
- `tests/test_cli_push_budget_geo.py` - New: push flags, budget/geo_check forwarding, exception-branch, state-file-path coverage
- `tests/test_cli_apply.py` - Extended 3 pre-existing `execute_plan` fakes with `**kwargs` (Rule 3 auto-fix, see Deviations)
- `.planning/REQUIREMENTS.md` - Minted ANTI-01…ANTI-07 + traceability rows

## Decisions Made
- `settings.py`: bare `float(os.getenv(...))` for the four numeric settings (no helper needed); only the two booleans need `_bool_env`, since Python's `bool('false')` is `True` and would silently disable the guard on any non-empty string.
- `execute_plan`'s `budget.save()` placement: the last statement inside each `for chunk in ...:` loop body, after the try/except — covers a chunk that succeeded OR failed ordinarily (per-item/per-chunk), but the upload loop's `if not prepped: continue` early-exit (all files failed local S3-prep, no chunk write was even attempted) deliberately does not call `save()` there, since no write-call token spend needs persisting for that iteration.
- `reconcile_tripped()+save()` fires from exactly 3 sites (upload-loop `RateLimitError`, delete-loop `RateLimitError`, and inside `note_failure()`'s `ConsecutiveWriteFailureError` raise) exactly as the plan specified. Note for future readers: when a `ConsecutiveWriteFailureError` trips on the Nth chunk of a run, the prior N-1 chunks already ran their own normal-path `save()` — so the *total* `budget.save()` call count across a tripped run is `(N-1) + 1`, not `1`. Verified explicitly in `test_consecutive_write_failure_reconciles_and_saves_before_raising`.
- `budget`/`geo_check` are constructed and forwarded for **both** `push --apply` and `sync --apply` by default (per the plan's locked must_haves truth) — `sync` gets the same anti-abuse protection as `push` with zero new sync-only flags, since both verbs hit the identical anti-abuse surface via the same `execute_plan()` call site.
- `_build_geo_check`'s `country_override or AURA_COUNTRY` precedence means `--country` always wins when supplied, falling back to the env default otherwise; a falsy result (neither set) returns `None`, matching `check_geo`'s own falsy-`expected_country` skip contract.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `tests/test_cli_apply.py`'s pre-existing `execute_plan` fakes needed `**kwargs`**
- **Found during:** Task 3 (cli.py wiring) — running `tests/test_cli_apply.py` after wiring `run_sync` to forward `budget`/`geo_check` by default
- **Issue:** `run_sync` now always calls `execute_plan(..., budget=..., geo_check=..., **exec_kwargs)` on any confirmed `--apply`. The three pre-existing hand-written fakes in `test_cli_apply.py` (`_patch_execute_plan`'s `fake_execute_plan`, plus `rate_limited_execute_plan` and `failing_execute_plan`) had fixed keyword-only parameter lists with no catch-all, so every one of those tests started raising `TypeError: ... got an unexpected keyword argument 'budget'`, which `run_sync`'s generic `except Exception` branch caught and reported as `Failed to sync frame: ...` — silently breaking 9 pre-existing tests.
- **Fix:** Added `**kwargs` to all three fake signatures. No existing assertion changed — the fakes simply accept-and-ignore the new kwargs, matching the plan's "Both `push --apply` and `sync --apply` get a budget + geo_check by default" must_have while keeping every original test's own assertions intact.
- **Files modified:** `tests/test_cli_apply.py`
- **Verification:** `uv run pytest tests/test_cli_push_budget_geo.py tests/test_cli_apply.py tests/test_cli_sync.py -q` → 32 passed
- **Committed in:** `dc9c759` (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking, Rule 3)
**Impact on plan:** Necessary to satisfy the plan's own explicit "budget+geo_check forwarded by default for both verbs" requirement without breaking pre-existing coverage. No scope creep — no new behavior added beyond accepting the new default kwargs.

## Issues Encountered

None beyond the deviation above.

## User Setup Required

None - no external service configuration required for this plan. The default geo resolver (`_default_resolver`, from Plan 09-01) requires no API key and is never invoked by any test in this plan (every test injects a fake `geo_check`/resolver). Live use of the geo guard requires setting `AURA_COUNTRY` (e.g. `AURA_COUNTRY=FR`) — this is optional; when unset, the guard is skipped entirely (fail-open-by-omission, matching `check_geo`'s falsy contract), so no action is required to keep using `push`/`sync --apply` as before.

## Next Phase Readiness

- The proactive write-rate-budget + geo pre-flight guard is now the DEFAULT behavior for real applies (`push --apply` and `sync --apply`), making the Pushd write-lockout structurally hard to hit going forward.
- All 7 minted `ANTI-0N` requirements (ANTI-01–07) are traced to Phase 9 in `REQUIREMENTS.md` and marked complete.
- No blockers. This phase's scope (Plans 09-01 + 09-02) is now fully executed; a live verification run (`aura-cli push --apply` or `sync --apply` against a real frame) would be the natural follow-up to confirm the guard behaves as designed under real anti-abuse conditions, but is not required by this plan's own scope.

---
*Phase: 09-proactive-write-rate-limiter-geo-guard*
*Completed: 2026-07-09*

## Self-Check: PASSED

- FOUND: auraframes/utils/settings.py
- FOUND: auraframes/sync.py
- FOUND: auraframes/cli.py
- FOUND: tests/test_settings_budget.py
- FOUND: tests/test_execute_plan_budget_geo.py
- FOUND: tests/test_cli_push_budget_geo.py
- FOUND: tests/test_cli_apply.py
- FOUND: .planning/REQUIREMENTS.md
- FOUND commit: 0abdb71 (feat: settings.py env config + REQUIREMENTS.md back-fill)
- FOUND commit: a75f07e (feat: execute_plan budget/geo_check integration)
- FOUND commit: dc9c759 (feat: cli.py wiring — push flags, factories, exception branches)
