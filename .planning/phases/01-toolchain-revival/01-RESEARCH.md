# Phase 1: Toolchain Revival - Research

**Researched:** 2026-06-29
**Domain:** Python packaging (`uv` + `pyproject.toml`) + pydantic v1→v2 migration on Python 3.14
**Confidence:** HIGH (dependency resolution, install, and every migration idiom were executed and verified against the real toolchain: uv 0.11.7, CPython 3.14.4, pydantic 2.13.4)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Specify dependencies in `pyproject.toml` with **loose version floors** (`>=`), not exact pins — e.g. `pydantic>=2`, `httpx>=0.27`, `boto3>=1.34`, etc. Let `uv` resolve the latest versions that build on Python 3.14. (The 2022-era pins — `pydantic~=1.10.4`, `httpx==0.23.1`, `pillow~=9.5.0`, `boto3==1.26.38` — mostly will not build on 3.14 and must move up.)
- **D-02:** **Commit `uv.lock`** for reproducibility, so a fresh checkout resolves the same versions. (Floors give freshness; the lockfile gives determinism — both, by design.)
- **D-03:** Delete the UTF-16 `requirements.txt`; `pyproject.toml` + `uv.lock` are the sole dependency manifest (ENV-01).
- **D-04:** Make the **entire `auraframes` package import-clean** under pydantic v2 — not just `auraframes/models/*`. This explicitly includes `auraframes/utils/io.py`, whose top-level `from pydantic.json import pydantic_encoder` **hard-fails on v2** and must be replaced.
- **D-05:** **Defer runtime-only call sites** that do not execute at import time to Phase 2. Specifically the `.dict(...)` calls inside `auraframes/api/assetApi.py` (~line 21, ~line 97) and `auraframes/api/frameApi.py` (~line 90, `frame_partial.dict(exclude_unset=True)`). Note: the `@validator` in `auraframes/models/asset.py:118` runs at class-definition (import) time and **IS in scope here** — migrate it to `@field_validator`.
- **D-06:** Replace the `AllOptional` metaclass (`auraframes/models/meta.py`), which subclasses pydantic v1 internals (`pydantic.main.ModelMetaclass`), with an **idiomatic pydantic v2 partial-model factory** — no reliance on private internals. Acceptable mechanisms: a helper that rebuilds the model with every field Optional/defaulted, or `pydantic.create_model`.
- **D-07:** Preserve the **public surface** of partials. `FramePartial` must keep the same name, import path, and expose **every field as optional**. `frame_partial.dict(exclude_unset=True)` semantics must remain achievable (call site migrates in Phase 2, but the model must support exclude-unset partial serialization).
- **D-08:** Add a **minimal committed pytest smoke test** (e.g. `tests/test_imports.py`) that (a) imports `auraframes` and every `auraframes/models/*` module without error and (b) asserts a `FramePartial` field is optional. Run via `uv run pytest`.
- **D-09:** Add **`pytest` as a dev dependency** in `pyproject.toml` (dev/optional group).

### Claude's Discretion
- Exact resolved dependency versions (within the floors above) — `uv` decides.
- The precise mechanism for the v2 partial-model factory (helper vs. `create_model`), as long as it avoids private internals and preserves the public surface (D-06/D-07).
- Whether to add a `requires-python` constraint and/or `.python-version` file, and any `[build-system]` / project metadata details in `pyproject.toml` — use standard `uv` conventions. Target interpreter is Python 3.14 (3.14.4 on this machine).
- The exact v2 replacement for `pydantic_encoder` in `io.py` (D-04).

### Deferred Ideas (OUT OF SCOPE)
- **Runtime `.dict()` → `.model_dump()` migration** in `auraframes/api/assetApi.py` and `auraframes/api/frameApi.py` — runtime-only, exercised in Phase 2's live read path (D-05).
- **`datetime.utcnow()` deprecation** in `auraframes/utils/dt.py:11` — flagged in CONCERNS.md; not import-blocking, touch only if it surfaces during Phase 2/3.
- **Async HTTP migration, AWS pool-ID config, typed exception hierarchy, `main.py` example** — explicitly out of scope for this milestone.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ENV-01 | Dependency management migrated to `uv` with a `pyproject.toml`, replacing the UTF-16 `requirements.txt` | "Standard Stack" + "uv project layout" pattern; a complete `pyproject.toml` was authored and verified to resolve. Delete path for `requirements.txt` confirmed (UTF-16 LE, decoded contents captured). |
| ENV-02 | All dependencies resolve and install/build on Python 3.14 via `uv` | **VERIFIED end-to-end**: `uv lock --python 3.14` resolved 37 packages; `uv sync --python 3.14 --extra dev` installed all of them from cp314 wheels with exit 0. Resolved versions captured below. |
| ENV-03 | The pydantic model layer is migrated to pydantic v2, preserving the `AllOptional` partial-model behaviour | Every import-time v1 surface inventoried; a `create_model(__base__=...)` partial factory was executed and confirmed to preserve method surface, name, isinstance, and produce all-optional fields. `field_validator` + `io.py` serialization replacements verified. |

