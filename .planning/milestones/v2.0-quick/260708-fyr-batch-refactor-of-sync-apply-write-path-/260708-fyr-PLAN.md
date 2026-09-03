---
phase: quick-260708-fyr
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - auraframes/api/frameApi.py
  - auraframes/api/assetApi.py
  - auraframes/sync.py
  - tests/test_write_endpoints_failloud.py
  - tests/test_execute_plan.py
  - tests/test_write_throttling.py
autonomous: true
requirements: [SYNC-03, SYNC-04, WRITE-05]
gap_closure: false

must_haves:
  truths:
    - "A single sync --apply upload chunk of up to WRITE_BATCH_SIZE new files issues exactly ONE select_asset call and ONE batch_update call to Pushd (not 2x select_asset + 1x batch_update per file), collapsing ~3N write calls to ~2 per chunk."
    - "Each upload file's per-file outcome is attributed via batch_update's successes: any file whose unique local_identifier is absent from the successes list is recorded by Path in ExecutionResult.upload_failures; present ones increment upload_succeeded."
    - "A partial batch_update response (some local_identifiers present, some absent) yields a correct mixed upload_succeeded / upload_failures split with the right Paths named."
    - "More than WRITE_BATCH_SIZE files split into multiple chunks, each chunk's two Pushd write calls paced by the injected throttle, with per-chunk call counts assertable offline."
    - "D-09 ordering (all uploads attempted before any delete), the RateLimitError whole-batch fast-path, and the ConsecutiveWriteFailureError backstop all still fire; a chunk that fully fails aborts the run early rather than grinding through every remaining chunk."
    - "pytest -m 'not live' is green with zero network / AWS access."
  artifacts:
    - auraframes/api/frameApi.py
    - auraframes/api/assetApi.py
    - auraframes/sync.py
    - tests/test_write_endpoints_failloud.py
    - tests/test_execute_plan.py
    - tests/test_write_throttling.py
  key_links:
    - "The client-generated unique local_identifier (uuid per file) is the join key between execute_plan's {local_identifier -> Path} map and batch_update's successes[].local_identifier -- this is the sole per-file attribution mechanism in batch mode."
    - "The WRITE_BATCH_SIZE chunk boundary is where the Pushd write-call count collapses from ~3N to ~2 per chunk; S3 uploads remain per-file (AWS, not a Pushd anti-abuse surface)."
    - "The consecutive-write-failure counter spans chunks and bumps once per attributed-failed file (reset on any per-file success), so a single fully-failed chunk pushes the run past MAX_CONSECUTIVE_WRITE_FAILURES and aborts fast."
---

<objective>
Refactor the `sync --apply` write path so a bulk apply of N files issues batched
Pushd write calls (~2 per ~50-file chunk) instead of ~3N single-element calls,
while preserving per-file failure attribution and every existing safety
invariant (throttle, RateLimitError abort, consecutive-failure backstop, D-09
ordering).

Root cause (already fully diagnosed by decompiling the official Aura Android
app, see `.planning/debug/resolved/select-asset-401-unauthorized.md`): Pushd's
`select_asset` (POST `/frames/{id}/select_asset`) and `batch_update` (PUT
`/assets/batch_update.json`) are NATIVE BATCH endpoints that accept
`{"assets":[...N...]}`; the official app sends the whole collection in ONE call.
Our wrappers hardcode a single-element array, so a sync of N files fires ~3N
Pushd write calls, which is the real trigger of the anti-abuse 401/475 lockout.
The already-shipped 0.5s throttle + consecutive-failure backstop are palliative
and MUST be kept.

Purpose: eliminate the ~100x Pushd write-call inflation at its source (call
count), not just pace it.
Output: batched API wrappers, a chunked `execute_plan`, and rewritten offline
tests proving the new batched semantics.

DEFERRED / OUT OF SCOPE (do NOT attempt here, do NOT put in must_haves): any
live write against the real account. The account may still be sensitized from
prior testing. Live end-to-end re-verification of the batched flow is a
separate, human-approved step on a recovered/cooled-down account. This plan is
verified OFFLINE ONLY via mocks/fakes.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
</execution_context>

<context>
@.planning/STATE.md
@CLAUDE.md

@auraframes/api/frameApi.py
@auraframes/api/assetApi.py
@auraframes/sync.py
@auraframes/models/asset.py
@tests/offline.py
@tests/test_execute_plan.py
@tests/test_write_throttling.py
@tests/test_write_endpoints_failloud.py
@.planning/debug/resolved/select-asset-401-unauthorized.md

