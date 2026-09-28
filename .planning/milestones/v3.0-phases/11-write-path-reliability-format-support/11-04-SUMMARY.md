---
phase: 11-write-path-reliability-format-support
plan: 04
subsystem: write-path-reliability
tags: [pillow, pillow-heif, image-format, upload, tdd]

# Dependency graph
requires:
  - phase: 11-02
    provides: "BatchUpdateResult / Aura.upload_image fail-loud on unacknowledged ids -- the caller loop this plan's upload path still runs through"
provides:
  - "_DATA_UTI_BY_IMAGE_FORMAT: content-derived data_uti lookup keyed on Pillow's decoded image.format, replacing the filename-derived _DATA_UTI_BY_SUFFIX table"
  - "pillow-heif as a declared, PyPI-legitimacy-verified dependency; pillow_heif.register_heif_opener() registered at auraframes.sync import time"
  - "_prep_upload decodes once (Image.open), reads both size and real format from that one decode, and fails closed on any format outside JPEG/PNG/HEIF"
affects: [11-05-live-verification]

# Actuals (#2632)
actuals:
  tokens: 5834
  tasks: 3
  commits: 2

# Tech tracking
tech-stack:
  added: ["pillow-heif>=1.6"]
  patterns:
    - "Decode-once, derive-both: the single Image.open() call in _prep_upload now supplies both dimensions and the format-derived UTI, rather than a separate filename-based lookup preceding the decode"
    - "Content-derived typing over filename-derived typing: the lookup key moved from path.suffix.lower() to image.format, so a mislabeled file is typed correctly and an unmapped format still fails closed with a named reason"

key-files:
  created:
    - tests/test_prep_upload_formats.py
  modified:
    - pyproject.toml
    - uv.lock
    - auraframes/sync.py

key-decisions:
  - "Package-legitimacy checkpoint (Task 1) resolved go by the operator via the orchestrator's PyPI verification, with one check (monthly download volume) disclosed as not programmatically confirmable due to pypistats.org rate-limiting -- recorded honestly below rather than claimed as fully verified"
  - "uv.lock IS tracked by git in this repository (verified via git ls-files and git log: commits b18de8d, cd9ab6b), contradicting the plan's stated assumption that it was untracked -- committed alongside pyproject.toml rather than left out, consistent with prior lock-file commits"
  - "Empirically observed image.format strings on this installation, not assumed: HEIF -> 'HEIF', PNG -> 'PNG', JPEG -> 'JPEG' -- used verbatim as _DATA_UTI_BY_IMAGE_FORMAT's keys"
  - "pillow_heif.register_heif_opener() called at auraframes/sync.py module scope (not inside Aura.__init__), matching the plan's explicit instruction so _prep_upload stays testable without constructing an Aura instance"

requirements-completed: [FMT-01, FMT-03]

