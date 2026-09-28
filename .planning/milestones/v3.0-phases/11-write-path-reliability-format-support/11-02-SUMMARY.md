---
phase: 11-write-path-reliability-format-support
plan: 02
subsystem: write-path-reliability
tags: [pydantic, batch-update, error-attribution, tdd]

# Dependency graph
requires:
  - phase: 11-01
    provides: "AuraError/WriteEndpointError exception hierarchy in auraframes/client.py"
provides:
  - "BatchUpdateResult (ids, successes, unacknowledged) as batch_update's named return type"
  - "Aura.upload_image fails loud (WriteEndpointError) instead of silently discarding batch_update's result"
  - "test_read_03_pagination asserting the cursor loop's own correctness instead of a server-inconsistent equality"
affects: [11-03-placeholder-reconciliation, 11-05-live-verification]

# Actuals (#2632)
actuals:
  tokens: 8068
  tasks: 3
  commits: 4

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "typing.NamedTuple return type (BatchUpdateResult) so a new named field is addable to a return value without breaking positional unpacking at every existing call site"
    - "Strict outbound / tolerant inbound parsing split at one API boundary: AssetPartialId's cross-field validator stays untouched for outbound construction; a per-entry try/except ValidationError on the inbound successes array skips one malformed row without aborting the whole batch"
    - "pydantic v2 ValidationError.errors(include_url=False, include_input=False) to redact raw input values before logging a validation failure on untrusted server-supplied content"

key-files:
  created:
    - tests/test_batch_update_contract.py
  modified:
    - auraframes/api/assetApi.py
    - auraframes/aura.py
    - auraframes/sync.py
    - tests/test_asset_partial.py
    - tests/test_read_path.py
    - tests/test_execute_plan.py
    - tests/test_execute_plan_budget_geo.py
    - tests/test_write_throttling.py
    - tests/test_write_endpoints_failloud.py

key-decisions:
  - "BatchUpdateResult is a typing.NamedTuple, not a dataclass or a plain tuple -- it is reachable by name (result.unacknowledged) for new callers while staying positionally unpackable, which matters less here since every call site was migrated in the same commit, but keeps the type maximally compatible with any future caller"
  - "unacknowledged is returned, never raised on -- batch_update's own docstring already documented a partial successes list as the endpoint's NORMAL batch signal before this plan; raising here would abort chunks that are behaving exactly as designed"
  - "The outbound AssetPartialId validator was verified (by test), not rewritten -- REL-06's flagged planner assumption (validator already fires under pydantic v2) held, so REL-06 closes via a proving test plus the new inbound tolerance rather than any change to auraframes/models/asset.py"
  - "test_read_03_pagination's replacement assertions describe the client's own responsibility (page-fetch delta, id uniqueness, 0 < drained <= total), not the server's internal count consistency -- the old assertion (drained == total) was falsified by the server itself (171 vs 149 measured live 2026-08-25), not by a client bug"

patterns-established:
  - "Any future API-boundary parser that must tolerate one malformed entry among many should copy the per-entry try/except ValidationError + logger.warning(keys-only) shape from batch_update's successes loop, not a whole-response try/except"

requirements-completed: [REL-06, REL-07, REL-08]

