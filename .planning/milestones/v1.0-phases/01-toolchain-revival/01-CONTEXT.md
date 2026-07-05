# Phase 1: Toolchain Revival - Context

**Gathered:** 2026-06-29
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase makes the project **install, build, and import** cleanly on Python 3.14
managed by `uv`, with the pydantic model layer running on **pydantic v2**.

In scope: dependency management migrated to `pyproject.toml` + `uv` (UTF-16
`requirements.txt` removed), all deps resolving/building on Python 3.14, the model
layer migrated to pydantic v2 (preserving `AllOptional` partial-model behaviour), and
the whole `auraframes` package importing without error.

Out of scope: any live-API behaviour (login/list/fetch/download — Phase 2), run docs
and the verification report (Phase 3), and broad refactors beyond what's needed to
install + import.

</domain>

<decisions>
## Implementation Decisions

### Dependency Management & Pinning
- **D-01:** Specify dependencies in `pyproject.toml` with **loose version floors** (`>=`),
  not exact pins — e.g. `pydantic>=2`, `httpx>=0.27`, `boto3>=1.34`, etc. Let `uv`
  resolve the latest versions that build on Python 3.14. (The 2022-era pins —
  `pydantic~=1.10.4`, `httpx==0.23.1`, `pillow~=9.5.0`, `boto3==1.26.38` — mostly will
  not build on 3.14 and must move up.)
- **D-02:** **Commit `uv.lock`** for reproducibility, so a fresh checkout resolves the
  same versions. (Floors give freshness; the lockfile gives determinism — both, by
  design, for a "prove it still works" revival.)
- **D-03:** Delete the UTF-16 `requirements.txt`; `pyproject.toml` + `uv.lock` are the
  sole dependency manifest (ENV-01).

### Migration Scope (this phase)
- **D-04:** Make the **entire `auraframes` package import-clean** under pydantic v2 — not
  just `auraframes/models/*`. This explicitly includes `auraframes/utils/io.py`, whose
  top-level `from pydantic.json import pydantic_encoder` **hard-fails on v2** and must be
  replaced (e.g. `model.model_dump()` + `json.dumps`, or a v2 JSON encoder).
- **D-05:** **Defer runtime-only call sites** that do not execute at import time to Phase
  2, since they can't be exercised until the live-API work. Specifically the `.dict(...)`
  calls inside methods of `auraframes/api/assetApi.py` (~line 21, ~line 97) and
  `auraframes/api/frameApi.py` (~line 90, `frame_partial.dict(exclude_unset=True)`).
  Note: the `@validator` in `auraframes/models/asset.py:118` runs at class-definition
  (import) time and IS in scope here — migrate it to `@field_validator`.

### AllOptional / Partial Models
- **D-06:** Replace the `AllOptional` metaclass (`auraframes/models/meta.py`), which
  subclasses pydantic v1 internals (`pydantic.main.ModelMetaclass`), with an **idiomatic
  pydantic v2 partial-model factory** — no reliance on private internals (so it won't
  silently break on future pydantic bumps). Acceptable mechanisms: a helper that rebuilds
  the model with every field Optional/defaulted, or `pydantic.create_model`.
- **D-07:** Preserve the **public surface** of partials. `FramePartial` (and any other
  `AllOptional`-based partial) must keep the same name, import path, and expose **every
  field as optional** — satisfying success criterion #4. `frame_partial.dict(exclude_unset=True)`
  semantics must remain achievable (its call site migrates in Phase 2 per D-05, but the
  model must support exclude-unset partial serialization).

### Verification
- **D-08:** Add a **minimal committed pytest smoke test** (e.g. `tests/test_imports.py`)
  that (a) imports `auraframes` and every `auraframes/models/*` module without error and
  (b) asserts a `FramePartial` field is optional (all-optional behaviour preserved). Run
  via `uv run pytest`.
- **D-09:** Add **`pytest` as a dev dependency** in `pyproject.toml` (dev/optional group)
  — establishes the test harness that Phases 2–3 will reuse for live-API verification.

### Claude's Discretion
- Exact resolved dependency versions (within the floors above) — `uv` decides.
- The precise mechanism for the v2 partial-model factory (helper vs. `create_model`),
  as long as it avoids private internals and preserves the public surface (D-06/D-07).
