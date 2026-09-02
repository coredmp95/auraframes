# Phase 5: CLI Skeleton + Status - Pattern Map

**Mapped:** 2026-07-06
**Files analyzed:** 4 (1 new, 3 reused/modified)
**Analogs found:** 3 / 4

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `auraframes/cli.py` (new) | controller (CLI entrypoint) | request-response | `main.py` | role-match (facade-demo script, no existing argparse CLI exists) |
| `pyproject.toml` (modify) | config | N/A | `pyproject.toml` (existing `[project]`/`[project.optional-dependencies]` sections) | exact (additive section, same file) |
| `auraframes/aura.py` (reused as-is) | service (facade) | CRUD (read) | itself — `Aura.login()`, `Aura.frame_api.get_frames()` already implement the needed calls | exact |
| `auraframes/utils/settings.py` (reused as-is) | config/utility | request-response (env read) | itself — already reads `AURA_EMAIL`/`AURA_PASSWORD`-adjacent vars | exact |

No dedicated `argparse` CLI exists anywhere in the codebase yet — `main.py` is the closest analog for "a script that drives `Aura` end-to-end and prints a concise, non-secret summary," which is exactly the shape `status` needs. The credential-guard-then-login-then-print pattern in `main.py` is the strongest available precedent for D-07/D-08/D-09.

## Pattern Assignments

### `auraframes/cli.py` (new) — controller, request-response

**Analog:** `main.py` (full file, 65 lines — read in one pass)

**Imports pattern** (`main.py:1-7`):
```python
import os
import sys

from dotenv import load_dotenv

from auraframes.aura import Aura
from auraframes import export
```
For `cli.py`, drop the `export` import (not needed for `status`) and add `argparse`:
```python
import argparse
import os
import sys

from dotenv import load_dotenv

from auraframes.aura import Aura
```

**Credential guard pattern (D-07, D-09)** (`main.py:19-28`):
```python
load_dotenv()

if not os.getenv('AURA_EMAIL') or not os.getenv('AURA_PASSWORD'):
    print(
        'AURA_EMAIL / AURA_PASSWORD not set — export them (or add a local .env '
        'used by the test path) to run the read-path demo.'
    )
    sys.exit(0)
```
Adapt for `status`: check each var independently and report per-var pass/fail (D-07 wants `AURA_EMAIL: set` / `AURA_EMAIL: NOT SET` individually, not a combined message), and exit non-zero instead of `0` (D-08/D-09 — this is the one behavioral divergence from `main.py`, which exits `0` cleanly since it's a demo, not a scriptable CLI):
```python
email_set = bool(os.getenv('AURA_EMAIL'))
password_set = bool(os.getenv('AURA_PASSWORD'))
print(f"AURA_EMAIL: {'set' if email_set else 'NOT SET'}")
print(f"AURA_PASSWORD: {'set' if password_set else 'NOT SET'}")
if not (email_set and password_set):
    sys.exit(1)
```

**Login + facade call pattern** (`main.py:30-36`):
```python
aura = Aura()
aura.login()                                    # READ-01

frames = aura.frame_api.get_frames()            # READ-02 (first frame)
if not frames:
    print('No frames on this account — nothing to read.')
    sys.exit(0)
frame = frames[0]
```
For `status`, iterate all frames (D-06 — name + id only, no single-frame selection) and wrap `login()` in a try/except since `AccountApi.login` raises `RuntimeError` on failure (see Shared Patterns below — this is the D-08 exit-non-zero hook):
```python
try:
    aura.login()
except RuntimeError as e:
    print(f'Login failed: {e}')
    sys.exit(1)

frames = aura.frame_api.get_frames()
print(f'Logged in as {os.getenv("AURA_EMAIL")}')
print(f'{len(frames)} frames:')
for f in frames:
    print(f'  - {f.name} (id: {f.id})')
```

**Concise, non-secret summary print pattern** (`main.py:56-60`):
```python
print('Read-path demo complete:')
print(f'  Frame:          {frame.name} ({frame.id})')
print(f'  Total assets:   {len(assets)}')
```
This is the direct precedent for D-05's concise (non-table) summary format — same `print()`-per-line style, no secrets, no logging framework noise.

**`main()` entry function shape** (`main.py:14, 63-64`):
```python
def main():
    ...

if __name__ == '__main__':
    main()
```
`cli.py`'s `main()` must additionally set up `argparse` subparsers (D-02) before dispatching to a `status` handler — no existing argparse precedent in this codebase, so use stdlib `argparse` docs conventions directly (per CONTEXT.md D-01, confirmed HIGH confidence, no project-specific variant needed):
```python
def main():
    parser = argparse.ArgumentParser(prog='aura-cli')
    subparsers = parser.add_subparsers(dest='command', required=True)
    subparsers.add_parser('status', help='Check config/auth health and list frames')
    args = parser.parse_args()

    if args.command == 'status':
        return _status()

if __name__ == '__main__':
    sys.exit(main())
```

---

### `pyproject.toml` (modify) — config, N/A

**Analog:** itself (existing file, 24 lines — read in full)

Existing structure to extend (`pyproject.toml:1-16`):
```toml
[project]
name = "auraframes"
version = "0.1.0"
requires-python = ">=3.14"
dependencies = [ ... ]

[project.optional-dependencies]
dev = ["pytest>=8"]
```
Add a new `[project.scripts]` table (confirmed absent today — net-new section, not a modification of an existing one, per CONTEXT.md):
```toml
[project.scripts]
aura-cli = "auraframes.cli:main"
```
No dependency change needed — `argparse` is stdlib (D-01).

---

### `auraframes/aura.py` (reused as-is) — service, CRUD

**Analog:** itself

No modifications expected. `status` calls two existing methods directly:

**`login()`** (`auraframes/aura.py:33-46`):
```python
def login(self, email: str = None, password: str = None):
    if email is None:
        email = os.getenv('AURA_EMAIL')
    if password is None:
        password = os.getenv('AURA_PASSWORD')

    user = self.account_api.login(email, password)

    self._client.add_default_headers({
        'x-token-auth': user.auth_token,
        'x-user-id': user.id
    })

    return self
```
Note: `login()` returns `self`, and `user` (with `.email`/`.name` etc.) is not retained on the `Aura` instance — if `status` needs the authenticated user's display info beyond the raw env var, it must call `account_api.login(...)` directly or `cli.py` should track `os.getenv('AURA_EMAIL')` for the "Logged in as ..." line (simplest — matches D-05's example output, which just echoes the email).

