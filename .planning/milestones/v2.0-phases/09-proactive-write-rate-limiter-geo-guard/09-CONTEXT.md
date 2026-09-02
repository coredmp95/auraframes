# Phase 9: Proactive Write Rate-Limiter & Geo Guard - Context

**Gathered:** 2026-07-09
**Status:** Ready for planning
**Source:** Approved design spec (`docs/superpowers/specs/2026-07-09-write-rate-limiter-design.md`)

<domain>
## Phase Boundary

Make the Pushd write-lockout **structurally impossible** to hit by adding two proactive
client-side guards consulted by the bulk-write path (`execute_plan`):

1. A **proactive request budget** (token bucket) that waits or stops cleanly *before* the
   client would trip the server's undocumented anti-abuse limit (~42 write requests,
   ~40 min recovery). State is **persisted per-account** and **reconciled** to empty on any
   real trip.
2. A **configurable geo pre-flight guard** that refuses writes when the exit-IP country
   differs from the account's configured country — the empirically #1 cause of the
   persistent `401` write-lockout.

**In scope:** new `auraframes/ratelimit.py` module (`WriteBudget`, `check_geo`, new
exceptions), integration into `execute_plan` via new injectable params, settings/env +
`push` CLI flags, and 100%-offline tests.

**Out of scope (YAGNI, from spec):**
- Client-level interception of *every* write path (only bulk `execute_plan` writes are the abuse vector).
- Reading the true server-side budget (not exposed; local estimate + reconcile is the model).
- Auto-detecting the account's home country (explicit `AURA_COUNTRY` config instead).

</domain>

<decisions>
## Implementation Decisions

All items below are **locked** by the approved design spec.

### Architecture / placement
- **Approach A (dedicated injectable module).** New `auraframes/ratelimit.py` consulted by
  `execute_plan` — matches the existing injectable-seam pattern (`sleep`, `throttle_seconds`,
  `batch_size`, `chunk_delay`, `on_wait`). NOT bolted inline into `execute_plan` (B), NOT a
  client-level interceptor (C).
- `execute_plan` gains new injectable params: `budget: WriteBudget | None`,
  `geo_check: Callable | None`, `wait_on_budget: bool`, `max_wait_seconds: float`. When
  `budget is None`, behavior is **exactly as today** (backward compatible — existing offline
  tests stay green without a budget).

### `WriteBudget` (token bucket)
- State: `tokens: float`, `updated_at: datetime`.
- `acquire(n, *, wait, max_wait, now, sleep, on_wait=None)`: refill by
  `refill_per_min * minutes_since(updated_at)` (capped at `capacity`); if `tokens >= n` consume;
  else compute `wait_seconds`; if `wait` and `wait_seconds <= max_wait` → `sleep()` (surface
  countdown via the existing `on_wait` hook) then consume, else raise `BudgetExhausted(wait_seconds)`.
- `reconcile_tripped(now)`: force `tokens = 0`, `updated_at = now`. Called when a real
  `RateLimitError` / `ConsecutiveWriteFailureError` occurs despite the budget.
- `load(path)` / `save(path)`: JSON round-trip.
- Clock (`now`) and `sleep` are **injected** for deterministic offline tests.
- **Request currency, not photos:** an upload chunk costs `2` (`select_asset` + `batch_update`);
  a delete chunk costs `1`.

### `check_geo(expected_country, *, resolver, fail_open=True)`
- Falsy `expected_country` → return `None` (skip).
- Else `resolver()` returns exit-IP country code (default resolver: `GET ipinfo.io/json`,
  short timeout). Mismatch → raise `GeoMismatchError(found, expected)`.
- Resolver raises/times out → **fail-open by default** (log warning, allow write); configurable
  to fail-closed. An ipinfo outage must never block a legitimate upload.

### Persistence
- State file: `~/.config/auraframes/budget-<sha1(email)[:12]>.json` (per-account, no collision).
- Directory from `AURA_STATE_DIR` (default `~/.config/auraframes`).
- Read once at start of a run; **re-written after each successful write chunk** so an
  interrupt (Ctrl-C/crash) leaves an accurate estimate. On a trip: `reconcile_tripped()` then save.

### Integration in `execute_plan`
- **Pre-flight:** call `geo_check()` once before any write; `GeoMismatchError` propagates to CLI.
- **Before each write chunk:** `budget.acquire(reqs)` (`reqs=2` upload, `1` delete).
- **Existing error paths unchanged**, plus `budget.reconcile_tripped()` + `save()` grafted onto
  the `RateLimitError` and `ConsecutiveWriteFailureError` branches. The existing
  abort-after-N-failures backstop remains the ultimate safety net below the proactive budget.
- **After each successful chunk:** `budget.save()`.

