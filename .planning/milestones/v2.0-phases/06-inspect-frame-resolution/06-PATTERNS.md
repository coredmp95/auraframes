# Phase 6: Inspect + Frame Resolution - Pattern Map

**Mapped:** 2026-07-06
**Files analyzed:** 5 (2 modified, 3 new)
**Analogs found:** 5 / 5

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `auraframes/cli.py` (`build_parser()`, `main()` modified) | config/route wiring | request-response | itself (existing `status` wiring) | exact (same file, extend in place) |
| `auraframes/cli.py` (`run_inspect()` new function) | controller | request-response (CRUD-read) | `run_status()` in same file | exact |
| `auraframes/cli.py` (`resolve_frame()` new function, or new `frame_resolver.py`) | utility/transform | transform (pure, in-memory) | none exists — net-new logic | no analog |
| `tests/offline.py` (`make_router()` modified — add `get_frame` route) | test fixture/utility | request-response (mock) | existing `frames.json`/`login.json` branches in same function | exact (same file, extend in place) |
| `tests/fixtures/frame_detail.json` (new) | config/fixture | file-I/O | `tests/fixtures/frames.json` | exact |
| `tests/test_cli_inspect.py` (new) | test | request-response | `tests/test_cli_status.py` | exact |

## Pattern Assignments

### `auraframes/cli.py` — `build_parser()` (config/route wiring)

**Analog:** current `build_parser()`, same file, lines 11-23

**Current shape** (`auraframes/cli.py:11-23`):
```python
def build_parser() -> argparse.ArgumentParser:
    """Construct the root `aura-cli` parser. Subparsers are structured so
    `inspect`/`sync` siblings can be added in later phases (D-02)."""
    parser = argparse.ArgumentParser(prog='aura-cli')
    subparsers = parser.add_subparsers(dest='command', required=True)
    status_parser = subparsers.add_parser('status', help='Check config/auth health and list account frames')
    status_parser.add_argument(
        '--debug',
        action='store_true',
        default=False,
        help='Show verbose loguru request/response logging on stderr',
    )
    return parser
```

**Target shape** — move `--debug` to root parser (folded todo), add `inspect` subparser:
```python
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='aura-cli')
    parser.add_argument('--debug', action='store_true', default=False,
                         help='Show verbose loguru request/response logging on stderr')
    subparsers = parser.add_subparsers(dest='command', required=True)
    subparsers.add_parser('status', help='Check config/auth health and list account frames')
    inspect_parser = subparsers.add_parser('inspect', help="Inspect a frame's photos and metadata")
    inspect_parser.add_argument('--frame', required=True, help='Frame name (substring) or id')
    return parser
```

**Dispatch pattern — current** (`auraframes/cli.py:93-98`):
```python
def main(argv=None) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)

    if args.command == 'status':
        return run_status(debug=args.debug)
```

