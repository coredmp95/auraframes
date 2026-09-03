# Feature Research

**Domain:** Directory-to-cloud-device sync CLI (mirror/inspect/status for the Aura Frames unofficial API)
**Researched:** 2026-07-05
**Confidence:** HIGH (sync-tool conventions; corroborated across rclone/aws-cli/rsync/gsutil docs) / HIGH (Aura-specific findings — verified directly against this repo's source, not inferred) / LOW (live behavior of the two unverified write endpoints this milestone depends on)

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist for *any* tool that claims to "sync a directory to a remote." Missing these makes the tool feel unsafe or unfinished, especially since deletion is destructive to a live user's actual photo frame.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Dry-run by default | Every reference tool (`rclone sync`, `aws s3 sync --delete`, `rsync --delete`, `gsutil rsync -d`) treats "preview before destructive delete" as the standard safety convention, not an opt-in extra. `rclone`/`gsutil` docs explicitly recommend running `-n`/`--dry-run` first "especially when working with important data." | LOW | Already the spec'd default (`sync` dry-runs unless `--apply`/`--yes`). Print the same plan that would run for real — never a different code path, or dry-run can lie. |
| Explicit apply/execute flag | `rsync`/`aws s3`/`gsutil` all gate the *destructive* variant behind an explicit flag or separate invocation (`--delete` itself, or dry-run-then-rerun-without-`-n`). No mainstream sync tool auto-executes deletions without an explicit signal. | LOW | Spec already has `--apply`/`--yes`. Recommend requiring the flag be explicit even if `--frame` is passed — no "sync now" implicit default. |
| Per-action plan output (add/delete/skip) before executing | rclone's dry-run verbose output lists files to copy, **FILES TO BE DELETED**, and files to update, then a summary — this three-bucket breakdown is the de facto standard shape for sync-preview output. | LOW-MED | Group output into "will upload N", "will delete N", "unchanged N" — mirrors what every reference tool prints. |
| Content-based comparison key (not filename/mtime) | Content hashing "detects true duplicates even if files are renamed or moved, unlike methods comparing only filenames, sizes, or modification dates" — and this codebase's own `Asset.md5_hash` field (populated via `S3Client.get_md5`, a base64 MD5 digest, in `auraframes/aws/s3client.py:14-15`) is already the API's native comparison key. Filenames on Aura assets are server-rehashed on upload anyway, so filename-matching would be unreliable even if desired. | MED | **Grounded in code, not just convention**: `auraframes/models/asset.py:65` already has `md5_hash: Optional[str]`. Compute base64-MD5 of local file bytes (same algorithm as `get_md5()`) and compare to each asset's `md5_hash` returned by `get_assets()`. **Unverified assumption to confirm live early in the phase**: does `get_assets()` actually populate `md5_hash` for *pre-existing* frame assets (not just ones this client uploaded)? If the field is frequently null for legacy/device-uploaded assets, hash-matching degrades silently to "always looks new" — this is a concrete phase-1 spike, not a coding risk. |
| Non-zero exit code on failure / plan-has-changes signal | AWS CLI convention: exit 0 on success, non-zero on failure, checked via `$?` in scripting. Standard CLI expectation for anything meant to be scriptable/cron-able. | LOW | Recommend: `0` = ran clean (dry-run or apply, nothing failed), non-zero = any upload/delete failure. Consider a distinct code for "dry-run found pending changes" only if scripting demand emerges — not required for MVP. |
| Frame targeting by name OR id | Milestone spec requires `--frame <name|id>`. No API endpoint resolves name→id server-side (`FrameApi.get_frames()` only returns the full list); client must resolve locally. | LOW | Resolve by exact `id` match first, then case-sensitive `name` match against `get_frames()`. **Must handle duplicate names** (nothing stops two frames sharing a display name) — fail loudly with a "multiple frames named X, use --frame <id>" error rather than silently picking one. |
| Progress indication for multi-file operations | Table-stakes UX for any tool moving many files; this codebase already has `tqdm` as a dependency and uses it in `download_images_from_assets()` (`auraframes/aura.py`). | LOW | Reuse the existing `tqdm` pattern already proven in the read path — no new dependency needed. |
| Human-readable summary line at the end | Every reference tool (`rclone`, `aws s3 sync`, `rsync`) ends a run with a short totals line (files transferred, deleted, bytes, errors). Users expect "what just happened" without re-reading the whole log. | LOW | e.g. `12 uploaded, 3 deleted, 41 unchanged, 0 failed`. |

### Differentiators (Competitive Advantage)

Not required for a minimally-safe sync tool, but valuable given this project's specific context (unofficial/undocumented API, unverified write paths, single-user CLI rather than a general-purpose sync product).

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Prefer `remove_asset` (unassociate) over `delete_asset` (destroy) as the sync-delete primitive | `FrameApi.remove_asset()`'s own docstring says it "does not seem to remove the asset from S3/Glacier" — i.e. reversible/soft. `AssetApi.delete_asset()`'s docstring says **"currently unknown if this is used ... maybe this deletes it from S3/Glacier"** — i.e. the code author themselves flags it as unverified and possibly hard-destructive. For a mirror-delete feature whose whole risk profile is "irreversibly nukes a user's real photos," defaulting to the already-safer, already-documented-as-non-destructive primitive is a meaningful safety differentiator over a naive implementation that reaches for `delete_asset` because the name sounds more "sync --delete"-correct. | LOW (once decided) | **This is an explicit architectural decision for requirements, not just an implementation detail** — recommend `sync`'s delete action call `remove_asset`, not `delete_asset`, and document why in REQUIREMENTS.md/ADR. |
| `--max-delete`-style safety guardrail | rsync's own best-practice guidance: "add a guardrail... If rsync would delete more than N files, it aborts before touching anything," recommended specifically for `--delete` pipelines. Directly transferable to a frame-mirror tool where a wrong `<dir>` argument (e.g., an empty or wrong-directory typo) could otherwise queue mass deletion of a real frame's entire photo set. | LOW | e.g. abort `--apply` if planned deletions exceed some threshold or percentage of the frame's assets, unless `--yes`/a stronger override is also given. Cheap insurance given the destructive stakes called out in the milestone itself. |
| Machine-readable plan output (`--json`) | Useful for scripting/CI use of `sync --dry-run`, mirroring `rclone`'s `lsjson`/`lsf --format` pattern (human-readable by default, structured on request). | MED | Defer unless a concrete scripting need shows up — see Anti-Features/MVP notes; nice differentiator, not core value. |
| Idempotent no-op reruns | Running `sync` twice in a row with no local changes should plan/report zero actions — this is what "mirror" *means*, and it's the natural side effect of hash-based comparison done right. Differentiator only in the sense that it must be explicitly tested, since it's exactly the case naive filename/mtime-based sync tools get wrong (mtime changes on file copy, git checkout, etc., even when content is identical). | LOW | Validate with a same-directory-twice UAT case in the phase's verification. |
| `inspect` shows frame metadata beyond the bare asset list (owner, contributor/member count, `num_assets`) | Milestone spec explicitly asks for "member/contributor count, any stats-like fields" — confirmed available: `Frame.contributors: Optional[list[User]]` and `Frame.num_assets: int` already exist on the model (`auraframes/models/frame.py:47,62`), no new API surface needed. | LOW | Straightforward — this is already-hydrated data, just needs to be selected/printed, not fetched anew. |
| `status` reports which *account* is authenticated (not just "auth OK") | Doctor/status commands across the ecosystem (Salesforce CLI, `cli doctor` for M365) report identity/scope info, not just a boolean — "auth mode, configuration, roles, and scopes" is the cited convention. Concretely available here via `AccountApi.login()`'s returned `User` (`email`, `name`, `id`) and `FrameApi.get_frames()` for "frames on the account." | LOW | All backed by already-verified read-path calls (`login`, `get_frames`) — zero new/unverified API risk for `status`. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that look like natural extensions of "sync a directory" but would be scope creep, unsafe, or unsupported by the actual API surface for this milestone.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|------------------|-------------|
| Continuous/watch-mode sync (auto-run on filesystem change) | Feels like the "real" Google-Photos-style experience — background auto-upload. | No official/stable long-poll or push mechanism has been verified for this unofficial API; `SQSClient` long-polls and blocks (documented architectural constraint), and the whole write path is unverified live in the first place. Building a daemon on top of an unverified, reverse-engineered write path multiplies risk for zero validated value this milestone. | Ship one-shot `sync` invocable by hand or via cron/systemd timer; defer daemon/watch mode to a future milestone once the write path has live mileage. |
| Two-way / bidirectional sync (pull frame-only photos back to disk too) | "Real sync tools like `rclone bisync` do this" — feels more complete. | Explicitly out of scope per PROJECT.md ("this is the first user-facing entry point," target is directory→frame mirror). Bidirectional sync also reintroduces conflict-resolution complexity (what if the frame and the directory both changed the "same" photo?) with no product need identified. | One-directional mirror only: local directory is the source of truth, frame is the destination. `dump_frame`/`download_images_from_assets` (already existing, read-only) remain the separate pull-path if ever needed. |
| Default deletion via `AssetApi.delete_asset` (hard destroy) | Sounds more "thorough" / matches the `--delete` naming convention users know from `rsync`/`aws s3 sync`. | The method's own docstring flags it as unverified ("currently unknown if this is used") and possibly Glacier/S3-destructive and irreversible — exactly the failure mode the milestone's dry-run-by-default safety posture exists to prevent. | Use `FrameApi.remove_asset` (documented as non-destructive to S3/Glacier) as the sync-delete primitive; treat `delete_asset` as out of scope for this milestone's `sync` command. |
| Storage/quota reporting in `status`/`inspect` | Every consumer cloud-storage CLI (Dropbox, Google Drive, iCloud) reports "X GB used of Y GB." | **Confirmed absent from this API's data model** — a full read of `auraframes/models/frame.py` and `auraframes/models/user.py` turns up no storage/quota-shaped field anywhere (only `Frame.num_assets: int`, a photo *count*, not a byte quota). Building UI/plumbing for a field that doesn't exist is wasted work and would have to be faked or omitted anyway. | Report `num_assets` (asset count) as the closest available "stats-like field" per the milestone's own fallback language; explicitly state in `status`/`inspect` output or docs that no storage-quota concept exists in this API, rather than silently omitting it and leaving the question open. |
| Filename- or mtime-based change detection (skip files that "look" unchanged) | Simpler and faster than hashing every file on every run — the naive first implementation. | Well-established failure mode across the sync-tool ecosystem: mtimes change on copy/checkout/restore even when bytes are identical (causing false "changed" reclassification and wasted re-uploads), while renamed-but-byte-identical files get treated as an unrelated delete+add pair instead of a no-op. Filenames server-side are also rewritten/normalized by Aura's own upload flow, so local-filename-to-remote-filename matching is not even reliably meaningful here. | Content-hash comparison (base64 MD5, matching the API's own `Asset.md5_hash`/`get_md5()` convention) as the sole comparison key, per Table Stakes above. Optionally pre-filter by file size as a cheap first-pass bucket (mirrors the "bucket by byte size before hashing" tiered strategy used by dedup tooling) if hashing a very large directory proves slow — a performance optimization, not a correctness mechanism. |
| Renaming/relabeling matched assets on the frame when the local file was renamed but content is identical | Feels like "proper" rename-handling, mirroring how some sync tools detect a rename as a move rather than delete+add. | No Aura API endpoint exists to rename/relabel an already-uploaded asset's display filename independent of re-uploading it (only `update_taken_at_date`, `crop_asset`, `batch_update` metadata fields are exposed, none of which target `file_name` post-upload in a documented way). Attempting this would mean inventing behavior against an undocumented API with no verification path. | Treat a renamed-but-identical-content local file as an exact hash match — no action taken, full stop. This is actually the *correct* mirror semantics (content is what matters), not a compromise. |

