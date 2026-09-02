---
phase: 09-proactive-write-rate-limiter-geo-guard
fixed_at: 2026-07-09T10:08:03Z
review_path: .planning/phases/09-proactive-write-rate-limiter-geo-guard/09-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 9: Code Review Fix Report

**Fixed at:** 2026-07-09T10:08:03Z
**Source review:** .planning/phases/09-proactive-write-rate-limiter-geo-guard/09-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 4 (1 Critical + 3 Warning; Info findings IN-01..IN-03 out of scope)
- Fixed: 4
- Skipped: 0

**Verification:** `uv run pytest -q` => 172 passed, 4 skipped, 0 failed. The 4
skipped are the live-API tests (`live` marker) which require real credentials;
the pre-existing `tests/test_read_path.py::test_read_03_pagination` is among
them and is skipped rather than failing in this offline environment. Every
touched file also passed a Python `ast.parse` syntax check.

## Fixed Issues

### CR-01: Token bucket refills to full capacity after any wait, defeating rate limiting

**Files modified:** `auraframes/ratelimit.py`, `tests/test_ratelimit.py`
**Commit:** 85cf984
**Applied fix:** On the wait path, `acquire()` no longer resets `self.tokens`
to `capacity`. It now accrues exactly the waited deficit
(`tokens += refill_per_min * wait_seconds / 60`, clamped to `capacity`),
landing on exactly `n` tokens, then consumes `n` to reach ~0 — so pacing is
enforced after the first wait instead of the bucket jumping to full. Also
advanced `updated_at` by `timedelta(seconds=wait_seconds)` so the next
`acquire()` does not re-count the waited interval as fresh elapsed time
(`timedelta` added to the datetime import). The two `== 27.0` assertions in
`tests/test_ratelimit.py`
(`test_acquire_wait_mode_sleeps_in_1s_steps_calls_on_wait_then_consumes` and
`test_acquire_wait_mode_works_without_on_wait_callback`) — which encoded the
buggy post-wait value — were corrected to `== 0.0` with updated comments.

_Note (logic change): this is a math-correctness fix. It is fully covered by
the corrected unit tests (post-wait `tokens == 0.0`, and the existing
non-wait refill/clamp tests still pass), and matches the intended semantics
confirmed for this phase. Worth a human eyeballing the corrected assertion
once, per standard practice for logic fixes._

### WR-01: `AURA_WRITE_BUDGET_WAIT` and `AURA_WRITE_BUDGET_MAX_WAIT` parsed but never used

**Files modified:** `auraframes/cli.py`
**Commit:** 9ce26f0
**Applied fix:** Imported the two previously-dead constants into `cli.py` and
wired them into `run_sync`'s `exec_kwargs`: the effective wait/max-wait now
falls back to the env value when the corresponding `--no-wait` / `--max-wait`
flag is not supplied (flag takes precedence over env). To preserve the Phase 08
"defaults don't override execute_plan defaults" contract that the existing
tests assert (`wait_on_budget is None` / `max_wait_seconds is None` at default
settings), each kwarg is forwarded only when its effective value actually
differs from execute_plan's own default (`True` / `3600.0`, captured as the
`_EXECUTE_PLAN_DEFAULT_WAIT` / `_EXECUTE_PLAN_DEFAULT_MAX_WAIT` module
constants). This adapts the review's suggested one-liner so no existing test
regresses while still giving `AURA_WRITE_BUDGET_WAIT=false` /
`AURA_WRITE_BUDGET_MAX_WAIT=<n>` a real effect. Verified against
`test_cli_push_budget_geo.py`, `test_settings_budget.py`, and
`test_cli_apply.py` (42 passed).

### WR-02: `WriteBudget.load()` not crash-safe against a corrupt/truncated state file

**Files modified:** `auraframes/ratelimit.py`
**Commit:** 2b7a359
**Applied fix:** `save()` now writes atomically — payload to a `<name>.tmp`
sibling in the same directory, then `os.replace()` onto the final path (added
`import os`) — so an interrupted write can never leave a truncated JSON file.
`load()` now wraps the `json.loads` / key access / `datetime.fromisoformat`
parse in `try/except (json.JSONDecodeError, KeyError, TypeError, ValueError)`,
logging a warning and returning a fresh bucket on any corruption instead of
propagating an opaque error that would brick every subsequent
`push` / `sync --apply`. (`TypeError` added beyond the review's suggested set
to also cover a non-dict / non-string `updated_at` payload.)

### WR-03: `acquire()` divides by `refill_per_min` without guarding zero

**Files modified:** `auraframes/ratelimit.py`
**Commit:** 75ca373
**Applied fix:** Added a `if self.refill_per_min <= 0: raise
BudgetExhausted(float('inf'))` guard immediately before the `wait_seconds`
division on the deficit path, so a user setting
`AURA_WRITE_BUDGET_REFILL_PER_MIN=0` to "pause" writes gets a clean
`BudgetExhausted` stop rather than an uncaught `ZeroDivisionError` (a
non-positive refill can never satisfy a deficit anyway, so the wait would be
infinite).

## Skipped Issues

None — all in-scope findings were fixed. (Info findings IN-01, IN-02, IN-03
were out of scope for the `critical_warning` fix scope and were not attempted.)

---

_Fixed: 2026-07-09T10:08:03Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
