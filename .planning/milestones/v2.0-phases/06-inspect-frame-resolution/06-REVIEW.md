---
phase: 06-inspect-frame-resolution
reviewed: 2026-07-07T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - auraframes/cli.py
  - tests/fixtures/frame_detail.json
  - tests/offline.py
  - tests/test_cli_inspect.py
findings:
  critical: 0
  warning: 3
  info: 2
  total: 5
status: issues_found
---

# Phase 06: Code Review Report

**Reviewed:** 2026-07-07T00:00:00Z
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Reviewed the `inspect --frame <name|id>` command (`auraframes/cli.py`'s `resolve_frame()`
and `run_inspect()`), its offline test suite (`tests/test_cli_inspect.py`), the new
`frame_detail.json` fixture, and the routing addition in `tests/offline.py`. Ran the full
6-test offline suite (`uv run pytest tests/test_cli_inspect.py -q` → 6 passed) and also
exercised `run_inspect()` directly against the offline fixtures to observe actual stdout,
which is what surfaced WR-03 below.

No Critical/blocker issues — no secrets leaked, no crashes on the tested paths, and the
frame-resolution logic (`resolve_frame()`) correctly implements the documented D-01..D-04
precedence (name-substring match, ambiguous short-circuit before id fallback, id fallback
only on zero name matches). Three Warnings: an inconsistency between `run_status()` and
`run_inspect()`'s post-login error handling (the same defect class Phase 5's review already
flagged in `run_status()` was fixed only in the new `run_inspect()` sibling, not backported),
an overly broad fixture-routing predicate in `tests/offline.py` that will silently misroute
several real API paths to the frame-detail fixture instead of a 404, and a demonstrated
count mismatch in `inspect`'s own output between the frame-metadata "Assets" line and the
paginated "Photos" line. Two Info items on duplicated boilerplate and directly-executed I/O
side effects during "offline" tests.

## Warnings

### WR-01: `run_status()` still has the unguarded post-login crash that `run_inspect()` was written to avoid

**File:** `auraframes/cli.py:100-104` (contrast with `auraframes/cli.py:171-205`)
**Issue:** Phase 5's code review (`.planning/phases/05-cli-skeleton-status/05-REVIEW.md`,
WR-01) flagged that `run_status()` wraps only `aura.login()` in a `try/except Exception`;
the subsequent `aura.frame_api.get_frames()` call and the `for frame in frames` loop are
unguarded, so a non-2xx `/frames.json` response (`httpx.HTTPStatusError` via
`response.raise_for_status()`) or a `frames` key drift (`TypeError` iterating `None` in
`FrameApi.get_frames()`) crashes the CLI with a raw traceback instead of the
`print(...); return 1` contract every other failure path follows.

This phase's `run_inspect()` explicitly fixes the identical defect class one function
below — its comment at `cli.py:205-207` even cites `"WR-01 fail-loud (D-05)"` as the
rationale for wrapping `get_frames()`/`resolve_frame()`/`get_frame()`/`get_all_assets()` in
a broad `try/except`. Since `cli.py` was rewritten wholesale this phase (the diff shows the
entire file as new), this was the opportunity to backport the same one-line fix to
`run_status()`, but it wasn't — the two sibling command handlers now have inconsistent
failure-mode guarantees for the exact same underlying API call (`get_frames()`).
**Fix:** Extend `run_status()`'s try block to cover the post-login work, mirroring
`run_inspect()`'s pattern:
```python
try:
    aura.login()
    frames = aura.frame_api.get_frames()
except Exception as e:
    print(f'Login failed: {e}')
    return 1

print(f'Logged in as {os.getenv("AURA_EMAIL")}')
print(f'{len(frames)} frames:')
for frame in frames:
    print(f'  - {frame.name} (id: {frame.id})')
return 0
```
Add a regression test (`offline_aura(overrides={'/v5/frames.json': httpx.Response(500, ...)})`)
in `tests/test_cli_status.py` to lock in exit-code-1 behavior, matching the equivalent
coverage this phase already added for `inspect`.

### WR-02: `tests/offline.py`'s frame-detail routing predicate is broader than the endpoints it's meant to cover

**File:** `tests/offline.py:50-55`
**Issue:** The branch added for the Phase 6 `get_frame()` detail route is:
```python
if path.startswith("/v5/frames/") and path.endswith(".json") \
        and "/assets" not in path and "/activities" not in path:
    return httpx.Response(200, json=_load("frame_detail.json"))
```
This matches *any* `/v5/frames/{id}/...json` path that doesn't literally contain the
substrings `/assets` or `/activities` — not just the intended `/v5/frames/{id}.json`
detail route. Verified against `FrameApi`'s other real endpoints that share the same
`/frames/{id}/...` prefix and a `.json` suffix and would therefore be silently misrouted
to `frame_detail.json` instead of the default 404 fallback:
- `/frames/{id}/goto.json` (`show_asset`)
- `/frames/{id}.json` via `update_frame`'s PUT (correct endpoint, but routed here even for
  PUT — the router doesn't check `request.method`, so a PUT to update a frame would
  currently receive back a *read* fixture shaped like a `get_frame()` response)