**Dispatch pattern — target** (adds Pitfall 5's `else` guard from RESEARCH.md):
```python
def main(argv=None) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)
    if args.command == 'status':
        return run_status(debug=args.debug)
    if args.command == 'inspect':
        return run_inspect(args.frame, debug=args.debug)
    raise ValueError(f"Unhandled command: {args.command}")
```

---

### `auraframes/cli.py` — `run_inspect()` (controller, request-response)

**Analog:** `run_status()`, `auraframes/cli.py:55-90`

**Full analog for shape reference** (`auraframes/cli.py:55-90`):
```python
def run_status(aura=None, debug: bool = False) -> int:
    """Status command handler. Returns a process exit code (0 success, 1
    failure) — never calls sys.exit directly. Accepts an optional injected
    `Aura` (dependency-injection seam) so this is testable offline."""
    email_set = bool(os.getenv('AURA_EMAIL'))
    password_set = bool(os.getenv('AURA_PASSWORD'))
    print(f"AURA_EMAIL: {'set' if email_set else 'NOT SET'}")
    print(f"AURA_PASSWORD: {'set' if password_set else 'NOT SET'}")

    if not (email_set and password_set):
        return 1

    aura = aura or Aura()
    _configure_cli_logging(debug)

    try:
        aura.login()
    except Exception as e:
        print(f'Login failed: {e}')
        return 1

    frames = aura.frame_api.get_frames()
    print(f'Logged in as {os.getenv("AURA_EMAIL")}')
    print(f'{len(frames)} frames:')
    for frame in frames:
        print(f'  - {frame.name} (id: {frame.id})')

    return 0
```

**Copy exactly:**
- Signature shape: `def run_inspect(frame_arg: str, aura=None, debug: bool = False) -> int:`
- Config-check-before-network guard is NOT needed again (frame_arg is required by argparse, not an env var) — start directly with `aura = aura or Aura(); _configure_cli_logging(debug)`.
- The `try/except Exception as e: print(...); return 1` wrapper around `aura.login()` — copy verbatim.
- **New wrapping needed beyond the analog:** RESEARCH.md's Security Domain section (WR-01 carried forward) recommends the same broad `try/except` also wrap the post-login `get_frames()`/`get_frame()`/`get_all_assets()` calls, since `inspect` is the first subcommand to call these post-login — follow the same `print(f'...: {e}'); return 1` shape, not a new error format.
- Never call `sys.exit()` — return an `int`, matching `run_status()`.

**Call sequence to implement (from RESEARCH.md Pattern 1-3, grounded in existing methods):**
```python
frames = aura.frame_api.get_frames()          # auraframes/api/frameApi.py:13-19, existing, unmodified
# resolve_frame(...) — see below, net-new
frame, total_asset_count = aura.frame_api.get_frame(resolved.id)   # auraframes/api/frameApi.py:21-36, existing, NEW call site
assets = aura.get_all_assets(resolved.id)     # auraframes/aura.py:59-68, existing, reused from dump_frame's pattern
```

**Source for `get_frame()`'s exact drift-fix return shape** (`auraframes/api/frameApi.py:21-36`):
```python
def get_frame(self, frame_id: str) -> tuple[Frame, int]:
    json_response = self._client.get(f'/frames/{frame_id}.json')
    frame_data = json_response.get('frame')
    total_asset_count = json_response.get('total_asset_count')
    if total_asset_count is None and frame_data:
        total_asset_count = frame_data.get('num_assets')
    return Frame(**frame_data), total_asset_count
```
Use the returned `total_asset_count` directly for D-11 — do not re-derive it from `frame.num_assets`.

**Source for `get_all_assets()`'s pagination-draining shape** (`auraframes/aura.py:59-68`):
```python
def get_all_assets(self, frame_id: str, limit: int = 1000, page_delay: float = 0.0):
    paginated_assets, cursor = self.frame_api.get_assets(frame_id, limit=limit)
    assets = paginated_assets
    while cursor:
        paginated_assets, cursor = self.frame_api.get_assets(frame_id, limit=limit, cursor=cursor)
        if page_delay:
            time.sleep(page_delay)
        assets.extend(paginated_assets)
    return assets
```

**Fields needed for output formatting (confirmed types via direct model reads):**
- `Frame.name: str`, `Frame.id: str`, `Frame.user: User` (`auraframes/models/frame.py:26-27,84`)
- `Frame.contributors: Optional[list[User]] = None` (`auraframes/models/frame.py:47`) — **always guard with `(frame.contributors or [])`** before `len()`/iterating (Pitfall 3).
- `User.name: str`, `User.email: str` (`auraframes/models/user.py:9-10`)
- `Asset.id: str` (`auraframes/models/asset.py:52`), `Asset.file_name: str` (line 45), `Asset.taken_at: str` + `.taken_at_dt` property (lines 83, 105-106) — use `.taken_at_dt`, not a hand-rolled `datetime.strptime`.
- `Asset.md5_hash: Optional[str] = None` (`auraframes/models/asset.py:65`) — read-only observation for the D-12 live spike, no code change to the model.

---

### `auraframes/cli.py` — `resolve_frame()` (utility/transform, no analog)

**No existing analog** — this is net-new pure-function logic (RESEARCH.md confirms no name-search endpoint or prior resolution helper exists anywhere in the codebase).

**Illustrative shape from RESEARCH.md Pattern 1** (matches CONTEXT.md D-01 through D-04):
```python
def resolve_frame(target: str, frames: list[Frame]) -> Frame:
    name_matches = [f for f in frames if target.lower() in f.name.lower()]
    if len(name_matches) == 1:
        return name_matches[0]
    if len(name_matches) > 1:
        raise AmbiguousFrameError(name_matches)          # D-03: list name+id pairs, no id fallback attempted
    id_matches = [f for f in frames if f.id == target]     # exact match, case-sensitive (A1: unconfirmed edge case, low risk)
    if len(id_matches) == 1:
        return id_matches[0]
    raise FrameNotFoundError(frames)                       # D-04: list available frame names
```
Placement: either a top-level function in `cli.py` (smaller diff, recommended unless it grows past ~30 lines) or a new `auraframes/frame_resolver.py` (Claude's discretion per CONTEXT.md). No existing convention in `STRUCTURE.md` covers this exact case since it has no HTTP call and doesn't belong in `*Api`.

Error handling for the two failure paths must follow `run_status()`'s `print(...); return 1` fail-loud convention (D-05) — whether `resolve_frame()` raises custom exceptions caught in `run_inspect()`, or returns a sentinel, follow the same terminal `print(); return 1` shape already established.

---

### `tests/offline.py` — `make_router()` (test fixture/utility, request-response mock)

**Analog:** existing branches in the same function, `tests/offline.py:34-51`

**Current shape** (`tests/offline.py:22-53`):
```python
def make_router(overrides: dict | None = None):
    overrides = overrides or {}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path  # includes the '/v5' base_url prefix

        if path in overrides:
            return overrides[path]

        if path == "/v5/login.json":
            return httpx.Response(200, json=_load("login.json"))
        if path == "/v5/frames.json":
            return httpx.Response(200, json=_load("frames.json"))
        if path.endswith("/assets.json"):
            cursor = request.url.params.get("cursor")
            fixture = "assets_page2.json" if cursor else "assets_page1.json"
            return httpx.Response(200, json=_load(fixture))

        return httpx.Response(404, json=_load("error_envelope.json"))

    return handler
```

**Required addition** (Pitfall 1 from RESEARCH.md — must be added BEFORE the final 404 fallthrough, and must exclude `/assets`/`/activities` sub-paths so it doesn't shadow the existing `assets.json` branch):
```python
if path.startswith("/v5/frames/") and path.endswith(".json") and "/assets" not in path and "/activities" not in path:
    return httpx.Response(200, json=_load("frame_detail.json"))
```
This is a **Wave 0 test-infrastructure task**, not incidental — no offline `inspect` test can reach the metadata-display step without it (currently falls through to 404/`error_envelope.json`).

**`offline_aura()` DI seam** (`tests/offline.py:56-66`) — reuse unchanged, same as `test_cli_status.py` does via `offline_aura(overrides={...})` for per-test route substitution (needed to exercise D-03's ambiguous-match path, per Pitfall 2 — do not edit the shared single-frame `frames.json` fixture).

---

### `tests/fixtures/frame_detail.json` (new fixture, file-I/O)

**Analog:** `tests/fixtures/frames.json` (single existing frame fixture, shape confirmed via `test_cli_status.py` assertions: `'Fake Frame'`, `'frame-fake-0001'`).

**Required shape** (per `FrameApi.get_frame()`'s parsing, `auraframes/api/frameApi.py:27-36`):
```json
{
  "frame": { "...same Frame field shape as frames.json's single entry, plus contributors/user..." },
  "total_asset_count": 3
}
```
Must include a `"user"` object (required, non-Optional `Frame.user: User`) and should include a `"contributors"` list with at least one entry to exercise D-10's formatting, plus a variant/second test case with `"contributors": null` to exercise the Pitfall 3 guard.

---

### `tests/test_cli_inspect.py` (new test file)

**Analog:** `tests/test_cli_status.py` (full file, 98 lines) — mirror its structure exactly per RESEARCH.md's Recommended Project Structure.

**Structural elements to copy verbatim:**
- The `_reset_loguru` autouse fixture (`tests/test_cli_status.py:16-24`) — copy unchanged, same loguru-singleton reset rationale applies to any new CLI test file.
- Test naming convention: `test_<command>_<scenario>_<expected>` (e.g. `test_status_missing_creds_exits_nonzero_no_network`).
- Calling the handler function directly (`run_status(...)` / here `run_inspect(...)`), never `main()`, so `load_dotenv()` doesn't interfere (`tests/test_cli_status.py:1-3` docstring).
- Using `monkeypatch.setenv`/`delenv` for env vars, `capsys.readouterr()` for output assertions, `offline_aura(overrides={...})` for injected failures — copy pattern from `test_status_login_failure_exits_nonzero` (`tests/test_cli_status.py:56-67`).
- Never assert the password value appears in output — same secret-non-leak assertion style as `test_status_success_lists_frames_and_never_prints_password` (`tests/test_cli_status.py:39-53`, `assert 'super-secret-pw' not in out`).

**New test cases needed (no direct analog, net-new scenarios):**
- Ambiguous match (D-03): use `offline_aura(overrides={'/v5/frames.json': httpx.Response(200, json={...two-frame payload...})})` per Pitfall 2, assert both matching names+ids appear in output and rc == 1.
- Not-found (D-04): substring/id matches nothing, assert available frame names listed and rc == 1.
- Resolution by id fallback (D-02): substring matches zero, but the arg equals `Frame.id` exactly.
- Successful full flow: single name match -> `get_frame()` -> `get_all_assets()` -> assert name/owner/contributor-count/asset-count and first-N photo lines all appear.

## Shared Patterns

### Fail-loud, non-zero exit (D-05, D-08 carried from Phase 5)
**Source:** `run_status()`, `auraframes/cli.py:76-82`
**Apply to:** `run_inspect()`'s login wrapper AND (new, per WR-01) its post-login data-fetch calls, AND `resolve_frame()`'s ambiguous/not-found paths.
```python
try:
    aura.login()
except Exception as e:
    print(f'Login failed: {e}')
    return 1
```

### Testable-handler shape: return int, accept injected `aura` (D-01/D-02 Phase 5, reaffirmed Pattern 3)
**Source:** `run_status(aura=None, debug: bool = False) -> int`, `auraframes/cli.py:55`
**Apply to:** `run_inspect(frame_arg: str, aura=None, debug: bool = False) -> int`

### Offline DI/mock-transport harness
**Source:** `tests/offline.py` (`make_router`, `offline_aura`) — extend the router (add `frame_detail.json` route), reuse `offline_aura()` unchanged.
**Apply to:** `tests/test_cli_inspect.py`, and any fixture-swap needed for D-03's multi-frame test case.

### `--debug` / logging config (folded todo, now root-level, cross-cutting)
**Source:** `_configure_cli_logging()`, `auraframes/cli.py:26-52` — unchanged internals; only its call site moves from per-subcommand to once, before dispatch, driven by the newly root-level `args.debug`.
**Apply to:** Both `run_status()`'s existing call and `run_inspect()`'s new call — same function, same placement rule ("after `Aura()` construction, before any HTTP call").

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `resolve_frame()` (in `cli.py` or new `frame_resolver.py`) | utility/transform | transform (pure, in-memory) | Net-new business logic; no name/id-resolution helper exists anywhere in the codebase (confirmed via RESEARCH.md's Integration Points and API surface read of `frameApi.py`) — planner should use RESEARCH.md's Pattern 1 illustrative code directly rather than search for a closer analog. |

## Metadata

**Analog search scope:** `auraframes/cli.py`, `auraframes/api/frameApi.py`, `auraframes/aura.py`, `auraframes/models/{frame,asset,user}.py`, `tests/offline.py`, `tests/test_cli_status.py`, `tests/fixtures/*.json`
**Files scanned:** 9 source/test files read directly (no large-file Grep-first strategy needed — all files under 200 lines)
**Pattern extraction date:** 2026-07-06
</content>