coverage:
  - id: D1
    description: "AssetApi.batch_update returns BatchUpdateResult(ids, successes, unacknowledged) -- the sent-but-unacknowledged local_identifier set is a named, addressable part of the result for every caller"
    requirement: "REL-07"
    verification:
      - kind: unit
        ref: "tests/test_batch_update_contract.py#test_unacknowledged_is_empty_when_every_sent_id_is_acknowledged"
        status: pass
      - kind: unit
        ref: "tests/test_batch_update_contract.py#test_unacknowledged_preserves_sent_order_for_a_partial_acknowledgement"
        status: pass
      - kind: unit
        ref: "tests/test_batch_update_contract.py#test_absent_successes_key_yields_the_full_sent_set_unacknowledged_without_raising"
        status: pass
      - kind: unit
        ref: "tests/test_batch_update_contract.py#test_empty_assets_list_yields_three_empty_collections_and_one_request"
        status: pass
    human_judgment: false
  - id: D2
    description: "A malformed successes entry (neither id nor local_identifier) is skipped and logged (keys + redacted validation error only, never raw values) instead of raising -- one junk row in a batch response cannot cost the whole chunk's per-file attribution"
    requirement: "REL-06"
    verification:
      - kind: unit
        ref: "tests/test_batch_update_contract.py#test_malformed_successes_entry_is_skipped_without_raising"
        status: pass
    human_judgment: false
  - id: D3
    description: "Aura.upload_image binds batch_update's result and raises WriteEndpointError naming the frame id and unacknowledged local_identifier(s) instead of silently discarding the return value"
    requirement: "REL-07"
    verification:
      - kind: unit
        ref: "auraframes/aura.py::Aura.upload_image (raise path proven by inspect.getsource containment check in the plan's own acceptance criteria; no offline S3/SQS harness exists to drive upload_image end-to-end in this plan)"
        status: pass
    human_judgment: true
    rationale: "upload_image constructs a real S3Client/SQSClient internally with no injectable seam (unlike execute_plan), so there is no offline test harness in this repo that can drive it end-to-end to prove the raise fires from a real call. Coverage here is: (1) a static source-inspection check that both 'unacknowledged' and 'WriteEndpointError' appear in the method body, verified in this plan's acceptance criteria, and (2) BatchUpdateResult's own unit-tested unacknowledged-computation logic (D1). Wiring the two together end-to-end was not independently exercised."
  - id: D4
    description: "AssetPartialId's outbound cross-field validator (unmodified by this plan) is proven by test to fire on both no-arg and keyword-expanded construction; single-field construction and to_request_format()'s wire shape are proven unchanged"
    requirement: "REL-06"
    verification:
      - kind: unit
        ref: "tests/test_asset_partial.py#test_asset_partial_id_no_args_raises_validation_error"
        status: pass
      - kind: unit
        ref: "tests/test_asset_partial.py#test_asset_partial_id_keyword_expanded_all_none_raises_validation_error"
        status: pass
      - kind: unit
        ref: "tests/test_asset_partial.py#test_asset_partial_id_single_field_constructions_succeed"
        status: pass
      - kind: unit
        ref: "tests/test_asset_partial.py#test_asset_partial_id_to_request_format_unchanged_by_this_phase"
        status: pass
      - kind: unit
        ref: "tests/test_batch_update_contract.py#test_asset_partial_id_construction_with_neither_field_raises"
        status: pass
    human_judgment: false
  - id: D5
    description: "test_read_03_pagination asserts what the client controls (more than one page fetched, no duplicate asset id, 0 < drained <= total) instead of an equality the server itself does not honour; no percentage tolerance, float comparison, or slack constant"
    requirement: "REL-08"
    verification:
      - kind: unit
        ref: "tests/test_read_path.py -- collection-only structural checks (4 tests collected, live-marker preserved, no 'len(assets)==total' substring)"
        status: pass
    human_judgment: true
    rationale: "test_read_03_pagination is @pytest.mark.live and requires a real Aura account with >=2 assets on the first frame; it was not executed live in this plan (deferred to plan 11-05's live verification task per the plan's own acceptance criteria). Coverage here is the offline structural proof (assertion shapes present, old equality absent, marker/skip preserved) plus 'not live' suite green; the live run itself needs a human-available live account and is explicitly out of scope for this plan."

# Metrics
duration: ~25min
completed: 2026-09-03
status: complete
---

# Phase 11 Plan 02: Write-Path Reliability -- batch_update's Unacknowledged Set Summary

