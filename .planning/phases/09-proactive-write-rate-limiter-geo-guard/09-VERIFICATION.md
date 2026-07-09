---
phase: 09-proactive-write-rate-limiter-geo-guard
verified: 2026-07-09T10:12:00Z
status: passed
score: 21/21 must-haves verified
behavior_unverified: 0
overrides_applied: 0
---

# Phase 9: Proactive Write Rate-Limiter & Geo Guard Verification Report

**Phase Goal:** Make write blocking structurally impossible — a proactive, configurable
client-side request budget (WriteBudget token bucket, persisted + reconciled per account)
that waits/stops before tripping the Pushd anti-abuse limit (~42 write requests / ~40 min
recovery), plus a configurable geo pre-flight guard that refuses writes when the exit-IP
country differs from the account's country.

**Verified:** 2026-07-09T10:12:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

**Plan 09-01 (module core, ANTI-01/02/07)**

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `WriteBudget.acquire(n)` refills by `refill_per_min * elapsed_minutes` (clamped ≥0), caps at capacity, consumes `n` when available | ✓ VERIFIED | `auraframes/ratelimit.py:91-97`; `tests/test_ratelimit.py::test_acquire_refills_by_elapsed_minutes_then_consumes`, `::test_acquire_refill_never_pushes_tokens_above_capacity`, `::test_acquire_elapsed_clamp_backward_clock_adds_zero_tokens`, `::test_acquire_elapsed_clamp_same_instant_adds_zero_tokens`, `::test_acquire_fresh_bucket_none_updated_at_does_not_crash` — all pass |
| 2 | Wait mode sleeps computed `wait_seconds` in 1s steps via injected `sleep`, calling `on_wait` each second, then consumes; stop mode raises `BudgetExhausted(wait_seconds)` | ✓ VERIFIED | `auraframes/ratelimit.py:110-126`; `tests/test_ratelimit.py::test_acquire_wait_mode_sleeps_in_1s_steps_calls_on_wait_then_consumes` (`sleep.calls==[1,1,1]`, `waits.calls==[3,2,1]`, `tokens==0.0`), `::test_acquire_stop_mode_raises_budget_exhausted_when_wait_false`, `::test_acquire_stop_mode_raises_when_wait_seconds_exceeds_max_wait` — all pass |
| 3 | **CR-01 anti-burst fix holds:** post-wait tokens land at the deficit (`n`, then consumed to ≈0), NOT reset to full `capacity`; `updated_at` advances by the waited interval | ✓ VERIFIED | Code at `ratelimit.py:118-126` computes `tokens += refill_per_min*wait_seconds/60` (not `= capacity`) and `updated_at += timedelta(seconds=wait_seconds)`. Both wait-mode tests assert `tokens == 0.0` (corrected from the pre-fix `27.0`, per `09-REVIEW.md`/`09-REVIEW-FIX.md`). Independently re-derived by hand: with defaults (capacity=30, refill=0.75/min) a fresh bucket's first `acquire(2)` waits 160s and lands on `tokens=0.0`, not `28.0`. Also independently spot-checked live in this verification session: two back-to-back `acquire(2, wait=True)` calls (second call's `now` advanced by the first call's simulated wait time) each require a full wait — no burst — confirming pacing holds across multiple chunks, not just a single call |
| 4 | `reconcile_tripped(now)` forces `tokens=0`, `updated_at=now` | ✓ VERIFIED | `ratelimit.py:128-134`; `tests/test_ratelimit.py::test_reconcile_tripped_zeroes_tokens_and_sets_updated_at` passes |
| 5 | `save()`/`load()` round-trip tokens+updated_at through JSON with no drift; missing-file `load()` returns a fresh bucket | ✓ VERIFIED | `ratelimit.py:136-178`; `tests/test_ratelimit.py::test_save_then_load_round_trips_tokens_and_updated_at`, `::test_load_of_missing_path_returns_fresh_bucket_without_raising` pass. WR-02 fix: `save()` writes atomically (`.tmp` + `os.replace`), `load()` falls back to a fresh bucket on corrupt JSON/keys instead of raising |
| 6 | `check_geo`: falsy `expected_country` → None, skip (resolver not called); match → None; mismatch → `GeoMismatchError(found, expected)`; resolver-raises fails open by default (logs+None), fails closed when `fail_open=False` | ✓ VERIFIED | `ratelimit.py:197-222`; `tests/test_ratelimit.py::test_check_geo_skips_and_does_not_call_resolver_when_expected_country_falsy`, `::test_check_geo_returns_none_on_case_insensitive_match`, `::test_check_geo_raises_geo_mismatch_error_on_country_mismatch`, `::test_check_geo_fails_open_by_default_when_resolver_raises`, `::test_check_geo_fails_closed_when_fail_open_false` — all pass |
| 7 | Country comparison is case-insensitive (`found.upper()==expected.upper()`) | ✓ VERIFIED | `ratelimit.py:220`; `test_check_geo_returns_none_on_case_insensitive_match` (`'fr'` vs `'FR'`) passes |

