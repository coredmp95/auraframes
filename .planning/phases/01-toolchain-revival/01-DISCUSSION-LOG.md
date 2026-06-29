# Phase 1: Toolchain Revival - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-29
**Phase:** 1-Toolchain Revival
**Areas discussed:** Dependency pinning, Migration scope, AllOptional approach, Verify imports

---

## Dependency pinning

| Option | Description | Selected |
|--------|-------------|----------|
| Loose floors + commit uv.lock | Minimum versions (`>=`), let `uv` resolve latest that builds on 3.14; commit `uv.lock` for reproducibility | ✓ |
| Pin exact latest + lock | Exact `==` pins chosen now plus `uv.lock`; max determinism, stale faster | |
| Loose floors, no lockfile | Floors only, no committed lock; leanest but non-reproducible | |

**User's choice:** Loose floors + commit uv.lock
**Notes:** Balances "fresh enough to build on 3.14" with reproducibility — fits the pragmatic revival constraint.

---

## Migration scope

| Option | Description | Selected |
|--------|-------------|----------|
| Import-clean: all modules | Fix everything needed so every module imports — models layer AND `io.py`'s top-level `pydantic_encoder` import; defer runtime-only `.dict()` in `api/` to Phase 2 | ✓ |
| Models layer only (literal criteria) | Fix only `auraframes/models/*`; leave `io.py` broken since it's "utils" | |
| Full v2 sweep now | Migrate every v1 call site this phase including runtime `.dict()`; more churn | |

**User's choice:** Import-clean: all modules
**Notes:** Whole package importable now is the clean Phase 1 boundary; runtime-only paths wait for Phase 2 when they're exercised.

---

## AllOptional approach

| Option | Description | Selected |
|--------|-------------|----------|
| Idiomatic v2 factory | Replace metaclass with a v2-native partial-model factory (helper or `create_model`); no private internals; identical public surface | ✓ |
| Port the metaclass to v2 | Keep metaclass shape, retarget at v2 internals; smallest change but still fragile | |
| You decide during planning | Lock only the requirement (all fields optional, same interface), defer mechanism | |

**User's choice:** Idiomatic v2 factory
**Notes:** Avoids the private-internal fragility CONCERNS.md flagged; durable across future pydantic bumps.

---

## Verify imports

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal pytest smoke test | Committed `tests/test_imports.py` importing all modules + asserting a `FramePartial` field is Optional; run via `uv run pytest`; adds `pytest` dev dep | ✓ |
| Committed smoke script | Standalone `scripts/smoke_import.py` via `uv run`, no pytest | |
| Manual one-liner only | `uv run python -c 'import auraframes'`, nothing committed | |

**User's choice:** Minimal pytest smoke test
**Notes:** Establishes a re-runnable test harness for the live-API verification in Phases 2–3.

---

## Claude's Discretion

- Exact resolved dependency versions within the floors (`uv` decides).
- Precise v2 partial-model factory mechanism (helper vs. `create_model`), provided it avoids private internals and preserves the public surface.
- `requires-python` constraint / `.python-version` file / `[build-system]` metadata — standard `uv` conventions (target Python 3.14).
- Exact v2 replacement for `pydantic_encoder` in `io.py`.

## Deferred Ideas

- Runtime `.dict()` → `.model_dump()` migration in `api/assetApi.py` and `api/frameApi.py` — Phase 2.
- `datetime.utcnow()` deprecation in `utils/dt.py:11` — touch only if it surfaces in Phase 2/3.
- Async HTTP migration, AWS pool-ID config, typed exception hierarchy, `main.py` example — out of scope for this milestone (REQUIREMENTS.md v2 / Out of Scope).
