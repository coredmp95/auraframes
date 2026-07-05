# Stack Research

**Domain:** CLI additions for an existing sync httpx/pydantic/boto3 client (directory-to-frame sync)
**Researched:** 2026-07-05
**Confidence:** MEDIUM (codebase inspection is HIGH; ecosystem library facts are LOW/web-sourced but cross-checked; one core design question — whether `md5_hash` round-trips on `GET assets` — is unverified and must be checked live early in the milestone)

## Executive Framing

The single most important finding in this research did not come from the web — it came
from the codebase itself. **`auraframes/models/asset.py` already has an `md5_hash: Optional[str]`
field, and `auraframes/aws/s3client.py` already computes it** (`get_md5()` = base64-encoded
`hashlib.md5(data).digest()`) as part of the existing upload flow (`Aura.upload_image()` sets
`asset.md5_hash = md5` before calling `AssetApi.batch_update()`). This means the API is
*already* MD5-content-addressed for exactly the "does this local file already exist on the
frame" question the sync command needs to answer. The stack recommendation below is built
around reusing that existing convention rather than inventing a new one.

It also matters that **uploaded filenames are randomized** — `S3Client.upload_file()` names
every object `f'{uuid4()}{extension}'` — so `Asset.file_name` on a remote asset has no
relationship to the local file it came from. Filename/path matching is not viable as a diff
key; content hash is the only reliable correlation between "this file in the directory" and
"this asset on the frame."

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `argparse` (stdlib) | bundled with Python 3.14 | CLI arg/subcommand parsing for `sync` / `inspect` / `status` | Zero new dependencies. This is the *first* real CLI in a codebase whose stated philosophy is "pragmatic modernization... avoid broad refactors" and whose current dependency list (pydantic, httpx, boto3, Pillow, piexif, geopy, loguru, tqdm, python-dotenv) contains no CLI framework. Three subcommands, a handful of flags (`--frame`, `--apply`/`--yes`, `--dry-run` default) is squarely inside what `add_subparsers()` + `store_true` handles cleanly. Adding click or typer here would be the first framework dependency introduced purely for developer convenience, not because argparse is inadequate. |
| `hashlib.md5` (stdlib) | bundled | Content-hash key for local-file ↔ remote-asset matching | Matches the digest algorithm the Aura/Pushd API *already* uses (`Asset.md5_hash`, computed with `hashlib.md5` in `s3client.py`). Using sha256 or blake2b locally would require either double-hashing or a translation layer with zero benefit — there is nothing to compare a stronger/faster hash against on the remote side. MD5 is used here purely as a content-addressing key (S3 ETags use the same non-cryptographic pattern), not for security, so its cryptographic weaknesses are irrelevant. |
| Remote listing (`FrameApi.get_assets()`) as source of truth | existing, no new code needed | Diff basis for `sync` (upload new / skip matching / delete orphaned) | `get_assets()` already returns the *full, paginated* asset list for a frame each call — no persistent local manifest is structurally required to know "what's on the frame." Whether this eliminates the need for a manifest entirely depends on one unverified fact (see **Verify Live First** below): does the `GET /frames/{id}/assets.json` response actually populate `md5_hash`, or is that field only ever sent on write (`batch_update`)? `md5_hash` is `Optional[str] = None` on the model and is hydrated generically (`Asset(**asset_data)`), so if the API includes it in listing responses it "just works" already — nothing to build. If it does not, a minimal local manifest becomes necessary (see **Stack Patterns by Variant**). |

### Verify Live First (blocks the diff design)

This is a spike, not a library choice, but it gates everything else in this section:

1. Upload one test asset (or inspect an existing frame with `inspect`/a debug script).
2. Call `FrameApi.get_assets()` and check whether `md5_hash` is non-null on the returned `Asset` objects.
3. If populated → local MD5 vs. `Asset.md5_hash` equality check is sufficient; no manifest needed (recommended path).
4. If null/absent on read → fall back to the manifest-file variant below.

Flag this explicitly for the roadmap: it should be one of the first things checked in the
phase that implements `sync`'s diff logic, ideally before the diff algorithm is finalized.

### Supporting Libraries (already present — no new install needed)

