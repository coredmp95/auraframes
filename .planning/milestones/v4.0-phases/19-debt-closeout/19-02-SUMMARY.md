---
phase: 19-debt-closeout
plan: 02
subsystem: logging+client
tags: [logger, loguru, client, test-01, offline-tested]
requires:
  - auraframes/aura.py (_init_logger, the leaking two logger.add calls)
  - auraframes/client.py (Client.__init__ base_url composition, v1.1 deferral)
  - auraframes/cli.py (_configure_cli_logging — the reconfigure contract to preserve)
  - tests/fixtures/login.json (auth_token/id the exact-value assertions read)
provides:
  - aura.py module-level _LOGGER_READY guard (MOD-04: one log file per process)
  - Client(base_url=...) additive injection seam (TEST-01 candidate #4)
  - tests/test_aura_logger.py (3 behavioral + 1 shape test)
  - test_offline_login_sets_exact_authenticated_values / test_authenticated_headers_propagate_to_subsequent_requests / test_client_base_url_is_injectable (TEST-01 #2/#4)
stems_from: []
keys_in: []
keys_out: []

decisions:
  - D-03 honored as research-amended — module-level guard (CONTEXT's per-instance
    wording superseded by 19-RESEARCH before execution; the plan carried the
    module-level truth and the red-green tracer proved it).
  - D-04 honored — file-count assertions on glob (never filenames), tmp-cwd isolation.
  - D-05 honored — exact fixture values ('fake-auth-token-0001' / 'user-fake-0001')
    asserted post-login AND on a subsequent request's wire headers via a capturing
    router override (cleaner than the transport-surgery first draft).
  - D-06 honored — additive base_url: str | None = None; injected host+path asserted.

session_type: execution
completed: 2026-09-29
commits: [d46e7a8]
---
# Phase 19, Plan 02 Execution Summary: logger guard + TEST-01 candidates

**Status:** complete · **Wave:** 1 · **Commits:** d46e7a8

## Delivered

- **MOD-04**: `aura.py` module-level `_LOGGER_READY` guard — first `Aura()`
  construction registers the stderr + `logs/file_{time}.log` sinks, every later
  construction is a sink no-op. Zero `logger.remove` in aura.py (grep-gated);
  `cli.py`'s `_configure_cli_logging()` remains the single wholesale reconfigure
  point and is test-proven still working with the guard active. The vestigial
  commented-out teardown line dies too.
- **TEST-01 candidate #2**: `test_offline_login_sets_exact_authenticated_values`
  (fixture's exact `x-token-auth`/`x-user-id` values post-login) +
  `test_authenticated_headers_propagate_to_subsequent_requests` (a follow-up GET
  through the SAME logged-in client carries both values on the wire, captured by
  a router-override handler).
- **TEST-01 candidate #4**: additive `Client(base_url=…)` (None ⇒ the historical
  `AURA_API_BASE_URL/AURA_API_VERSION` composition, zero-arg callers untouched) +
  `test_client_base_url_is_injectable` (injected host `mock.invalid`, path
  `/v9/probe.json`, fully offline).
- `tests/test_cli_status.py` reset fixture now also resets `_LOGGER_READY` — its
  tests legitimately depend on a fresh `Aura()` re-registering sinks after the
  fixture's `logger.remove()`, which is exactly the behavior the guard changed.

## Red-green tracer evidence

- Pre-fix: `test_repeated_construction_spawns_one_log_file` ERRORED on the
  missing `_LOGGER_READY` attribute (red), then passed post-fix showing 1 file
  for 3 constructions.
- Order-dependence catch: the new guard made
  `test_status_debug_flag_restores_verbose_stderr` fail in full-suite order
  (it expects a fresh construction to re-register sinks after the fixture's
  global `logger.remove()`) — fixed by resetting the guard in that fixture,
  preserving the file's documented per-test contract.

## Verification

- `uv run pytest tests/test_aura_logger.py -q` → 4 passed
- `uv run pytest tests/test_offline_read_path.py -q` → 11 passed (8 pre-existing untouched + 3 new)
- Full offline suite: **401 passed** (394 + 7) · zero live network
- `! grep -q "logger.remove" auraframes/aura.py` → clean

## Deviations

- None against the plan's must_haves. (The propagation test's first draft used
  httpx-internal transport surgery; replaced with the harness's callable
  override before any commit — noted here for honesty, invisible to the gates.)
