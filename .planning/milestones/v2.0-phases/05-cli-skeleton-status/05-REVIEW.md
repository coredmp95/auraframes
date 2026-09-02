---
phase: 05-cli-skeleton-status
reviewed: 2026-07-06T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - auraframes/cli.py
  - tests/test_cli_status.py
  - pyproject.toml
findings:
  critical: 0
  warning: 2
  info: 3
  total: 5
status: issues_found
---

# Phase 05: Code Review Report

**Reviewed:** 2026-07-06T00:00:00Z
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Reviewed the new `aura-cli status` skeleton (`auraframes/cli.py`), its offline test suite
(`tests/test_cli_status.py`), and the `pyproject.toml` console-script wiring. The core
credential-gate-before-network-call logic (D-09) is correctly implemented and covered by
tests, and no secrets are printed or logged. Verified the 3 offline tests actually pass
(`uv run pytest tests/test_cli_status.py -q` → 3 passed) and traced `run_status()` into
`Aura.login()` / `AccountApi.login()` / `Client` to confirm the error paths behave as the
tests assert.

No Critical/blocker issues found — no secrets, injection, or crash-on-normal-path bugs.
Two Warnings: an unhandled-exception gap after a successful login, and a silent-success
fallback in `main()` for any future unmatched subcommand. Three minor Info items (grammar,
a stale test docstring claim, and a stray quote-style inconsistency).

## Warnings

### WR-01: Unhandled exception if `get_frames()` fails after a successful login

**File:** `auraframes/cli.py:45-49`
**Issue:** `run_status()` wraps only `aura.login()` in a `try/except Exception` (lines
37-43). The subsequent calls — `aura.frame_api.get_frames()` (line 45) and the
`for frame in frames` loop (line 48) — are unguarded. If the `/frames.json` endpoint
returns a non-2xx status, `Client.get()` calls `response.raise_for_status()` and raises
`httpx.HTTPStatusError`, which propagates straight out of `run_status()`. Similarly, if
the API drifts and omits the `frames` key, `FrameApi.get_frames()` does
`json_response.get('frames')` → `None`, and iterating over `None` raises `TypeError`
(`auraframes/api/frameApi.py:19`) — also unguarded.

The project's own rationale for the login `try/except` (comment at cli.py:40-42: "bad
credentials, network error, or API drift all surface here — a broad catch at the CLI
boundary is correct") applies identically to `get_frames()`, since this is the same
undocumented, moving-target API (per CLAUDE.md constraints). As written, a transient
network blip or API-shape drift between login and the frame listing crashes the CLI with
a raw traceback and a non-deterministic exit code, instead of the intended
`print(...); return 1` contract that the rest of `run_status()` follows. This code path
is also untested — none of the three tests in `tests/test_cli_status.py` exercise a
post-login failure.

**Fix:** Extend the try/except (or add a second one) to cover the post-login work:
```python
aura = aura or Aura()

try:
    aura.login()
    frames = aura.frame_api.get_frames()
except Exception as e:
    print(f'Login failed: {e}')  # or a distinct message for the frames-fetch case
    return 1

print(f'Logged in as {os.getenv("AURA_EMAIL")}')
print(f'{len(frames)} frames:')
for frame in frames:
    print(f'  - {frame.name} (id: {frame.id})')

return 0
```
Add a regression test using `offline_aura(overrides={'/v5/frames.json': httpx.Response(500, ...)})`
to lock in the exit-code-1 behavior.

### WR-02: `main()` silently returns success for any unmatched subcommand

**File:** `auraframes/cli.py:58-59`
**Issue:** `main()` only handles `args.command == 'status'`; there is no `else`/`elif`
branch. Today this is unreachable because `build_parser()` defines exactly one subparser
(`status`) with `required=True`, so argparse itself rejects any other value with exit code
2 before `main()`'s body runs (verified: `parse_args(['bogus'])` → `SystemExit(2)`).
However, the function's own docstring says this parser is deliberately structured so
`inspect`/`sync` siblings can be added in later phases (D-02). The moment a new subparser
is added without a corresponding `elif` in `main()`, `main()` falls through and implicitly
returns `None` — and `sys.exit(None)` exits with code **0**, silently reporting success
for a command that was never actually executed.
**Fix:** Make the fallthrough an explicit, loud failure so it fails safe when new
subcommands are wired up incompletely:
```python
if args.command == 'status':
    return run_status()

raise NotImplementedError(f'unhandled command: {args.command}')
```

## Info

### IN-01: Incorrect pluralization in frame count output

**File:** `auraframes/cli.py:47`
**Issue:** `print(f'{len(frames)} frames:')` always uses the plural "frames", so a
single-frame account prints "1 frames:" (also asserted verbatim in
`tests/test_cli_status.py:38`, so the test currently locks in the typo).
**Fix:** `print(f"{len(frames)} frame{'s' if len(frames) != 1 else ''}:")`

### IN-02: Test module docstring's `load_dotenv()` claim is inaccurate

**File:** `tests/test_cli_status.py:1-3`
**Issue:** The module docstring states tests "Calls run_status() directly (never main())
so load_dotenv() is not invoked and a filesystem .env cannot interfere." This is true of
`cli.py`'s own `load_dotenv()` call in `main()`, but `tests/conftest.py:8` unconditionally
calls `load_dotenv()` at collection time for the whole `tests/` session (it runs before
any test body, including this file's). The tests are still correct in practice because
each test calls `monkeypatch.delenv`/`setenv` explicitly before invoking `run_status()`,
overriding whatever `conftest.py`'s `load_dotenv()` loaded — but the docstring's stated
reasoning for *why* they're safe is not accurate, which could mislead a future editor into
removing the `monkeypatch` calls as "unnecessary".
**Fix:** Clarify the docstring, e.g.: "...`monkeypatch` explicitly sets/clears
`AURA_EMAIL`/`AURA_PASSWORD` in every test, which overrides both a real shell environment
and anything `tests/conftest.py`'s session-level `load_dotenv()` may have loaded."

### IN-03: Inconsistent quote style

**File:** `auraframes/cli.py:46`
**Issue:** `print(f'Logged in as {os.getenv("AURA_EMAIL")}')` mixes double quotes inside an
f-string while every other string literal in this file (and the codebase per CLAUDE.md
conventions) uses single quotes. Minor, but stands out as the one exception in an
otherwise consistent file.
**Fix:** Not strictly necessary (nested quoting requires the alternation), but could use
`os.environ['AURA_EMAIL']` pulled into a local variable earlier alongside `email_set` to
avoid the mixed-quote line entirely.

---

_Reviewed: 2026-07-06T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