*ENV-04 (developer setup docs) is Phase 3 — out of scope here.*
</phase_requirements>

## Summary

This phase is a mechanical-but-precise revival, not a redesign. Two work streams, both independently verifiable: (1) replace the broken UTF-16 `requirements.txt` with a `pyproject.toml` + committed `uv.lock`, and (2) migrate the pydantic model layer from v1 to v2 so the whole package imports under pydantic 2.x.

The dependency stream carries **almost no risk**: I authored the proposed `pyproject.toml` with the agreed `>=` floors and ran `uv lock --python 3.14` followed by `uv sync --python 3.14 --extra dev` in a scratch project. All 37 transitive packages resolved and installed from prebuilt cp314 wheels in under a second — including every heavy native dependency (pydantic-core/Rust, Pillow, h2). There is no sdist-build step and no 3.14 wheel gap as of June 2026. The 2022-era pins are dead, but their modern successors are all wheel-available.

The pydantic stream has exactly **three import-time breakers** and one dependent: `meta.py` (`pydantic.main.ModelMetaclass` — removed in v2), `utils/io.py` (`from pydantic.json import pydantic_encoder` — module removed in v2), the `@validator` in `asset.py:118` (in-scope per D-05), and `frame.py:93` (`FramePartial(Frame, metaclass=AllOptional)`, which resolves once `meta.py` is rewritten). I verified replacement idioms for all of them against pydantic 2.13.4. **The single most important landmine** for the planner: in pydantic v2, `Optional[X]` *without* an explicit `= None` is a **required, nullable** field — not an optional one. The codebase's models (`asset.py`, `frame.py`, etc.) declare dozens of `Optional[...]` fields with no default, relying on v1's implicit-None behavior. The `AllOptional` metaclass relied on exactly this. The v2 partial factory must set `default=None` explicitly (it does), and the planner must decide whether to also restore implicit-None defaults on the *base* models (a runtime concern that will otherwise bite Phase 2 deserialization).

**Primary recommendation:** Author a standard flat-layout `pyproject.toml` (hatchling backend, `requires-python = ">=3.14"`, the floors below, `pytest` in a `dev` optional group), commit `uv.lock`, delete `requirements.txt`. Replace `AllOptional` with a `create_model(name, __base__=Model, **{f: (Optional[ann], None)})` factory. Migrate the one `@validator` to `@field_validator(..., ) @classmethod` with `ValidationInfo`. Replace `pydantic_encoder` with a small `default=` callable that returns `obj.model_dump(mode="json")`. Add `tests/test_imports.py` asserting `FramePartial.model_fields["id"].is_required() is False`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Dependency declaration & resolution | Build/Packaging (`pyproject.toml` + `uv.lock`) | — | `uv` owns env, interpreter, lockfile; `pyproject.toml` is the single manifest (D-03) |
| Data validation / DTO definition | Data Modeling (`auraframes/models/*`) | — | pydantic `BaseModel` is the validation + (de)serialization layer; v2 migration lives here |
| Partial-model generation | Data Modeling (`models/meta.py` factory) | — | `AllOptional` → `create_model` factory; pure model-layer concern |
| JSON serialization of models to disk | Utilities (`auraframes/utils/io.py`) | Data Modeling | `write_model` orchestrates `json.dump`; depends on the model layer's `model_dump` |
| Import-time smoke verification | Test harness (`tests/`) | — | pytest exercises the model + utils import graph (empty `__init__.py` means tests must import submodules explicitly) |

## Standard Stack

These are the project's **existing** dependencies (from the UTF-16 `requirements.txt`), moved to modern floors per D-01. Every version below is the one `uv` actually resolved on Python 3.14 in this session — captured for the planner's reference only; **do not pin these** (D-01 says floors, `uv` decides).