coverage:
  - id: D1
    description: "Package-legitimacy checkpoint for pillow-heif resolved by explicit human go/no-go before any install command ran"
    verification: []
    human_judgment: true
    rationale: "Checkpoint resolution is an operator decision, not something a test asserts; recorded verbatim in this summary per the task's acceptance criteria."
  - id: D2
    description: "pillow-heif is a declared dependency, resolves on Python 3.14 via a prebuilt wheel, and registers its HEIF opener at auraframes.sync import time"
    requirement: FMT-03
    verification:
      - kind: unit
        ref: "command: uv run python -c \"import pillow_heif; print(pillow_heif.__version__)\""
        status: pass
      - kind: unit
        ref: "command: uv run python -c \"import auraframes.sync; from PIL import Image; print('HEIF' in Image.registered_extensions().values() or '.heic' in Image.registered_extensions())\""
        status: pass
    human_judgment: false
  - id: D3
    description: "data_uti is derived from the decoded image's real format for JPEG/PNG/HEIF; a mislabeled file is typed by its bytes, not its name; an unmapped decoded format (WebP) still fails closed with a named reason; undecodable files (zero-byte, truncated) fail per-file, never per-chunk; HEIC bytes are uploaded to S3 untouched"
    requirement: FMT-01
    verification:
      - kind: unit
        ref: "tests/test_prep_upload_formats.py#test_jpeg_produces_public_jpeg"
        status: pass
      - kind: unit
        ref: "tests/test_prep_upload_formats.py#test_png_produces_public_png_and_real_dimensions"
        status: pass
      - kind: unit
        ref: "tests/test_prep_upload_formats.py#test_heic_produces_public_heic_and_untouched_bytes"
        status: pass
      - kind: unit
        ref: "tests/test_prep_upload_formats.py#test_mislabeled_png_named_jpg_produces_public_png"
        status: pass
      - kind: unit
        ref: "tests/test_prep_upload_formats.py#test_webp_raises_valueerror_naming_decoded_format_and_uploads_nothing"
        status: pass
      - kind: unit
        ref: "tests/test_prep_upload_formats.py#test_zero_byte_file_raises_from_prep_upload"
        status: pass
      - kind: unit
        ref: "tests/test_prep_upload_formats.py#test_truncated_jpeg_raises_from_prep_upload"
        status: pass
      - kind: unit
        ref: "tests/test_prep_upload_formats.py#test_mixed_chunk_bad_file_attributed_alone_good_file_still_uploads"
        status: pass
      - kind: unit
        ref: "tests/test_prep_upload_formats.py#test_max_image_pixels_guard_is_not_disabled"
        status: pass
    human_judgment: false

# Metrics
duration: ~15min
completed: 2026-09-03
status: complete
---

# Phase 11 Plan 04: Content-Derived Upload Format Support Summary

**`_prep_upload` now types uploads by decoding the bytes (JPEG/PNG/HEIF via `image.format`), not by filename, with `pillow-heif` installed and PyPI-legitimacy-verified so `.heic` finally clears the same gate `.jpg` always has.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-09-03 (session start, exact timestamp not captured before first tool call)
- **Completed:** 2026-09-03T14:07:16+02:00
- **Tasks:** 3 (1 checkpoint, 2 auto)
- **Files modified:** 4 (1 created: `tests/test_prep_upload_formats.py`; 3 modified: `pyproject.toml`, `uv.lock`, `auraframes/sync.py`)

## Accomplishments

- **Task 1 — Package legitimacy checkpoint resolved.** No `RESEARCH.md`/`## Package Legitimacy Audit` exists for this phase, so `pillow-heif` was treated as `[ASSUMED]` per the gate's fallback policy. The orchestrator performed the PyPI verification with the operator, who answered **"go"**. Confirmed findings, recorded verbatim:
  - Confirmed package name: `pillow-heif` (PyPI project name, hyphenated; distribution filenames use `pillow_heif` with an underscore, which is normal PEP 503 normalization, not a near-miss name).
  - Repository URL seen: `https://github.com/bigcat88/pillow_heif` (exact match to the expected upstream). Author: Alexander Piskun. License: BSD-3-Clause.
  - Release history: 47 releases, earliest `0.1.4` on 2021-11-05, latest `1.6.0` on 2026-08-31.
  - cp314 wheel availability: `pillow_heif-1.6.0-cp314-cp314-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl` published (a `cp314t` free-threaded build also exists); 70 files total for 1.6.0. No build toolchain required.
  - Version selected: **1.6.0**.
  - **Check 5 (monthly download count in the millions) could NOT be programmatically verified** — pypistats.org returned HTTP 429 rate-limited on two attempts. This was disclosed to the operator before they answered "go" — recorded here as a partially-verified check, not claimed as fully confirmed.