## Feature Dependencies

```
sync (upload leg)
    └──requires──> upload_image write path (select_asset → S3 → SQS → batch_update)
                       └──STATUS: existing code, NEVER verified live (per PROJECT.md) — HIGH RISK dependency

sync (delete leg)
    └──requires──> FrameApi.remove_asset (unassociate)
                       └──STATUS: existing code, NEVER verified live — HIGH RISK dependency
    └──conflicts-with──> AssetApi.delete_asset (hard destroy) — do not use for sync's delete leg (see Anti-Features)

sync (diff/plan logic, both legs)
    └──requires──> content-hash comparison (local MD5 vs Asset.md5_hash)
                       └──requires──> get_all_assets() / FrameApi.get_assets() cursor pagination
                                          └──STATUS: verified live (READ-03) ✓ low risk
                       └──ASSUMPTION TO VERIFY: md5_hash populated on pre-existing (non-client-uploaded) assets

sync, inspect, status (frame targeting by name|id)
    └──requires──> FrameApi.get_frames()
                       └──STATUS: verified live (READ-02) ✓ low risk

inspect
    └──requires──> FrameApi.get_frame() + get_assets()  [STATUS: verified live ✓]
    └──enhances-with──> Frame.contributors, Frame.num_assets (already-hydrated fields, no new call)

status
    └──requires──> AccountApi.login()  [STATUS: verified live ✓]
    └──requires──> FrameApi.get_frames()  [STATUS: verified live ✓]
    └──does NOT require──> any unverified write-path method (status is read-only by nature)
```

