---
phase: 11-write-path-reliability-format-support
plan: 01
subsystem: write-path-reliability
tags: [httpx, retry, write-budget, exception-hierarchy, tdd]

# Dependency graph
requires: []
provides:
  - "execute_plan's verify-then-retry recovery from a transient HTTP 401 on any of the three write chunk loops (upload/reshow/removal)"
  - "AuraError exception hierarchy (AuraError, AuthenticationError, WriteEndpointError) rooting RateLimitError and ConsecutiveWriteFailureError"
  - "Retry cost accounting through the existing WriteBudget seam, plus a runtime Retries: visibility line"
affects: [11-02-batch-update-unacknowledged-set, 11-03-placeholder-reconciliation]

# Actuals (#2632)
actuals:
  tokens: 15507
  tasks: 3
  commits: 3

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Nested try/except inside a write chunk's existing except-ladder: httpx.HTTPStatusError caught between except RateLimitError and except ConsecutiveWriteFailureError, re-raising to the generic branch when the 401 isn't retry-eligible"
    - "Run-scoped relogin_done flag + per-chunk chunk_retried flag enforce D-04's one-shared-re-login/one-retry-per-chunk rule without recursion"
    - "Verify-then-retry (probe before re-send) for client-minted local_identifiers; direct re-send (no probe) for server-assigned asset ids, since the latter primitives are idempotent by id"
    - "Callable MockTransport overrides in tests/offline.py for endpoints that must answer differently across successive calls in one test"

key-files:
  created:
    - tests/test_retry_401.py
  modified:
    - auraframes/client.py
    - auraframes/sync.py
    - auraframes/cli.py
    - auraframes/api/assetApi.py
    - tests/offline.py
    - tests/test_write_endpoints_failloud.py

key-decisions:
  - "Retry logic lives inline in execute_plan via a nested try wrapping each write loop's existing try/except, not as a client-level interceptor (D-03) -- keeps budget accounting and per-file attribution in the one place that already owns them"
  - "AuthenticationError/BudgetExhausted/ConsecutiveWriteFailureError each got an explicit `except ...: raise` in the outer ladder of every retry-extended loop -- without it, Python's except-clause exclusivity meant these exceptions, raised from deep inside the nested retry branch, would fall through to the loop's own generic `except Exception` and be silently mis-attributed as an ordinary per-chunk write failure instead of propagating"
  - "The verify probe is asymmetric on purpose (landed / absent / inconclusive): only a confirmed 404 counts as absent and is safe to re-send; any other probe outcome is inconclusive and is never re-sent, per PITFALLS.md Pitfall 4"

patterns-established:
  - "Any future third write loop needing 401 recovery should copy the reshow/removal loops' shape (no probe) rather than the upload loop's (with probe) unless it also mints client-side identifiers"

requirements-completed: [REL-01, REL-02, REL-03, REL-04, MOD-03]