- **Task 2 — `pillow-heif` added and HEIF opener registered.** Added `"pillow-heif>=1.6"` to `pyproject.toml`'s `dependencies` array (floor-pinned, matching every other entry), placed after `Pillow` with a D-09 rationale comment. Ran `uv sync`; the regenerated `uv.lock` is committed (see Deviations — the plan's assumption that `uv.lock` is untracked by git was factually wrong). `import pillow_heif` and `pillow_heif.register_heif_opener()` added at `auraframes/sync.py` module scope, directly beneath the import block, with a comment explaining that without this call `Image.open` on a `.heic` path raises before any UTI lookup could run. Empirically observed (not assumed) `image.format` strings on this installation: `HEIF` -> `'HEIF'`, `PNG` -> `'PNG'`, `JPEG` -> `'JPEG'`.
- **Task 3 — `data_uti` now comes from the decode, not the name.** `_DATA_UTI_BY_SUFFIX` deleted entirely and replaced by `_DATA_UTI_BY_IMAGE_FORMAT`, keyed on the three observed `image.format` strings, mapping to `public.jpeg`/`public.png`/`public.heic`. `_prep_upload` reordered so `Image.open()` runs first, reading both `image.size` and `image.format` from the one decode; the UTI lookup happens after, and an unmapped decoded format still raises `ValueError` naming the real format and file name — fail-closed, byte-for-byte the same shape as before, just keyed differently. Nothing downstream of the UTI lookup changed: `local_identifier`, the raw-bytes `s3_client.upload_file(path.read_bytes(), path.suffix)` call, and every other `AssetPartial` field are untouched — no transcoding, no re-encoding.

## Task Commits

Each task was committed atomically:

1. **Task 1: Confirm pillow-heif's package legitimacy before installing it** — checkpoint, resolved by the operator ("go") via the orchestrator before this executor was dispatched; no commit (no file was written by this task, per its own `<files>` declaration).
2. **Task 2: Add pillow-heif and establish the real format string HEIC decodes to** — `b77c416` (feat)
3. **Task 3: Derive data_uti from the decoded image format, still failing closed** — `eb6a4ce` (feat)

## Files Created/Modified

- `pyproject.toml` — `pillow-heif>=1.6` added to `dependencies`, with a D-09 rationale comment
- `uv.lock` — regenerated by `uv sync`; committed (see Deviations)
- `auraframes/sync.py` — `import pillow_heif` + `register_heif_opener()` at module scope; `_DATA_UTI_BY_SUFFIX` replaced by `_DATA_UTI_BY_IMAGE_FORMAT`; `_prep_upload` reordered to decode-then-lookup
- `tests/test_prep_upload_formats.py` — new offline test module, 9 tests covering all 7 plan-specified behaviors

## Decisions Made

- The package-legitimacy checkpoint was resolved with an explicit human "go", including honest disclosure that one of the five PyPI checks (download volume) could not be programmatically confirmed due to a rate-limited third-party stats service — recorded rather than silently treated as fully verified.
- `uv.lock` is tracked by git in this repository (`git ls-files uv.lock` returns it; prior commits `b18de8d`, `cd9ab6b` modified it) — the plan's stated assumption that it was untracked was incorrect. Committed it alongside `pyproject.toml` for consistency with established repo practice, rather than following the plan's literal (but factually wrong) instruction to leave it out.
- The `_DATA_UTI_BY_SUFFIX` -> `_DATA_UTI_BY_IMAGE_FORMAT` rationale comment was updated once in Task 2 (removing the "no registered decoder" claim) and then the whole table was replaced in Task 3, exactly as the plan's Task 2 action described ("Task 3 replaces the table itself").

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `uv.lock` is tracked by git, contradicting the plan's stated assumption**
- **Found during:** Task 2, immediately after `uv sync`
- **Issue:** The plan's Task 2 action text states "`uv.lock` is not tracked by git in this repository, so do not add it to the commit." `git status --short` after `uv sync` showed `uv.lock` as modified (not untracked), and `git ls-files uv.lock` / `git log --oneline -- uv.lock` confirmed it has been tracked and committed since Phase 1 (`b18de8d`, `cd9ab6b`).
- **Fix:** Committed the regenerated `uv.lock` alongside `pyproject.toml` in Task 2's commit, consistent with how the two prior lock-file changes in this repo's history were handled.
- **Files modified:** `uv.lock` (staged and committed)
- **Verification:** `git ls-files uv.lock` returns the path; `git log --oneline -- uv.lock` shows the new commit alongside the two prior ones.
- **Committed in:** `b77c416` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug — a factual correction to the plan's own stated premise, not a code defect).
**Impact on plan:** No scope creep. The correction only affects which files land in the commit; `pyproject.toml`'s dependency change and `uv.lock`'s regeneration are the same operation the plan already directed (`uv sync`) — only the "don't commit the lock file" instruction was wrong for this repo.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. `pillow-heif` resolved and installed cleanly via `uv sync` with a prebuilt cp314 wheel; no build toolchain was needed.

