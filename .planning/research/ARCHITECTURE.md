# Architecture Research

**Domain:** CLI integration onto an existing facade/Client/*Api Python client (directory-to-frame sync)
**Researched:** 2026-07-05
**Confidence:** HIGH (codebase-grounded; CLI-framework choice cross-checked against current web sources)

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│  NEW: auraframes/cli.py  (click group: aura)                         │
│  ┌───────────┐  ┌───────────┐  ┌────────────────────────────────┐   │
│  │  status   │  │  inspect  │  │  sync <dir> --frame <name/id>   │   │
│  └─────┬─────┘  └─────┬─────┘  └───────────────┬─────────────────┘   │
├────────┼──────────────┼────────────────────────┼──────────────────────┤
│        │              │           NEW: auraframes/sync.py            │
│        │              │        SyncPlan (compute) / execute_plan()   │
│        │              │                        │                     │
│        │        NEW: auraframes/utils/frames.py│                     │
│        │        resolve_frame(frames, ident)   │                     │
│        │              │                        │                     │
│        │        NEW: auraframes/utils/hashing.py                     │
│        │        local_content_hash(path) -> md5 (b64, S3Client-compat)│
├────────┴──────────────┴────────────────────────┴──────────────────────┤
│                  EXISTING: auraframes/aura.py (Aura facade)           │
│   login() · get_all_assets() · upload_image() · account_api ·        │
│   frame_api · asset_api · people_api · activity_api                  │
├────────────────────────────────────────────────────────────────────────┤
│  EXISTING: auraframes/api/*Api.py   (FrameApi, AssetApi, ...)         │
├────────────────────────────────────────────────────────────────────────┤
│  EXISTING: auraframes/client.py (Client, DI transport seam)          │
│  EXISTING: auraframes/aws/{s3client,sqsclient}.py (Cognito anon auth)│
└──────────────────────────────────────────────────────────────────────┘

  UNCHANGED: main.py stays the standalone read-path facade demo.
```

### Component Responsibilities

| Component | Responsibility | Status |
|-----------|----------------|--------|
| `auraframes/cli.py` | Click group `aura` with `status`/`inspect`/`sync` subcommands; owns argument parsing, output formatting, confirmation UX, exit codes | **NEW** |
| `auraframes/sync.py` | Computes a `SyncPlan` (diff of local dir vs. remote assets) and, separately, executes it (upload/remove) | **NEW** |
| `auraframes/utils/frames.py` | `resolve_frame(frames, identifier)` — resolve a `Frame` by exact id or case-insensitive name from an already-fetched list | **NEW** |
| `auraframes/utils/hashing.py` | `local_content_hash(path) -> str` — base64 MD5 digest, bit-compatible with `S3Client.get_md5` / `Asset.md5_hash` | **NEW** |
| `auraframes/aura.py` (`Aura`) | Facade composing all `*Api` + AWS clients; login/session state; `get_all_assets`, `upload_image` | **MODIFIED** (see below) |
| `auraframes/api/frameApi.py` (`FrameApi`) | `get_frames`, `get_assets` (cursor pagination), `select_asset`, `remove_asset`, `exclude_asset` | **UNCHANGED** (consumed as-is) |
| `auraframes/api/assetApi.py` (`AssetApi`) | `batch_update`, `delete_asset`, `crop_asset` | **UNCHANGED** (consumed as-is) |
| `main.py` | Standalone read-path facade demo (login → list → download); loads `.env`; exits cleanly without creds | **UNCHANGED** — not the CLI entrypoint |
| `pyproject.toml` | Adds `click` dependency + `[project.scripts]` console entry point | **MODIFIED** |

## Recommended Project Structure

```
auraframes/
├── cli.py                 # NEW — click group + subcommands (status/inspect/sync)
├── sync.py                # NEW — SyncPlan dataclass, diff computation, execute_plan()
├── aura.py                # MODIFIED — hoist S3Client/SQSClient reuse for multi-file loops (see Anti-Patterns)
├── api/
│   ├── frameApi.py         # unchanged, consumed via Aura.frame_api
│   └── assetApi.py         # unchanged, consumed via Aura.asset_api
├── models/
│   └── asset.py            # unchanged — md5_hash field already exists, needs LIVE verification (see Gaps)
└── utils/
    ├── frames.py            # NEW — resolve_frame()
    ├── hashing.py            # NEW — local_content_hash()
    ├── settings.py           # unchanged
    ├── io.py                 # unchanged
    └── dt.py                 # unchanged
main.py                       # UNCHANGED — demo entrypoint stays as-is
pyproject.toml                 # MODIFIED — add click, [project.scripts] aura = "auraframes.cli:cli"
```

### Structure Rationale

- **`cli.py` at package root, not `__main__.py`, not replacing `main.py`:** the codebase's existing top-level entrypoint (`main.py`) is explicitly a facade-only demo (see `main.py:1-75`, `PROJECT.md` "Known still-open... `main.py` facade-only read-path demo"). Requirements (PROJECT.md, "Key context") state *"No CLI exists today (`main.py` is a demo only) — this is the first user-facing entry point."* Replacing `main.py` would break that documented role and the existing manual verification path. A new `auraframes/cli.py` module keeps `main.py` untouched and gives the CLI a proper package location that can be unit-tested with `click.testing.CliRunner` (mirrors the project's existing pytest-first testing culture) and wired to a `console_scripts` entry point (`aura = "auraframes.cli:cli"` in `pyproject.toml`) so `uv run aura sync ...` works without `python main.py`.
- **`sync.py` as its own module, not folded into `aura.py`:** `Aura` is already a facade with acknowledged debt (loguru sink leak on repeated construction, `upload_image`/`upload_images` half-finished TODO stubs at `aura.py:100-104`). Growing it further with diffing/planning logic would deepen the "God object" anti-pattern the codebase already has a TODO against (`Aura.clone`, `Aura.upload_images` are unimplemented placeholders reserved for exactly this kind of workflow). Keeping `sync.py` as a *consumer* of `Aura` (same relationship `main.py` already has) preserves the existing layering: `Api` classes have zero business logic, `Aura` composes them, and now `sync.py` composes `Aura` for one specific workflow — consistent with "one thin layer per concern."
- **`utils/frames.py` and `utils/hashing.py` next to `utils/dt.py`/`utils/io.py`:** both are pure, stdlib-only helpers with no network/model dependencies, matching the existing `utils/` contract ("Shared helpers with no business logic," snake_case module names, stdlib-only in `dt.py`/`io.py`).

## Architectural Patterns

### Pattern 1: Plan/Execute split for the destructive command

**What:** `sync` always computes a `SyncPlan` (a plain, serializable list of actions: upload/remove/skip) before touching the network for a write. The CLI prints the plan unconditionally. Only when `--apply`/`--yes` is passed does the CLI call `sync.execute_plan(plan, aura, frame)`.
**When to use:** Any command that can delete/mutate remote state based on a diff against local state — exactly the "full-mirror deletion is destructive" requirement in PROJECT.md.
**Trade-offs:** Slightly more code (two functions instead of one), but it's the only way to make "dry-run by default" a structural guarantee rather than an `if` check sprinkled through the upload/delete code path. It also makes the diff engine trivially testable offline (no network needed to assert on a `SyncPlan`), which fits the project's existing offline-first test investment (`tests/offline.py`, Phase 4).

**Example:**
```python
# auraframes/sync.py
from dataclasses import dataclass
from auraframes.models.asset import Asset

@dataclass
class SyncAction:
    kind: str          # "upload" | "remove" | "skip"
    local_path: str | None
    asset: Asset | None
    reason: str        # "new" | "hash-mismatch" | "removed-locally" | "unchanged"

@dataclass
class SyncPlan:
    frame_id: str
    actions: list[SyncAction]

    def summary(self) -> str:
        ...

def compute_plan(local_dir: str, remote_assets: list[Asset], frame_id: str) -> SyncPlan:
    ...  # pure function — no I/O beyond reading local file bytes to hash them

def execute_plan(plan: SyncPlan, aura, frame_id: str) -> None:
    for action in plan.actions:
        if action.kind == "upload":
            aura.upload_image(frame_id, action.local_path, action.asset)
        elif action.kind == "remove":
            aura.frame_api.remove_asset(frame_id, ...)
```

### Pattern 2: Subcommand dispatch via `click.group()`

**What:** A single `cli()` click group in `auraframes/cli.py` with `@cli.command()` for `status`, `inspect`, `sync`. Shared setup (load `.env`, construct + login `Aura`, resolve `--frame`) lives in a `click.pass_context`/`ctx.obj` pattern so each subcommand doesn't re-implement login.
**When to use:** Any CLI with >1 related subcommand that share auth/setup — this is exactly Click's documented sweet spot (subcommand groups + `ctx.obj` for shared state).
**Trade-offs:** Click is a new dependency (not in current `pyproject.toml`), but it's the most widely adopted Python CLI framework (Click ~38.7% of Python CLI projects per current surveys) and its `click.testing.CliRunner` gives offline, no-network CLI tests — consistent with this project's investment in offline testability (Phase 4). Typer (built on Click, type-hint driven) is a reasonable alternative given this codebase's heavy use of type hints everywhere, but it pulls in Click anyway plus its own dependency surface for marginal boilerplate savings on a 3-command CLI; recommend Click directly for the smaller, more explicit dependency footprint that matches this codebase's "pragmatic, not magic" style (docstrings over decor 
ator-inferred behavior, explicit types, no metaclass-driven CLI parsing).
**Example:**
```python
# auraframes/cli.py
import click
from auraframes.aura import Aura
from auraframes.utils.frames import resolve_frame

@click.group()
@click.pass_context
def cli(ctx):
    ctx.obj = {}

@cli.command()
@click.option('--frame', required=True, help='Frame name or id')
@click.pass_context
def inspect(ctx, frame):
    aura = Aura().login()
    frames = aura.frame_api.get_frames()
    target = resolve_frame(frames, frame)
    ...

@cli.command()
@click.argument('directory')
@click.option('--frame', required=True)
@click.option('--apply', is_flag=True, help='Execute the plan (default: dry-run)')
@click.option('--yes', '-y', is_flag=True, help='Skip confirmation prompt')
def sync(directory, frame, apply, yes):
    ...
    if apply and not yes:
        click.confirm(f'Apply {len(plan.actions)} changes to frame {target.name}?', abort=True)
```

### Pattern 3: Frame resolution as a pure lookup over an already-fetched list

**What:** `FrameApi.get_frames()` (`frameApi.py:13`) already returns fully-hydrated `Frame` objects with `.id` and `.name` (`models/frame.py:26-27`). There is no "get frame by name" endpoint on the live API, so resolution is 100% client-side: fetch all frames once, then match.
**When to use:** Every subcommand that accepts `--frame <name|id>`.
**Trade-offs:** Requires one `get_frames()` call per CLI invocation (cheap — it's the account's frame list, not assets), but keeps the API surface untouched (no new endpoint calls invented) and testable offline against `tests/fixtures/frames.json`.
**Example:**
```python
# auraframes/utils/frames.py
from auraframes.models.frame import Frame

class FrameResolutionError(Exception):
    pass

def resolve_frame(frames: list[Frame], identifier: str) -> Frame:
    by_id = [f for f in frames if f.id == identifier]
    if len(by_id) == 1:
        return by_id[0]
    by_name = [f for f in frames if f.name.lower() == identifier.lower()]
    if len(by_name) == 1:
        return by_name[0]
    if len(by_name) > 1:
        raise FrameResolutionError(
            f"Ambiguous frame name '{identifier}' matches {len(by_name)} frames; use the frame id instead."
        )
    raise FrameResolutionError(f"No frame found matching '{identifier}'.")
```

## Data Flow

### `sync` command flow

```
CLI: aura sync ./photos --frame "Living Room"
    │
    ▼
Aura().login()                       (existing: account_api.login → header mutation)
    │
    ▼
frame_api.get_frames()               (existing) → resolve_frame() (NEW) → Frame
    │
    ▼
aura.get_all_assets(frame.id)        (existing: cursor-paginated) → list[Asset]
    │
    ▼
scan local_dir + local_content_hash()  (NEW, utils/hashing.py) → list[(path, hash)]
    │
    ▼
sync.compute_plan(local, remote)     (NEW) → SyncPlan (upload/remove/skip actions)
    │
    ▼
CLI prints plan (ALWAYS, even without --apply)
    │
    ├─ no --apply  → exit here (dry-run is the default)
    │
    └─ --apply (+ confirm unless --yes)
         │
         ▼
    sync.execute_plan(plan, aura, frame.id)   (NEW)
         │
         ├─ upload action → aura.upload_image(frame.id, path, asset)   (existing, aura.py:106)
         │     → frame_api.select_asset → S3Client.upload_file → asset_api.batch_update → SQS confirm
         │
         └─ remove action → frame_api.remove_asset(frame.id, AssetPartialId(id=asset.id))  (existing, frameApi.py:135)
```

### `inspect` / `status` flow (read-only)

```
status:  Aura().login() → account_api (current user) → frame_api.get_frames() → print health + frame list
inspect: Aura().login() → frame_api.get_frames() → resolve_frame() → aura.get_all_assets(frame.id) → print listing
```

Neither `status` nor `inspect` ever call `upload_image`, `delete_asset`, `batch_update`, or `remove_asset` — this is the "read-only groundwork" phase referenced in the build order below.

## Integration Points (concrete file references)

| Integration point | File:line | Consumed by |
|---|---|---|
| `Aura.__init__(self, client: Client \| None = None)` | `auraframes/aura.py:25` | CLI constructs one `Aura()` per invocation (or injects a `Client(transport=...)` for offline CLI tests, same DI seam as Phase 4) |
| `Aura.login()` | `auraframes/aura.py:35` | Shared setup in every subcommand |
| `Aura.get_all_assets(frame_id, ...)` | `auraframes/aura.py:59` | `inspect` + `sync` (remote asset listing, cursor-paginated already handled) |
| `Aura.upload_image(frame_id, image_path, asset)` | `auraframes/aura.py:106` | `sync.execute_plan()` upload actions — **first live verification of this path is this milestone's goal** |
| `Aura.get_sqs()` | `auraframes/aura.py:130` | Called internally by `upload_image`; **note:** sets `self.sqsClient` outside `__init__` (only created on first call) — fragile if `sync` calls `upload_image` in a tight loop, see Anti-Patterns |
| `FrameApi.get_frames()` | `auraframes/api/frameApi.py:13` | `resolve_frame()` input; `status` frame listing |
| `FrameApi.get_frame(frame_id)` | `auraframes/api/frameApi.py:21` | `inspect` frame metadata (name, num_assets, owner via `.user`) |
| `FrameApi.get_assets(frame_id, limit, cursor)` | `auraframes/api/frameApi.py:38` | Underlying call inside `Aura.get_all_assets` |
| `FrameApi.select_asset(frame_id, asset_partial_id)` | `auraframes/api/frameApi.py:105` | Called inside `Aura.upload_image` before S3 upload |
| `FrameApi.remove_asset(frame_id, asset_partial_id)` | `auraframes/api/frameApi.py:135` | `sync.execute_plan()` remove actions — **recommended** removal call (disassociates from *this* frame only) |
| `AssetApi.batch_update(asset)` | `auraframes/api/assetApi.py:9` | Called inside `Aura.upload_image` after S3 upload, to push `md5_hash`/`file_name`/dimensions |
| `AssetApi.delete_asset(asset)` | `auraframes/api/assetApi.py:74` | **NOT recommended** for `sync`'s remove path — see Anti-Patterns (scope mismatch) |
| `Asset.md5_hash` | `auraframes/models/asset.py:65` | Content-hash diffing basis — **needs live verification**, see Gaps |
| `Asset.is_local_asset` | `auraframes/models/asset.py:109` | Determines whether an asset from `get_all_assets` was ever confirmed uploaded (id present) vs. a local-only placeholder |
| `Frame.id` / `Frame.name` | `auraframes/models/frame.py:26-27` | `resolve_frame()` match fields |
| `S3Client.upload_file(data, extension)` / `get_md5(data)` | `auraframes/aws/s3client.py:14,30` | Confirms the hash algorithm to mirror client-side (`base64(md5(bytes))`) so local hashes are directly comparable to `Asset.md5_hash` |
| `Client(transport=...)` DI seam | `auraframes/client.py:45` | Reuse for CLI-level offline tests (`click.testing.CliRunner` + `tests/offline.py`'s `offline_aura()` composition) |
| `pyproject.toml` `[project.scripts]` | *(new section)* | `aura = "auraframes.cli:cli"` console entry point |

## Anti-Patterns

### Anti-Pattern 1: Growing `Aura` into a sync orchestrator

**What people do:** Add `sync_directory()`, `compute_diff()`, `hash_local_file()` methods directly onto the `Aura` facade because it's the existing "do everything" entry point.
**Why it's wrong:** `Aura` already carries acknowledged debt (loguru sink leak per construction, unimplemented `clone`/`upload_images` stubs, mixed responsibility for AWS auth + API composition + logging init). Every new unrelated method makes `Aura` harder to reason about and re-introduces the exact "single facade with everything" pattern the project's own architecture notes flag as an anti-pattern candidate.
**Do this instead:** Keep `sync.py` as a separate module that takes an already-constructed, already-logged-in `Aura` (or its sub-APIs) as a parameter — same relationship `main.py` already has with `Aura`. `Aura` stays a pure composition root.

### Anti-Pattern 2: Using `AssetApi.delete_asset` for the sync "remove" action

**What people do:** Call `delete_asset()` when a local file disappears, assuming "delete" is the natural inverse of "upload."
**Why it's wrong:** Per its own docstring (`assetApi.py:74-88`), `delete_asset` is explicitly of unknown scope — "**Currently unknown if this is used**... maybe this deletes it from S3/Glacier," which could affect the asset across every frame/collaborator it's attached to, not just the one frame being synced. A directory→frame mirror tool should only affect *its target frame's* association.
**Do this instead:** Use `FrameApi.remove_asset(frame_id, asset_partial_id)` (`frameApi.py:135-148`), which explicitly "disassociates an asset from a frame" and "does not seem to remove the asset from S3/Glacier" — the scoped, reversible operation that matches "mirror this directory to this frame," not "delete this photo everywhere." Treat `delete_asset` as out of scope for `sync` entirely unless a future requirement explicitly asks for account-wide deletion.

### Anti-Pattern 3: Re-authenticating AWS per file in a sync loop

**What people do:** Call `Aura.upload_image()` unmodified in a loop over many local files — each call currently does `client = S3Client()` fresh (`aura.py:117`), which re-runs Cognito anonymous auth (`AWSClient.auth()`) on every single upload.
**Why it's wrong:** For a real directory sync (dozens–hundreds of files), that's redundant Cognito handshakes per file — slow and needlessly chatty against AWS, and `SQSClient` is similarly re-created via `get_sqs()` per call.
**Do this instead:** When wiring `sync.execute_plan()`, hoist a single authenticated `S3Client`/`SQSClient` pair for the whole batch and pass it through, OR add an overload of `upload_image` that accepts pre-built clients. This is a small, additive modification to `aura.py`, not a new component — flag it explicitly in the phase that implements the destructive upload path so it isn't silently reproduced at scale.

### Anti-Pattern 4: Skipping the plan/execute split "because sync is simple"

**What people do:** Compute the diff and immediately act on it inside one function, gating the destructive parts with scattered `if apply:` checks.
**Why it's wrong:** PROJECT.md is explicit that "full-mirror deletion is destructive" and dry-run must be the default — a scattered-`if` implementation is one missed branch away from an unintended live delete against a real account, and it can't be unit-tested without mocking network calls for every dry-run assertion.
**Do this instead:** `compute_plan()` must be a pure function with zero network writes (reads are fine — it needs the already-fetched remote asset list and local file hashes). `execute_plan()` is the only function allowed to call `upload_image`/`remove_asset`. The CLI only invokes `execute_plan` behind `--apply` (+ `--yes` or an interactive `click.confirm`).

## Build Order (phased, safety-first)

1. **Phase: CLI skeleton + `status` (read-only, zero API-write surface)**
   - Add `click` to `pyproject.toml` + `[project.scripts]` entry point.
   - `auraframes/cli.py`: click group, `status` subcommand only — reuses `Aura().login()` + `FrameApi.get_frames()`, prints config/auth health and account frame list.
   - Prove the packaging/entrypoint wiring (`uv run aura status`) works end-to-end without touching any new sync logic.
   - Zero risk: no new component beyond the CLI shell itself.

2. **Phase: `inspect` + frame resolution (read-only)**
   - `auraframes/utils/frames.py`: `resolve_frame()`.
   - `inspect` subcommand: `--frame <name|id>` → resolve → `FrameApi.get_frame()` (metadata) + `Aura.get_all_assets()` (listing).
   - **Live-verify here** whether `Asset.md5_hash` is actually populated on assets returned from `GET /frames/{id}/assets.json` for photos that were *not* uploaded through this client (this is the open question flagged in the milestone — the field exists in the model but its population source on read is unconfirmed). This phase is the cheapest place to answer it, since it's pure reading.

3. **Phase: sync-diffing engine, dry-run only (read-only w.r.t. the frame; local disk read for hashing)**
   - `auraframes/utils/hashing.py`: `local_content_hash()`, matching `S3Client.get_md5`'s `base64(md5(bytes))` scheme.
   - `auraframes/sync.py`: `SyncPlan`/`SyncAction`/`compute_plan()` only (no `execute_plan()` yet).
   - `sync` subcommand exists but **`--apply` is not yet implemented / not yet wired** — every invocation prints the plan and exits. This proves the diff algorithm (new/changed/removed detection) against real frame data without any possibility of a live write.
   - Depending on the phase-2 verification result: if `md5_hash` isn't reliably present on read, fall back to filename+size+`taken_at` heuristics for "unchanged" detection, and treat any asset lacking a hash as "needs re-check" rather than silently trusting a stale match.

4. **Phase: destructive execution path, gated (the actual write/delete verification this milestone exists for)**
   - `sync.execute_plan()`: wires upload actions to `Aura.upload_image()` (first live verification of select_asset → S3 → SQS → batch_update) and remove actions to `FrameApi.remove_asset()` (scoped disassociation, not `AssetApi.delete_asset()`).
   - Apply the Anti-Pattern 3 fix (hoist S3/SQS client reuse) as part of this phase, since it's only a problem once real multi-file execution exists.
   - `--apply` flag + `--yes`/interactive `click.confirm()` gate wired in the CLI.
   - This is the only phase that should touch a real account/frame with write intent — sequence it last, and only after phases 1–3 have proven login, listing, resolution, and diffing correct against live data in read-only mode.

## Scaling Considerations

Not a scale-sensitive domain (single-user CLI against one account's frames), but two practical thresholds matter:

| Scale | Consideration |
|-------|--------------------------|
| Small frame (<100 assets), small local dir | Current cursor pagination (`FrameApi.get_assets`, `limit=1000` default) and a single-pass local dir walk are more than sufficient; no batching needed. |
| Large frame / large local dir (hundreds–thousands of files) | Local hashing is I/O-bound — reading every file's full bytes to MD5 it on every `sync` invocation gets slow; consider a size+mtime pre-filter before hashing (only hash candidates whose size/mtime differ from a cached manifest) as a later optimization, not required for MVP. AWS re-auth-per-upload (Anti-Pattern 3) is the first real bottleneck once file counts grow past a handful. |

## Sources

- Primary source: this repository — `auraframes/aura.py`, `auraframes/client.py`, `auraframes/api/frameApi.py`, `auraframes/api/assetApi.py`, `auraframes/aws/s3client.py`, `auraframes/models/asset.py`, `auraframes/models/frame.py`, `main.py`, `pyproject.toml`, `tests/offline.py` — confidence HIGH (direct code read, not inference).
- [Real Python — Click and Python: Build Extensible and Composable CLI Apps](https://realpython.com/python-click/) — subcommand group patterns — confidence MEDIUM (community tutorial, cross-checked against Click's own documented `@click.group()`/`ctx.obj` behavior).
- [dasroot.net — Building CLI Tools with Python: Click, Typer, and argparse](https://dasroot.net/posts/2025/12/building-cli-tools-python-click-typer-argparse/) — framework comparison / adoption figures — confidence MEDIUM (single web source, used only to corroborate the Click-vs-Typer trade-off, not as the sole basis for the recommendation).
- [Typer — Alternatives, Inspiration and Comparisons](https://typer.tiangolo.com/alternatives/) — Typer's own framing of when it's preferable to Click — confidence MEDIUM.

---
*Architecture research for: Aura Frames directory-to-frame sync CLI (v2.0 milestone)*
*Researched: 2026-07-05*
