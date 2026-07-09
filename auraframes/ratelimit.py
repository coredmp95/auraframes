"""Standalone, injectable write-rate-budget + geo pre-flight guard module
(Phase 09: proactive-write-rate-limiter-geo-guard).

`WriteBudget` is a client-side token bucket that makes the Pushd anti-abuse
write-lockout structurally hard to hit: callers must `acquire()` tokens
before issuing a batch of write network calls, either waiting for enough
tokens to refill or stopping cleanly before ever making the call.

This module touches no existing source and has no side effects at import
time -- it never calls `datetime.utcnow()`, `time.sleep()`, or `httpx`
directly during any *tested* path. `now` and `sleep` are injected by the
caller (mirroring the `sleep=time.sleep` seam already used by
`auraframes.sync.execute_plan`), so this module is 100% offline-testable.

`WriteBudget.save()`/`load()` persist ONLY `tokens` + `updated_at` to a
per-account JSON state file -- never the email, password, or any auth
token (see the phase's threat register, T-09-02).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


class BudgetExhausted(Exception):
    """Raised by `WriteBudget.acquire()` in stop mode (`wait=False`, or a
    computed `wait_seconds` exceeding `max_wait`) instead of ever making the
    gated write call. Carries `wait_seconds` so the CLI (Plan 09-02) can
    print how long a retry would need to wait."""

    def __init__(self, wait_seconds: float):
        self.wait_seconds = wait_seconds
        super().__init__(
            f'Write budget exhausted; would need to wait {wait_seconds:.1f}s '
            'for enough tokens to refill.'
        )


@dataclass
class WriteBudget:
    """A per-account client-side token bucket gating batches of Pushd write
    network calls. Mirrors the `ExecutionResult`/`SyncPlan` plain-dataclass
    style used in `auraframes/sync.py` (pydantic is reserved for API DTOs).

    `path` is a constructor field (never hardcoded internally) so tests
    always pass a pytest `tmp_path` value and production wiring (Plan 09-02)
    computes the real `~/.config/auraframes/...` path at the CLI boundary.
    """

    capacity: float
    refill_per_min: float
    path: Path
    tokens: float = 0.0
    updated_at: datetime | None = None

    def acquire(self, n, *, wait, max_wait, now, sleep, on_wait=None) -> None:
        """Refill by elapsed minutes since `updated_at` (clamped to >=0 per
        the clock-skew/None-updated_at Pitfall 2 fix), cap at `capacity`,
        then either consume `n` tokens immediately, wait for them (sleeping
        in 1s steps via the injected `sleep`, surfacing `on_wait(remaining)`
        each second -- mirrors `execute_plan.interchunk_pause()`), or raise
        `BudgetExhausted` if `wait=False` or the wait would exceed `max_wait`.

        `now` is a VALUE supplied by the caller, never read internally --
        this module never calls `datetime.utcnow()`.
        """
        elapsed_minutes = max(0.0, (now - (self.updated_at or now)).total_seconds() / 60.0)
        self.tokens = min(self.capacity, self.tokens + self.refill_per_min * elapsed_minutes)
        self.updated_at = now

        if self.tokens >= n:
            self.tokens -= n
            return

        wait_seconds = (n - self.tokens) / self.refill_per_min * 60.0
        if not wait or wait_seconds > max_wait:
            raise BudgetExhausted(wait_seconds)

        remaining = wait_seconds
        while remaining > 0:
            if on_wait:
                on_wait(remaining)
            step = 1.0 if remaining >= 1.0 else remaining
            sleep(step)
            remaining -= step

        self.tokens = self.capacity  # fully refilled by definition of having waited wait_seconds
        self.tokens -= n

    def reconcile_tripped(self, now) -> None:
        """Force the bucket to empty (tokens=0, updated_at=now) after a real
        anti-abuse trip (`RateLimitError`/`ConsecutiveWriteFailureError`) so
        the next run's proactive budget reflects reality even though the
        server-side trip wasn't caused by this bucket running dry."""
        self.tokens = 0
        self.updated_at = now

    def save(self) -> None:
        """Write `tokens` + `updated_at` (isoformat, or null) as JSON to
        `self.path`, creating parent directories as needed. No path
        argument -- always writes to the field set at construction, so
        callers can call a bare `budget.save()`. Persists no credential
        material (T-09-02)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({
            'tokens': self.tokens,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }))

    @classmethod
    def load(cls, path: Path, *, capacity: float, refill_per_min: float) -> 'WriteBudget':
        """Reconstruct a `WriteBudget` from `path`. If `path` does not
        exist, returns a fresh bucket (tokens=0, updated_at=None) without
        raising -- the common case for a first-ever run."""
        if not path.exists():
            return cls(capacity=capacity, refill_per_min=refill_per_min, path=path)
        data = json.loads(path.read_text())
        return cls(
            capacity=capacity, refill_per_min=refill_per_min, path=path,
            tokens=data['tokens'],
            updated_at=datetime.fromisoformat(data['updated_at']) if data['updated_at'] else None,
        )