### Dependency Notes

- **`sync`'s upload leg requires the unverified `upload_image` flow:** this is the single biggest schedule/complexity risk in the whole milestone. `select_asset` → S3 upload → SQS poll → `batch_update` is multi-step, stateful, and has never been exercised against the live API. Recommend the roadmap put a "verify one live upload round-trip" spike *before* building the full `sync` command around it, so API drift (auth, payload shape, SQS queue behavior) surfaces early and cheaply rather than inside a half-built CLI feature.
- **`sync`'s delete leg requires `remove_asset`, not `delete_asset`:** also never verified live. Same spike-first recommendation applies — confirm `remove_asset` actually detaches the asset from the frame's asset list (and doesn't error/no-op silently, given this codebase's known pattern of swallowing API `error` fields) before wiring it into a `--apply` code path.
- **`status` and `inspect` have zero new-risk dependencies:** both compose exclusively from already-live-verified read-path calls (`login`, `get_frames`, `get_frame`, `get_assets`) plus fields already present on hydrated models. These can be built and shipped with high confidence independent of the upload/delete spikes landing — good candidates for an earlier phase.
- **Content-hash comparison requires confirming `md5_hash` population on the read side**, not just the write side. This is a data-availability question (does the API return it for assets it didn't just receive from this client?), answerable with a single live `get_assets()` call inspected for the field — cheap to de-risk early, alongside the read-path phase's existing verified calls.
- **Frame name/id resolution has no dependency risk** (pure client-side logic over `get_frames()`), but needs an explicit decision on duplicate-name handling (see Table Stakes) — a design question, not an API risk.

## MVP Definition

### Launch With (v1)

Minimum viable set — proves the write path live and delivers the milestone's stated "done" bar (a real round-trip on the user's live frame, verified via `inspect`).