- `/frames/{id}/reconfigure.json`, `/frames/{id}/add_playlist.json`,
  `/frames/{id}/remove_playlist.json`, `/frames/{id}/select_asset.json` (contains
  `select_asset`, not `/assets`, so the exclusion doesn't catch it)

None of these are exercised by the current test suite, so nothing fails today, but the
first future offline test that hits one of them (e.g. an offline `update_frame()` or
`select_asset()` test) will get a confusing false-positive 200 with unrelated
frame-detail JSON instead of a clear 404/shape-mismatch signal, making the resulting test
failure much harder to diagnose than "endpoint not routed."
**Fix:** Narrow the predicate to the exact detail path shape, and consider checking the
HTTP method:
```python
import re
_FRAME_DETAIL_RE = re.compile(r"^/v5/frames/[^/]+\.json$")
...
if request.method == "GET" and _FRAME_DETAIL_RE.match(path):
    return httpx.Response(200, json=_load("frame_detail.json"))
```

### WR-03: `inspect`'s "Assets" count and "Photos (showing X of Y)" count can disagree with no indication to the user

**File:** `auraframes/cli.py:195-199`
**Issue:** Running `run_inspect()` against this phase's own offline fixtures reproduces a
visible inconsistency:
```
Assets: 3
Photos (showing 2 of 2, API order):
```
`Assets: 3` comes from `FrameApi.get_frame()`'s `total_asset_count` return value
(`frame_detail.json`'s top-level `"total_asset_count": 3"`), while `Photos (showing 2 of 2...)`
comes from `len(aura.get_all_assets(...))`, the actual paginated asset list
(`assets_page1.json` + `assets_page2.json` = 2 assets total). The two numbers are sourced
from independent API responses that the codebase already documents as prone to drift
(`frameApi.py`'s "Phase 2 live drift" comment on `total_asset_count`/`num_assets`), and
this phase's own `06-02-SUMMARY.md` records the same divergence being observed live
("`Assets: 77`... differs from the actual paginated total (106)") and explicitly treats it
as accepted, non-actionable drift rather than a defect to fix.
Surfacing this to a real end user with zero context (no footnote, no caveat) reads as the
tool being broken or lying about how many photos exist, even though the root cause is
understood and was a conscious scope decision.
**Fix:** At minimum, note the possible divergence when it's observed, e.g.:
```python
if total_asset_count is not None and total_asset_count != len(assets):
    print(f'Assets: {total_asset_count} (frame metadata; {len(assets)} returned by the '
          f'asset list endpoint — known API drift, see PROJECT.md)')
else:
    print(f'Assets: {total_asset_count}')
```
so the discrepancy reads as a documented quirk instead of an apparent bug.

## Info

### IN-01: Duplicated login-guard boilerplate between `run_status()` and `run_inspect()`

**File:** `auraframes/cli.py:87-98`, `auraframes/cli.py:158-169`
**Issue:** The `aura = aura or Aura()` / `_configure_cli_logging(debug)` /
`try: aura.login() except Exception as e: print(f'Login failed: {e}'); return 1` sequence,
plus its accompanying comment block, is duplicated verbatim between the two command
handlers. `sync`/`upload` (Phases 7-8, per `06-CONTEXT.md`) will need the same sequence
again, tripling the duplication.
**Fix:** Extract a small helper, e.g.:
```python
def _login_or_none(aura, debug: bool) -> Aura | None:
    _configure_cli_logging(debug)
    try:
        aura.login()
        return aura
    except Exception as e:
        print(f'Login failed: {e}')
        return None
```
and have each handler do `aura = aura or Aura(); aura = _login_or_none(aura, debug); if aura is None: return 1`.

### IN-02: "Offline" tests perform real filesystem I/O via `_configure_cli_logging()`

**File:** `auraframes/cli.py:65-68`, exercised by every test in `tests/test_cli_inspect.py`
**Issue:** Every `run_inspect()` call in this suite (all 6 tests, default `debug=False`)
runs `_configure_cli_logging(False)`, which does `os.makedirs('logs/', exist_ok=True)` and
`logger.add('logs/file_{time}.log')` — real directory/file creation relative to the
process's current working directory, not mocked or redirected in tests. `logs/` is
gitignored so this doesn't dirty git status, but the test module's own docstring
advertises "runs with zero network access" without mentioning it also performs real disk
writes on every run, which could surprise a future editor relying on that docstring, and
makes the suite's actual side effects (and behavior under a read-only CWD, e.g. some CI
sandboxes) less obvious than "offline" implies.
**Fix:** Not blocking, but consider a `tmp_path`-based `monkeypatch.chdir()` fixture (or
patching `logger.add` in tests) if fully side-effect-free test runs become a goal.

---

_Reviewed: 2026-07-07T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
