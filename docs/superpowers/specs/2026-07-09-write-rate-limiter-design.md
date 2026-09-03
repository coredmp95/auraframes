# Design — Proactive Write Rate-Limiter & Geo Guard

**Date:** 2026-07-09
**Status:** Approved (brainstorming), pending implementation plan
**Branch context:** work started on `gsd/phase-08-...`; implementation to be routed through GSD (see CLAUDE.md) — likely its own phase.

## Problem

The Aura/Pushd write path trips an undocumented server-side anti-abuse limit that returns
`401` on writes (escalating to `475` on login) and does **not** clear with time on its own
when the real cause is geographic. Two distinct, empirically measured causes:

1. **Geo mismatch (cause #1).** When the client's exit-IP country differs from the account's
   country, **every** write returns `401`, persistently (measured: VPN in Belgium vs. a
   France account → writes 401 for >13h; switching the VPN to France unblocked writes
   instantly). Login and reads keep working under both geos — the block is write-endpoint-only.
2. **Request-rate limit (real, but generous).** Under correct geo, writes still trip after a
   burst. Measured capacity ≈ **42 write requests** before `401`; recovery ≈ **~40 min** of
   write-freeze. The currency is the **request**, not the photo: batched, one chunk of 50
   photos = 2 requests (`select_asset` + `batch_update`), so ~42 requests ≈ ~1000 photos.
   Failed write attempts also appear to consume budget.

The existing pacing (throttle 0.5s, batch 50, 5s inter-chunk delay, abort-after-5-failures
backstop) is **reactive** — it spaces writes and aborts *after* a trip. Goal: make blocking
**structurally impossible** via a **proactive**, configurable budget the client tracks itself,
plus a geo pre-flight guard.

## Decisions (from brainstorming)

- **Budget-exhausted behavior:** configurable; **default = wait** (sleep until refilled) with a
  configurable `--max-wait` cap, beyond which it stops cleanly.
- **Cross-invocation state:** **persist + reconcile.** A per-account state file on disk holds
  the token-bucket state; on any real `401/475` trip the estimate is corrected (bucket → empty).
- **Geo guard:** **configurable pre-flight.** If an expected country is configured, verify the
  exit-IP country before any write and refuse on mismatch; if unconfigured, skip.
- **Placement (Approach A):** a dedicated, injectable `ratelimit` module consulted by
  `execute_plan` — matches the existing injectable-seam pattern (`sleep`, `throttle_seconds`,
  `batch_size`), keeps logic isolated and offline-testable. Not bolted into `execute_plan`
  (B), not a client-level interceptor (C).

## Architecture

New module `auraframes/ratelimit.py`:

### `WriteBudget` — token bucket
State: `tokens: float`, `updated_at: datetime`.

- `acquire(n, *, wait, max_wait, now, sleep, on_wait=None)`:
  1. Refill: `tokens = min(capacity, tokens + refill_per_min * minutes_since(updated_at))`.
  2. If `tokens >= n` → consume (`tokens -= n`), set `updated_at = now`, return.
  3. Else compute `wait_seconds` until `n` tokens exist. If `wait` and `wait_seconds <= max_wait`
     → `sleep(wait_seconds)` (surfacing a countdown via `on_wait`, reusing the existing hook),
     then consume. Else raise `BudgetExhausted(wait_seconds)`.
- `reconcile_tripped(now)`: force `tokens = 0`, `updated_at = now`. Called when a real
  `RateLimitError` / `ConsecutiveWriteFailureError` occurs despite the budget — corrects drift.
- `load(path)` / `save(path)`: JSON round-trip.

Parameters (`capacity`, `refill_per_min`) come from settings/env; the clock (`now`) and
`sleep` are injected so the whole thing is deterministic in tests.

### `check_geo(expected_country, *, resolver, fail_open=True)`
- `expected_country` falsy → return `None` (skip).
- Else `resolver()` returns the exit-IP country code (default resolver: `GET ipinfo.io/json`,
  short timeout). Mismatch → raise `GeoMismatchError(found, expected)`.
- Resolver raises / times out → **fail-open** by default (log a warning, allow the write) so an
  ipinfo outage never blocks a legitimate upload. Configurable to fail-closed.

### Persistence
State file: `~/.config/auraframes/budget-<sha1(email)[:12]>.json` (per-account; no multi-account
collision). Directory from `AURA_STATE_DIR`. Read once at start of a run; **re-written after each
successful write chunk** so an interrupt (Ctrl-C/crash) leaves an accurate estimate. On a trip,
`reconcile_tripped()` then save.

### Integration in `execute_plan`
New injectable params: `budget: WriteBudget | None`, `geo_check: Callable | None`,
`wait_on_budget: bool`, `max_wait_seconds: float`. When `budget is None` the function behaves
exactly as today (backward compatible; keeps offline tests that don't care about budget green).

- **Pre-flight:** call `geo_check()` once before any write; `GeoMismatchError` propagates to the CLI.
- **Before each write chunk:** `budget.acquire(reqs)` where `reqs = 2` for an upload chunk
  (`select_asset` + `batch_update`) and `1` for a delete chunk.
- **Existing error paths unchanged**, plus `budget.reconcile_tripped()` + `save()` grafted onto
  the `RateLimitError` and `ConsecutiveWriteFailureError` branches. The backstop remains the
  ultimate safety net below the proactive budget.
- **After each successful chunk:** `budget.save()`.

## Configuration (settings.py + env + CLI flags)

| Concept | Constant / env | Default |
|---|---|---|
| bucket capacity | `AURA_WRITE_BUDGET_CAPACITY` | `30` (conservative, < 42 measured) |
| refill rate | `AURA_WRITE_BUDGET_REFILL_PER_MIN` | `0.75` (≈ full in ~40 min) |
| wait vs stop | `AURA_WRITE_BUDGET_WAIT` | `true` |
| max wait | `AURA_WRITE_BUDGET_MAX_WAIT` | `3600` (seconds) |
| expected country | `AURA_COUNTRY` | unset → geo check skipped |
| geo fail mode | `AURA_GEO_FAIL_OPEN` | `true` |
| state dir | `AURA_STATE_DIR` | `~/.config/auraframes` |

`push` CLI flags (per-run overrides): `--max-wait`, `--no-wait`, `--country`, `--ignore-budget`
(escape hatch that bypasses the budget entirely for the run).

## Error handling

New exceptions in `ratelimit.py`:
- `GeoMismatchError(found, expected)` → CLI: "VPN/exit IP in {found}, account expects {expected}
  — switch your VPN and retry." Refuses to write.
- `BudgetExhausted(wait_seconds)` (stop-cleanly path) → CLI: "write budget exhausted, come back
  in ~{minutes} min (or pass --no-wait / raise --max-wait)."

Existing `RateLimitError` (429/475) and `ConsecutiveWriteFailureError` remain as the reactive
safety net and now also drive `reconcile_tripped()`.

## Testing (100% offline)

- **`WriteBudget`**: refill math across elapsed intervals; `acquire` in wait mode (sleeps the
  right duration, then consumes) and stop mode (raises `BudgetExhausted` with correct
  `wait_seconds`); persistence round-trip; `reconcile_tripped` zeroes the bucket. Injected
  clock + `sleep` + tmp state file — no real time, no real disk-home.
- **`check_geo`**: match (passes), mismatch (`GeoMismatchError`), resolver failure (fail-open
  passes with warning; fail-closed raises) — injected resolver, no network.
- **`execute_plan` integration**: a fake `WriteBudget` asserting `acquire` is called once per
  chunk with the right `reqs` (2 upload / 1 delete), geo pre-flight called once, and
  `reconcile_tripped` invoked on the simulated trip paths. Uses the existing injected
  `sleep`/`s3`/`sqs`/`aura` fakes.

## Out of scope (YAGNI)

- Client-level interception of every write path (only bulk `execute_plan` writes are the abuse
  vector).
- Reading the true server-side budget (not exposed; the local estimate + reconcile is the model).
- Auto-detecting the account's home country (explicit `AURA_COUNTRY` config instead).