Reference interfaces (do not change):
- `AssetPartialId.to_request_format()` -> `{'asset_id': id}` or `{'asset_local_identifier': local_identifier}` (asset.py).
- `AssetPartial = make_partial(Asset, "AssetPartial")`; batch_update sends `.dict(include={...})` of each asset (works on Asset and AssetPartial alike).
- `s3_client.upload_file(data: bytes, extension: str) -> (filename, md5)` (per-file, AWS, NOT throttled -- not a Pushd anti-abuse surface).
- `sqs_client.get_queue_url(frame_id)` / `receive_message(queue_url, wait_time_seconds=...)` -- best-effort/observational only, never gates success.
- The offline harness `offline_aura(overrides=...)` routes `httpx.MockTransport` purely by request path (see tests/offline.py); per-payload discrimination is done by monkeypatching `aura.asset_api.batch_update` / `aura.frame_api.remove_asset` directly (established pattern in test_execute_plan.py).
- Legacy single-item callers to preserve by backward-compat: `Aura.upload_image()` in aura.py calls `select_asset(frame_id, AssetPartialId(...))` and `batch_update(asset)` with a SINGLE item and discards batch_update's return value.
</context>

<tasks>

<task type="auto">
  <name>Task 1: Make the Pushd write wrappers accept batches (frameApi + assetApi)</name>
  <files>auraframes/api/frameApi.py, auraframes/api/assetApi.py</files>
  <action>
Widen the three native-batch Pushd wrappers to accept either a single item or a
list, sending the whole collection in one `{"assets":[...]}` array (this is what
the official app does -- the root-cause fix for the ~3N call inflation).

`FrameApi.select_asset(frame_id, asset_partial_ids)`: change the parameter to
accept `AssetPartialId | list[AssetPartialId]`. Normalize a single instance to a
one-element list at the top (so legacy single-item callers in aura.py keep
working unchanged -- backward compat, no call-site churn). Build the payload as
`{'assets': [a.to_request_format() for a in items]}`. KEEP both fail-loud
guards verbatim in behavior: raise RuntimeError on the `error` envelope, and
raise RuntimeError on a nonzero `number_failed`. Return `number_failed`. Update
the docstring: this endpoint is a native batch accepting the whole collection in
one call; `number_failed` is a count only (not per-item), so a batched caller
cannot learn WHICH item failed from select_asset alone.

`FrameApi.remove_asset(frame_id, asset_partial_ids)`: apply the identical
single-or-list normalization and one-array payload. Keep both fail-loud guards
and the `number_failed` return. Update the docstring the same way. (This lets
the delete loop batch too; per-item delete attribution degrades to per-chunk --
a nonzero number_failed or raised error fails the whole chunk's deletes, since
remove_asset returns only a count. That tradeoff is deliberate and documented in
Task 2.)

Leave `exclude_asset` unchanged -- it is not on the sync write path; keep scope
tight.

`AssetApi.batch_update(assets)`: change the parameter to accept
`Asset | AssetPartial | list[Asset | AssetPartial]`. Normalize a single instance
to a one-element list. Build `{"assets": [a.dict(include={... the existing field
set ...}) for a in items]}` -- reuse the exact same include field set already in
the method. KEEP the `error`-envelope RuntimeError raise (a whole-call failure).
REMOVE the `len(successes) < len(ids)` partial-failure raise: in batch mode a
partial success is the NORMAL, expected signal that the caller must attribute
per-file, not an error to abort on. Return `(ids, [AssetPartialId(**s) for s in
successes])` exactly as today. Update the docstring: `successes` (each carrying
`id` + `local_identifier`) is the per-file source of truth; a caller matches
each sent `local_identifier` against `successes[].local_identifier` to attribute
success/failure per file. Note in the docstring that the legacy single-item
caller (`Aura.upload_image`) discards the return value, so dropping the partial
raise does not change its behavior.

Do NOT change `AssetPartialId`, `AssetPartial`, `to_request_format`, or the
include field set.
  </action>
  <verify>
    <automated>python -m pytest tests/test_write_endpoints_failloud.py -m "not live" -q</automated>
  </verify>
  <done>
