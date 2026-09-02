---
phase: 09-proactive-write-rate-limiter-geo-guard
reviewed: 2026-07-09T09:34:24Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - auraframes/ratelimit.py
  - auraframes/utils/settings.py
  - auraframes/sync.py
  - auraframes/cli.py
  - tests/test_ratelimit.py
  - tests/test_settings_budget.py
  - tests/test_execute_plan_budget_geo.py
  - tests/test_cli_push_budget_geo.py
  - tests/test_cli_apply.py
findings:
  critical: 1
  warning: 3
  info: 3
  total: 7
status: issues_found
---

# Phase 9: Code Review Report

**Reviewed:** 2026-07-09T09:34:24Z
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Phase 09 adds a client-side token-bucket write rate-limiter (`WriteBudget`), a geo
pre-flight guard (`check_geo`), and wires both into `execute_plan` / `run_sync`. The
no-op-when-disabled contract (budget/geo_check `None`) is correctly preserved — every
budget touch point is guarded by `if budget is not None`, `geo_check` by `if geo_check
is not None`, and `clock` is only invoked on budget paths — so backward compatibility is
byte-identical, as claimed and as `test_backward_compat_no_budget_no_geo_check_touches_nothing_new`
verifies. Credential-leakage protection also holds: `save()` persists only `tokens` +
`updated_at`, and the state filename is a sha1 hash of the email, never the email itself.

However, the token-bucket **refill math is incorrect on the wait path** (CR-01): after
waiting for tokens, the bucket is reset to *full capacity* instead of to the amount
actually accrued. This grossly under-limits the writer after the very first wait —
directly defeating the anti-burst purpose that is the whole point of this phase — and the
unit test bakes the wrong value in as expected. Additionally, two parsed env vars are
never wired to anything (WR-01), and the persistence layer is not crash-safe (WR-02).

## Critical Issues

### CR-01: Token bucket refills to full capacity after any wait, defeating rate limiting

**File:** `auraframes/ratelimit.py:102-111`
**Issue:**
On the wait path, `acquire()` computes `wait_seconds` as the time to accrue exactly the
*deficit* (`n - tokens`), sleeps for it, then does:

```python
self.tokens = self.capacity  # fully refilled by definition of having waited wait_seconds
self.tokens -= n
```

The comment's reasoning is wrong. Waiting `wait_seconds` accrues `refill_per_min *
wait_seconds/60 == (n - tokens)` tokens — reaching exactly `n`, **not** `capacity`. The
correct post-wait state is `tokens == n`, then consume `n` → `~0`. Setting
`tokens = capacity` over-grants `capacity - n` tokens on every wait.

Concrete impact with the shipped defaults (`capacity=30`, `refill_per_min=0.75`): a fresh
bucket's first `acquire(2)` waits ~160s, then lands on `tokens = 30 - 2 = 28`. The next
**14 chunks fire back-to-back with zero pacing**, because the bucket is now full. The
intended rate (~0.75 token/min ≈ one write-pair every ~2.7 min) is not enforced at all
after the first wait — exactly the burst the anti-abuse lockout trips on, which this whole
phase exists to prevent.

Secondary defect in the same block: `updated_at` is left at the pre-wait `now`, so the
next `acquire(now=clock())` re-counts the waited interval as fresh elapsed time (masked
only by the capacity clamp).

Note: `tests/test_ratelimit.py:132` asserts `budget.tokens == 27.0` and
`test_acquire_wait_mode_works_without_on_wait_callback` asserts `== 27.0`, i.e. the tests
encode the buggy behavior and give false confidence. These assertions must be updated
alongside the fix.

**Fix:**
```python
    remaining = wait_seconds
    while remaining > 0:
        if on_wait:
            on_wait(remaining)
        step = 1.0 if remaining >= 1.0 else remaining
        sleep(step)
        remaining -= step

    # Waiting wait_seconds accrues exactly (n - tokens) tokens -> tokens == n.
    self.tokens += self.refill_per_min * wait_seconds / 60.0
    self.tokens = min(self.capacity, self.tokens)
    self.updated_at = self.updated_at + timedelta(seconds=wait_seconds) if self.updated_at else self.updated_at
    self.tokens -= n