### Core (runtime)
| Library | Floor (recommend) | Resolved on 3.14 | Purpose | Why standard |
|---------|-------------------|------------------|---------|--------------|
| pydantic | `>=2` | 2.13.4 | All API DTOs / validation | Current major; v1 is EOL for new work [VERIFIED: uv resolution] |
| httpx (extra `http2`) | `>=0.27` | 0.28.1 | HTTP client (`client.py`, `export.py`) | HTTP/2 client already used [VERIFIED: uv resolution] |
| h2 | `>=4` | 4.3.0 | HTTP/2 protocol for httpx | Required for `http2=True` [VERIFIED: uv resolution] |
| requests | `>=2.31` | 2.34.2 | Listed legacy dep (not used in active src) | Pre-existing pin; kept for parity [VERIFIED: uv resolution] |
| boto3 | `>=1.34` | 1.43.36 | AWS S3/SQS clients | Pre-existing [VERIFIED: uv resolution] |
| botocore | `>=1.34` | 1.43.36 | boto3 core (`Config`) | Pre-existing [VERIFIED: uv resolution] |
| Pillow | `>=10.4` | 12.2.0 | Image read/thumbnail | Pre-existing; 12.x has cp314 wheels [VERIFIED: uv resolution] |
| piexif | `>=1.1.3` | 1.1.3 | EXIF read/write | Pure-Python, no build [VERIFIED: uv resolution] |
| geopy | `>=2.4` | 2.4.1 | Reverse geocoding | Pre-existing [VERIFIED: uv resolution] |
| loguru | `>=0.7` | 0.7.3 | Structured logging | Pre-existing [VERIFIED: uv resolution] |
| tqdm | `>=4.66` | 4.68.3 | Progress bars | Pre-existing [VERIFIED: uv resolution] |

### Supporting (dev)
| Library | Floor | Resolved | Purpose | When to use |
|---------|-------|----------|---------|-------------|
| pytest | `>=8` | 9.1.1 | Test runner for smoke test (D-08/D-09) | `uv run pytest` |

### Notes on floors
- `httpx>=0.27` keeps us clear of the 0.23 era; resolved to 0.28.1. **httpx 0.28 dropped some legacy constructor args** (e.g. `proxies=`, `app=`) — irrelevant at import time and `client.py` only uses `Client(http2=True)`, `Timeout`, `Response`. Any runtime fallout is a **Phase 2** concern, not this phase.
- `requests>=2.31` chosen as a security floor (older requests has CVEs); it is otherwise unused in active source. Could be dropped entirely, but D-01/scope says revive what's there, so keep it.
- `boto3`/`botocore` jumped from 1.26 → 1.43. The `botocore.config.Config` API used in `awsclient.py` is stable; any drift is Phase 2.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| hatchling build backend | `setuptools`, `uv_build`, `flit-core` | hatchling is uv's de-facto default for `uv init --package`, zero-config for flat layout. `uv_build` is newer/lighter but less battle-tested. Either works; hatchling recommended for familiarity. |
| `[project.optional-dependencies]` dev group | `[dependency-groups]` (PEP 735) | PEP 735 `[dependency-groups]` is the newer idiom uv supports for *non-published* dev deps and is arguably cleaner. D-09 says "dev/optional group" — either satisfies it. `optional-dependencies` is more portable; `dependency-groups` is more correct for dev-only tooling. Planner's choice. |

**Installation (the workflow to encode in tasks):**
```bash
uv sync --extra dev     # creates .venv, installs runtime + dev, writes/uses uv.lock
uv run pytest           # runs the smoke test inside the managed env
```
(If using `[dependency-groups]` instead of an extra, `uv sync` installs the default group automatically and `--extra dev` becomes unnecessary.)

**Version verification:** Performed live this session — `uv lock --python 3.14` (37 pkgs, 494ms) + `uv sync --python 3.14 --extra dev` (exit 0, all wheels). No package required an sdist build.

## Package Legitimacy Audit

slopcheck was **not installable** in this environment. However, the normal slop risk (an LLM hallucinating a novel package name) **does not apply here**: every package below is a pre-existing, human-authored pin lifted verbatim from the project's original `requirements.txt`, and each was just confirmed to resolve and install a real cp314 wheel via `uv sync`. Provenance is the existing manifest, not a model suggestion.

