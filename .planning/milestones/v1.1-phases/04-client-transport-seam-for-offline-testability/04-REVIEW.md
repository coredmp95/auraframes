---
phase: 04-client-transport-seam-for-offline-testability
reviewed: 2026-07-04T17:25:46Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - auraframes/aura.py
  - auraframes/client.py
  - tests/fixtures/assets_page1.json
  - tests/fixtures/assets_page2.json
  - tests/fixtures/error_envelope.json
  - tests/fixtures/frames.json
  - tests/fixtures/login.json
  - tests/offline.py
  - tests/test_fixtures_validity.py
  - tests/test_offline_read_path.py
findings:
  critical: 0
  warning: 1
  info: 3
  total: 4
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-07-04T17:25:46Z
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Reviewed the additive transport-seam change (`Client(transport=...)`, `Aura(client=...)`), the `Aura.login()` default-argument fix, and the new offline fixture/harness/test suite. The core seam is sound: `httpx.Client`'s `transport` parameter defaults to `None` identically whether passed explicitly or omitted, so live callers (`main.py`, `tests/conftest.py`) are unaffected; the `login()` fix correctly moves `os.getenv(...)` evaluation from import/def-time (stale/mutable-default bug) to call-time. All 9 offline tests pass, and Pydantic hydration was verified against every required field on `Frame`, `Asset`, and `User` for all four fixture files.

One real, reproducible defect was found: the new `offline_aura()` helper is designed to be instantiated fresh per test (not session-scoped), and `Aura._init_logger()` unconditionally calls `logger.add(...)` on the global loguru singleton with no idempotency guard. This causes duplicate stderr log lines and an unbounded, ever-growing set of orphaned log files under `logs/` — confirmed empirically (3 `Aura()` instantiations produced 7 live handlers and progressively 1x/2x/3x-duplicated log lines, plus 3 new log files left on disk). This is a genuine bug that predates this phase but is directly and repeatedly triggered by the exact usage pattern this phase's harness introduces, and will get worse as more offline tests are added (the stated intent of `tests/offline.py`).

The remaining findings are minor coverage/robustness gaps in the new test harness.

## Warnings

### WR-01: `Aura._init_logger()` leaks loguru sinks and log files on every `Aura()` instantiation, and the new offline harness triggers this repeatedly per test run

**File:** `auraframes/aura.py:136-145` (triggered via `tests/offline.py:56-66`)
**Issue:** `_init_logger()` is called unconditionally from `Aura.__init__` and always calls `logger.add(sys.stderr, ...)` and `logger.add('logs/file_{time}.log')` with no check for whether sinks were already registered. `loguru.logger` is a process-wide global singleton, so each `Aura()` instance permanently adds two more sinks that are never removed for the lifetime of the process.

Previously this was low-impact because both `main.py` and the live `aura` fixture in `tests/conftest.py` instantiate `Aura()` exactly once per process (the live fixture is `scope="session"`). This phase's `tests/offline.py::offline_aura()` is explicitly designed to be called fresh, non-session-scoped, once per test (`tests/test_offline_read_path.py` calls it 4 separate times, plus a 5th bare `Client()` construction) — this is exactly the repeated-instantiation pattern that turns the latent bug into an actively-observed one.

Reproduced directly:
```
$ uv run python -c "
from tests.offline import offline_aura
for i in range(3):
    a = offline_aura()
    a.login(email='fake@example.invalid', password='fake-pw')
from loguru import logger
print('handler count:', len(logger._core.handlers))
"
# stderr shows the POST log line printed once, then twice, then three times
# handler count: 7
$ ls logs/ | wc -l   # grows by one file per Aura() instantiation, forever
```
As more offline tests are added (the stated purpose of this phase), every `pytest` run will keep appending new stderr sinks (increasingly duplicated console/log output, obscuring real signal) and new orphaned files under `logs/` that are never cleaned up.

**Fix:** Make sink registration idempotent, e.g. a class-level guard:
```python
class Aura:
    _logging_initialized = False

    def _init_logger(self):
        if Aura._logging_initialized:
            return
        os.makedirs('logs/', exist_ok=True)
        logger.add(sys.stderr, level="INFO", format="...")
        logger.add('logs/file_{time}.log')
        Aura._logging_initialized = True
```
or call `logger.remove()` before re-adding the two sinks so repeated construction stays at a fixed sink count instead of growing unbounded.

## Info

### IN-01: Swallowed exception detail in `download_images_from_assets`

**File:** `auraframes/aura.py:86-94`
**Issue:** `except Exception as e: failed_to_retrieve.append(asset)` binds `e` but never logs or inspects it — only a count (`len(failed_to_retrieve)`) is logged afterward via `logger.debug`. This is inconsistent with the sibling handler in `upload_image` (`aura.py:106-111`), which does `logger.error(e)`. Given this phase is explicitly about making the read path verifiable/testable, discarding the actual failure reason makes it harder to diagnose *why* a dump partially failed (network vs. EXIF vs. disk error all look identical).
**Fix:**
```python
except Exception as e:
    logger.error(f'Failed to retrieve asset {asset.id}: {e}')
    failed_to_retrieve.append(asset)
```

### IN-02: `error_envelope.json` fallback path in the offline router is never exercised by any test

**File:** `tests/offline.py:51`, `tests/fixtures/error_envelope.json`
**Issue:** `make_router`'s default branch (`return httpx.Response(404, json=_load("error_envelope.json"))`, used for any unmatched path) is loaded but no test in `tests/test_offline_read_path.py` ever hits an unmatched route to exercise it. A typo in a future endpoint path added to the router (e.g. a wrong URL string) would silently fall through to this generic 404 instead of failing loudly with a clear "route not configured" error, and nothing currently proves the fallback fixture itself is even well-formed against a real 404 shape.
**Fix:** Add a small test that deliberately hits an unrouted path (e.g. `aura.people_api.get_people()` or similar) through `offline_aura()` and asserts an `httpx.HTTPStatusError` is raised, exercising the fallback branch and fixture together.

### IN-03: Cursor-presence check in the offline router conflates `None` and empty-string cursor values

**File:** `tests/offline.py:47-48`
**Issue:** `cursor = request.url.params.get("cursor"); fixture = "assets_page2.json" if cursor else "assets_page1.json"` uses truthiness, not an explicit `is not None` / presence check. Production code (`Client.get`) only strips `None` values from `query_params`, not empty strings, so a hypothetical caller passing `cursor=""` would have it sent on the wire, and the router would silently route back to page 1 instead of surfacing the mismatch. Not currently reachable by any code path in the reviewed files (all callers pass `cursor=None` on the first page), but it's a latent sharp edge in the harness that a future test could trip over confusingly.
**Fix:** `fixture = "assets_page2.json" if cursor is not None else "assets_page1.json"`.

---

_Reviewed: 2026-07-04T17:25:46Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