- [ ] `status` — creds/login/account check (zero new API risk; build first, use it to sanity-check the environment before spiking upload/delete)
- [ ] `inspect` — list frame assets + name/owner/contributor-count/num_assets (zero new API risk; also doubles as the verification tool for `sync`'s results, per the milestone's own "verified visually + via inspect" done bar)
- [ ] `sync <dir> --frame <name|id>` dry-run mode (content-hash diff plan: uploads/deletes/unchanged, no mutation) — the core value differentiator, buildable and testable without touching the unverified write endpoints at all
- [ ] `sync ... --apply`/`--yes` real execution — upload leg via existing `upload_image` flow, delete leg via `remove_asset` — this is where live write-path verification actually happens
- [ ] Frame targeting by name or id, with duplicate-name error handling
- [ ] Per-run summary output (N uploaded / N deleted / N unchanged / N failed) and non-zero exit on any failure

### Add After Validation (v1.x)

Trigger: the v1 write path has run cleanly against the live account/frame at least once and the team wants to make repeated/scripted use safer or more transparent.

- [ ] `--max-delete` safety guardrail — add once real usage patterns (directory sizes, typical delete volumes) are known, so the threshold is calibrated rather than guessed
- [ ] `--json` machine-readable plan/result output — add if/when `sync` starts getting invoked from scripts or CI rather than interactively
- [ ] Size-based pre-filter before hashing — add only if hashing a real user's directory proves slow enough to matter (performance optimization, not correctness)

