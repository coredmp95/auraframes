---
phase: 01-toolchain-revival
verified: 2026-06-29T11:00:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
re_verification: false
---

# Phase 01: Toolchain Revival — Verification Report

**Phase Goal:** The project installs, builds, and imports cleanly on Python 3.14 managed by `uv`, with the pydantic model layer running on v2.
**Verified:** 2026-06-29
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `uv sync` resolves and installs every dependency on Python 3.14 with no build failures | VERIFIED | `uv sync --python 3.14 --extra dev` exits 0; 37 packages resolved (all cp314 wheels, 0 sdist builds). Live run confirmed. |
| 2 | `pyproject.toml` defines the project and dependencies; UTF-16 `requirements.txt` is gone | VERIFIED | `pyproject.toml` exists with `[project]`, `requires-python = ">=3.14"`, 11 `>=`-floored deps, `dev` extra, `[build-system]`/hatchling. `requirements.txt` absent on disk and untracked in git. |
| 3 | `import auraframes` and all `auraframes/models/*` modules import without error under pydantic v2 | VERIFIED | `uv run pytest -q tests/test_imports.py` → 9/9 passed. Explicit full-package import command exits 0. Pydantic runtime: 2.13.4. `-W error::DeprecationWarning` raises no `PydanticDeprecatedSince20`. |
| 4 | Partial models (`FramePartial` via `make_partial` factory) still expose all fields as optional | VERIFIED | `all(not f.is_required() for f in FramePartial.model_fields.values())` is True. `FramePartial(name='x').model_dump(exclude_unset=True) == {'name': 'x'}`. `isinstance(FramePartial(), Frame)` is True. `is_portrait` and `get_frame_type` methods survive on the partial. |

**Score:** 4/4 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `pyproject.toml` | Single dependency manifest with `[project]` and `>=` floors | VERIFIED | Contains `name = "auraframes"`, `requires-python = ">=3.14"`, 11 runtime deps, `dev` extra with `pytest>=8`, hatchling build backend. No exact pins (`==`) found. |
| `uv.lock` | Hash-pinned resolved dependency tree for Python 3.14 | VERIFIED | Exists on disk. `version = 1` header confirmed. 37 packages. Committed in git (`b18de8d`). |
| `.python-version` | Interpreter pin so bare `uv run` selects Python 3.14 | VERIFIED | Contains `3.14`. Committed in git (un-ignored via `!.python-version` in `.gitignore`). |
| `auraframes/models/meta.py` | v2 `make_partial` factory replacing `AllOptional` | VERIFIED | Exports `make_partial(model, name)`. Uses `create_model(__base__=model)`. No `pydantic.main.ModelMetaclass` or `AllOptional` reference. |
| `auraframes/utils/io.py` | v2 JSON serialization via `model_dump(mode="json")` | VERIFIED | `_pydantic_default` callable using `model_dump(mode="json")` passed as `default=` to `json.dump`. No `pydantic.json` or `pydantic_encoder`. Single + list branches both work (behavioral spot-check passed). |
| `auraframes/models/frame.py` | `FramePartial` built via factory; base-model `Optional` fields defaulted to `None` | VERIFIED | `FramePartial = make_partial(Frame, "FramePartial")` at line 93. `Frame.model_fields["deleted_at"].is_required()` is False. `Frame.model_fields["frame_type"].is_required()` is False. |
| `auraframes/models/asset.py` | `@field_validator` on `AssetPartialId`; base-model `Optional` fields defaulted to `None` | VERIFIED | Imports `field_validator, ValidationInfo`. `AssetPartialId.check_id_or_local_id` uses `@field_validator('id')` + `@classmethod`. `Asset.model_fields["favorite"].is_required()` is False. |
| `tests/test_imports.py` | Import smoke test + `FramePartial` all-optional assertion | VERIFIED | 8 parametrized import cases + 1 `test_framepartial_all_optional` test. References `is_required` and `importlib.import_module`. All 9 pass under `uv run pytest`. |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `auraframes/models/frame.py` | `auraframes/models/meta.py` | `make_partial(Frame, "FramePartial")` | WIRED | Line 7 imports `make_partial`; line 93 uses it. `FramePartial` is the return value. |
| `tests/test_imports.py` | `FramePartial.model_fields` | `is_required()` assertion | WIRED | `test_framepartial_all_optional` imports `FramePartial` and asserts `not f.is_required()` for all fields. Passes at runtime. |
| `pyproject.toml` | `uv.lock` | `uv lock --python 3.14` | WIRED | `uv.lock` names `auraframes` as the project; `requires-python = ">=3.14"` carries through. Lock committed (`b18de8d`). |

---

### Data-Flow Trace (Level 4)