| Library | Version (pinned today) | Purpose | When to Use |
|---------|---------|---------|-------------|
| `tqdm` | `>=4.66` (already a dependency) | Progress bars during multi-file upload/download batches in `sync` | Reuse for the `sync --apply` upload/delete loop exactly as it's already used in `Aura.download_images_from_assets()` — no new dependency, consistent UX with existing batch operations. |
| `python-dotenv` | `>=1.0` (already a dependency) | `.env` loading for `AURA_EMAIL`/`AURA_PASSWORD` | `status` and all three commands need credentials resolved the same way `main.py` already does it — reuse the existing `load_dotenv()` call site, don't reintroduce a second config mechanism. |
| `loguru` | `>=0.7` (already a dependency) | Structured logging for `sync`'s plan/apply actions | Reuse `Aura._init_logger()`'s existing sinks rather than adding a second logging setup for the CLI. (Note: the known sink-leak-on-repeated-construction bug is pre-existing tech debt, not introduced by this milestone — don't fix it here unless it's already in scope.) |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `uv` (already adopted) | Run/install the CLI entry point | Add a `[project.scripts]` entry (e.g. `aura-sync = "auraframes.cli:main"`) to `pyproject.toml` so `uv run aura-sync sync ./photos --frame Kitchen` works without inventing a second invocation convention beyond the existing `python main.py` pattern. |
| `pytest` (already a dev dependency) | Test the CLI's argument parsing and diff logic offline | The existing `Client(transport=...)` / `Aura(client=...)` DI seam and `httpx.MockTransport` harness (Phase 4) already give the CLI's `sync`/`inspect` logic an offline test path — build CLI tests on top of that harness rather than adding a second CLI-testing library (`click.testing.CliRunner` etc. — moot if argparse is chosen, since there is nothing framework-specific to test beyond `argparse.Namespace` construction, which is trivially unit-testable). |

## Installation

```bash
# Core CLI: no new dependencies required (argparse + hashlib are stdlib)

# Only if the manifest-file variant is needed (see below) — still stdlib, no install:
# `json` + `pathlib` are stdlib; a manifest does not require a new dependency either.

# Optional nicety only, not required for MVP scope (nicer `inspect`/`status` tables):
# uv add rich
```

