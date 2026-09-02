# Phase 7: Sync-Diffing Engine (Dry-Run Only) - Pattern Map

**Mapped:** 2026-07-07
**Files analyzed:** 3 (1 modified, 2 reused-as-is)
**Analogs found:** 1 / 1 (the only file needing a new pattern is `cli.py`; the other two are direct reuse, not new patterns)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `auraframes/cli.py` — new `sync` subparser + `run_sync()` handler + `compute_plan()` helper | controller (CLI command handler) + utility (pure diff function) | request-response (CLI) / transform (diff) | `run_inspect()` + `resolve_frame()` in the same file (`auraframes/cli.py`) | exact (same file, same conventions, sibling command) |
| `auraframes/aws/s3client.py` — `get_md5(data)` | utility | transform | N/A — reused as-is, no new file/pattern needed | reuse, not analog |
| `auraframes/models/asset.py` — `Asset.md5_hash`, `Asset.id`, `Asset.taken_at_dt` | model | CRUD (read-only field access) | N/A — reused as-is, no new file/pattern needed | reuse, not analog |

Note: there is no separate `auraframes/sync.py` file mandated — CONTEXT.md leaves the
scan/hash/diff helper's location to Claude's discretion, "following the precedent set by
`resolve_frame`'s placement" (i.e., a pure function living in `cli.py`, or a small sibling
module import into `cli.py` — either way, `run_sync()` must be the CLI-layer orchestrator
following `run_inspect()`'s shape exactly).

## Pattern Assignments

### `auraframes/cli.py` — `sync` subparser wiring (controller, request-response)

**Analog:** `build_parser()`, same file, lines 19-39

**Current subparser wiring pattern** (lines 28-39):
```python
parser = argparse.ArgumentParser(prog='aura-cli')
parser.add_argument(
    '--debug',
    action='store_true',
    default=False,
    help='Show verbose loguru request/response logging on stderr',
)
subparsers = parser.add_subparsers(dest='command', required=True)
subparsers.add_parser('status', help='Check config/auth health and list account frames')
inspect_parser = subparsers.add_parser('inspect', help="Inspect a frame's photos and metadata")
inspect_parser.add_argument('--frame', required=True, help='Frame name (substring) or id')
return parser
```