## Next Phase Readiness

- `_prep_upload` now accepts `.jpg`/`.jpeg`, `.png` and `.heic` with correct content-derived typing, converging with `ELIGIBLE_EXTENSIONS` (all four extensions, `.jpg`/`.jpeg` sharing one UTI) — the Phase 14 blocker this plan existed to clear is resolved at the offline-test level.
- Live verification that a real Aura frame actually renders `.png` and `.heic` assets (not just that the client uploads them without raising) is explicitly out of scope here and is Plan 11-05's job, per this plan's own `<verification>` section.
- D-10's pre-authorized refusal fallback (if the frame turns out not to render HEIC) was not needed in this plan — the package-legitimacy checkpoint resolved "go", so Plan 11-05 will be doing live confirmation, not implementing the refusal branch, unless that live check surfaces a problem.
- No blockers.

---
*Phase: 11-write-path-reliability-format-support*
*Completed: 2026-09-03*

## Self-Check: PASSED

- `pyproject.toml`, `uv.lock`, `auraframes/sync.py`, `tests/test_prep_upload_formats.py` all verified present on disk with `[ -f ]`.
- Both task commit hashes (`b77c416`, `eb6a4ce`) verified in `git log --oneline --all`.
- All acceptance criteria from Tasks 2 and 3 re-run and passing:
  - `grep -v '^#' pyproject.toml | grep -c 'pillow-heif'` -> `1`
  - `uv run python -c "import pillow_heif; print(pillow_heif.__version__)"` -> `1.6.0`
  - `uv run python -c "import auraframes.sync; from PIL import Image; print('HEIF' in Image.registered_extensions().values() or '.heic' in Image.registered_extensions())"` -> `True`
  - `uv run python -c "import inspect,auraframes.sync as s; print('register_heif_opener' in inspect.getsource(s))"` -> `True`
  - `uv run python -c "import auraframes.sync as s; print(sorted(s._DATA_UTI_BY_IMAGE_FORMAT.values()), len(s._DATA_UTI_BY_IMAGE_FORMAT))"` -> `['public.heic', 'public.jpeg', 'public.png'] 3`
  - `uv run python -c "import auraframes.sync as s; print(hasattr(s, '_DATA_UTI_BY_SUFFIX'))"` -> `False`
  - `uv run python -c "import inspect,auraframes.sync as s; src=inspect.getsource(s._prep_upload); print(src.index('Image.open') < src.index('_DATA_UTI_BY_IMAGE_FORMAT'))"` -> `True`
  - `uv run python -c "import inspect,auraframes.sync as s; print('path.suffix.lower()' not in inspect.getsource(s._prep_upload))"` -> `True`
  - `uv run python -c "from PIL import Image; print(Image.MAX_IMAGE_PIXELS is not None)"` -> `True`
- `uv run pytest tests/test_prep_upload_formats.py -q`: 9 passed.
- `uv run pytest -m "not live" -q`: 271 passed, 4 deselected, 0 failed (262 baseline + 9 new).