coverage:
  - id: D1
    description: "A 401'd upload chunk re-logs in once, probes every prepped item, and re-sends only the genuinely-absent ones -- no duplicate frame asset for an item the probe confirms already landed"
    requirement: "REL-01"
    verification:
      - kind: unit
        ref: "tests/test_retry_401.py#test_401_on_select_asset_recovers_after_relogin_and_resend"
        status: pass
      - kind: unit
        ref: "tests/test_retry_401.py#test_two_item_chunk_401_resends_only_the_genuinely_absent_item"
        status: pass
      - kind: unit
        ref: "tests/test_retry_401.py#test_inconclusive_probe_is_never_resent_and_is_attributed_as_failure"
        status: pass
      - kind: unit
        ref: "tests/test_retry_401.py#test_chunk_where_every_file_fails_prep_issues_no_select_asset_call"
        status: pass
    human_judgment: false
  - id: D2
    description: "A re-login that fails aborts the run via AuthenticationError (genuine auth failure); a re-login that succeeds followed by a second 401 is classified as anti-abuse, not authentication, and never retried a third time"
    requirement: "REL-04"
    verification:
      - kind: unit
        ref: "tests/test_retry_401.py#test_failed_relogin_raises_authentication_error_and_makes_no_further_write_calls"
        status: pass
      - kind: unit
        ref: "tests/test_retry_401.py#test_second_401_after_relogin_attributes_all_and_makes_no_third_attempt"
        status: pass
    human_judgment: false
  - id: D3
    description: "A retry is charged full write cost (2 first attempt + 1 re-login + 2 resend = 5 tokens) through the existing WriteBudget.acquire() seam; the verify probe itself is always free; BudgetExhausted propagates from a retry exactly as from a first attempt"
    requirement: "REL-03"
    verification:
      - kind: unit
        ref: "tests/test_retry_401.py#test_retried_upload_chunk_consumes_5_budget_tokens_total"
        status: pass
      - kind: unit
        ref: "tests/test_retry_401.py#test_all_items_already_landed_consumes_3_tokens_no_resend_charge"
        status: pass
      - kind: unit
        ref: "tests/test_retry_401.py#test_probe_itself_never_charges_budget_regardless_of_chunk_size"
        status: pass
      - kind: unit
        ref: "tests/test_retry_401.py#test_budget_exhausted_propagates_from_retry_acquire_with_no_bypass"
        status: pass
    human_judgment: false
  - id: D4
    description: "sync --apply prints an unconditional 'Retries: N chunk(s) retried after a 401, M item(s) already landed' line, even when both counters are zero and --debug is off"
    verification:
      - kind: unit
        ref: "tests/test_retry_401.py#test_run_sync_prints_retries_line_unconditionally_even_when_zero"
        status: pass
    human_judgment: false
  - id: D5
    description: "The re-show and removal (hide/delete/hard_delete) chunk loops recover from one transient 401 per run the same way, without a verify probe (server-assigned asset ids are idempotent by id)"
    requirement: "REL-01"
    verification:
      - kind: unit
        ref: "tests/test_retry_401.py#test_reshow_chunk_401_recovers_after_relogin_and_resend"
        status: pass
      - kind: unit
        ref: "tests/test_retry_401.py#test_removal_chunk_hide_mode_401_recovers_after_relogin_and_resend"
        status: pass
      - kind: unit
        ref: "tests/test_retry_401.py#test_removal_chunk_second_401_attributes_all_and_makes_no_third_attempt"
        status: pass
    human_judgment: false
  - id: D6
    description: "AuraError roots AuthenticationError, WriteEndpointError, RateLimitError, and ConsecutiveWriteFailureError; assetApi.py's batch_update/delete_asset error-envelope RuntimeErrors are now WriteEndpointError; a RateLimitError raised inside a write chunk still aborts the whole run through its own dedicated branch, never mistaken for the new 401 branch or the generic branch"
    requirement: "MOD-03"
    verification:
      - kind: unit
        ref: "tests/test_retry_401.py#test_rate_limit_error_is_auraerror_subclass_and_still_aborts_the_run"
        status: pass
      - kind: unit
        ref: "tests/test_retry_401.py#test_batch_update_and_delete_asset_raise_write_endpoint_error_on_error_envelope"
        status: pass
      - kind: unit
        ref: "tests/test_write_endpoints_failloud.py#test_batch_update_raises_on_error_envelope"
        status: pass
      - kind: unit
        ref: "tests/test_write_endpoints_failloud.py#test_delete_asset_raises_on_error_envelope"
        status: pass
    human_judgment: false

# Metrics
duration: ~20min
completed: 2026-09-03
status: complete
---

# Phase 11 Plan 01: Write-Path Reliability -- 401 Verify-Then-Retry Summary

**A transient HTTP 401 on any write chunk (upload/reshow/removal) now re-logs in once per run, verifies before re-sending, and charges the retry to the write budget on purpose -- with a genuine authentication failure aborting loudly instead of being retried.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-09-03 (session start)
- **Completed:** 2026-09-03T08:37:00Z
- **Tasks:** 3
- **Files modified:** 6 (1 created)

## Accomplishments