select_asset/remove_asset/batch_update each accept a single item OR a list and
send one combined `{"assets":[...]}` array. select_asset/remove_asset keep both
fail-loud guards; batch_update keeps only the error-envelope raise and returns
(ids, successes) on any partial. Existing single-item fail-loud tests still pass;
legacy aura.py single-item callers are untouched.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Chunk execute_plan into batched writes with per-file attribution (sync.py)</name>
  <files>auraframes/sync.py</files>
  <behavior>
    - A chunk of K<=WRITE_BATCH_SIZE upload files performs K per-file S3 uploads, then exactly ONE select_asset(all K local_identifiers) and ONE batch_update(all K AssetPartials); throttle is called once before select_asset and once before batch_update (2 throttles per upload chunk, S3 uploads are NOT throttled).
    - Per-file attribution: build a unique local_identifier (uuid) per file and a {local_identifier -> Path} map; after batch_update returns (ids, successes), any file whose local_identifier is absent from successes is appended to upload_failures by (Path, reason); present ones increment upload_succeeded and reset the consecutive-failure counter.
    - A per-file prep/S3 failure (unsupported extension, Image.open error, upload_file raising) is caught for THAT file only, recorded in upload_failures, and does not stop the rest of the chunk.
    - A whole-chunk Pushd failure (select_asset or batch_update raising a non-RateLimitError) attributes ALL prepped files in that chunk as failed with the exception message.
    - RateLimitError from any batched write propagates uncaught (whole-batch abort), never recorded as a per-item failure.
    - The consecutive-failure counter spans chunks and both loops, bumps once per attributed-failed file, resets on any per-file success; a single fully-failed chunk of >=MAX_CONSECUTIVE_WRITE_FAILURES files raises ConsecutiveWriteFailureError after exactly MAX attributed failures (remaining files never attempted).
    - Deletes are chunked: ONE remove_asset(all AssetPartialId(id=...) in the chunk) per delete chunk, throttled once; on success all deletes in the chunk succeed, on a raised error all deletes in the chunk are recorded failed with the message (coarse per-chunk attribution, since remove_asset returns only a count).
    - progress(kind, identifier, ok) fires exactly once per RESOLVED file/asset (upload Path or delete id), never on the RateLimitError abort path; total progress calls == len(to_upload)+len(to_delete) unless a consecutive-failure abort stops it early.
    - All uploads are attempted before any delete (D-09).
  </behavior>
  <action>
Add a module-level `WRITE_BATCH_SIZE = 50` constant near WRITE_THROTTLE_SECONDS,
with a comment explaining: the official app has no hard client cap but never
bursts 100+ in practice; a huge batch could re-trip anti-abuse or hit an
undocumented server limit, so chunk at ~50. Add a `batch_size: int =
WRITE_BATCH_SIZE` keyword parameter to `execute_plan` (injectable like
throttle_seconds/sleep, for offline chunk-boundary tests).

Replace the per-file `_execute_upload` round-trip with a chunked flow. For each
chunk of `sorted(plan.to_upload)` sliced at `batch_size`:
  1. Per-file S3 prep phase (per-file failures isolated): for each path, resolve
     `data_uti` via `_DATA_UTI_BY_SUFFIX` (raise/record ValueError if unmapped,
     fail-closed as today), read image dimensions via `Image.open` (use a `with`
     block so the file handle closes), generate `local_identifier =
     str(uuid.uuid4())`, call `s3_client.upload_file(path.read_bytes(),
     path.suffix)` -> (filename, md5), build the `AssetPartial(...)` with the
     same fields the old `_execute_upload` used (local_identifier, file_name,
     md5_hash, height, width, taken_at, data_uti, selected, upload_priority).
     Collect prepped tuples (path, local_identifier, partial) and a
     {local_identifier -> path} map. Any exception here is caught for that file:
     append (path, str(e)) to upload_failures, progress('upload', path, False),
     note_failure(str(e)).
  2. If no files prepped successfully in the chunk, continue to the next chunk.
  3. Batched Pushd writes (each preceded by throttle()): call
     `aura.frame_api.select_asset(frame_id, [AssetPartialId(local_identifier=lid)
     for (_, lid, _) in prepped])`; optionally do at most ONE best-effort
     `sqs_client.receive_message` poll for the chunk (never used to gate
     success -- log at debug only); then `_, successes =
     aura.asset_api.batch_update(frame_id-not-needed; [partial for (_, _,
     partial) in prepped])`. Build `succeeded = {s.local_identifier for s in
     successes}`. For each (path, lid, _) in prepped: if lid in succeeded ->
     upload_succeeded += 1, reset consecutive counter, progress True; else ->
     append (path, 'file not acknowledged in batch_update successes') to
     upload_failures, progress False, note_failure(that reason).
  4. Wrap the batched writes in the existing except structure: re-raise
     RateLimitError uncaught; on any other Exception attribute ALL prepped files
     in the chunk as failed (append + progress False + note_failure per file,
     using str(e)).

