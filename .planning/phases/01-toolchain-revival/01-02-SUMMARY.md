---
phase: 01-toolchain-revival
plan: 02
subsystem: testing
tags: [pydantic, pydantic-v2, create_model, field_validator, pytest, model-migration]

# Dependency graph
requires:
  - phase: 01-toolchain-revival (plan 01-01)
    provides: uv-managed pyproject.toml + uv.lock on Python 3.14 with pydantic 2.13.4 and pytest 9.1.1
provides:
  - pydantic v2-clean model layer (entire auraframes package imports without error)
  - make_partial(model, name) factory replacing the AllOptional metaclass (D-06/D-07)
  - model_dump-based JSON serialization in utils/io.py (D-04)
  - committed import smoke test (tests/test_imports.py) asserting import-cleanliness + FramePartial optionality (D-08)
affects: [phase-02-live-read-verification, phase-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Partial-model factory via create_model(name, __base__=model) instead of metaclass subclassing"
    - "JSON serialization via a default= callable using model_dump(mode=json), preserving single + list branches"
    - "Parametrized pytest import smoke test as a continuously-verifiable migration guard"

key-files:
  created:
    - tests/test_imports.py
  modified:
    - auraframes/models/meta.py
    - auraframes/utils/io.py
    - auraframes/models/frame.py
    - auraframes/models/asset.py

key-decisions:
  - "Replace AllOptional metaclass with public make_partial() factory (no pydantic private internals, D-06)"
  - "Add = None to all Optional base-model fields in Frame/Asset to restore v1 implicit-None semantics (Q#1)"
  - "Faithful straight-port of AssetPartialId validator to @field_validator, preserving the latent field-ordering no-op (Q#2)"

patterns-established:
  - "Pattern: make_partial(model, name) for any future PATCH-style partial model"
  - "Pattern: write_model serializes via _pydantic_default callable, not pydantic_encoder"

requirements-completed: [ENV-03]

# Metrics
duration: 34min
completed: 2026-06-29
---

# Phase 01 Plan 02: Pydantic v1 to v2 Model-Layer Migration Summary

**Migrated the entire `auraframes` model layer to pydantic v2 — AllOptional metaclass replaced by a `make_partial` create_model factory, `pydantic_encoder` replaced by a `model_dump(mode=json)` serializer, `@validator` ported to `@field_validator` — with a committed pytest import smoke test guarding it.**

## Performance

- **Duration:** 34 min
- **Started:** 2026-06-29T10:02:00Z
- **Completed:** 2026-06-29T10:36:18Z
- **Tasks:** 3
- **Files modified:** 5 (1 created, 4 modified)

## Accomplishments
- The whole `auraframes` package now imports cleanly under pydantic 2.13.4 (ROADMAP SC#3) — three import-time v1 breakers eliminated.
- `FramePartial` remains all-optional and instance-isinstance-of-`Frame`, built via the `make_partial` factory; `is_portrait`/`get_frame_type` methods survive (ROADMAP SC#4 / D-07).
- Base-model `Optional[...]` fields in `Frame` and `Asset` defaulted to `None`, restoring v1 implicit-None semantics and preventing a guaranteed Phase-2 instantiation failure (Q#1).
- Committed `tests/test_imports.py` (9 tests) makes import-cleanliness and partial-optionality continuously verifiable for Phases 2-3 (D-08).

## Task Commits

Each task was committed atomically:

1. **Task 1: Replace v2-removed internals (meta.py factory + io.py serialization)** - `2c0d080` (refactor)
2. **Task 2: Migrate frame.py and asset.py to pydantic v2** - `5ac96b7` (feat)
3. **Task 3: Add committed import smoke test** - `d590c7b` (test)

## Files Created/Modified
- `auraframes/models/meta.py` - Removed `AllOptional`/`pydantic.main.ModelMetaclass`; added public `make_partial(model, name)` using `create_model(name, __base__=model, ...)`.
- `auraframes/utils/io.py` - Removed `pydantic.json.pydantic_encoder`; added `_pydantic_default` callable using `model_dump(mode="json")`, passed as `default=` to `json.dump` (preserves single + `list[BaseModel]` branches).
- `auraframes/models/frame.py` - `FramePartial = make_partial(Frame, "FramePartial")`; all `Optional` fields defaulted to `None`.
- `auraframes/models/asset.py` - `AssetPartialId` uses `@field_validator("id")` + `@classmethod` + `ValidationInfo`; all `Asset` `Optional` fields defaulted to `None`.
- `tests/test_imports.py` - Parametrized import smoke test + FramePartial all-optional assertion.

## Decisions Made
- Used the public `create_model(__base__=model)` factory rather than subclassing pydantic internals (D-06). Iterating `model.model_fields` (not `__annotations__`) sidesteps the `from __future__ import annotations` string-annotation fragility that broke the old metaclass.
- Added `= None` to all `Optional` base-model fields (Q#1). This is not a D-05 violation — D-05 locks the runtime `.dict()` call sites in `api/*` (untouched here), not field declarations. It faithfully restores v1 implicit-None semantics within the two model files already being edited.
- AssetPartialId validator ported faithfully to `@field_validator`, preserving the pre-existing latent field-ordering no-op (Q#2). The `model_validator(mode="after")` correctness fix is deferred to Phase 2.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None. All three task verifications (including the `-W error::DeprecationWarning` check confirming no `PydanticDeprecatedSince20` from the validator) passed on first run; `uv run pytest -q` reports 9 passed.

## Known Stubs
None. No placeholder data, hardcoded empties, or unwired data sources introduced.

## Phase-2 Carryover
1. **D-05:** Runtime `.dict()` → `.model_dump()` migration in `api/assetApi.py` / `api/frameApi.py` (deliberately untouched here).
2. **Q#2:** Optional `AssetPartialId` `@model_validator(mode="after")` correctness fix to make the id-or-local_identifier check actually raise (currently a behavior-preserving no-op on empty input).
3. **Note:** Bare `Any` fields in `Asset` (`burst_id`, `burst_selection_types`, `represents_burst`, `taken_at_granularity`, `video_clip_start`) were left without defaults per the plan's Optional-only scope; if Phase-2 live instantiation requires them optional, add `= None` then.

## Next Phase Readiness
- Model layer is v2-clean and import-verified; ready for Phase 2 live read-path verification (login → list → download).
- The committed smoke test will catch any regression in import-cleanliness or FramePartial optionality during Phase 2/3 work.

## Self-Check: PASSED

All 5 source/test files and the SUMMARY exist on disk; all three task commits (2c0d080, 5ac96b7, d590c7b) present in git history.

---
*Phase: 01-toolchain-revival*
*Completed: 2026-06-29*