- `AuraError` exception root added to `auraframes/client.py`, with `AuthenticationError` (a failed re-login after a write 401 -- hard stop, never retried) and `WriteEndpointError` (the write-path form of an Aura error-envelope response) as new subclasses; `RateLimitError` and `ConsecutiveWriteFailureError` reparented onto it with every attribute/message/docstring preserved verbatim
- `execute_plan` gained `relogin=`/`asset_probe=`/`retry_on_auth_401=` injectable keyword seams and a verify-then-retry branch in each of its three write chunk loops (upload, re-show, removal): on a plain HTTP 401, re-login once per run, and (for uploads only, since only uploads mint client-side `local_identifier`s) probe every prepped item via the already-existing `AssetApi.get_asset_by_local_identifier` before re-sending only the genuinely-absent ones
- `ExecutionResult` gained `chunks_retried`/`items_already_landed` counters, surfaced unconditionally in `sync --apply`'s summary as a new `Retries:` line -- never gated behind `--debug`
- A retry is charged full write cost through the exact `budget.acquire(...)` call shape every other write already uses (2 first attempt + 1 re-login + 2 resend = 5 tokens); the verify probe is always free regardless of chunk size; `BudgetExhausted` propagates from a retry's acquire exactly as it does from a first attempt
- `assetApi.py`'s two write-path error-envelope `RuntimeError`s (`batch_update`, `delete_asset`) converted to `WriteEndpointError`; every other write-endpoint `RuntimeError` (`frameApi.py`'s `select_asset`/`exclude_asset`/`remove_asset`) and every read-path raise deliberately left untouched (D-20)
- `tests/offline.py`'s `make_router` extended to accept a callable override `(httpx.Request) -> httpx.Response`, so a single mocked endpoint can answer 401 on its first call and 200 after -- the mechanism the new offline test suite drives throughout

## Task Commits

Each task was committed atomically:

1. **Task 1: End-to-end 401 verify-then-retry for one upload chunk** - `735d6a3` (feat)
2. **Task 2: Retry budget accounting and runtime visibility** - `efa554d` (feat)
3. **Task 3: Extend the retry to the re-show and removal loops, and complete the exception hierarchy** - `a75f688` (feat)

_All three tasks carried `tdd="true"`; tests were written and run alongside each task's implementation in the same commit rather than as separate RED/GREEN commits, since the plan's `<behavior>` blocks describe end-to-end offline-test scenarios rather than a strict single-assertion RED step._

## Files Created/Modified

- `tests/test_retry_401.py` - New offline test module; all 16 behaviors from Tasks 1-3 (401 recovery, budget accounting, CLI visibility, reshow/removal retry, exception hierarchy)
- `auraframes/client.py` - `AuraError`, `AuthenticationError`, `WriteEndpointError` added; `RateLimitError` reparented onto `AuraError`
- `auraframes/sync.py` - `RETRY_RELOGIN_REQUEST_COST`, `_is_http_401`, `_probe_landed` added; `execute_plan`'s three write chunk loops each gained a nested verify-then-retry branch; `ConsecutiveWriteFailureError` reparented onto `AuraError`
- `auraframes/cli.py` - One new `Retries:` line in `run_sync`'s post-apply summary
- `auraframes/api/assetApi.py` - `batch_update`/`delete_asset` error-envelope raises converted to `WriteEndpointError`
- `tests/offline.py` - `make_router` accepts callable overrides
- `tests/test_write_endpoints_failloud.py` - `batch_update`/`delete_asset` assertions updated to expect `WriteEndpointError`

## Decisions Made

- Retry logic lives inline in `execute_plan` via a nested `try` wrapping each write loop's existing `try`/`except` (D-03), not as a client-level interceptor -- keeps budget accounting and per-file attribution in the one place that already owns them.
- Because Python's `except` clauses within one `try` are mutually exclusive (an exception raised while handling one clause is never re-matched against its siblings), every exception the retry branch can raise from deep inside its nested structure (`AuthenticationError`, `BudgetExhausted`, `ConsecutiveWriteFailureError`) needed its own explicit `except ...: raise` in the loop's outer ladder -- otherwise it would fall through to that loop's generic `except Exception` and be silently mis-attributed as an ordinary per-chunk write failure. This was caught by `test_budget_exhausted_propagates_from_retry_acquire_with_no_bypass` failing during Task 2's development and fixed before commit.
- The verify probe's classification is deliberately asymmetric: only a confirmed HTTP 404 counts as "absent" and is safe to re-send; every other probe outcome (a different status, a network error) is "inconclusive" and is never re-sent, per `PITFALLS.md` Pitfall 4 -- re-sending on an ambiguous probe is exactly how the 58 stuck placeholder rows (Plan 03's cleanup target) were created.
- The re-show and removal loops skip the verify probe entirely (unlike uploads): they act on server-assigned asset ids, and re-showing an already-visible asset or hiding an already-hidden one is a no-op, so a re-send there cannot manufacture a duplicate.