| Package | Registry | Source repo | Provenance | Disposition |
|---------|----------|-------------|-----------|-------------|
| pydantic | PyPI | github.com/pydantic/pydantic | existing requirements.txt | Approved [VERIFIED: uv resolution] |
| httpx | PyPI | github.com/encode/httpx | existing | Approved [VERIFIED: uv resolution] |
| h2 | PyPI | github.com/python-hyper/h2 | existing | Approved [VERIFIED: uv resolution] |
| requests | PyPI | github.com/psf/requests | existing | Approved [VERIFIED: uv resolution] |
| boto3 | PyPI | github.com/boto/boto3 | existing | Approved [VERIFIED: uv resolution] |
| botocore | PyPI | github.com/boto/botocore | existing | Approved [VERIFIED: uv resolution] |
| Pillow | PyPI | github.com/python-pillow/Pillow | existing | Approved [VERIFIED: uv resolution] |
| piexif | PyPI | github.com/hMatoba/Piexif | existing | Approved [VERIFIED: uv resolution] |
| geopy | PyPI | github.com/geopy/geopy | existing | Approved [VERIFIED: uv resolution] |
| loguru | PyPI | github.com/Delgan/loguru | existing | Approved [VERIFIED: uv resolution] |
| tqdm | PyPI | github.com/tqdm/tqdm | existing | Approved [VERIFIED: uv resolution] |
| pytest | PyPI | github.com/pytest-dev/pytest | new dev dep (D-09); canonical test runner | Approved [VERIFIED: uv resolution] |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*No `checkpoint:human-verify` gate is warranted: these are not LLM-introduced names, and the committed `uv.lock` (D-02) pins them by hash, providing supply-chain integrity at install time.*

## Architecture Patterns

### System Architecture Diagram (this phase's seam)

```
                         pyproject.toml  (single manifest, D-03)
                                │  uv lock / uv sync  (--python 3.14)
                                ▼
                          uv.lock  ──►  .venv (cp314 wheels)
                                              │
                  ┌───────────────────────────┴───────────────────────────┐
                  ▼                                                         ▼
          import auraframes            (D-08 smoke test: uv run pytest tests/test_imports.py)
                  │                                                         │
   ┌──────────────┼───────────────────────────┐                           │
   ▼              ▼                             ▼                           ▼
models/meta.py  models/asset.py            utils/io.py             assert FramePartial
(AllOptional →  (@validator →              (pydantic_encoder →     .model_fields['x']
 create_model   @field_validator)           model_dump+json.dumps)  .is_required() is False
 factory)            │                          │
   │                 ▼                          ▼
   └──► frame.py: FramePartial = make_partial(Frame)   [PHASE-2 DEFERRED: .dict() call sites
                                                         in api/assetApi.py, api/frameApi.py]
```

### Recommended Project Structure (flat layout — keep existing)
```
auraframes/             # existing flat-layout package (unchanged structure)
├── __init__.py         # empty — tests must import submodules explicitly
├── models/             # pydantic DTOs (migration target)
├── api/                # .dict() call sites here are PHASE 2
├── aws/  utils/  ...
pyproject.toml          # NEW — single dependency manifest
uv.lock                 # NEW — committed (D-02)
.python-version         # OPTIONAL — pins 3.14 for `uv run`
tests/
└── test_imports.py     # NEW — D-08 smoke test
requirements.txt        # DELETE (D-03)
```

### Pattern 1: `uv` project for an existing flat-layout package
**What:** Standard `[project]` + `[build-system]` `pyproject.toml`; `uv sync` builds the env from it and writes `uv.lock`.
**When to use:** Always for this phase.
**Example (authored and resolution-verified this session):**
```toml
# Source: authored for this project; verified via `uv lock`/`uv sync` on CPython 3.14.4
[project]
name = "auraframes"
version = "0.1.0"
requires-python = ">=3.14"
dependencies = [
    "pydantic>=2",
    "httpx[http2]>=0.27",
    "h2>=4",
    "requests>=2.31",
    "boto3>=1.34",
    "botocore>=1.34",
    "Pillow>=10.4",
    "piexif>=1.1.3",
    "geopy>=2.4",
    "loguru>=0.7",
    "tqdm>=4.66",
]

[project.optional-dependencies]
dev = ["pytest>=8"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```
Notes: `httpx[http2]` pulls `h2` transitively; listing `h2` explicitly is harmless and matches the existing manifest. With a flat-layout package named `auraframes/`, hatchling auto-detects the package — no `[tool.hatch.build.targets.wheel]` needed. Add `.python-version` containing `3.14` so bare `uv run` selects the right interpreter without `--python`.