```
(Equivalently, since `wait_seconds` was derived so the deficit is closed exactly, set
`self.tokens = 0.0` after the loop. Either way, do **not** reset to `capacity`.) Update
the two `== 27.0` assertions in `tests/test_ratelimit.py` to the corrected value.

## Warnings

### WR-01: `AURA_WRITE_BUDGET_WAIT` and `AURA_WRITE_BUDGET_MAX_WAIT` are parsed but never used

**File:** `auraframes/utils/settings.py:27-28`
**Issue:**
Both env vars are read into module constants (and unit-tested in
`test_settings_budget.py`) but are never imported or referenced anywhere else in the
package — `cli.py` imports only `AURA_WRITE_BUDGET_CAPACITY`,
`AURA_WRITE_BUDGET_REFILL_PER_MIN`, `AURA_COUNTRY`, `AURA_GEO_FAIL_OPEN`, and
`AURA_STATE_DIR` (`grep` confirms zero other references). Consequently, `run_sync` only
adjusts wait behavior via the `--no-wait` / `--max-wait` flags and always lets
`execute_plan` fall back to its own `wait_on_budget=True` / `max_wait_seconds=3600.0`
defaults. A user who sets `AURA_WRITE_BUDGET_WAIT=false` or `AURA_WRITE_BUDGET_MAX_WAIT`
in their environment gets **no effect and no warning** — dead configuration that
contradicts the "configured exclusively via environment variables" project convention.

**Fix:** Either wire the env defaults into `run_sync` so the flags override the env (not
the hardcoded default), e.g.:
```python
# in run_sync, when building exec_kwargs:
exec_kwargs['wait_on_budget'] = False if no_wait else AURA_WRITE_BUDGET_WAIT
exec_kwargs['max_wait_seconds'] = max_wait if max_wait is not None else AURA_WRITE_BUDGET_MAX_WAIT
```
(importing the two constants in `cli.py`), or remove the two unused settings and their
tests if env control was not intended.

### WR-02: `WriteBudget.load()` is not crash-safe against a corrupt/truncated state file

**File:** `auraframes/ratelimit.py:121-145`
**Issue:**
`save()` uses a single non-atomic `self.path.write_text(...)`; an interrupted write (Ctrl-C,
disk full, crash mid-write) leaves a truncated file. `load()` only guards `path.exists()`
— `json.loads(path.read_text())` (JSONDecodeError) and `data['tokens']` /
`data['updated_at']` (KeyError) are unguarded. A single corrupt state file therefore
**bricks every subsequent `push` / `sync --apply`**: the exception is caught by
`run_sync`'s generic `except Exception` and surfaced as an opaque `Failed to sync frame:
<json error>` with rc 1, until the user manually locates and deletes the file under
`~/.config/auraframes/`. This undermines the phase's own robustness goal (making the write
path resilient).

**Fix:** Make `save()` atomic (write to a temp file in the same dir, then `os.replace`) and
have `load()` fall back to a fresh bucket on parse/key errors:
```python
try:
    data = json.loads(path.read_text())
    tokens = data['tokens']
    updated_at = datetime.fromisoformat(data['updated_at']) if data['updated_at'] else None
except (json.JSONDecodeError, KeyError, ValueError):
    logger.warning(f'Corrupt write-budget state at {path}; starting fresh.')
    return cls(capacity=capacity, refill_per_min=refill_per_min, path=path)
```

### WR-03: `acquire()` divides by `refill_per_min` without guarding zero

**File:** `auraframes/ratelimit.py:98`
**Issue:**
`wait_seconds = (n - self.tokens) / self.refill_per_min * 60.0` raises
`ZeroDivisionError` when `refill_per_min == 0` and the bucket lacks enough tokens.
`AURA_WRITE_BUDGET_REFILL_PER_MIN` is a free-form `float(os.getenv(...))` (settings.py:26),
so a user setting it to `0` to "pause" writes triggers an uncaught crash (surfaced as
`Failed to sync frame: division by zero`) rather than a clean stop. With a zero refill the
bucket can also never refill to satisfy a deficit, so waiting would be infinite anyway.

**Fix:** Treat a non-positive `refill_per_min` deficit as an immediate stop:
```python
if self.refill_per_min <= 0:
    raise BudgetExhausted(float('inf'))
wait_seconds = (n - self.tokens) / self.refill_per_min * 60.0
```

## Info

### IN-01: `reconcile_tripped` assigns int `0` to a float field

**File:** `auraframes/ratelimit.py:118`
**Issue:** `self.tokens = 0` assigns an `int` where every other assignment (and the
dataclass default `tokens: float = 0.0`) uses a float. Harmless numerically but
inconsistent and round-trips through JSON as `0` vs `0.0`.
**Fix:** `self.tokens = 0.0`.

### IN-02: `cli.py` imports a private symbol and passes a redundant default

**File:** `auraframes/cli.py:17,286`
**Issue:** `_build_geo_check` imports the private `_default_resolver` and passes
`resolver=_default_resolver` explicitly, but that is already `check_geo`'s default
parameter value — the argument is redundant, and reaching into another module's
underscore-private name couples the CLI to an implementation detail.
**Fix:** Drop the `resolver=` argument (and the `_default_resolver` import):
`lambda: check_geo(country, fail_open=AURA_GEO_FAIL_OPEN)`.

### IN-03: `check_geo` assumes `resolver()` returns a non-empty string

**File:** `auraframes/ratelimit.py:187`
**Issue:** `found.upper()` runs outside the try/except. If a resolver returns `None`
(e.g. a future/alternate resolver, or an unexpected ipinfo payload shape), this raises
`AttributeError` on the success path regardless of `fail_open`, bypassing the fail-open
contract. An empty string would produce a `GeoMismatchError(found='')` with an unhelpful
message. Low likelihood given the shipped `_default_resolver`, but the fail-open guarantee
does not cover a malformed-but-non-raising resolver result.
**Fix:** Coerce/validate `found` inside the try block, or guard: `if not found: return
None` (fail-open) before the comparison.

---

_Reviewed: 2026-07-09T09:34:24Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