**Plan 09-02 (live-path integration, ANTI-03/04/05/06/07)**

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 8 | `budget is None` AND `geo_check is None` → `execute_plan` behaves byte-identically to pre-Phase-09 | ✓ VERIFIED | `auraframes/sync.py` every touch point guarded by `if budget is not None:` / `if geo_check is not None:`; `tests/test_execute_plan_budget_geo.py::test_backward_compat_no_budget_no_geo_check_touches_nothing_new` passes; `tests/test_execute_plan.py` and `tests/test_write_throttling.py` pass unmodified (`uv run pytest -q` full run confirms, see below) |
| 9 | Each upload chunk calls `budget.acquire(2, ...)`; each delete chunk calls `budget.acquire(1, ...)` | ✓ VERIFIED | `sync.py:485-490` (upload, `n=2`), `sync.py:563-566` (delete, `n=1`); `test_execute_plan_budget_geo.py::test_upload_only_plan_acquires_2_per_chunk_and_saves_after_each_chunk`, `::test_delete_only_plan_acquires_1_per_chunk` pass |
| 10 | `geo_check()` called exactly once, before ANY write, including a delete-only plan | ✓ VERIFIED | `sync.py:425-431` — first executable statement of `execute_plan`, before `ExecutionResult()`; `test_execute_plan_budget_geo.py::test_geo_check_called_exactly_once_before_any_write_including_delete_only`, `::test_geo_mismatch_aborts_before_any_write_call` pass |
| 11 | `reconcile_tripped(clock())+save()` fires on BOTH `RateLimitError` branches AND the `ConsecutiveWriteFailureError` raise-site (inside `note_failure`) before propagating | ✓ VERIFIED | `sync.py:450-458` (note_failure), `sync.py:528-534` (upload RateLimitError), `sync.py:574-578` (delete RateLimitError); `test_execute_plan_budget_geo.py::test_rate_limit_error_upload_chunk_reconciles_and_saves_before_raising`, `::test_rate_limit_error_delete_chunk_reconciles_and_saves_before_raising`, `::test_consecutive_write_failure_reconciles_and_saves_before_raising` — all pass |
| 12 | `budget.save()` runs after every normally-returning write chunk (upload and delete) | ✓ VERIFIED | `sync.py:553-559` (upload), `sync.py:588-589` (delete); the same tests above assert `save_calls` counts matching chunk counts (e.g. 2 chunks → `save_calls==2`; a 5-chunk tripped run → `save_calls==5` = 4 normal + 1 reconcile) |
| 13 | Both `push --apply` and `sync --apply` get a budget + geo_check by default (constructed in `run_sync` from settings env) | ✓ VERIFIED | `cli.py:439-446` (`_build_write_budget`/`_build_geo_check` called unconditionally in `run_sync`, both verbs share this code path); `tests/test_cli_push_budget_geo.py::test_push_apply_forwards_budget_and_geo_check_by_default`, `::test_sync_apply_no_new_flags_still_forwards_default_budget_and_geo_check` pass |
| 14 | The four override flags (`--max-wait`/`--no-wait`/`--country`/`--ignore-budget`) exist on `push` and forward through; `--ignore-budget` bypasses the budget entirely (kwarg omitted) | ✓ VERIFIED | `cli.py:89-92` (push-only flags; confirmed absent from `sync_parser`, lines 64-68), `cli.py:279-280` (`_build_write_budget` returns `None` when `ignore_budget`); `test_cli_push_budget_geo.py::test_push_apply_ignore_budget_forwards_no_budget_kwarg`, `::test_push_no_wait_forwards_wait_on_budget_false`, `::test_push_max_wait_forwards_max_wait_seconds`, `::test_push_country_flag_builds_geo_check`, `::test_build_parser_push_exposes_new_flags_sync_does_not` pass |
| 15 | `GeoMismatchError` and `BudgetExhausted` surface as clean CLI messages and exit code 1 | ✓ VERIFIED | `cli.py:527-539`, ordered before the generic `except Exception` catch-all; `test_cli_push_budget_geo.py::test_geo_mismatch_error_produces_clean_message_and_exit_1`, `::test_budget_exhausted_produces_clean_message_and_exit_1` pass |
| 16 | `settings.py` parses budget floats and the two booleans (`AURA_WRITE_BUDGET_WAIT`, `AURA_GEO_FAIL_OPEN`) defensively via `_bool_env`; `AURA_COUNTRY` unset → None; `AURA_STATE_DIR` expands `~` | ✓ VERIFIED | `auraframes/utils/settings.py:11-32`; `tests/test_settings_budget.py` (defaults, bool-parse, `~`-expand) all pass |