### Pattern 2: pydantic v2 partial-model factory (replaces `AllOptional`, D-06/D-07)
**What:** A function that returns a new model subclass with every field made `Optional` and defaulted to `None`.
**When to use:** For `FramePartial` and any future partial.
**Example (executed and verified against pydantic 2.13.4):**
```python
# Source: verified this session — preserves methods, name, isinstance; all fields optional
from typing import Optional
from pydantic import BaseModel, create_model

def make_partial(model: type[BaseModel], name: str) -> type[BaseModel]:
    fields = {
        fname: (Optional[finfo.annotation], None)
        for fname, finfo in model.model_fields.items()
    }
    return create_model(name, __base__=model, **fields)

# frame.py:
FramePartial = make_partial(Frame, "FramePartial")
```
Why `__base__=model` (not `__base__=BaseModel`): it **preserves the base model's methods** (`Frame.is_portrait()`, `get_frame_type()`) and makes `isinstance(fp, Frame)` true — both confirmed. Iterating `model.model_fields` (not `__annotations__`) means **string annotations from `from __future__ import annotations` are already resolved to real types** — the exact fragility that broke the old metaclass goes away. `model_dump(exclude_unset=True)` on instances works, satisfying D-07's exclude-unset requirement (verified output: `FramePartial(name="x").model_dump(exclude_unset=True)` → `{'name': 'x'}`).

If a future model uses field aliases, extend the tuple to `(Optional[finfo.annotation], Field(default=None, alias=finfo.alias))` — alias preservation verified. The current models use no aliases (field names match JSON keys), so the simple form suffices.

### Pattern 3: `@validator` → `@field_validator` (asset.py:118, in-scope per D-05)
**What:** v2 field validator; decorator order is `@field_validator` then `@classmethod`; cross-field access via `ValidationInfo.data`.
**Example (verified):**
```python
# Source: verified this session against pydantic 2.13.4
from pydantic import field_validator, ValidationInfo

class AssetPartialId(BaseModel):
    id: Optional[str] = None
    local_identifier: Optional[str] = None
    user_id: Optional[str] = None

    @field_validator("id")
    @classmethod
    def check_id_or_local_id(cls, v: Optional[str], info: ValidationInfo) -> Optional[str]:
        if not info.data.get("local_identifier") and not v:
            raise ValueError("Either id or local_identifier is required")
        return v
```
**Behavior note (pre-existing latent bug, preserved):** `info.data` only contains fields validated *before* the current one, and `id` is declared *before* `local_identifier`. So when `id` is empty, `info.data["local_identifier"]` is not yet present and the check passes silently — `AssetPartialId()` does **not** raise. This is identical to the v1 behavior (`values` had the same ordering semantics), so a straight port preserves behavior per scope discipline. If correctness is desired, a `@model_validator(mode="after")` fixes it — but that is arguably a Phase 2 behavior change, not import-clean work. Flagged as an open question; default recommendation is the faithful straight port.

### Pattern 4: replace `pydantic_encoder` in `io.py` (D-04)
**What:** `pydantic.json.pydantic_encoder` was removed in v2. Replace with a `default=` callable so `write_model` keeps handling both a single model and `list[BaseModel]`.
**Example (verified — handles single and list):**
```python
# Source: verified this session — json.dump recurses lists and applies default per element
import json
from typing import Union
from pydantic import BaseModel

def _pydantic_default(obj):
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

def write_model(model: Union[BaseModel, list[BaseModel]], path: str) -> None:
    with open(path, "w") as out:
        json.dump(model, out, default=_pydantic_default)
```
This is the minimal-diff replacement: it keeps the existing `json.dump(model, out, default=...)` shape, and `mode="json"` ensures nested non-JSON types (datetimes, enums) serialize correctly. (Alternative one-liner `json.dumps(model.model_dump(mode="json"))` does **not** handle the `list[BaseModel]` branch without a type check, so the `default=` form is preferred.)

### Pattern 5: D-08 smoke test
```python
# tests/test_imports.py
import importlib
import pytest

MODEL_MODULES = [
    "auraframes",
    "auraframes.models.user", "auraframes.models.person",
    "auraframes.models.activity", "auraframes.models.asset",
    "auraframes.models.frame", "auraframes.models.meta",
    "auraframes.utils.io",
]

@pytest.mark.parametrize("mod", MODEL_MODULES)
def test_imports_clean(mod):
    importlib.import_module(mod)

def test_framepartial_all_optional():
    from auraframes.models.frame import FramePartial
    # every field optional (D-07); verified idiom on pydantic 2.13.4
    assert all(not f.is_required() for f in FramePartial.model_fields.values())
```
`ModelField.is_required()` is the verified v2 way to assert optionality (returns `False` for defaulted fields). `auraframes/__init__.py` is empty, so importing the submodules explicitly is what actually exercises the migration (noted in CONTEXT.md integration points).