### Future Consideration (v2+)

Defer until the one-shot CLI has real mileage and a clear signal that more automation is wanted.

- [ ] Watch-mode / daemon auto-sync — defer until the one-shot write path has proven stable over repeated live runs; building a background process on an unverified reverse-engineered API compounds risk
- [ ] Bidirectional sync (pull frame-only assets back to local dir) — explicitly out of scope for this milestone (PROJECT.md); the existing `dump_frame`/`download_images_from_assets` read path already covers "get things off the frame" separately
- [ ] Multi-frame fan-out sync (one directory to many frames at once) — no evidence of demand; adds cross-frame consistency questions not needed for the stated core value

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|----------------------|----------|
| `status` (auth/account health check) | MEDIUM | LOW | P1 |
| `inspect` (frame listing + metadata) | HIGH | LOW | P1 |
| `sync` dry-run diff (content-hash plan) | HIGH | MEDIUM | P1 |
| `sync --apply` upload leg | HIGH | HIGH (unverified dependency) | P1 |
| `sync --apply` delete leg (`remove_asset`) | HIGH | HIGH (unverified dependency) | P1 |
| Frame name/id targeting + duplicate-name handling | MEDIUM | LOW | P1 |
| Per-run summary + exit codes | MEDIUM | LOW | P1 |
| `--max-delete` guardrail | MEDIUM | LOW | P2 |
| `--json` output mode | LOW-MEDIUM | MEDIUM | P2 |
| Size-prefilter before hashing | LOW | LOW | P3 |
| Watch-mode / daemon sync | LOW (unvalidated demand) | HIGH | P3 |
| Bidirectional sync | LOW (out of scope) | HIGH | P3 |

**Priority key:**
- P1: Must have for launch (this milestone)
- P2: Should have, add when possible
- P3: Nice to have, future consideration

## Competitor Feature Analysis

Reference tools chosen because they define the standard conventions users bring to any "mirror a directory to a remote" tool.

| Feature | rclone `sync` | `aws s3 sync --delete` | `rsync --delete` | gphotos-sync (photo-specific) | Our Approach |
|---------|---------------|------------------------|-------------------|-------------------------------|--------------|
| Dry-run default | Opt-in `--dry-run` flag, but docs strongly push it as the mandatory first step before any `--delete` run | Opt-in `--dryrun` flag, same "always run first" guidance | Opt-in `-n`/`--dry-run`, same guidance | N/A (read-only backup tool, no delete/mirror leg) | Dry-run **on by default**, not opt-in — stronger safety posture given a single real (non-abstracted) live photo frame is the destination |
| Comparison key | Size + mtime by default, optional checksum (`--checksum`) for true content comparison | Size + mtime | Size + mtime by default, optional `--checksum` | Google's own hash-based duplicate detection server-side | Content hash (base64 MD5) as the **sole** key from day one — matches the API's own already-existing `md5_hash` field rather than defaulting to the weaker mtime/size heuristic these tools use out of the box |
| Delete primitive | Single `delete` operation, explicitly warns "sync can cause data loss" | Single `delete` (removes object from bucket) | Single `--delete`, with `--max-delete` as an available guardrail | N/A | Deliberately picks the **less destructive** of two available primitives (`remove_asset` over `delete_asset`) — a distinction these generic tools don't have to make since they only expose one delete operation each |
| Output format | Human-readable by default; separate machine-readable commands (`lsjson`, `lsf --format`) for scripting | Human-readable list of operations; `--quiet` to suppress | Human-readable, `--itemize-changes` for detail | N/A | Human-readable summary + per-action list for MVP; `--json` deferred to v1.x (same phased approach as rclone) |
| Safety guardrail on mass delete | None built-in beyond dry-run | None built-in beyond dry-run | `--max-delete=N` explicitly recommended | N/A | Deferred to v1.x as `--max-delete`-style guardrail — flagged as valuable but not blocking MVP |