**Additional review-fix items (WR-01/02/03, verified as part of the phase's own robustness claims)**

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 17 | `AURA_WRITE_BUDGET_WAIT`/`AURA_WRITE_BUDGET_MAX_WAIT` are actually wired into `run_sync` (not dead config) | ✓ VERIFIED | `cli.py:482-494` — effective wait/max-wait forwarded only when they'd change `execute_plan`'s own default, preserving the no-override contract; confirmed by `test_cli_push_budget_geo.py` (42 tests referenced in `09-REVIEW-FIX.md`, re-run below) |
| 18 | `WriteBudget.save()` is atomic; `load()` is crash-safe against a corrupt state file | ✓ VERIFIED | `ratelimit.py:146-153` (tmp-file + `os.replace`), `ratelimit.py:165-173` (try/except around parse, falls back to fresh bucket) |
| 19 | `acquire()` does not `ZeroDivisionError` on `refill_per_min<=0` | ✓ VERIFIED | `ratelimit.py:99-104` — guarded, raises clean `BudgetExhausted(inf)` |
| 20 | Per-account persisted state file carries no credential material (email/password) | ✓ VERIFIED | `ratelimit.py:147-150` (JSON body: `tokens`+`updated_at` only); `tests/test_ratelimit.py::test_save_writes_no_credential_material_only_tokens_and_updated_at`; `tests/test_cli_push_budget_geo.py::test_state_file_path_derives_from_sha1_email_and_body_has_no_email` — email appears only as a `sha1(email)[:12]` filename fragment, never in the body |
| 21 | Guard is a true no-op when `budget`/`geo_check` are `None` (no partial wiring) | ✓ VERIFIED | Every one of the 7 new touch points in `sync.py` is behind an explicit `is not None` check (verified by direct code read); `test_backward_compat_no_budget_no_geo_check_touches_nothing_new` plus the full pre-existing `test_execute_plan.py`/`test_write_throttling.py`/`test_cli_apply.py`/`test_cli_sync.py` suites pass unmodified |

**Score:** 21/21 truths verified (0 present-but-behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `auraframes/ratelimit.py` | `WriteBudget`, `check_geo`, `_default_resolver`, `GeoMismatchError`, `BudgetExhausted` | ✓ VERIFIED | All symbols present, substantive (223 lines, no stubs), wired into `sync.py`/`cli.py` |
| `tests/test_ratelimit.py` | 100%-offline unit coverage of the whole module | ✓ VERIFIED | 19 tests, all pass, zero real network/disk/time calls |
| `auraframes/utils/settings.py` | 7 new env-config constants + `_bool_env` | ✓ VERIFIED | Present, imported and used by `cli.py` |
| `auraframes/sync.py` | `execute_plan` gains 5 new keyword-only params, budget/geo integration | ✓ VERIFIED | Present, wired at 7 distinct touch points, all guarded |
| `auraframes/cli.py` | `push` flags, `_build_write_budget`/`_build_geo_check`, exception branches | ✓ VERIFIED | Present, wired into `run_sync` and `main()` |
| `tests/test_settings_budget.py` | Settings coverage | ✓ VERIFIED | Present, passes |
| `tests/test_execute_plan_budget_geo.py` | `execute_plan` integration coverage | ✓ VERIFIED | Present, passes (14 tests) |
| `tests/test_cli_push_budget_geo.py` | CLI wiring coverage | ✓ VERIFIED | Present, passes |
| `.planning/REQUIREMENTS.md` | ANTI-01..07 defined + traced to Phase 9 | ✓ VERIFIED | New "Anti-Abuse Hardening (v2.x)" subsection + traceability rows present |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `WriteBudget` | `self.path` | constructor field, no hardcoded path | ✓ WIRED | `ratelimit.py:76` dataclass field; `save()`/`load()` never hardcode a path |
| `WriteBudget.acquire`/`reconcile_tripped` | injected `now`/`sleep` | keyword params, never internal clock/sleep calls | ✓ WIRED | Confirmed by code read: no `datetime.utcnow()`/`time.sleep()` calls anywhere in `ratelimit.py`; `httpx.get` appears only inside `_default_resolver`, never invoked by the test suite |
| `run_sync` | `WriteBudget.load(...)` | `_build_write_budget` factory | ✓ WIRED | `cli.py:268-284`, called at `cli.py:445` |
| `run_sync` | `check_geo(...)` | `_build_geo_check` factory closure | ✓ WIRED | `cli.py:287-296`, called at `cli.py:446` |
| `run_sync` | `execute_plan` | `exec_kwargs` additive forwarding | ✓ WIRED | `cli.py:465-494`; `budget`/`geo_check` forwarded whenever built, override kwargs only when explicitly supplied — `test_sync_defaults_do_not_override_execute_plan_defaults`-style guarantee preserved by `test_cli_apply.py` still passing |
| `note_failure()` closure | `budget`/`clock` | Python closure (no new plumbing) | ✓ WIRED | `sync.py:450-458` reads `budget`/`clock` from the enclosing `execute_plan` scope directly |

### Data-Flow Trace (Level 4)

Not applicable — this phase has no UI/rendering data flow. The relevant "data flow" is the
budget/geo objects flowing from `settings.py` env → `cli.py` factories → `execute_plan`
params, which is covered under Key Link Verification above (all real objects, not stubs —
`WriteBudget.load()` reads real JSON state; `check_geo` closures wrap the real `_default_resolver`
in production, fakes only in tests).

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full test suite (existing + new) stays green except the pre-existing unrelated live-API failure | `uv run pytest -q` | `1 failed, 175 passed` — the 1 failure is `tests/test_read_path.py::test_read_03_pagination`, a live-network pagination test unrelated to Phase 9 (documented in `09-01-SUMMARY.md` as pre-existing/out of scope) | ✓ PASS |
| New module's isolated suite | `uv run pytest tests/test_ratelimit.py -q` | `19 passed` | ✓ PASS |
| CR-01 anti-burst fix: two consecutive `acquire()` waits never grant a burst | Manual `python -c` script (this verification session): fresh bucket → `acquire(2, wait=True)` waits and lands on `tokens=0.0`; a second `acquire(2, wait=True)` at `now` advanced only by the first call's simulated wait time again lands on `tokens=0.0` (never jumps to `capacity=30`) | `tokens=0.0` after both calls | ✓ PASS |
| Anti-pattern scan for debt markers in phase-touched files | `grep -n -E "TBD\|FIXME\|XXX\|TODO\|HACK\|PLACEHOLDER"` across all 8 phase files | Only 1 hit: `settings.py:6` `# TODO: Load device identifier through config` — pre-existing, unrelated to Phase 9 (predates this phase; not touched by ANTI-0N work) | ✓ PASS (no phase-introduced debt markers) |

### Probe Execution

Not applicable — no `scripts/*/tests/probe-*.sh` conventions or declared probes for this
phase; this is a library/CLI tooling phase verified via pytest, not shell probes.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|--------------|-------------|--------------|--------|----------|
| ANTI-01 | 09-01 | `WriteBudget` token-bucket core | ✓ SATISFIED | Truths 1-5 above |
| ANTI-02 | 09-01 | `check_geo` pre-flight guard | ✓ SATISFIED | Truths 6-7 above |
| ANTI-03 | 09-02 | `execute_plan` integration, no-op guard | ✓ SATISFIED | Truths 8-10, 21 above |
| ANTI-04 | 09-02 | Reconcile-on-trip wiring | ✓ SATISFIED | Truth 11 above |
| ANTI-05 | 09-02 | `settings.py` env config + `_bool_env` | ✓ SATISFIED | Truth 16 above |
| ANTI-06 | 09-02 | `push` CLI flags + exception branches | ✓ SATISFIED | Truths 13-15 above |
| ANTI-07 | 09-01 + 09-02 | 100%-offline test coverage | ✓ SATISFIED | All test files pass, zero network/disk/time real calls confirmed by code read |

No orphaned requirements: `.planning/REQUIREMENTS.md`'s "Anti-Abuse Hardening (v2.x)" section
lists exactly ANTI-01..07, all 7 traced to Phase 9 (Traceability table, lines 96-102), matching
the 7 requirement IDs declared across both plans' frontmatter exactly.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `auraframes/utils/settings.py` | 6 | `# TODO: Load device identifier through config` | ℹ️ Info | Pre-existing, predates this phase (`DEVICE_IDENTIFIER` config, unrelated to ANTI-0N work) — not a phase-introduced gap |

No stub returns, empty handlers, hardcoded-empty data flows, or console.log-only
implementations found in any of the 8 files touched by this phase.

### Human Verification Required

None. This phase produces library/CLI logic fully exercisable via offline unit and
integration tests; no UI, no real-time behavior, and no external-service dependency that
can't be verified through injected fakes. The one component that does touch a real external
service in production (`_default_resolver` → `ipinfo.io`) is explicitly scoped by the plan
as "no network-hitting unit test required" and is never invoked by any test — this is a
documented, intentional design choice (fail-open by default specifically because it can't be
verified live in CI), not a gap.

### Gaps Summary

None. All 21 derived must-have truths (merged from both plans' `must_haves.truths`,
`key_links`, and `prohibitions` blocks) are verified against the actual codebase — not just
present, but exercised by passing tests, and independently re-derived by hand for the
critical CR-01 anti-burst fix. The code-review cycle (`09-REVIEW.md` → `09-REVIEW-FIX.md`)
caught and fixed a genuine blocker (the token bucket over-refilling to full capacity after a
wait) plus three warnings (dead config, non-atomic persistence, zero-division); all four
fixes are confirmed present in the current source and covered by tests. The full test suite
(`uv run pytest -q`) reproduces the summary's claimed `175 passed, 1 failed`, where the one
failure is a pre-existing, unrelated live-API pagination test.

---

_Verified: 2026-07-09T10:12:00Z_
_Verifier: Claude (gsd-verifier)_