### Anti-Patterns to Avoid
- **Subclassing pydantic internals** (`pydantic.main.ModelMetaclass`, `pydantic._internal.*`) — the original sin being removed (D-06). The factory uses only public `create_model` + `model_fields`.
- **Pinning exact versions** in `pyproject.toml` — violates D-01. Floors + committed lock is the design.
- **One-liner `json.dumps(model.model_dump())`** for `write_model` — silently breaks the `list[BaseModel]` path; use the `default=` callable.
- **Fixing the `.dict()` call sites now** — they are runtime-only and explicitly Phase 2 (D-05). Touching them here is scope creep.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Making all model fields optional | Manual re-declaration of every field, or `__annotations__` munging | `create_model(__base__=Model, **{f: (Optional[ann], None)})` | Public API; resolves forward refs; preserves methods/aliases; survives pydantic bumps |
| Serializing pydantic models to JSON | Custom recursive encoder | `model.model_dump(mode="json")` + `json.dump(default=...)` | v2 handles datetimes/enums/nested models natively |
| Resolving deps on 3.14 / locking | Hand-edited pins, `pip freeze` | `uv lock` + committed `uv.lock` | Hash-pinned, reproducible, picks wheel-available versions |
| Detecting if a field is optional | Inspecting defaults manually | `model.model_fields[name].is_required()` | Canonical v2 introspection API |

**Key insight:** Every piece of this migration has a first-party pydantic/uv API. The original code's fragility came entirely from reaching into private internals; the v2 idioms are all public and were verified to work.

## Runtime State Inventory

This is a code/packaging migration (rename of a dependency *mechanism* + API surface), so the rename-style inventory mostly does not apply, but checked explicitly:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — no datastore keys reference dependency or model names. The on-disk JSON written by `write_model`/`cache.py` is data-shaped, not schema-locked to pydantic version. | None |
| Live service config | None — no external service stores a dependency manifest. | None |
| OS-registered state | None — no scheduled tasks, services, or daemons. | None |
| Secrets/env vars | None changed — `AURA_EMAIL`/`AURA_PASSWORD`/`AURA_LOCALE`/`AURA_APP_IDENTIFIER`/`AURA_DEVICE_IDENTIFIER` are read in `settings.py` and are unaffected by this phase. | None |
| Build artifacts | **`requirements.txt` (UTF-16 LE)** is the old manifest — delete (D-03). No `*.egg-info`, no compiled artifacts, no prior `.venv`/`uv.lock` present (verified: `ls` shows none). A fresh `uv sync` creates `.venv` + `uv.lock`. | Delete `requirements.txt`; ensure `.venv` is gitignored (it is — `.gitignore` present). |

## Common Pitfalls

### Pitfall 1: `Optional[X]` without a default is REQUIRED in pydantic v2 (THE landmine)
**What goes wrong:** In v1, `field: Optional[str]` implied `= None`. In v2 it is a **required** field that merely accepts `None`. The models declare dozens of `Optional[...]` fields with no default (`asset.py`: `auto_landscape_16_10_rect`, `colorized_file_name`, … ~30 of them; `frame.py`: `deleted_at`, `brightness`, `frame_queue_url`, …). The `AllOptional` metaclass relied on this implicit-None behavior.
**Why it happens:** Deliberate v2 design change (explicitness).
**How to avoid:**
- For **partials**: the factory sets `default=None` explicitly — handled (verified `is_required() is False`).
- For **base models** (`Frame`, `Asset`, `User`, etc.): these still *import/define* fine (class definition does not fail). They only fail at **instantiation** — i.e. when deserializing live API responses in **Phase 2**. So strictly per D-04/D-05, fixing base-model defaults is **not import-blocking**. **But** leaving them guarantees a Phase 2 failure and arguably violates ENV-03's "preserving behaviour." See Open Question #1 — the planner must decide: add `= None` to base-model Optionals now (recommended, low-risk, ~2 files) vs. defer to Phase 2.
**Warning signs:** `pytest` smoke test passes (import-only) but any `Frame(**resp)` / `Asset(**resp)` later raises `ValidationError: Field required`.
**Verification (this session):** `M(a="x")` with `b: Optional[str]` (no default) → `ValidationError`; with `c: Optional[str] = None` → `c.is_required()` is `False`.

### Pitfall 2: `pydantic.main.ModelMetaclass` no longer exists in v2
**What goes wrong:** `meta.py` raises `AttributeError`/`ImportError` the moment `frame.py` imports it — a hard import-time failure (D-06).
**How to avoid:** Replace with the `create_model` factory (Pattern 2). Confirmed `hasattr(pydantic.main, "ModelMetaclass")` is `False` on 2.13.4.