## Sources

- [rclone sync](https://rclone.org/commands/rclone_sync/) — HIGH confidence, official docs
- [rclone delete](https://rclone.org/commands/rclone_delete/) — HIGH confidence, official docs
- [rclone ls](https://rclone.org/commands/rclone_ls/), [rclone lsl](https://rclone.org/commands/rclone_lsl/), [rclone lsjson](https://rclone.org/commands/rclone_lsjson/), [rclone lsf](https://rclone.org/commands/rclone_lsf/) — HIGH confidence, official docs
- [Mastering Rclone Dry Run](https://www.go2share.net/article/rclone-dry-run) — MEDIUM confidence, third-party explainer, corroborates official docs
- [AWS CLI `s3 sync` reference](https://docs.aws.amazon.com/cli/latest/reference/s3/sync.html) — HIGH confidence, official docs
- [`s3 sync --delete` issue #6000](https://github.com/aws/aws-cli/issues/6000) — MEDIUM confidence, official repo issue thread (real-world edge cases)
- [rsync(1) man page](https://linux.die.net/man/1/rsync) — HIGH confidence, canonical reference
- [Rsync Best Practices — Always Test New Options With Dry-Run](https://eduvola.com/blog/rsync-best-practices-always-test) — MEDIUM confidence, third-party best-practices writeup (source of `--max-delete`/`--delete-after` guidance)
- [gsutil rsync command](https://cloud.google.com/storage/docs/gsutil/commands/rsync) — HIGH confidence, official docs
- [gsutil rsync.py source](https://github.com/GoogleCloudPlatform/gsutil/blob/master/gslib/commands/rsync.py) — HIGH confidence, primary source
- [Hash-based duplicate file detection overview](https://itoolkit.co/blog/2023/08/which-is-a-more-accurate-method-of-duplicate-file-detection/) — MEDIUM confidence, third-party but consistent with primary hashing literature
- [gphotos-sync (gilesknap)](https://github.com/gilesknap/gphotos-sync) — MEDIUM confidence, official repo README, read-only tool (informs what's *not* directly transferable — no delete/mirror leg to compare)
- [cli doctor — CLI for Microsoft 365](https://pnp.github.io/cli-microsoft365/cmd/cli/cli-doctor/) — HIGH confidence, official docs, source of "doctor reports auth mode/config/roles/scopes" convention
- **This repository's own source** (highest-confidence source for all Aura-specific findings, verified by direct code read, not inference):
  - `auraframes/models/asset.py` — confirms `md5_hash` field exists on `Asset`
  - `auraframes/aws/s3client.py` — confirms base64-MD5 (`get_md5()`) is the API's native hashing convention
  - `auraframes/models/frame.py`, `auraframes/models/user.py` — confirms **no** storage/quota field exists anywhere in the data model; confirms `contributors` and `num_assets` are available for `inspect`
  - `auraframes/api/frameApi.py` — confirms `remove_asset` is documented as non-destructive to S3/Glacier; confirms `get_frames()`/`get_frame()`/`get_assets()` are the only frame-listing primitives (no server-side name lookup)
  - `auraframes/api/assetApi.py` — confirms `delete_asset`'s docstring flags it as unverified/possibly-destructive ("currently unknown if this is used ... maybe this deletes it from S3/Glacier")
  - `auraframes/aura.py` — confirms the exact `upload_image` call sequence (`select_asset` → S3 upload → SQS poll → `batch_update`) this milestone must verify live
  - `.planning/PROJECT.md` — milestone scope, constraints, and explicit "never verified live" status of upload/delete/remove/crop methods

---
*Feature research for: directory-to-cloud-device sync CLI (Aura Frames unofficial API)*
*Researched: 2026-07-05*