**`AssetApi.batch_update` now returns a named `BatchUpdateResult(ids, successes, unacknowledged)`, tolerates one malformed inbound entry without raising, `Aura.upload_image` fails loud on a dropped id instead of discarding the result, and the suite's one server-inconsistent test now asserts the cursor loop's own correctness.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-09-03T08:30:00Z (session start)
- **Completed:** 2026-09-03T08:54:19Z
- **Tasks:** 3
- **Files modified:** 9 (1 created)

## Accomplishments

- `BatchUpdateResult` (`typing.NamedTuple`: `ids`, `successes`, `unacknowledged`) added at module scope in `auraframes/api/assetApi.py`; `batch_update`'s return type changed from a bare 2-tuple to this named result, with `unacknowledged` computed as the sent local_identifiers (in sent order) that never appear among the parsed `successes` entries
- Inbound `successes` parsing made tolerant: each entry is constructed inside a `try`/`except ValidationError`, with a malformed entry skipped and logged (keys + a `include_input=False`-redacted validation error, never raw values -- T-11-06) rather than crashing the whole chunk; the outbound `AssetPartialId` validator was verified by test, not modified (`auraframes/models/asset.py` untouched)
- Every destructuring call site migrated in the same commits: `sync.py`'s first-attempt and 11-01 retry-branch `batch_update` calls, and every `batch_update` fake across `tests/test_execute_plan.py`, `tests/test_execute_plan_budget_geo.py`, `tests/test_write_throttling.py`, `tests/test_write_endpoints_failloud.py`
- `Aura.upload_image` now binds `batch_update`'s result and raises `WriteEndpointError` (naming the frame id and the dropped local_identifier(s)) when `unacknowledged` is non-empty, closing REL-07 for every caller, not just `execute_plan`
- Four new tests in `tests/test_asset_partial.py` prove `AssetPartialId`'s outbound validator fires on both no-arg and keyword-expanded construction, and that single-field construction / `to_request_format()`'s wire shape are unchanged -- closing REL-06 by proof rather than assumption
- `test_read_03_pagination` rewritten to assert three things the client controls (more than one `/assets.json` page fetched via a before/after `aura._client.history` delta, no duplicate asset id across pages, `0 < len(assets) <= total`) instead of a drained-count-equals-`total` equality that the server itself does not honour (171 vs 149 measured live on 2026-08-25)

## Task Commits

Each task was committed atomically:

1. **Task 1: batch_update returns the unacknowledged set and tolerates a malformed inbound entry** - `ec7a02c` (feat)
2. **Task 2: upload_image consumes the unacknowledged signal; prove the outbound validator** - `e8304c1` (feat)
3. **Task 3: test_read_03_pagination asserts the cursor loop's own correctness** - `6781467` (fix)

**Deviation fix:** `7188d66` (fix) -- redact `input_value` from the malformed-entry `logger.warning` (T-11-06), applied after Task 1's commit once the leak was discovered during self-verification.

**Plan metadata:** commit created below.

_All tasks carried `tdd="true"` except Task 3 (`type="auto"`, a pure test-file rewrite with no new implementation behavior); tests were written and run alongside each task's implementation in the same commit._

## Files Created/Modified

- `tests/test_batch_update_contract.py` - New offline module; all 6 behaviors from Task 1 (unacknowledged computation, order preservation, absent-key tolerance, empty-list handling, malformed-entry tolerance, outbound-strictness proof)
- `auraframes/api/assetApi.py` - `BatchUpdateResult` NamedTuple added; `batch_update` returns it; inbound `successes` parsing made tolerant with a redacted warning on a malformed entry
- `auraframes/aura.py` - `upload_image` binds `batch_update`'s result and raises `WriteEndpointError` on a non-empty `unacknowledged`; gained a docstring
- `auraframes/sync.py` - Both `batch_update` destructures (first attempt, 11-01 retry branch) updated to read `.successes` from the new result; surrounding attribution logic unchanged (D-18)
- `tests/test_asset_partial.py` - Four new proving tests for `AssetPartialId`'s outbound validator + `to_request_format()`; header docstring records the REL-06 finding
- `tests/test_read_path.py` - `test_read_03_pagination` assertions replaced; module's other three tests untouched
- `tests/test_execute_plan.py`, `tests/test_execute_plan_budget_geo.py`, `tests/test_write_throttling.py`, `tests/test_write_endpoints_failloud.py` - Every `batch_update` fake/destructure migrated to `BatchUpdateResult`