### Pitfall 3: `pydantic.json` module removed in v2
**What goes wrong:** `from pydantic.json import pydantic_encoder` in `io.py:6` is a top-level import → hard failure on *any* import that transitively pulls `utils/io.py` (D-04).
**How to avoid:** Pattern 4's `default=` callable.

### Pitfall 4: `@validator`'s deprecated shim is not enough
**What goes wrong:** `from pydantic import validator` still imports in v2 (deprecated alias) and won't crash, so it's tempting to leave it — but D-05 explicitly scopes it in, and it emits `PydanticDeprecatedSince20` warnings. Use `@field_validator` (Pattern 3).
**Warning signs:** Deprecation warnings in `pytest` output.

### Pitfall 5: Empty `__init__.py` makes a naive smoke test vacuous
**What goes wrong:** `import auraframes` imports nothing (empty `__init__.py`), so a test that only does that exercises none of the migration.
**How to avoid:** Import each `models/*` module and `utils/io` explicitly (Pattern 5).

### Pitfall 6 (forward-looking, NOT this phase): httpx 0.28 / boto3 1.43 runtime drift
**What goes wrong:** Large version jumps in httpx (0.23→0.28) and boto3 (1.26→1.43) may change runtime behavior. None affects import. Flagged so the planner does **not** chase it here — it's Phase 2.

## Code Examples

(All verified examples are inline above under Architecture Patterns 1–5. They were executed against CPython 3.14.4 / pydantic 2.13.4 this session, not transcribed from docs.)

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `requirements.txt` + pip | `pyproject.toml` + `uv.lock` (uv) | uv mainstream 2024–2025 | Reproducible, fast, interpreter-managed |
| `@validator` / `@root_validator` | `@field_validator` / `@model_validator` | pydantic v2.0 (2023) | Decorator + `ValidationInfo` signature |
| `.dict()` / `.json()` | `.model_dump()` / `.model_dump_json()` | pydantic v2.0 | (`.dict()` sites deferred to Phase 2, D-05) |
| `pydantic.json.pydantic_encoder` | `model_dump(mode="json")` | pydantic v2.0 (module removed) | Must replace in `io.py` |
| `pydantic.main.ModelMetaclass` (internal) | `create_model` + `model_fields` (public) | pydantic v2.0 | Metaclass approach is dead |
| `Optional[X]` ⇒ implicit `None` default | `Optional[X]` ⇒ required-nullable; need explicit `= None` | pydantic v2.0 | The central migration landmine (Pitfall 1) |
| `datetime.utcnow()` | `datetime.now(timezone.utc)` | Python 3.12 deprecation | Out of scope (Deferred; `dt.py`) |

**Deprecated/outdated:**
- pydantic v1 model APIs throughout — being migrated.
- UTF-16 `requirements.txt` — being deleted.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `requests` (unused in active source) should be retained for parity rather than dropped | Standard Stack notes | Low — keeping an unused dep is harmless; dropping it is also fine and is a planner judgment call |
| A2 | Faithful straight-port of the `@validator` (preserving the latent field-ordering bug) is the in-scope choice; the `model_validator` fix is Phase-2 behavior change | Pattern 3 / Open Q#2 | Low — both import cleanly; only differs in runtime validation strictness exercised in Phase 2 |

*(Dependency versions and every migration idiom are `[VERIFIED]` by execution, not assumed.)*

## Open Questions

1. **Base-model `Optional[...]` defaults — fix now or defer to Phase 2?**
   - What we know: Base models (`Frame`, `Asset`, `User`, `Activity`, `Person`) have many `Optional[...]` fields with no `= None`. Under v2 these are required-nullable. Class *definition* succeeds (import-clean ✔), but *instantiation* from API responses will fail — a Phase 2 event.
   - What's unclear: Whether ENV-03 ("preserving the model layer behaviour") obligates restoring implicit-None now, vs. D-05's "defer runtime-only."
   - Recommendation: **Add `= None` to base-model Optional fields in this phase** — it is the model-layer's job (ENV-03), it is a tiny mechanical diff confined to `models/*`, and it prevents a guaranteed Phase 2 regression. If the planner prefers strict D-05 adherence, defer — but then the smoke test must NOT attempt to instantiate base models, and Phase 2 must own it explicitly.

2. **`AssetPartialId` validator: faithful port vs. correctness fix?**
   - What we know: The cross-field check is a no-op when `id` is the empty/missing one, in both v1 and v2 (field-ordering). A straight port preserves behavior.
   - Recommendation: Straight port now (Pattern 3); note the `model_validator(mode="after")` correctness fix as a Phase 2 candidate. (A2)