### Configuration (settings.py + env + CLI flags)
| Concept | Constant / env | Default |
|---|---|---|
| bucket capacity | `AURA_WRITE_BUDGET_CAPACITY` | `30` (conservative, < 42 measured) |
| refill rate | `AURA_WRITE_BUDGET_REFILL_PER_MIN` | `0.75` (≈ full in ~40 min) |
| wait vs stop | `AURA_WRITE_BUDGET_WAIT` | `true` |
| max wait | `AURA_WRITE_BUDGET_MAX_WAIT` | `3600` (seconds) |
| expected country | `AURA_COUNTRY` | unset → geo check skipped |
| geo fail mode | `AURA_GEO_FAIL_OPEN` | `true` |
| state dir | `AURA_STATE_DIR` | `~/.config/auraframes` |

- `push` CLI flags (per-run overrides): `--max-wait`, `--no-wait`, `--country`, `--ignore-budget`
  (escape hatch that bypasses the budget entirely for the run).

### Error handling
- New exceptions in `ratelimit.py`:
  - `GeoMismatchError(found, expected)` → CLI: "VPN/exit IP in {found}, account expects {expected}
    — switch your VPN and retry." Refuses to write.
  - `BudgetExhausted(wait_seconds)` (stop-cleanly path) → CLI: "write budget exhausted, come back
    in ~{minutes} min (or pass --no-wait / raise --max-wait)."
- Existing `RateLimitError` (429/475) and `ConsecutiveWriteFailureError` remain the reactive
  safety net and now also drive `reconcile_tripped()`.

### Claude's Discretion
- Exact JSON schema/key names of the persisted state file (spec fixes semantics, not byte layout).
- Precise wording of CLI messages beyond the intent captured above.
- Where the default `ipinfo.io` resolver helper lives (in `ratelimit.py` vs a small helper).
- How `budget`/`geo_check` are constructed and wired from `cli.py` (factory vs inline).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design source (authoritative)
- `docs/superpowers/specs/2026-07-09-write-rate-limiter-design.md` — the full approved design:
  problem, measured limits, architecture, config table, error handling, offline test plan, YAGNI.

### Code seams to integrate with (existing)
- `auraframes/sync.py` (`execute_plan` @ line 304) — the bulk write path; injectable-seam pattern
  (`s3_client`, `sqs_client`, `throttle_seconds`, `batch_size`, `chunk_delay`, `sleep`, `on_wait`,
  `progress`). This is where `budget` / `geo_check` are consulted.
- `auraframes/sync.py` (`ConsecutiveWriteFailureError` @ line 127) — reactive backstop; a trip here
  must drive `reconcile_tripped()`.
- `auraframes/client.py` (`RateLimitError` @ line 28) — 429/475 fast-path signal; a trip here must
  drive `reconcile_tripped()`.
- `auraframes/utils/settings.py` — env-var config module; add the new `AURA_WRITE_BUDGET_*`,
  `AURA_COUNTRY`, `AURA_GEO_FAIL_OPEN`, `AURA_STATE_DIR` constants here.
- `auraframes/cli.py` (`push` subparser @ ~line 58, `_execute`/`exec_kwargs` @ ~line 242-405) —
  where new `push` flags are declared and forwarded into `execute_plan`; `on_wait` / `progress`
  hooks already wired here (`_report_wait`, `_report_progress`).

### New file this phase produces
- `auraframes/ratelimit.py` — `WriteBudget`, `check_geo`, `GeoMismatchError`, `BudgetExhausted`.

### Test analogs (existing offline-test conventions)
- `tests/test_client_rate_limit.py`, `tests/test_cli_apply.py`, `tests/test_cli_sync.py` —
  injected-fake style (fake `s3`/`sqs`/`aura`, injected `sleep`) to mirror for budget/geo tests.

</canonical_refs>

<specifics>
## Specific Ideas

- Measured anti-abuse envelope (drives defaults): ~**42 write requests** before `401`, ~**40 min**
  write-freeze recovery. Capacity default `30` and refill `0.75/min` are deliberately conservative.
- Geo lockout is *write-endpoint-only*: login and reads keep working under a mismatched geo, so
  the guard is a pre-flight specific to the write path.
- Failed write attempts appear to consume budget too — reconcile-on-trip is what keeps the local
  estimate honest against server reality.
- See memory: `[[pushd-write-geofence]]`, `[[pushd-batch-endpoints]]`, `[[pushd-app-upload-mechanism]]`.

</specifics>

<deferred>
## Deferred Ideas

None beyond the YAGNI list in Phase Boundary — the spec fully scopes this phase.

</deferred>

<requirements_note>
## Requirements Mapping

Phase 9 is a **new hardening phase** added after the original v1 milestone (all 13 v1
requirements shipped in Phases 5-8). It has no pre-existing requirement IDs — ROADMAP lists
`Requirements: TBD (map during planning)`. New requirement IDs (e.g. `ANTI-01…`) should be
minted during planning and back-filled into `.planning/REQUIREMENTS.md`.

</requirements_note>

---

*Phase: 09-proactive-write-rate-limiter-geo-guard*
*Context gathered: 2026-07-09 from approved design spec*
