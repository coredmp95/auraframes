# Pitfalls Research

**Domain:** Directory-to-frame sync CLI (upload + full-mirror delete) against an unofficial,
undocumented cloud photo API, layered onto a write path that has never been exercised live
**Researched:** 2026-07-05
**Confidence:** HIGH for codebase-derived findings (read directly from `auraframes/`
source in this repo); MEDIUM for general destructive-sync-tool conventions (rclone/AWS
CLI, cross-checked against two independent sources)

## Critical Pitfalls

### Pitfall 1: The existing upload path has a hardcoded frame ID baked into the SQS confirm step

**What goes wrong:**
`Aura.get_sqs()` calls `self.sqsClient.get_queue_url('4ab446b4-33a7-4a76-881d-d545d153ab5a')`
— a literal frame ID, not the `frame_id` argument passed into `upload_image()`. Every
upload through the existing `Aura.upload_image()` path listens for confirmation on
**one specific frame's queue**, regardless of which frame you're actually uploading to.
For any frame other than that one, the SQS step is silently talking to the wrong (or a
now-nonexistent) queue.

**Why it happens:**
This code was written and only ever tested against one frame during original
development ~3 years ago (per `CLAUDE.md`: "written ~3 years ago and have never been
exercised against the live API"). The hardcode was never surfaced because nothing
exercised it end-to-end since.

**How to avoid:**
Parameterize `get_sqs`/`get_queue_url` on the actual target `frame_id` before this code
is used for anything beyond the one frame it was written against. Treat this as a
pre-existing bug to fix in groundwork, not a design decision to preserve.

**Warning signs:**
Upload appears to succeed (S3 PUT + `batch_update` both return 200) but the SQS
`receive_message` call returns nothing for every frame except the original hardcoded
one — easy to misread as "device hasn't confirmed yet" (transient) when it's actually
"listening to the wrong queue" (permanent, per-frame).

**Phase to address:** Groundwork / write-path verification phase, before any sync logic
is built on top of `upload_image`.

---

### Pitfall 2: Content-hash diffing will collide with the API's own MD5 format and this app's own EXIF-rewrite step

**What goes wrong:**
Two separate mismatches compound here:
1. **Format mismatch.** `S3Client.get_md5()` produces
   `base64.b64encode(hashlib.md5(data).digest())` (S3 `Content-MD5`-style base64), and
   that's what's stored server-side as `asset.md5_hash`. A sync tool that computes local
   file hashes with `hashlib.md5(data).hexdigest()` (the natural default) will produce
   hex, not base64 — every local file will look "different" from its remote twin
   forever, even when byte-identical. This is a permanent false-positive, not a rare
   edge case.
2. **EXIF rewrite mismatch.** `ExifWriter`/`export.get_image_from_asset()` (used by the
   already-shipped `dump_frame`) rewrites EXIF datetime/GPS into downloaded images. If a
   user's sync source directory was ever populated by this tool's own dump/export path,
   the local bytes differ from the frame's original bytes by design — a hash diff will
   flag the *entire library* as changed on first run, even though nothing changed
   visually.

**Why it happens:** Both mismatches look plausible mid-implementation (hex is the
default `hashlib` output; EXIF rewriting was built to fix real display bugs) and both
are invisible until you actually run a diff against the live account and every single
photo shows up as "changed."

**How to avoid:**
- Standardize on base64 MD5 (matching the API's own field) for the diff key, or compute
  visual-content hashes (e.g. hash decoded pixel data / a perceptual hash) instead of
  raw file bytes if EXIF-only edits should be ignored.
- Explicitly decide and document whether metadata-only differences (EXIF rotation,
  GPS, timestamp) should trigger re-upload. Given Pitfall 3 (social-metadata loss on
  delete+recreate), the safer default is: diff on decoded pixel content, not raw bytes.
- Add a fixture-backed unit test asserting `local_hash(fresh_download) ==
  asset.md5_hash` for at least one real downloaded asset, to catch format drift before
  it causes a mass false-positive re-sync live.

**Warning signs:** A dry-run plan proposes re-uploading/deleting close to 100% of a
frame's existing library on what should be a no-op run.

**Phase to address:** Diffing/hashing implementation phase — must be validated with a
unit test *before* the first live dry-run, and re-validated in the live write-path
verification phase against real server-reported `md5_hash` values.

---

### Pitfall 3: "Full-mirror delete" is ambiguous between `remove_asset` (soft, reversible) and `delete_asset` (hard, untested) — picking the wrong one is catastrophic or a no-op

**What goes wrong:**
`FrameApi.remove_asset`'s own docstring says: "Disassociates an asset from a frame.
**This does not seem to remove the asset from S3/Glacier.**" It's a soft unlink from one
frame's slideshow — the asset persists in the account. `AssetApi.delete_asset`'s
docstring says: "**Currently unknown if this is used**... maybe this deletes it from
S3/Glacier." That's the actually-destructive, real-delete candidate — and it is the
single least-tested code path in the entire client (marked unknown by the original
author, never exercised live per project context).

A "full mirror" sync that silently picks `delete_asset` because it sounds more thorough
risks calling the most unverified, potentially irreversible endpoint in the codebase
against a real account's real photo library, with no prior evidence it behaves as
named. A sync that picks `remove_asset` thinking it deletes, when it only unlinks, will
leave storage/quota untouched and could surprise the user when "removed" photos
reappear in another view (e.g. via `PeopleApi`/albums) or in `inspect` output scoped to
a different frame.

**Why it happens:** Both methods are plausible reads of "delete" for someone who hasn't
traced the original author's own uncertainty markers (`# TODO`) in the docstrings.

**How to avoid:**
- Default the CLI's delete semantics to `remove_asset` (soft, frame-scoped,
  reversible) — matches the milestone's actual need (mirror what's *on this frame*) and
  avoids the highest-risk, least-verified code path.