3. **`dev` deps: `[project.optional-dependencies]` vs. PEP 735 `[dependency-groups]`?**
   - Both satisfy D-09. Recommendation: planner's discretion; `optional-dependencies dev` is the more conservative/portable choice and matches the `uv sync --extra dev` workflow documented above.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| uv | ENV-01/02 (resolve, lock, sync) | ✓ | 0.11.7 | — |
| CPython 3.14 | ENV-02 target interpreter | ✓ | 3.14.4 (`/usr/bin/python3.14`) | uv can also download a managed 3.14 |
| pytest | D-08/D-09 smoke test | ✓ (system 9.0.2; will be installed into `.venv` as dev dep, resolved 9.1.1) | — | — |
| Network (PyPI) | dependency download | ✓ (uv sync downloaded all wheels) | — | — |
| C/Rust build toolchain | only if a dep lacked a wheel | not needed | — | All deps had cp314 wheels — no build required |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** none — full `uv sync` succeeded.

## Security Domain

ASVS Level 1 (`security_asvs_level: 1`, `security_enforcement: true`). This phase performs **no auth, no network I/O, and no user-input handling at runtime** — it is packaging + class-definition migration. The dominant security surface is therefore **supply chain**.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no (Phase 2/3) | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | indirect | pydantic v2 is the validation layer; this phase only migrates it, exercised in Phase 2 |
| V6 Cryptography | no (this phase) | — |
| V14 Configuration / Dependency Management | **yes** | Committed `uv.lock` pins every dependency by **hash** (D-02) — reproducible, tamper-evident installs. Floors avoid known-vulnerable old versions (`requests>=2.31`, modern `urllib3` 2.7.0). |

### Known Threat Patterns for this phase

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Dependency confusion / slopsquat | Spoofing/Tampering | All deps are pre-existing human-authored pins from the original manifest; `uv.lock` hash-pins them; no LLM-introduced names (see Package Legitimacy Audit) |
| Malicious transitive dependency | Tampering | `uv.lock` records the full resolved tree with hashes; review the 37-package tree on commit |
| Supply-chain version drift on fresh checkout | Tampering | Committing `uv.lock` (D-02) makes a clean checkout resolve identical versions |

**Out-of-scope security debt (deferred, from CONCERNS.md):** plaintext password/token logging (`client.py`), hardcoded Cognito pool IDs (`aws/*`), missing `response.raise_for_status()` — all are **runtime** concerns for Phase 2/3, not import-time, and outside this phase's boundary. Listed here only so the planner does not mistake them for Phase 1 work.

## Sources

### Primary (HIGH confidence)
- **Live execution against the project toolchain** (uv 0.11.7, CPython 3.14.4, pydantic 2.13.4) — `uv lock --python 3.14` (37 pkgs), `uv sync --python 3.14 --extra dev` (exit 0), and four probe scripts verifying: Optional-default behavior, `create_model` partial factory (methods/name/isinstance/all-optional/alias), `field_validator` + `ValidationInfo`, `io.py` serialization (single + list), `pydantic.main.ModelMetaclass` removal, `is_required()` introspection.
- **Codebase inspection** — full grep sweep of `auraframes/` for every pydantic surface (`pydantic.main.ModelMetaclass`, `validator`, `pydantic_encoder`, `.dict()`, inner `Config`, `parse_obj`/`construct`); `file`/`iconv` decode of UTF-16 `requirements.txt`.

### Secondary (MEDIUM confidence)
- CONTEXT.md (D-01..D-09), REQUIREMENTS.md (ENV-01..03), CONCERNS.md, STACK.md, STATE.md, CLAUDE.md.

### Tertiary (LOW confidence)
- None relied upon. (Context7/ctx7 unavailable in this environment; substituted with direct execution against the resolved pydantic version, which is strictly stronger than docs for version-accuracy.)

## Metadata

**Confidence breakdown:**
- Standard stack / resolution on 3.14: **HIGH** — actually resolved and installed.
- pydantic v2 migration idioms: **HIGH** — every replacement executed against pydantic 2.13.4.
- Import-time breaker inventory: **HIGH** — exhaustive grep of the package.
- Base-model Optional-default scoping: **MEDIUM** — a genuine planner decision (Open Q#1), not a technical unknown.

**Research date:** 2026-06-29
**Valid until:** ~2026-07-29 (stable; uv and pydantic 2.x are mature. The only churn risk is a new pydantic minor changing `create_model`/`model_fields` — unlikely to break the public idioms used here.)
