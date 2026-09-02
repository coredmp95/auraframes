---
phase: 07-sync-diffing-engine-dry-run-only
reviewed: 2026-07-07T08:44:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - auraframes/cli.py
  - auraframes/sync.py
  - tests/test_cli_sync.py
  - tests/test_sync_engine.py
findings:
  critical: 1
  warning: 4
  info: 3
  total: 8
status: issues_found
---

# Phase 07: Code Review Report

**Reviewed:** 2026-07-07T08:44:00Z
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Reviewed the dry-run sync diff engine (`auraframes/sync.py`), its CLI wiring (`auraframes/cli.py::run_sync`), and both offline test suites. The multiset diff algorithm in `compute_plan` is sound and matches its documented semantics (verified by tracing every branch: matched/unchanged, surplus/delete, hashless/`frame_no_hash`, local-only/upload). The dry-run guarantee itself holds — no mutating call is reachable from `run_sync`.

However, `scan_directory` has a real, reproducible logic bug: pointing `sync` at a directory that does not exist (or that is actually a file, e.g. a typo'd path) does **not** raise or report an error. `Path.rglob('*')` silently yields nothing, so the function returns an empty `ScanResult`, and `run_sync` goes on to print a full "dry run" plan recommending every hashed asset currently on the frame be deleted — with exit code 0. I reproduced this directly against the offline harness (see CR-01). This is dangerous precisely because Phase 8's `execute_plan()` is expected to consume this same plan shape.

I also found a symlink-traversal gap that contradicts the module's own docstring claim, several quality issues (overly broad exception handling, non-deterministic output ordering, a test-side-effect on the real filesystem), and a couple of cosmetic/test-gap items.

## Critical Issues

### CR-01: Nonexistent/invalid `dir` argument is silently treated as an empty directory, producing a "delete everything" dry-run plan with exit code 0

**File:** `auraframes/sync.py:44` (`scan_directory`), consumed by `auraframes/cli.py:262-263` (`run_sync`)

**Issue:** `scan_directory` walks `root.rglob('*')` with no upfront check that `root` exists or is a directory. When `Path.rglob` is invoked on a path that does not exist, or on a path that is a regular file rather than a directory, it does not raise — it simply yields no entries. `scan_directory` therefore returns `ScanResult(local_hashes={}, skipped_non_image=0)` exactly as it would for a genuinely empty directory. Downstream, `compute_plan` sees zero local demand for every hash and marks **every** frame asset that has a `md5_hash` as a delete candidate. `run_sync` prints this as a normal dry-run report and returns `0` (success) — there is no error message, no warning, and no non-zero exit code indicating the user's `dir` argument was wrong.

Reproduced directly:
```
$ uv run python3 -c "
from auraframes.cli import run_sync
from tests.offline import offline_aura
... (frame asset with md5_hash set, one asset)
rc = run_sync('/tmp/this-dir-does-not-exist-abc123', 'Fake', aura=aura)
"
Sync plan for Fake Frame (id: frame-fake-0001) — DRY RUN, nothing will be changed
To upload: 0
To delete: 1
Unchanged: 0
  - asset-fake-001 (taken 2023-01-02 12:00:00)
rc= 0
```
The same silent-empty behavior occurs when `dir_arg` points at an existing regular file instead of a directory. A simple typo in the `dir` positional argument (or a directory not yet mounted/created) is indistinguishable from "this frame's photos have all been deleted locally," and nothing in the output signals that the scan target itself was invalid. This phase is dry-run only so no data loss occurs *yet*, but the plan produced is factually wrong and silently misleading, and this exact function is the intended foundation for Phase 8's `execute_plan()`.

**Fix:** Validate the scan root before treating an empty result as meaningful, and fail loudly (matching the codebase's existing D-05 fail-loud convention) rather than silently:
```python
# auraframes/sync.py
def scan_directory(root: Path) -> ScanResult:
    if not root.is_dir():
        raise NotADirectoryError(f'{root} is not an existing directory')
    ...
```
or equivalently, guard in `auraframes/cli.py::run_sync` before calling `scan_directory`:
```python
dir_path = Path(dir_arg)
if not dir_path.is_dir():
    print(f"'{dir_arg}' is not an existing directory")
    return 1
```
Add a regression test (see IN-01) covering both "directory does not exist" and "path is a file" to prevent silent re-introduction.

## Warnings

### WR-01: `scan_directory` follows symlinks to files outside the scanned directory, contradicting its own docstring

**File:** `auraframes/sync.py:30-56`

**Issue:** The docstring states traversal is bounded: *"`Path.rglob` does not follow directory symlinks, and only regular files (`is_file()`) are considered -- bounding traversal to real files under the user's own directory"*. This is only half true: `rglob` (Python 3.13+ `recurse_symlinks=False` default) indeed does not recurse into symlinked *directories* (verified), but a symlink to a *file* placed directly inside the scanned root is still matched by `rglob('*')`, and `p.is_file()` follows the symlink and returns `True`. `read_bytes()` then reads the *target's* content, wherever it lives on disk. Reproduced:
```python
# /tmp/symtest2/scanroot/link.jpg -> /tmp/symtest2/outside_secret.jpg (outside scanroot)
scan_directory(Path('/tmp/symtest2/scanroot'))
# => {'zdZf813zwGyOHNw+0+VWqw==': [Path('/tmp/symtest2/scanroot/link.jpg')]}
```
The file outside the scanned root was hashed and folded into the upload plan as if it were a real file under the target directory. If a user ever points `sync` at an untrusted/downloaded directory (e.g. an extracted archive) containing crafted symlinks, this silently pulls in and hashes files from anywhere else on disk the process can read.

**Fix:** Either explicitly document this behavior (drop the inaccurate "bounding" claim) or exclude symlinks explicitly:
```python
if not p.is_file() or p.is_symlink():
    continue
```

### WR-02: Overly broad `except Exception` collapses distinct failure modes into one misleading message

**File:** `auraframes/cli.py:243-285` (`run_sync`), also present in `run_inspect:176-214`

**Issue:** The single `try/except Exception as e` in `run_sync` wraps frame resolution, `aura.get_all_assets`, `scan_directory`, and `compute_plan` together. A local filesystem error surfaced from `scan_directory` (e.g. a `PermissionError` reading one file, or — per CR-01 — a bug that used to raise) is reported identically to a live API/auth failure: `Failed to sync frame: {e}`. This makes it hard for a user (or a bug report) to tell whether the problem is local (their directory) or remote (the API), and discards the traceback entirely.

**Fix:** Narrow the try block or add a nested boundary around the local scan so the message can distinguish local vs. remote failure, e.g.:
```python
try:
    scan = scan_directory(Path(dir_arg))
except OSError as e:
    print(f'Failed to scan {dir_arg}: {e}')
    return 1
```

### WR-03: `to_upload` ordering is filesystem-traversal-order-dependent, making dry-run output non-reproducible

**File:** `auraframes/sync.py:44`, `auraframes/sync.py:100`

**Issue:** `local_hashes` (and therefore the `to_upload` list built from `demand.items()`) is populated in whatever order `Path.rglob('*')` yields directory entries, which is OS/filesystem dependent and not sorted. Running `aura-cli sync` twice against the same directory on different machines (or the same machine after a filesystem defrag/reindex) can print the "To upload" list in a different order, which hurts diffability of dry-run output (e.g. users piping to `diff` between runs, or including it in a bug report).

**Fix:** Sort deterministically before printing, e.g. in `run_sync`:
```python
for path in sorted(plan.to_upload):
    print(f'  + {path}')
```

### WR-04: `_configure_cli_logging`'s default path writes real files to `<cwd>/logs/` during every offline test run, an unisolated shared side effect

**File:** `auraframes/cli.py:47-73`, exercised by every test in `tests/test_cli_sync.py` (all call `run_sync(..., aura=aura)` with the default `debug=False`)

**Issue:** Every `run_sync`/`run_status`/`run_inspect` call with `debug=False` (the test default) calls `os.makedirs('logs/', exist_ok=True)` and adds a real file sink at `logs/file_{time}.log`, relative to the process's current working directory — not `tmp_path`. This is confirmed happening in this checkout right now (`logs/*.log` files exist in the repo working tree from previous local/test runs). Under `pytest-xdist` or CI runners with a shared workspace, concurrent test processes race on the same `logs/` directory; more generally, tests should not have side effects on real project directories outside of `tmp_path`.

**Fix:** Consider allowing tests to inject a log directory (or monkeypatch `os.makedirs`/redirect via `monkeypatch.chdir(tmp_path)` in `tests/test_cli_sync.py`'s tests), so offline test runs are fully hermetic:
```python
def test_sync_...(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    ...
```

## Info

### IN-01: No test exercises a nonexistent/invalid `dir` argument — the exact gap behind CR-01

**File:** `tests/test_cli_sync.py`, `tests/test_sync_engine.py`

**Issue:** Neither test file has a case for `run_sync`/`scan_directory` being pointed at a directory that doesn't exist or at a path that is a file. This is precisely the scenario that produces the incorrect "delete everything" plan in CR-01 — a test here would have caught it before merge.

**Fix:** Add, once CR-01 is fixed:
```python
def test_sync_nonexistent_directory_fails_loudly(tmp_path, monkeypatch, capsys):
    _env(monkeypatch)
    missing = tmp_path / "does-not-exist"
    rc = run_sync(str(missing), 'Fake', aura=offline_aura())
    assert rc == 1
    assert 'To delete' not in capsys.readouterr().out
```

### IN-02: Incorrect pluralization in summary lines, locked in by the tests that assert on it

**File:** `auraframes/cli.py:277, 280`

**Issue:** `f'{plan.skipped_non_image} non-photo files skipped'` and `f'{plan.frame_no_hash} frame assets without a content hash...'` always use the plural form even when the count is `1` (e.g. "1 non-photo files skipped", "1 frame assets without a content hash"). `tests/test_cli_sync.py::test_sync_skips_non_image_files_with_summary_note` and `::test_sync_hashless_frame_asset_not_deleted` both assert on the grammatically-incorrect singular-count string, so the defect is now pinned by the test suite rather than caught by it.

**Fix:** Minor, cosmetic — pluralize conditionally if this is worth polishing before a public-facing CLI ships:
```python
noun = 'file' if plan.skipped_non_image == 1 else 'files'
print(f'{plan.skipped_non_image} non-photo {noun} skipped')
```

### IN-03: Loose `list` type hints instead of parameterized generics

**File:** `auraframes/sync.py:62, 68`

**Issue:** `SyncPlan.to_delete: list = field(default_factory=list)` and `compute_plan(local_hashes: ..., frame_assets: list, ...)` use bare `list` rather than `list[Asset]`. CLAUDE.md documents "Type hints used on all public method signatures" as a project convention; these hints are present but imprecise, weakening IDE/type-checker support for the exact item type callers should expect.

**Fix:**
```python
from auraframes.models.asset import Asset

@dataclass
class SyncPlan:
    to_upload: list[Path] = field(default_factory=list)
    to_delete: list[Asset] = field(default_factory=list)
    ...

def compute_plan(local_hashes: dict[str, list[Path]], frame_assets: list[Asset], skipped_non_image: int = 0) -> SyncPlan:
    ...
```

---

_Reviewed: 2026-07-07T08:44:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