- Treat `delete_asset` (hard delete) as an explicitly separate, opt-in, loudly-labeled
  capability if ever added — never the default behavior of `sync --apply`.
- Verify `remove_asset`'s actual effect live (does the photo really disappear from the
  frame, does it survive in the account/other frames) as part of write-path
  verification, and document the finding — don't rely on the 3-year-old docstring's
  guess.

**Warning signs:** Any design language in the sync spec that says "delete" without
specifying which endpoint; any code path that reaches for `delete_asset` because it
"sounds more correct" than `remove_asset`.

**Phase to address:** Write-path verification phase (confirm real behavior of both
endpoints against a disposable test frame/asset) → sync command design phase (lock the
default to `remove_asset`).

---

### Pitfall 4: Partial-failure states across select_asset → S3 → SQS → batch_update are not modeled, and there's no cleanup for any of them

**What goes wrong:**
The upload sequence is four independent network calls with no transaction boundary:
`select_asset` (stub the asset onto the frame) → S3 `put_object` (real bytes land in a
real bucket) → SQS `receive_message` (best-effort, 5s wait, single attempt, message
never deleted from the queue) → `batch_update` (attach real metadata, making the asset
"real"). A crash/network drop between any two steps leaves one of these states,
none of which the current code detects or repairs:
- Selected but never uploaded: a ghost asset stub on the frame with no backing image.
- Uploaded to S3 but `batch_update` never ran/failed: a real S3 object exists (storage
  cost) that no asset record points at — invisible orphan, no cleanup path exists
  anywhere in the codebase (`S3Client` has no `delete_object`).
- `batch_update` succeeds but the caller crashes before recording success locally: a
  naive re-run re-selects and re-uploads the same local file under a **new**
  `local_identifier`/S3 key (nothing in the existing code makes retries idempotent —
  see Pitfall 5), producing a duplicate visible asset rather than resuming cleanly.

**Why it happens:** This is inherent to a multi-step, non-transactional cloud pipeline
that was written to "just get one image up," not to survive interruption across a
batch of hundreds of files. The general AWS-recommended mitigations here are
lifecycle-rule cleanup for orphaned objects and idempotency keys on the confirming
write — neither exists in this codebase today.

**How to avoid:**
- Before starting a batch upload, persist a local manifest (path → intended
  `local_identifier` → step reached) so a crash mid-run is resumable instead of
  reprocessed from scratch.
- Make `local_identifier` a deterministic function of file content/path (not
  `uuid.uuid4()` per attempt — see Pitfall 5) so a retried upload recognizes "this file
  already has a stub/asset" instead of creating a second one.