**`frame_api.get_frames()`** — delegates to `FrameApi.get_frames()` (`auraframes/api/frameApi.py:12-18`):
```python
def get_frames(self) -> list[Frame]:
    json_response = self._client.get('/frames.json')
    return [Frame(**frame_data) for frame_data in json_response.get('frames')]
```
`Frame` model exposes `.name` and `.id` directly (confirmed via `main.py:35` usage `frame.name`, `frame.id`) — sufficient for D-06's name+id-only listing.

---

### `auraframes/utils/settings.py` (reused as-is) — config/utility, request-response

**Analog:** itself (full file, 6 lines)

```python
import os

LOCALE = os.getenv('AURA_LOCALE', 'en-US')
AURA_APP_IDENTIFIER = os.getenv('AURA_APP_IDENTIFIER', 'com.pushd.client')
DEVICE_IDENTIFIER = os.getenv('AURA_DEVICE_IDENTIFIER', '0000000000000000')
IMAGE_PROXY_BASE_URL = 'https://imgproxy.pushd.com'
```
Note: this module does **not** define `AURA_EMAIL`/`AURA_PASSWORD` constants — those are read directly via `os.getenv(...)` at call sites (`aura.py:38-41`, `main.py:23`). `status`'s config-health check should follow the same direct `os.getenv('AURA_EMAIL')` / `os.getenv('AURA_PASSWORD')` pattern rather than importing anything new from `settings.py` — D-07 requires checking these two vars specifically, and this file only holds the *optional* vars (explicitly out of scope per D-07/deferred section).

---

## Shared Patterns

### Fail-loud on login error (D-08)
**Source:** `auraframes/api/accountApi.py:26-30`
**Apply to:** `cli.py`'s `status` handler
```python
json_response = self._client.post('/login.json', login_payload)
if json_response.get('error') or not json_response.get('result'):
    raise RuntimeError(
        f"Aura login failed: {json_response.get('message') or json_response.get('error') or 'no result returned'}"
    )
```
`AccountApi.login` already raises `RuntimeError` with a descriptive message on failure. `cli.py` should catch this specific exception around `aura.login()` and translate it into a printed message + `sys.exit(1)` (D-08). No new exception type needed.

### HTTP-level failures (network errors, non-2xx before reaching login logic)
**Source:** `auraframes/client.py:56-64` (`Client.post`)
```python
response = self.http2_client.post(url=url, json=data, headers=headers, params=query_params)
self.history.append(response)
response.raise_for_status()
```
`httpx.HTTPStatusError` (and `httpx.ConnectError`/`httpx.TimeoutException` etc. for network failures) can propagate from `Client.post` before `AccountApi.login`'s own `RuntimeError` check ever runs. `status`'s try/except around `aura.login()` should catch a broader set (`Exception`) or at minimum both `RuntimeError` and `httpx.HTTPError` to satisfy D-08's "bad credentials, network error, API drift" scenarios.

### Secret redaction (never print password) — D-07
**Source:** `auraframes/client.py:13-31` (`_REDACT_KEYS`, `_redact()`)
```python
_REDACT_KEYS = {'password', 'auth_token', 'x-token-auth'}
_REDACTED = '***REDACTED***'
```
This is the existing project-wide convention for never leaking secrets into logs. `cli.py` doesn't need to import this directly (it never logs the raw request), but it establishes the precedent: only print `set`/`NOT SET` for `AURA_PASSWORD`, never the value or any part of it — consistent with how `Client` already treats `password` as a redact-key.

### Concise print-based summary output (D-05)
**Source:** `main.py:56-60`
**Apply to:** `cli.py`'s `status` output
```python
print('Read-path demo complete:')
print(f'  Frame:          {frame.name} ({frame.id})')
```
Plain `print()` calls, no table library, no `loguru` (loguru is reserved for the `Aura`-internal request/response logging sink, not user-facing CLI output — confirmed by `aura.py:_init_logger()` writing to `logs/file_{time}.log` + stderr at INFO, which would double up with direct `print()` if conflated).

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| argparse subparser wiring itself | controller/config | request-response | No existing argparse usage anywhere in the codebase (`main.py` takes no arguments) — planner should follow stdlib `argparse` conventions directly (CONTEXT.md D-01 confirms this is a standard, well-documented pattern, HIGH confidence, no project-specific variant to reconcile) |

## Metadata

**Analog search scope:** repo root (`pyproject.toml`, `main.py`), `auraframes/` (`aura.py`, `client.py`, `utils/settings.py`, `api/accountApi.py`, `api/frameApi.py`)
**Files scanned:** 7
**Pattern extraction date:** 2026-07-06
</content>
