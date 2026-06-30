---
slug: login-475-null-creds
status: resolved
trigger: "python3 main.py fails at aura.login() with httpx HTTPStatusError 475 from https://api.pushd.com/v5/login.json; request log shows the login payload email is None (password shows ***REDACTED*** but is also None — see redaction note)"
created: 2026-06-30
updated: 2026-06-30
---

# Debug Session: login-475-null-creds

## Symptoms

- **Expected:** `python3 main.py` reads AURA_EMAIL/AURA_PASSWORD from `.env` (loaded via `load_dotenv()` added in quick task 260630-qs8), authenticates, and runs the read-path demo.
- **Actual:** Login POST to `/login.json` returns HTTP 475; `client.post` `raise_for_status()` raises `httpx.HTTPStatusError`. The request-log Context shows `data.user.email = None`.
- **Error:** `httpx.HTTPStatusError: Client error '475 ' for url 'https://api.pushd.com/v5/login.json'` (traceback through `main.py:35` → `aura.py:43` → `accountApi.py:27` → `client.py:73`).
- **Timeline:** Surfaced immediately after quick task 260630-qs8 added `load_dotenv()` to `main.py`. The same 475 was also observed during that task's "accidental live run".
- **Reproduction:** `python3 main.py` with a populated `.env` (AURA_EMAIL/AURA_PASSWORD set) and no exported shell vars.

## Current Focus

- **hypothesis:** `aura.py:36` defines `def login(self, email: str = os.getenv('AURA_EMAIL'), password: str = os.getenv('AURA_PASSWORD'))`. Python evaluates default arguments **once, at function-definition time** — i.e. when `auraframes.aura` is imported. In `main.py` the `from auraframes.aura import Aura` import runs at module top, BEFORE `main()` calls `load_dotenv()`. With no shell-exported creds and `.env` not yet loaded, both defaults bake to `None`. `load_dotenv()` then populates `os.environ` at runtime, so the credential guard (`os.getenv(...)` evaluated at call time, `main.py:18`) passes — but `aura.login()` is called with no args and uses the stale `None` defaults, POSTing `{email: None, password: None}`. The API rejects null credentials with 475.
- **test:** Pass explicit creds to `aura.login(os.getenv('AURA_EMAIL'), os.getenv('AURA_PASSWORD'))` from `main.py` (resolved AFTER load_dotenv) — login should succeed, proving the early-evaluated defaults are the cause. Alternatively, print `inspect.signature(Aura.login)` defaults right after import to show they are `None`.
- **expecting:** With explicit runtime-resolved creds, the payload carries the real email and login returns a result (no 475).
- **next_action:** Verify the hypothesis (signature default inspection + explicit-cred login), then apply the fix.

## Evidence

- timestamp 2026-06-30: `aura.py:36` uses `os.getenv('AURA_EMAIL')`/`os.getenv('AURA_PASSWORD')` as DEFAULT ARGUMENT VALUES — evaluated at import (def) time, not call time. This is the canonical Python mutable/early-bound default-arg pitfall.
- timestamp 2026-06-30: `main.py` imports `from auraframes.aura import Aura` at module top (line ~4), which triggers evaluation of those defaults BEFORE `main()` runs `load_dotenv()`. So at import time `os.getenv` returns None (no shell creds, `.env` unread).
- timestamp 2026-06-30: `main.py:18` credential guard calls `os.getenv(...)` at runtime (after load_dotenv) → truthy → guard passes, masking the problem. `aura.login()` (`main.py:35`) is called with NO arguments → uses the baked-in None defaults.
- timestamp 2026-06-30: log shows `email: None` but `password: '***REDACTED***'`. `client.py` `_redact()` masks the password field to the literal `***REDACTED***` regardless of its real value, so password only LOOKS set; it is also None. This resolves the apparent asymmetry.
- timestamp 2026-06-30: `accountApi.login` (accountApi.py:15-27) builds `login_payload.user.email/password` directly from its `email`/`password` params and POSTs them; no further resolution of env vars happens downstream.

## Eliminated

- hypothesis: `.env` is not being loaded at all — ELIMINATED. The credential guard at `main.py:18` passes (the demo proceeds past it to login), which requires `os.getenv('AURA_EMAIL')` to be truthy at runtime; that only happens because `load_dotenv()` populated it. So `.env` IS loaded; the problem is that `login()`'s defaults were bound earlier, at import time.

## Proposed Fix (to verify and apply)

In `auraframes/aura.py`, change `login` to resolve env vars at CALL time, not def time:

```python
def login(self, email: str = None, password: str = None):
    if email is None:
        email = os.getenv('AURA_EMAIL')
    if password is None:
        password = os.getenv('AURA_PASSWORD')
    ...
```

This evaluates `os.getenv` when `login()` is invoked (after `load_dotenv()`), so the real `.env` creds flow into the payload. Explicit args still override env (preserves the documented API). Consider also having `main.py` pass creds explicitly for defense-in-depth, but the `aura.py` fix is the root-cause correction.

## Resolution

- **root_cause:** `Aura.login` bound `os.getenv('AURA_EMAIL')`/`os.getenv('AURA_PASSWORD')` as default argument values, which Python evaluates once at import time — before `main.py`'s `load_dotenv()` runs — baking both creds to `None` and POSTing null credentials, which the Pushd API rejects with HTTP 475.
- **fix:** Changed `login(self, email: str = None, password: str = None)` and resolve `os.getenv(...)` inside the body when an arg is `None`, so creds are read at call time (after `load_dotenv`). Explicit args still override env, preserving the documented contract. Added an offline regression guard (`tests/test_imports.py::test_login_defaults_are_none_sentinels`).
- **verification (non-network):** With creds unset, `Aura.login.__defaults__ == (None, None)`. With env populated after import (mocking the account API), the call-time payload carried the real email; explicit args still overrode env. `pytest -m "not live"` → 10 passed. Live login left for the user (hits the live Pushd API).
- **commit:** `b2c5c66` — fix(aura): resolve login credentials at call time, not import time. Files: `auraframes/aura.py`, `tests/test_imports.py`.