- On startup, reconcile: if a local manifest entry says "selected" but the live asset
  list shows no matching `md5_hash`/`file_name`, either resume from `batch_update` (if
  the S3 object exists — check via `S3Client.get_file`/`head_object`) or clean up the
  orphaned selection via `remove_asset` before retrying from scratch.
- Treat the SQS confirm step as optional/best-effort telemetry, not a required gate for
  correctness — the existing 5s single-attempt wait cannot reliably distinguish "device
  hasn't polled yet" from "something's wrong," and blocking sync progress on it
  conflates cloud-side success with local-device delivery.

**Warning signs:** Re-running a sync after an interrupted run produces duplicate
assets for files that were already fully uploaded; `inspect` shows more assets than
files in the source directory after a partial run.

**Phase to address:** Upload-flow hardening (groundwork, before wiring `sync` on top)
and the sync command's resume/retry design.

---

### Pitfall 5: Using a fresh `uuid.uuid4()` as the diffing key breaks idempotency and defeats "what's already synced" detection

**What goes wrong:**
`S3Client.upload_file()` generates a brand-new random filename per call
(`f'{uuid.uuid4()}{extension}'`), and nothing in the existing `upload_image()` flow
derives `local_identifier` deterministically from the file itself — it's read off the
`Asset` object passed in. If the new sync code follows this pattern and assigns a new
random ID per upload attempt (rather than a stable ID derived from, e.g., a hash of the
file's relative path), **every re-run of `sync` that hits a retry or re-scan will look
like a brand-new file**, since there's no way to recognize "this local file already has
a corresponding remote asset." This directly defeats the point of directory-to-frame
mirroring — the second `sync` run duplicates the first instead of being a no-op.

**Why it happens:** The 3-year-old code's `local_identifier` concept comes from the
iOS/Android client's on-device asset library identity, which has no natural analogue
for "a file living in a folder on a laptop." Naively generating one at upload time
(mirroring the S3 filename pattern) is the path of least resistance but throws away
the only stable join key across sync runs.

**How to avoid:** Derive `local_identifier` deterministically from something stable
about the source file — a content hash (careful: see Pitfall 2's format/EXIF caveats)
or a hash of the relative path, generated once and re-derivable on every subsequent
scan, not re-rolled per attempt. Persist the mapping (or make it purely
re-derivable/deterministic) so `sync`'s diff step can recognize previously-uploaded
files without relying on server-side data alone.

**Warning signs:** A second, immediate `sync --apply` run on an unchanged directory
proposes uploading files again instead of reporting "up to date."

**Phase to address:** Diffing/identity design, before the first live upload test.

---

### Pitfall 6: Partial pagination during diff makes "full mirror delete" delete things that are actually still present

**What goes wrong:**
`FrameApi.get_assets` is cursor-paginated; `Aura.get_all_assets` already loops correctly
to drain all pages. But a full-mirror sync's delete-detection ("what's on the frame
that's not in my local directory") is only safe if it diffs against the **complete**
remote asset list. Any code path that reads only the first page (e.g. a fast "peek" for
`inspect`, or a page-limited call added for performance) and feeds that partial list
into the delete-planning logic will conclude that assets on page 2+ are "extra" and
mark them for deletion — even though they're present, just unseen.

**Why it happens:** Pagination-draining is easy to get right for read-only listing
(low stakes if you miss a page — you just under-report) and easy to get silently wrong
when reused for delete-planning (high stakes — you over-delete). The existing
`get_assets` also has a real, cited history of API drift on adjacent fields (the
`total_asset_count` → `frame.num_assets` move documented in `FrameApi.get_frame`),
so the reverse-engineered pagination contract itself isn't guaranteed stable either.

**How to avoid:** The full-mirror delete-planning code path must always use the fully
drained asset list (reuse `Aura.get_all_assets`, never a single-page fetch), and should
assert/log the total count fetched vs. any `num_assets`/`total_asset_count` field
returned by `get_frame` as a sanity cross-check before computing what to delete — if
they disagree, abort the delete plan rather than proceeding on a possibly-incomplete
list.

**Warning signs:** Delete-plan count doesn't match `total_asset_count`/`num_assets`
minus locally-present files; delete-plan size is unexpectedly large relative to what
changed locally.

**Phase to address:** Sync command's delete-planning logic; add a live-verification
check in the write-path verification phase.

---

### Pitfall 7: Write-path errors are checked even less consistently than the read-path's existing silent-`pass`, and destructive calls report failure counts, not failure identities

**What goes wrong:**
The codebase already has one documented instance of surfacing API drift loudly
(`FrameApi.get_assets` raises `RuntimeError` on `json_response.get('error')`, per the
Phase 2 hardening noted in `PROJECT.md`), but this pattern is **not** applied to any of
the write/delete endpoints touched by this milestone: `select_asset`, `exclude_asset`,
and `remove_asset` all return `json_response.get('number_failed')` — a bare count, with
no indication of *which* asset(s) failed — and callers today discard even that (see
`Aura.upload_image`, which ignores `select_asset`'s return value entirely).
`AssetApi.batch_update`, `delete_asset`, and `crop_asset` don't check the `error` field
at all. For a destructive full-mirror sync, "3 items failed to remove" with no way to
know *which* 3 is functionally the same as silent failure — the sync tool cannot report
an accurate result, retry selectively, or warn the user which specific photo may be in
a half-deleted state.

**Why it happens:** This is inherited technical debt (explicitly named in
`CLAUDE.md`/`PROJECT.md` as "silent `pass` on some API `error` fields... masks drift"),
originally written for a read-heavy demo client where a missed error just meant stale
data. Extending that tolerance to delete operations is the actual novel risk this
milestone introduces.

**How to avoid:**
- Extend the fail-loud pattern already established for `get_assets` to every write/
  delete call this milestone touches: check `error` fields and raise/report on non-zero
  `number_failed`, not just on HTTP-level failure.
- Since these endpoints report only a count, not which item(s) failed, the sync tool
  should call `select_asset`/`remove_asset` **one asset at a time** (matching the
  existing code's documented usage: "Typical use of this endpoint results in a single
  AssetPartialId being sent per call") rather than batching many assets into one array
  — a per-item call lets a `number_failed == 1` be attributed to a specific file, which
  a batched call cannot.
- After every destructive batch, re-fetch the frame's asset list and diff against the
  intended post-sync state to positively confirm the outcome, rather than trusting the
  API's own success signal alone — given this API is undocumented and known to drift.

**Warning signs:** Sync reports "N removed" but a subsequent `inspect` shows a
different count than expected; `number_failed > 0` values appearing in logs without a
corresponding user-visible warning.

**Phase to address:** Write-path verification phase (extend fail-loud checks) and the
sync command's execution/reporting logic (per-item calls, post-sync reconciliation).

---

### Pitfall 8: Deleting-then-recreating an asset (rather than truly idempotent update) discards server-side social metadata the user may not expect to lose

**What goes wrong:**
Comments, reactions, and activity history are tied to an asset's `id` (see
`ActivityApi`/`Activity`/`Reaction`/`Comment` models). Any sync flow that reacts to a
detected "change" (see Pitfall 2's false-positive risk) by removing the old asset and
uploading it as new gives the new asset a new `id` — silently orphaning/discarding any
comments or reactions a frame's family/collaborators left on the original. This is
invisible in a file-content diff (bytes match or don't) but very visible and upsetting
to the actual humans using the frame.

**Why it happens:** A sync tool naturally models "changed" as "delete old, add new"
because there's no update-in-place primitive for swapping image bytes under an
existing asset id. Combined with Pitfall 2's false-positive hash mismatches, this
turns an accidental no-op detection failure into real, human-visible data loss on a
shared family device — arguably the single worst possible outcome for this app's
actual use case.

**How to avoid:**
- Never let "changed" auto-trigger delete+recreate without a distinct, louder
  confirmation step than a plain new upload — this is a strictly higher-risk operation
  than either an add or a soft remove alone.
- Before removing an asset flagged as "changed," check whether it has any associated
  activity (comments/reactions) via `ActivityApi` and surface that in the dry-run plan
  ("this photo has 3 comments that will be lost") so the user can make an informed
  call, rather than a bulk `--yes` blowing through it.
- Given Pitfall 3's guidance to default to soft `remove_asset` rather than hard
  `delete_asset`, this is somewhat mitigated for accidental false-positives (the
  underlying asset itself isn't destroyed, just unlinked from the frame) — but the
  *new* upload still gets a new id, so any comments tied to the *frame-specific*
  activity feed for the old association are still effectively orphaned from the
  frame's perspective.

**Warning signs:** Dry-run plan shows a file as both "delete" and "add" in the same
run for what the user believes is an unchanged photo.

**Phase to address:** Sync command's change-detection and delete-planning logic; surface
in dry-run output design.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Reuse `hashlib.md5().hexdigest()` for diffing instead of matching the API's base64 MD5 format | Faster to write, "just works" in isolation | Every file looks changed forever (Pitfall 2) — invisible until first live dry-run against real data | Never — validate format against one real `asset.md5_hash` before writing the diff logic |
| Random UUID per-upload `local_identifier` (mirrors existing `S3Client.upload_file` pattern) | Matches existing code style, zero new logic | Breaks re-run idempotency — every sync duplicates the last (Pitfall 5) | Never for the sync tool's own identity key; the existing pattern is fine only for the throwaway S3 object filename |
| Batch multiple assets into one `select_asset`/`remove_asset` call | Fewer HTTP round-trips, faster on large directories | `number_failed` count can't be attributed to a specific file — destructive-call failures become unattributable (Pitfall 7) | Acceptable only for the additive (non-destructive) `select_asset` add path once write-path error handling matures; never for delete calls in v2.0 |
| Skip a local resume/state manifest for uploads, rely on "just re-run it" | Less code, ships faster | Partial-failure states (orphaned S3 objects, ghost stubs) accumulate silently with no cleanup path (Pitfall 4) | Acceptable for an initial single-file live verification test; not acceptable once `sync` processes a whole directory unattended |
| Default full-mirror "delete" to `delete_asset` (hard) instead of `remove_asset` (soft) because it "sounds more like delete" | Feels more thorough/correct naming | Exercises the single least-tested, most uncertain write endpoint in the codebase against a real photo library (Pitfall 3) | Never as a default; only ever as an explicit, separately-labeled opt-in after `remove_asset`'s real behavior is live-verified |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| `api.pushd.com/v5` write endpoints (`select_asset`, `remove_asset`, `batch_update`, `delete_asset`) | Trusting HTTP 200 + no exception as proof of success, the way the existing read path did before its own `get_assets` hardening | Check the `error`/`number_failed` fields explicitly on every write call this milestone touches (Pitfall 7); this API is undocumented and known to drift, and writes fail in ways reads don't (partial success, item-level failure) |
| AWS Cognito anonymous auth (`AWSClient.auth`) | Reusing one long-lived `S3Client`/`SQSClient` instance across a large batch sync without handling credential expiry | Either mirror the existing per-call client construction (safe but chattier — each construction re-authenticates) or explicitly track credential TTL and re-auth mid-batch; don't assume one set of Cognito temp credentials outlives a large directory sync |
| SQS confirm queue (`SQSClient.receive_message`) | Treating a missing confirm message as upload failure, and never calling `delete_message` (queue is only ever peeked, never acknowledged) | Treat SQS confirm as best-effort telemetry, not a correctness gate (Pitfall 4); if kept at all, acknowledge consumed messages so repeated polls don't reprocess/lose visibility on the same message |
| Frame targeting by `--frame <name>` | Assuming frame names are unique across an account (nothing in the `Frame` model or `get_frames()` enforces this) | Require an exact, single match by name or fail loudly listing all ambiguous matches with their IDs; never proceed a destructive sync against a name match that could resolve to more than one frame |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Recomputing full-directory content hashes on every `sync` invocation | Sync gets slower as the photo library grows; large photo directories (RAW/HEIC originals) make hashing the dominant cost | Cache `(path, mtime, size) → hash` locally between runs; only rehash files whose mtime/size changed | Noticeable above a few hundred large photos; becomes a real UX problem in the thousands |
| One fresh `S3Client()`/`SQSClient()` (re-authenticating via Cognito) per file, at directory-sync scale | Cognito `get_id`/`get_credentials_for_identity` call volume scales linearly with file count | Batch/reuse credentials across a sync run with explicit TTL tracking, rather than the existing per-call-`upload_image` pattern verbatim | Matters once syncing tens-to-hundreds of files per run, both for wall-clock time and risk of hitting undocumented Cognito rate limits |
| Sequential per-file select→S3→SQS→batch_update for every file in a directory, no concurrency | Full mirror of a real photo library (hundreds of files) takes very long, increasing the exposure window for partial-failure states (Pitfall 4) | Fine as an MVP given the "write path never proven live" context — favor correctness/observability over throughput this milestone; note as a follow-up rather than optimizing prematurely | Becomes a real problem only once directory sizes grow well beyond an initial small test folder |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Logging full asset/file payloads at `INFO`/`DEBUG` during sync the same way the existing `Client` does (already redacts `password`/`auth_token`/`x-token-auth`) | New write payloads (batch_update bodies, S3 keys) could include local file paths or EXIF GPS data written to `logs/file_{time}.log` | Confirm the existing `_redact` allowlist still covers any new sensitive fields introduced by write payloads; GPS/location data in asset metadata is arguably sensitive even if not a literal "secret" |
| Hardcoded Cognito identity pool IDs and S3 bucket name in source (`s3client.py`, `sqsclient.py`) | Already-known tech debt; not new to this milestone, but a full-mirror delete CLI increases the blast radius of anyone reusing this code against pool IDs they don't understand | Out of scope to fix this milestone per `PROJECT.md`, but don't make it worse — don't add more hardcoded identifiers for new endpoints touched |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|------------------|
| `--yes`/`--apply` executes the full delete plan with no visibility into *why* each item was flagged | User can't sanity-check a "delete 40 photos" plan before it runs, especially given Pitfall 2's false-positive risk | Dry-run output (the default, per `PROJECT.md`) must list each planned delete with its detected reason (missing locally vs. detected-changed-so-replace) and, per Pitfall 8, flag any item that has associated comments/reactions |
| No circuit breaker on delete volume | A bug (e.g. Pitfall 2's hash-format mismatch or Pitfall 6's partial pagination) can silently escalate to "delete everything," and nothing stops it from executing | Borrow rclone's `--max-delete`-style convention: refuse to execute a delete plan above some absolute count or percentage of the frame's current library without an extra explicit override flag, even with `--apply`/`--yes` present |
| Ambiguous `--frame <name>` silently picks "a" frame if multiple match | A destructive sync could run against the wrong frame's real family photos | Require unique match; on ambiguity, list candidate frames with IDs and abort rather than guessing (see Integration Gotchas) |
| Treating dry-run and live mode as the same code path with an `if apply:` guard sprinkled at each call site | Easy to miss a guard and have dry-run silently perform a real destructive call | Structure the sync as: compute-plan (pure, no side effects) → print-plan → (only if `--apply`) execute-plan, so dry-run is structurally incapable of calling any write endpoint, not just conventionally prevented from it |

## "Looks Done But Isn't" Checklist

- [ ] **Upload verification:** Often missing confirmation that `batch_update`'s new asset is actually visible via a subsequent `get_assets`/`inspect` call, not just that the HTTP calls didn't throw — verify by re-fetching the frame after upload.
- [ ] **Delete verification:** Often missing confirmation that `remove_asset`'s claimed removal actually holds — verify by re-fetching the frame after delete and confirming the asset is gone, and check `number_failed` is `0` and not silently discarded.
- [ ] **Dry-run parity:** Often the dry-run path silently drifts from the real-execution path (different code, different assumptions) — verify by asserting the exact same plan-computation function feeds both `--dry-run` printing and `--apply` execution.
- [ ] **Frame targeting:** Often missing a uniqueness check on `--frame <name>` resolution — verify by testing against an account with two similarly-named frames (or simulate via a fixture) before trusting name-based targeting on `--apply`.
- [ ] **Idempotent re-run:** Often missing a second-run check — verify by running `sync --apply` twice in a row on an unchanged directory and confirming the second run reports zero changes, not a duplicate upload.
- [ ] **Partial-failure recovery:** Often missing a crash-mid-batch test — verify by killing the process mid-directory-sync and confirming a re-run resumes/reconciles rather than duplicating or leaving orphaned S3 objects.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|-----------------|
| Hardcoded SQS frame ID (Pitfall 1) | LOW | Parameterize `get_queue_url` call on the real `frame_id`; no data recovery needed, it's a code fix |
| Hash-format false positives (Pitfall 2) already triggered a bad delete plan pre-`--apply` | LOW | Caught by dry-run before execution if the safety default holds — fix the hash format and re-run dry-run to confirm plan collapses to empty/expected |
| Orphaned S3 objects from a crashed partial upload (Pitfall 4) | MEDIUM | No delete API exists in `S3Client` today — would need to add one, or accept the storage cost (bucket isn't owned by this project, it's Aura's) and instead focus on preventing new stub assets from persisting via `remove_asset` cleanup on the ghost selection |
| Duplicate assets from non-idempotent re-run (Pitfall 5) already uploaded live | MEDIUM | Identify duplicates by matching `original_file_name`/hash across assets sharing a `local_identifier` prefix pattern, then `remove_asset` the extras — manual reconciliation, no automated dedupe exists |
| Over-broad delete already executed against real photos (Pitfall 3/6/8, worst case) | HIGH | If `remove_asset` was used (soft default), the underlying photo likely still exists in the account/other frames/backups — recoverable by re-associating; if `delete_asset` (hard) was ever used, recovery depends entirely on whatever Aura's own backend retention/backup policy is, which this project has no visibility into — this is exactly why Pitfall 3's default matters |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|-------------------|---------------|
| 1. Hardcoded SQS frame ID | Write-path verification (groundwork) | Upload to a frame other than the hardcoded one and confirm SQS confirm targets the right queue |
| 2. Hash format / EXIF false positives | Diffing/hashing implementation | Unit test: local hash of a freshly downloaded real asset equals its `asset.md5_hash` |
| 3. remove_asset vs delete_asset ambiguity | Write-path verification + sync command design | Live-test both endpoints against a disposable test asset/frame; document actual observed behavior; lock CLI default to `remove_asset` |
| 4. Partial-failure states across the 4-step upload pipeline | Upload-flow hardening (groundwork) | Kill-mid-run test: interrupt after S3 PUT but before `batch_update`, confirm re-run reconciles without duplicating |
| 5. Non-deterministic `local_identifier` breaking idempotency | Diffing/identity design | Run `sync --apply` twice on an unchanged directory; second run must report zero changes |
| 6. Partial-pagination delete over-reach | Sync delete-planning logic | Cross-check delete-plan asset count against `get_frame`'s `num_assets`/`total_asset_count` before executing |
| 7. Silent write-error handling / unattributable failure counts | Write-path verification + sync execution/reporting | Force a single-asset failure (e.g. malformed payload) and confirm the CLI surfaces which file failed, not just a count |
| 8. Delete+recreate discarding social metadata | Sync change-detection/delete-planning + dry-run output design | Dry-run plan against a frame with at least one commented/reacted-to asset; confirm the plan surfaces the at-risk activity before any `--apply` |

## Sources

- Direct source reading of this repository (HIGH confidence, primary source):
  `auraframes/aura.py`, `auraframes/api/assetApi.py`, `auraframes/api/frameApi.py`,
  `auraframes/aws/s3client.py`, `auraframes/aws/sqsclient.py`,
  `auraframes/aws/awsclient.py`, `auraframes/client.py`, `auraframes/models/asset.py`
- [rclone sync command reference](https://rclone.org/commands/rclone_sync/) (MEDIUM — cross-checked)
- [rclone: Highly destructive actions require confirmation (issue #1574)](https://github.com/rclone/rclone/issues/1574)
- [rclone: don't delete files without --delete flag, like rsync (issue #8922)](https://github.com/rclone/rclone/issues/8922)
- [AWS CLI `s3 sync` reference](https://docs.aws.amazon.com/cli/latest/reference/s3/sync.html) (MEDIUM — cross-checked)
- [AWS: s3 sync --delete issue discussion (aws-cli #6000)](https://github.com/aws/aws-cli/issues/6000)
- [AWS: Checking object integrity for data uploads in Amazon S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/checking-object-integrity-upload.html) (MEDIUM)
- [AWS: How to prevent object overwrites with conditional writes](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html) (MEDIUM)
- `.planning/PROJECT.md` — milestone context, known tech debt, prior phase history

---
*Pitfalls research for: directory-to-frame sync CLI (upload + destructive full-mirror delete) on the Aura Frames Python client*
*Researched: 2026-07-05*