Not applicable. This phase produces no components that render dynamic data. All artifacts are toolchain configuration files, model definitions, or import tests.

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `uv sync` installs 37 deps, no build errors | `uv sync --python 3.14 --extra dev` | exit 0, 37 packages resolved | PASS |
| All runtime deps importable | `uv run python -c "import pydantic, PIL, h2, boto3, httpx, geopy, loguru, tqdm"` | `all-runtime-imports-ok`, exit 0 | PASS |
| Full package import clean | `uv run python -c "import auraframes, auraframes.models.user, ..."` | `full package import clean`, exit 0 | PASS |
| `FramePartial` all-optional + methods survive | `uv run python -c "from auraframes.models.frame import FramePartial, Frame; ..."` | All asserts pass, exit 0 | PASS |
| No deprecation warnings from `field_validator` | `uv run python -W error::DeprecationWarning -c "import auraframes.models.asset"` | No `PydanticDeprecatedSince20`, exit 0 | PASS |
| `write_model` handles single and list branches | `uv run python -c "from auraframes.utils.io import write_model; ..."` | `write_model single+list both work`, exit 0 | PASS |
| Import smoke test suite | `uv run pytest -q tests/test_imports.py` | `9 passed in 0.08s`, exit 0 | PASS |

---

### Probe Execution

No probe scripts declared in plans or present under `scripts/`. Skipped.

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| ENV-01 | 01-01 | Dependency management migrated to `uv` with `pyproject.toml`; UTF-16 `requirements.txt` deleted | SATISFIED | `pyproject.toml` committed. `requirements.txt` absent on disk and untracked. |
| ENV-02 | 01-01 | All dependencies resolve and install on Python 3.14 via `uv` | SATISFIED | `uv sync --python 3.14 --extra dev` exits 0; 37 packages, all cp314 wheels. |
| ENV-03 | 01-02 | Pydantic model layer migrated to v2, `AllOptional` partial behaviour preserved | SATISFIED | Pydantic 2.13.4 installed. `make_partial` factory replaces metaclass. 9/9 smoke tests pass. No v1 internals remain. |

No orphaned requirements found. REQUIREMENTS.md traceability table maps ENV-01, ENV-02, ENV-03 exclusively to Phase 1 — all accounted for and satisfied.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `auraframes/models/frame.py` | 77–78 | `# TODO` comments on `playlists` and `delivered_frame_gift` fields | Info | Pre-existing (present in original codebase before 5ac96b7). Not introduced by this phase. No impact on Phase 1 goal. |
| `auraframes/models/asset.py` | 26 | `# TODO: Have only seen "user"` on `AssetSetting.reason` | Info | Pre-existing. Not introduced by this phase. |

No `TBD`, `FIXME`, or `XXX` markers found in any file modified by this phase. No blockers.

---

### Review Findings Carryover (from 01-REVIEW.md)

The code review (`01-REVIEW.md`) identified 1 Critical and 3 Warnings. These are **not blockers for the Phase 1 import/install goal** — they are pre-existing behavioral defects or latent logic errors explicitly deferred by the plan. Recorded here for Phase 2 traceability:

| Finding | File | Nature | Phase 1 Impact | Deferral |
|---------|------|--------|---------------|----------|
| CR-01: `AssetPartialId` cross-field validator is non-functional | `asset.py:118` | Faithful straight-port preserves pre-existing latent field-ordering no-op (plan Q#2). `AssetPartialId()` with neither field is silently accepted. | None — import succeeds; runtime invariant is broken but Phase 1 does not instantiate `AssetPartialId` | Phase 2 per plan Q#2: replace with `@model_validator(mode="after")` |
| WR-01: `build_path` raises `FileNotFoundError` for bare filename | `io.py:11` | Pre-existing bug (identical in original `io.py`). `os.makedirs('')` raises when dirname is empty. | None — Phase 1 does not call `build_path` | Phase 2 / as needed |
| WR-02: `Asset.is_local_asset` always `False` | `asset.py:109` | Pre-existing latent logic error. `id: str` is required so `self.id is None` can never be True. | None | Phase 2 semantics decision |
| WR-03: `Frame.get_frame_type` treats `frame_type == 0` as missing | `frame.py:90` | Truthiness check vs. `None` check. Pre-existing. | None | Phase 2 / as needed |
| IN-01: Unused `import pydantic` in `frame.py` | `frame.py:4` | Dead import. Not introduced by this phase (verified via `git diff`). | None | Minor cleanup |

---

### Human Verification Required

None. All Phase 1 success criteria are programmatically verifiable and verified.

---

### Gaps Summary

No gaps. All 4 success criteria are VERIFIED by live command execution against the actual codebase.

---

_Verified: 2026-06-29_
_Verifier: Claude (gsd-verifier)_