## Decisions Made

- `BatchUpdateResult` is a `typing.NamedTuple`, not a dataclass -- reachable by name while staying positionally unpackable, matching the plan's explicit design instruction.
- `unacknowledged` is returned, never raised on: a partial `successes` list was already documented as this endpoint's normal batch signal before this plan; raising would abort chunks behaving exactly as designed.
- REL-06's flagged planner assumption (`AssetPartialId`'s validator already fires under pydantic v2) was independently reverified in this plan via `AssetPartialId()` and keyword-expanded construction tests, both raising as expected -- `auraframes/models/asset.py` was not touched.
- `test_read_03_pagination`'s live execution is explicitly deferred to plan 11-05 per the plan's own acceptance criteria; this plan only proves the assertion shapes are correct offline (structure, marker, skip behavior).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality / security] Malformed-entry warning leaked raw entry values via pydantic's default ValidationError string representation**
- **Found during:** Self-verification after Task 1's commit, while checking the threat model's T-11-06 mitigation ("never the entry's raw values, which carry user_id")
- **Issue:** `logger.warning(f"... {e}")` where `e` is a `pydantic.ValidationError` embeds each error's raw `input_value` in its default `str()`/`repr()` -- confirmed by constructing `AssetPartialId(**{'user_id': 'secret-user-12345'})` and observing the whole dict, including `user_id`, appear in `str(e)`. This directly contradicted the threat model's own stated mitigation for T-11-06 (medium severity, information disclosure), which the original implementation only satisfied in the docstring/comment, not in the actual log call.
- **Fix:** Replaced `{e}` with `e.errors(include_url=False, include_input=False)`, pydantic v2's structured, input-redacted error list -- keys and error type/message are logged, input values never are.
- **Files modified:** `auraframes/api/assetApi.py`
- **Verification:** `uv run pytest -m "not live" -q` (231 passed, 0 failed) re-run after the fix; manual confirmation that `include_input=False` strips `input_value` from the constructed error list.
- **Committed in:** `7188d66`

---

**Total deviations:** 1 auto-fixed (1 Rule 2 -- security/correctness).
**Impact on plan:** Necessary for correctness against the plan's own threat model. No scope creep -- the fix stayed inside the single `except ValidationError` block Task 1 introduced.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `BatchUpdateResult` is the one true shape for `batch_update`'s return across the whole repo -- no bare 2-tuple return remains anywhere in `auraframes/` or `tests/`.
- `Aura.upload_image` and `execute_plan` (both attempts) now share the same `unacknowledged` computation from `batch_update` itself -- a single source of truth for "was this id acknowledged."
- `test_read_03_pagination`'s live execution against a real account is deferred to plan 11-05 as planned; this plan's job (correct offline assertion shapes) is done.
- No blockers for plan 11-03 (placeholder reconciliation) or 11-04 (format support).

---
*Phase: 11-write-path-reliability-format-support*
*Completed: 2026-09-03*

## Self-Check: PASSED

- All 9 key-files (created + modified) verified present on disk with `[ -f ]`.
- All 4 commit hashes (`ec7a02c`, `e8304c1`, `6781467`, `7188d66`) verified in `git log --oneline --all`.
- All acceptance criteria from all 3 tasks re-run and passing, including the deviation fix's own re-verification.
- `uv run pytest -m "not live" -q`: 231 passed, 0 failed, 4 deselected (221 baseline from 11-01 + 10 new: 6 in test_batch_update_contract.py, 4 in test_asset_partial.py).