- Whether to add a `requires-python` constraint and/or `.python-version` file, and any
  `[build-system]` / project metadata details in `pyproject.toml` — not discussed; use
  standard `uv` conventions. Target interpreter is Python 3.14 (3.14.4 on this machine).
- The exact v2 replacement for `pydantic_encoder` in `io.py` (D-04).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project & milestone scope
- `.planning/PROJECT.md` — what the client is, core value, in/out of scope for the revive milestone.
- `.planning/REQUIREMENTS.md` — ENV-01, ENV-02, ENV-03 are this phase's requirements (ENV-04 is Phase 3).
- `.planning/ROADMAP.md` §"Phase 1: Toolchain Revival" — goal, success criteria, the two planned plans (01-01 deps/uv, 01-02 pydantic v2).

### Codebase analysis (migration specifics already mapped)
- `.planning/codebase/CONCERNS.md` — **primary migration map.** Documents every pydantic v1
  site (`pydantic.main.ModelMetaclass` in `meta.py`, `@validator` in `asset.py:118`,
  `.dict()` in `assetApi.py`/`frameApi.py`, `pydantic_encoder` in `io.py:6`), the UTF-16
  `requirements.txt`, and the `datetime.utcnow()` deprecation.
- `.planning/codebase/STACK.md` — current dependency pins and runtime assumptions.
- `.planning/codebase/STRUCTURE.md` — package/module layout (`auraframes/models/`, `auraframes/utils/`).

### Files that will change
- `requirements.txt` (UTF-16; to be deleted)
- `auraframes/models/meta.py` (`AllOptional` metaclass → v2 factory)
- `auraframes/models/asset.py` (`@validator` → `@field_validator`)
- `auraframes/models/frame.py` (`FramePartial(Frame, metaclass=AllOptional)` → new factory usage)
- `auraframes/utils/io.py` (`pydantic_encoder` import → v2 serialization)
- `pyproject.toml`, `uv.lock`, `tests/test_imports.py` (new)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `auraframes/models/*` (`user.py`, `frame.py`, `asset.py`, `activity.py`, `person.py`) —
  existing pydantic `BaseModel` DTOs; field names already match API JSON keys. Migration
  is field-decorator / config changes, not a re-model.
- `auraframes/cache.py` already has an `async_cache` decorator prepared (unrelated to this
  phase, but signals the codebase anticipates change).

### Established Patterns
- Partial-model pattern: `class FramePartial(Frame, metaclass=AllOptional): pass`
  (`frame.py:93`) — the public contract to preserve (D-06/D-07).
- `AssetPartialId` uses a pydantic `@validator` for cross-field validation
  (`asset.py:118`) — migrates to `@field_validator` (runs at import time, so in-scope).
- `.dict(include=...)` / `.dict(exclude_unset=True)` used to build request payloads — these
  are runtime call sites, deferred to Phase 2 (D-05) but their v2 equivalent is
  `.model_dump(...)`.

### Integration Points
- `import auraframes` hits an empty `auraframes/__init__.py` (imports nothing on its own),
  so the smoke test (D-08) must import the models modules (and `auraframes.utils.io`)
  explicitly to actually exercise the migration.

</code_context>

<specifics>
## Specific Ideas

- The lockfile-plus-floors combination (D-01 + D-02) is deliberate: floors keep deps fresh
  enough to build on 3.14, the committed lock keeps the "it works" result reproducible.
- The import-clean boundary (D-04) is the seam between Phase 1 (installs + imports) and
  Phase 2 (live read path) — keep runtime serialization changes out of Phase 1 unless they
  block import.

</specifics>

<deferred>
## Deferred Ideas

- **Runtime `.dict()` → `.model_dump()` migration** in `auraframes/api/assetApi.py` and
  `auraframes/api/frameApi.py` — runtime-only, exercised in Phase 2's live read path (D-05).
- **`datetime.utcnow()` deprecation** in `auraframes/utils/dt.py:11` — flagged in
  CONCERNS.md; not import-blocking, touch only if it surfaces during Phase 2/3.
- **Async HTTP migration, AWS pool-ID config, typed exception hierarchy, `main.py` example**
  — explicitly out of scope for this milestone (REQUIREMENTS.md v2 / Out of Scope).

</deferred>

---

*Phase: 1-Toolchain Revival*
*Context gathered: 2026-06-29*