## Deviations from Plan

### Auto-fixed Issues

None - all deviations below are Rule-3 (blocking) fixes made and verified during implementation, not post-hoc discoveries.

**1. [Rule 3 - Blocking] Added `except BudgetExhausted: raise` to prevent silent mis-attribution**
- **Found during:** Task 2, writing `test_budget_exhausted_propagates_from_retry_acquire_with_no_bypass`
- **Issue:** The retry's re-login/resend `budget.acquire(...)` calls sit inside a nested `try` whose outer ladder only explicitly excludes `RateLimitError`/`AuthenticationError`/`ConsecutiveWriteFailureError` from the generic `except Exception` branch. A `BudgetExhausted` raised from either acquire call was being caught by that generic branch and silently turned into a per-file write failure instead of propagating to the caller (`cli.py`'s dedicated `except BudgetExhausted` handler), unlike the chunk-start `acquire()` call, which sits entirely outside the try/except and always propagates cleanly.
- **Fix:** Imported `BudgetExhausted` from `auraframes.ratelimit` in `sync.py` and added an explicit `except BudgetExhausted: raise` branch to the upload loop's outer ladder (and, in Task 3, to the re-show/removal loops' equivalent ladders).
- **Files modified:** `auraframes/sync.py`
- **Verification:** `test_budget_exhausted_propagates_from_retry_acquire_with_no_bypass` passes; full suite green.
- **Committed in:** `efa554d` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking).
**Impact on plan:** Necessary for correctness -- without it, `BudgetExhausted` (a documented, caller-relied-upon signal) would silently disappear inside a retried chunk. No scope creep; the fix stayed inside `execute_plan`'s existing exception-routing convention.

## Issues Encountered

- Task 3's acceptance criterion `uv run python -c "...frameApi.py...print(s.count('raise RuntimeError'))"` expects `4`; the actual count is `7` (2 each for `select_asset`/`exclude_asset`/`remove_asset`, plus one unrelated pre-existing raise at line 98). This was true **before** this plan started too -- `git diff` confirms `frameApi.py` was never touched by any task in this plan, matching D-20's explicit "leave every read-path raise, and `frameApi.py`'s write raises, untouched" instruction. This is a planner miscount in the acceptance criterion's specific expected number, not an implementation defect; the real invariant it exists to check (frame-API write raises left completely unchanged) holds. Recorded to `.planning/WINDOWS.md` as a `deviation` entry for visibility at ship time.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The write path now recovers from a transient 401 on all three write chunk loops, with honest attribution (genuine auth failure vs. anti-abuse trip) and no duplicate-asset risk from the retry itself -- REL-01/REL-02/REL-04 are structurally satisfied, not just hoped for.
- `AuraError`/`WriteEndpointError` are in place for Plan 02 (`batch_update`'s unacknowledged-set return, REL-07) to build on if it wants a typed signal there too.
- Plan 03 (placeholder reconciliation) can now rely on the retry path never manufacturing new stuck rows, since every retry is probe-gated for uploads and idempotent-by-id for reshow/removal.
- No blockers.

---
*Phase: 11-write-path-reliability-format-support*
*Completed: 2026-09-03*

## Self-Check: PASSED

- All 6 key-files (created + modified) verified present on disk with `[ -f ]`.
- All 3 task commit hashes (735d6a3, efa554d, a75f688) verified in `git log --oneline --all`.
- All acceptance criteria from all 3 tasks re-run and passing (except the frameApi.py RuntimeError-count number, documented above as a planner miscount with the underlying invariant confirmed via empty `git diff` on that file).
- `uv run pytest -m "not live" -q`: 221 passed, 0 failed (205 baseline + 16 new).