DROP the double select_asset and the per-file SQS polls entirely (the app does
not double; RESEARCH.md Pitfall 4 cargo-cult): ONE select_asset per chunk, at
most one best-effort SQS poll per chunk that never gates success/failure.

For deletes: chunk `plan.to_delete` at `batch_size`. For each chunk: throttle(),
call `aura.frame_api.remove_asset(frame_id, [AssetPartialId(id=asset.id) for
asset in chunk])`. On success: for each asset -> delete_succeeded += 1, reset
counter, progress('delete', asset.id, True). Re-raise RateLimitError uncaught.
On any other Exception: for each asset in the chunk -> append (asset.id, str(e))
to delete_failures, progress('delete', asset.id, False), note_failure(str(e)) --
coarse per-chunk attribution (documented, since remove_asset returns only a
count). Keep all uploads before all deletes (D-09). Keep `remove_asset` as the
ONLY delete primitive referenced in this module (D-06 structural isolation --
still never reference the hard-delete `delete_asset`, including in comments).

KEEP: the `throttle()` closure and `note_failure()` closure (the consecutive-run
backstop) exactly as-is in mechanism; the counter still bumps per attributed
file failure and resets on any success, so a fully-failed chunk of >=MAX files
aborts after exactly MAX attributed failures (append-then-note per file means
result.upload_failures holds exactly MAX at the abort, matching the existing
abort semantics). KEEP RateLimitError re-raise, ConsecutiveWriteFailureError,
throttle_seconds/sleep/max_consecutive_failures/progress parameters and their
defaults.

Rewrite the module docstring and the WRITE_THROTTLE_SECONDS comment to describe
the batched flow: per-file S3 prep, then ONE batched select_asset + ONE batch_update
per chunk (no double select_asset, no per-file SQS gating). Note that in batch
mode S3 uploads happen per-file BEFORE the batched select_asset, so a chunk-level
select_asset/batch_update failure can leave orphan (unassociated) S3 objects --
acceptable because S3 is AWS, not the Pushd anti-abuse surface, and orphaned
objects are inert.
  </action>
  <verify>
    <automated>python -m pytest tests/test_execute_plan.py tests/test_write_throttling.py -m "not live" -q</automated>
  </verify>
  <done>
execute_plan chunks uploads and deletes at WRITE_BATCH_SIZE (injectable), issues
one select_asset + one batch_update per upload chunk and one remove_asset per
delete chunk, attributes uploads per-file via batch_update successes, preserves
D-09 ordering, RateLimitError abort, the consecutive-failure backstop, throttle
pacing, and per-resolved-file progress. Task 3's rewritten tests pass.
  </done>
</task>

<task type="auto">
  <name>Task 3: Rewrite offline tests for the batched semantics</name>
  <files>tests/test_execute_plan.py, tests/test_write_throttling.py, tests/test_write_endpoints_failloud.py</files>
  <action>
The existing tests encode the OLD per-file semantics and MUST be updated to the
batched model (this is expected churn, not a regression). Keep every test
offline (no @pytest.mark.live), reusing the `offline_aura(overrides=...)`
MockTransport harness + duck-typed S3/SQS fakes already in these files, and the
established pattern of monkeypatching `aura.asset_api.batch_update` /
`aura.frame_api.remove_asset` for per-payload discrimination (MockTransport
routes only by path).

tests/test_write_endpoints_failloud.py: keep all single-item tests green
(backward compat). ADD list-mode cases: select_asset with a list of AssetPartialId
sends one call and returns number_failed; remove_asset with a list does the same;
batch_update with a LIST of AssetPartial returns (ids, successes) and does NOT
raise on a partial `successes` (fewer successes than sent) -- proving attribution
is now the caller's job.

tests/test_write_throttling.py: update throttle-count expectations to the batched
model -- ONE upload file = ONE chunk = 2 throttles (select_asset + batch_update),
NOT 3 (the double select_asset is gone). A delete chunk = 1 throttle. Keep
throttle_seconds=0 disables, and the supplied-interval test. Update the
consecutive-failure-run tests: a chunk whose select_asset returns plain 401 for
all files must abort after exactly MAX_CONSECUTIVE_WRITE_FAILURES attributed
failures (note: with batching, S3 uploads for the whole chunk happen BEFORE the
select_asset, so assertions like `s3.upload_calls == []` on a select_asset 401
no longer hold -- assert instead that no file was acknowledged / the run aborted
with MAX failures recorded). Keep: interspersed failures never trip; a success
resets the run; max_consecutive_failures=0 disables; the run spans the
upload->delete boundary. Keep RateLimitError (429/475) aborting the whole batch.