**What to copy for `sync`:** add a third subparser following the exact same shape —
positional `dir` argument (new, since `sync` takes a local directory, unlike
`inspect`/`status`) plus the same `--frame` flag `inspect` uses verbatim:
```python
sync_parser = subparsers.add_parser('sync', help='Dry-run diff a local directory against a frame')
sync_parser.add_argument('dir', help='Local directory to scan for photos')
sync_parser.add_argument('--frame', required=True, help='Frame name (substring) or id')
```
The docstring comment on line 21 ("Subparsers are structured so `inspect`/`sync` siblings
can be added in later phases (D-02)") already anticipates this exact addition — this
phase is that anticipated addition.

---

### `auraframes/cli.py` — `run_sync()` handler (controller, request-response)

**Analog:** `run_inspect()`, same file, lines 149-211

**Core pattern to copy** (full function, lines 149-211): the handler shape is:
1. `aura = aura or Aura()` — DI seam for offline testability (copy verbatim).
2. `_configure_cli_logging(debug)` — call immediately after `Aura()` construction, before
   any login/HTTP call (copy verbatim, same placement).
3. `try: aura.login() except Exception as e: print(f'Login failed: {e}'); return 1` —
   copy verbatim (lines 163-169).
4. Inner `try/except Exception as e` around the rest of the command body, printing
   `f'Failed to <verb> frame: {e}'` and returning 1 on failure (lines 171/205-209) — this
   is the fail-loud WR-01/D-05 convention; `run_sync` should wrap its scan+diff+print body
   the same way, e.g. `print(f'Failed to sync frame: {e}')`.
5. `frames = aura.frame_api.get_frames(); resolved = resolve_frame(frame_arg, frames)` —
   reuse `resolve_frame` exactly as `run_inspect` does (lines 172-173), including the
   `ambiguous`/`not_found` branches printed identically (lines 175-185) — copy verbatim,
   no changes needed since `sync --frame` uses the same resolution semantics.
6. `assets = aura.get_all_assets(resolved.frame.id)` (line 197) — reuse exactly for the
   frame-side of the diff (already paginates all assets, per CONTEXT.md's Reusable Assets
   note).
7. Function signature convention: `def run_sync(dir_arg: str, frame_arg: str, aura=None, debug: bool = False) -> int:` —
   mirrors `run_inspect(frame_arg: str, aura=None, debug: bool = False) -> int` (line
   149) with one added positional param for the directory.
8. Return convention: `int` exit code, never `sys.exit` directly — same as
   `run_status`/`run_inspect` (0 success, 1 failure) so `capsys`-based tests can assert on
   both stdout and return value.

**Ambiguous/not_found branch pattern to copy verbatim** (lines 175-185):
```python
if resolved.status == 'ambiguous':
    print(f"'{frame_arg}' matches more than one frame name — re-run with --frame <id>:")
    for candidate in resolved.candidates:
        print(f'  - {candidate.name} (id: {candidate.id})')
    return 1

if resolved.status == 'not_found':
    print(f"No frame matches name or id '{frame_arg}'. Available frames:")
    for candidate in resolved.candidates:
        print(f'  - {candidate.name} (id: {candidate.id})')
    return 1
```

---

### `resolve_frame()` / `FrameResolution` — reused as-is (pure function pattern to mirror for `compute_plan`)

**Analog:** `auraframes/cli.py` lines 109-146

**Pure-function/dataclass-result shape to copy for the new diff logic** (lines 109-146):
```python
@dataclass
class FrameResolution:
    frame: Frame | None
    status: str
    candidates: list[Frame] = field(default_factory=list)


def resolve_frame(target: str, frames: list[Frame]) -> FrameResolution:
    """Pure function — no I/O, no side effects."""
    ...
    return FrameResolution(frame=..., status=..., candidates=...)
```

**Apply this shape to the new diff function**, e.g.:
```python
@dataclass
class SyncPlan:
    to_upload: list[Path]       # deduped local files with no frame-side match
    to_delete: list[Asset]      # surplus frame assets, multiset-matched
    unchanged: int              # count of matched pairs
    skipped_non_image: int      # D-03 summary count


def compute_plan(local_hashes: dict[str, list[Path]], frame_assets: list[Asset]) -> SyncPlan:
    """Pure function — no I/O, no side effects (mirrors resolve_frame)."""
    ...
```
This directly satisfies CONTEXT.md's "Established Patterns" note: "the hash-diff
computation should follow the same shape ... for offline testability" and PROJECT.md's
dry-run-via-separate-functions requirement (`compute_plan()` vs. a future `execute_plan()`
in Phase 8).

---

### `main()` dispatch — reused pattern (controller, request-response)

**Analog:** `auraframes/cli.py` lines 214-223

**Current dispatch pattern**:
```python
def main(argv=None) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)

    if args.command == 'status':
        return run_status(debug=args.debug)
    if args.command == 'inspect':
        return run_inspect(args.frame, debug=args.debug)
    raise ValueError(f'Unhandled command: {args.command}')
```

**Add a third branch, copying the exact `if`-chain shape**:
```python
if args.command == 'sync':
    return run_sync(args.dir, args.frame, debug=args.debug)
```

---

## Shared Patterns

### DI seam + logging bootstrap
**Source:** `auraframes/cli.py` lines 158-161 (`run_inspect`), identical in `run_status` lines 87-90
**Apply to:** `run_sync()`
```python
aura = aura or Aura()
# Must run after Aura() construction (which registers the noisy sinks)
# and before login/get_frames (the HTTP calls that trigger them).
_configure_cli_logging(debug)
```

### Fail-loud login + broad-catch convention
**Source:** `auraframes/cli.py` lines 163-169 and 205-209
**Apply to:** `run_sync()` — wrap login in its own try/except returning 1 on
`Login failed: {e}`, and wrap the scan/hash/diff/print body in a second try/except
returning 1 on `Failed to sync frame: {e}`.

### Base64-MD5 hashing convention (SYNC-02)
**Source:** `auraframes/aws/s3client.py` line 14
```python
def get_md5(data):
    return base64.b64encode(hashlib.md5(data).digest()).decode('utf-8')
```
**Apply to:** local file content-hashing in the new sync helper — call
`from auraframes.aws.s3client import get_md5` and pass raw file bytes
(`Path.read_bytes()`) to it; do not reimplement the hashlib/base64 logic independently
(D-09's one-time live validation exists precisely to confirm this is byte-identical to
what the frame's `Asset.md5_hash` values encode).

### Frame-side asset field access for delete-candidate identification (D-08)
**Source:** `auraframes/models/asset.py` lines 45, 65, 83-85, 105-106; usage pattern at
`auraframes/cli.py` line 201
```python
# asset.py: fields already modeled, no schema change needed
md5_hash: Optional[str] = None
taken_at: str

@property
def taken_at_dt(self):
    return parse_aura_dt(self.taken_at)
```
```python
# cli.py inspect's existing print-shape to mirror for delete candidates
print(f'  - {asset.id} | {asset.file_name} | {asset.taken_at_dt}')
```
**Apply to:** delete-candidate lines in the sync plan output, per D-08's exact format
`- abc123 (taken 2024-03-11)` — i.e. `print(f'  - {asset.id} (taken {asset.taken_at_dt})')`,
omitting `file_name` since D-08 explicitly says no filename/hash is shown.

## No Analog Found

None — every file touched in this phase either follows `cli.py`'s existing
`run_inspect`/`resolve_frame` conventions directly, or is reused unmodified
(`s3client.get_md5`, `Asset.md5_hash`). There is no directory-scanning/hashing precedent
elsewhere in the codebase (confirmed net-new per CONTEXT.md's Integration Points note),
but the pure-function pattern to model it on (`resolve_frame`) is a strong analog, not a
gap.

## Metadata

**Analog search scope:** `auraframes/cli.py`, `auraframes/aws/s3client.py`,
`auraframes/models/asset.py`
**Files scanned:** 3 (full reads, all ≤ 230 lines — single-pass reads, no re-reads needed)
**Pattern extraction date:** 2026-07-07