No `uv add` is required for the CLI's core functionality under the recommended path. This
is a deliberate outcome of the research, not an oversight — flag it to the roadmap as a
positive constraint to preserve (don't let a later phase casually pull in click/typer/rich
for cosmetic reasons without weighing the dependency-footprint tradeoff explicitly).

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `argparse` | `click` (8.4.2) | If the CLI grows well beyond 3 commands, needs plugin-style command groups, or needs shell-completion/config-file layering out of the box. Click is mature, well-documented, and moderate in dependency weight (fewer transitive deps than typer). Not justified for 3 flat subcommands. |
| `argparse` | `typer` (0.26.8) | If the team wants type-annotation-driven CLI definitions and is willing to accept `rich` + `shellingham` + `annotated-doc` (+`colorama` on Windows) as new runtime dependencies. Typer as of 0.26 vendors Click internally rather than depending on it externally, which somewhat reduces the *external* dependency surface but the new deps it does add (`rich` et al.) are pure additions relative to today's stdlib-only CLI story. Better fit for a codebase that already leans on type hints for validation UX elsewhere (this one already does via pydantic, so it's not a bad fit long-term) — but it's overkill for a first, 3-command CLI. |
| Full-file `hashlib.md5` | Size + partial-hash proxy (like rsync/rclone's default quick-check) | Only relevant at rsync/rclone's scale (arbitrary huge files, remote filesystems with expensive full reads). A personal photo directory (hundreds to low-thousands of JPEGs, occasional video) makes full-file MD5 computation trivial (single-digit seconds total), and there is no cheap remote byte-size field on `Asset` to use as a quick-check proxy anyway — an extra `head_object` S3 call per asset to get `ContentLength` would cost more round trips than just hashing. |
| Remote listing as sole source of truth | Local JSON manifest (`.aura-sync/<frame_id>.json`) mapping local path → last-known md5 → remote asset id | **Only if the live-verify spike above shows `md5_hash` is not populated on `GET assets`.** In that case the manifest becomes the only way to know "this local file was already uploaded and became that remote asset," since filenames don't survive upload. Keep it a flat JSON file via stdlib `json` — do not add a database. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `click` or `typer` as a default choice | Adds a first framework dependency (plus, for typer, `rich`/`shellingham`/`annotated-doc`) to solve a problem 3 flat subcommands don't have; contradicts the codebase's stated "pragmatic, minimal-dependency" modernization stance | `argparse` (stdlib) |
| `sqlite3` or any embedded database for sync state | Massive overkill for tracking up to a few thousand path→hash→asset-id rows; adds schema/migration concerns the project has nowhere else | A flat JSON manifest file (stdlib `json`), and only if the live-verify spike shows it's actually needed |
| Shelling out to `rsync`/`rclone` as a subprocess | The sync target isn't a filesystem or generic remote — it's the Aura cloud API's asset/S3/SQS upload dance (`select_asset → S3 → SQS → batch_update`), which has no rsync/rclone backend; the actual sync logic must be custom Python against `AssetApi`/`FrameApi`/`S3Client` | Custom diff + upload/delete logic built on the existing `*Api` classes |
| Size/partial-hash "cheap proxy" hashing | No remote byte-size field exists on `Asset` to compare against cheaply; saves nothing at this data scale and adds a second, weaker matching path that can produce false positives | Full-file `hashlib.md5`, matching the API's own convention |
| Async/`asyncio` rewrite of the HTTP layer to speed up the sync command | Explicitly out of scope for this codebase ("Async migration of the HTTP client — not required to revive; existing sync client is fine") — this milestone doesn't change that calculus; `tqdm`-wrapped sequential/threaded batches are enough for a personal photo directory | Reuse the existing synchronous `httpx.Client` + `tqdm` batch pattern already in `Aura.download_images_from_assets()` |
| Introducing a second logging or config mechanism for the CLI | `loguru` sinks and `.env`/`python-dotenv` loading already exist and are wired through `Aura`/`main.py` | Reuse `Aura._init_logger()` and the existing dotenv call site |

## Stack Patterns by Variant

**If the live-verify spike confirms `Asset.md5_hash` is populated on `GET /frames/{id}/assets.json`:**
- Use remote listing alone as the diff source of truth. No manifest file, no new dependency.
- `sync` becomes: walk local dir → md5 each file → `get_all_assets(frame_id)` → set-diff on md5 → plan (upload / skip / delete) → print plan (dry-run default) → execute only behind `--apply`.

**If the spike shows `md5_hash` is null/absent on read (only ever accepted on write via `batch_update`):**
- Add a minimal local JSON manifest (stdlib `json`, no new dependency) written after every successful `sync --apply`, keyed by local file md5, storing `{local_path, md5, remote_asset_id, uploaded_at}`.
- The manifest becomes the only reliable record of "this local file is already that remote asset" (filenames don't survive upload). Still avoid a database — a flat file is enough at this scale, and the recovery story if it's ever lost/corrupted is "next `sync` re-uploads a duplicate," which is acceptable and dry-run-visible, not catastrophic.
- Treat the manifest as a cache, not a ledger of truth about what's *actually* on the frame — always reconcile against a fresh `get_all_assets()` call before deleting anything, so a stale/corrupted manifest can under-trust (extra uploads) but should never over-trust into a wrong deletion.

**Regardless of which variant applies — CLI destructive-action safety:**
- Default the `sync` command to a dry-run plan output (mirrors `aws s3 sync --dryrun` convention already familiar to anyone who's used AWS CLI, which this codebase's users likely have given the AWS-backed upload path).
- Require an explicit `--apply` (and/or `--yes` for skipping a final confirmation prompt) before any delete or upload executes, matching the milestone's own stated hard safety default ("Full-mirror deletion is destructive, so dry-run-first is a hard safety default").

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `argparse` (stdlib) | Python 3.14 | No version concerns; bundled. |
| `hashlib.md5` / `hashlib.file_digest` | Python 3.14 | `hashlib.file_digest()` (chunked, file-object based) is available since Python 3.11 — safe to use on 3.14 for hashing large video assets without manual chunking code, or a manual `while chunk := f.read(65536)` loop works identically on any version. |
| `Asset.md5_hash` field | pydantic v2 model already in place | No model changes needed — the field already exists and is `Optional[str]`; hydration is automatic from whatever the API response contains. |
| `S3Client.get_md5()` | existing `auraframes/aws/s3client.py` | The sync command's local-hash computation should produce values directly comparable to this function's output (base64-encoded raw MD5 digest, not hex digest) if the manifest/comparison path ever needs to line up with what gets sent to `batch_update` — pick one canonical representation (base64, matching the existing convention) and use it consistently in the new code rather than introducing hex digests as a second format. |

## Sources

- Codebase inspection (HIGH confidence — primary source, not a claim): `auraframes/models/asset.py:65` (`md5_hash` field), `auraframes/api/assetApi.py:29` (`md5_hash` included in `batch_update` payload), `auraframes/aws/s3client.py:14-15,30-34` (`get_md5()`, `upload_file()` UUID-based renaming), `auraframes/aura.py:106-128` (`upload_image()` end-to-end flow), `auraframes/api/frameApi.py:38-58` (`get_assets()` pagination/hydration), `pyproject.toml` (current dependency set).
- [Typer PyPI page](https://pypi.org/project/typer/) — LOW confidence, web-sourced, cross-checked against GitHub releases page — version 0.26.8 (June 2026), vendors Click since 0.26.0.
- [Click PyPI/changelog](https://click.palletsprojects.com/en/stable/changes/) — LOW confidence, web-sourced — version 8.4.2 (June 2026).
- [argparse — Python docs](https://docs.python.org/3/library/argparse.html) and [Real Python argparse guide](https://realpython.com/command-line-interfaces-python-argparse/) — LOW confidence, web-sourced — subcommand/dry-run patterns.
- [rclone sync docs](https://rclone.org/commands/rclone_sync/) / [rclone check docs](https://rclone.org/commands/rclone_check/) — LOW confidence, web-sourced — size/mtime vs. checksum comparison tradeoffs at scale.
- [AWS CLI s3 sync reference](https://docs.aws.amazon.com/cli/latest/reference/s3/sync.html) — LOW confidence, web-sourced — `--dryrun`/`--delete` safety convention.
- [hashlib.file_digest discussion / runebook reference](https://discuss.python.org/t/hashlib-file-digest-should-take-a-pathlib-path-object-to-compute-a-hash-of-file-in-the-filesystem/25995) — LOW confidence, web-sourced — chunked file hashing pattern, Python 3.11+.

---
*Stack research for: Aura Frames directory-to-frame sync CLI (v2.0 milestone)*
*Researched: 2026-07-05*