tests/test_execute_plan.py: rewrite the happy path to assert exactly ONE
select_asset + ONE batch_update call for a multi-file single chunk (e.g. capture
call counts by monkeypatching the wrappers or counting MockTransport hits). ADD:
  - a PARTIAL batch_update test -- monkeypatch batch_update to return successes
    for only some of the sent local_identifiers and assert upload_succeeded /
    upload_failures split names the correct Paths;
  - a CHUNKING test -- more than batch_size files (inject a small batch_size,
    e.g. batch_size=2, with >2 files) produces multiple select_asset/batch_update
    calls (assert the call count == number of chunks) and paces a throttle
    between chunks;
  - keep the D-09 all-uploads-before-all-deletes ordering assertion, adapted to
    the chunked/batched call shape.

Run the full offline suite at the end to confirm nothing else regressed
(test_cli_apply.py's fake_execute_plan is a monkeypatch and should be unaffected,
since cli.run_sync still calls execute_plan with the same signature + progress).
  </action>
  <verify>
    <automated>python -m pytest -m "not live" -q</automated>
  </verify>
  <done>
All offline tests pass (`pytest -m "not live"` green). Tests prove: batched call
counts (1 select_asset + 1 batch_update per upload chunk), per-file attribution
from PARTIAL batch_update successes, chunk splitting past batch_size with
inter-chunk pacing, and the preserved RateLimitError / consecutive-failure abort
behavior. No live tests were added or run.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| client -> Pushd write API | select_asset/batch_update/remove_asset now carry a whole chunk's identifiers in one call; a malformed batch could over-associate/over-remove. |
| client -> S3 (AWS) | per-file uploads precede the batched select_asset; a chunk-level Pushd failure can orphan S3 objects. |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-fyr-01 | Tampering | remove_asset batched deletes | medium | mitigate | Deletes chunk only assets already classified as surplus by compute_plan (D-06 multiset); remove_asset is frame-scoped (disassociate only, never hard-delete) and stays the sole delete primitive; a nonzero number_failed fails the whole chunk fail-loud rather than silently. |
| T-fyr-02 | Info disclosure | orphan S3 objects on chunk failure | low | accept | S3 uploads are AWS (not the Pushd anti-abuse surface); orphaned unassociated objects are inert and do not leak account data beyond the already-authorized bucket. No live writes performed here. |
| T-fyr-03 | Denial of Service | anti-abuse re-trip on large batch | medium | mitigate | Chunk at WRITE_BATCH_SIZE=50; KEEP the 0.5s throttle before each Pushd write and the RateLimitError + ConsecutiveWriteFailureError aborts so a re-trip stops the run fast instead of hammering. |
| T-fyr-SC | Tampering | dependency installs | low | accept | No new packages added; refactor of existing calls only. No install step, so no legitimacy checkpoint required. |
</threat_model>

<verification>
- `python -m pytest -m "not live" -q` is fully green (offline, no network, no AWS credentials).
- Batched call-count assertions prove ONE select_asset + ONE batch_update per upload chunk and ONE remove_asset per delete chunk.
- Per-file attribution proven against a PARTIAL batch_update successes response.
- Chunk-boundary behavior proven with an injected small batch_size.
- RateLimitError whole-batch abort and ConsecutiveWriteFailureError backstop still fire.
- Legacy single-item callers (aura.py) remain valid via single-or-list backward compat.
</verification>

<success_criteria>
- A sync --apply upload chunk of up to WRITE_BATCH_SIZE files makes ~2 Pushd write calls (down from ~3 per file), verified by offline call counts.
- Per-file upload failures are attributed by Path via batch_update successes; a partial batch splits correctly.
- Throttle pacing, RateLimitError abort, consecutive-failure backstop, and D-09 ordering are all preserved and tested offline.
- `pytest -m "not live"` green; no live writes attempted (live re-verification explicitly deferred to a separate human-approved step on a recovered account).
</success_criteria>

<output>
Update `.planning/STATE.md` Quick Tasks Completed table when done.
</output>
