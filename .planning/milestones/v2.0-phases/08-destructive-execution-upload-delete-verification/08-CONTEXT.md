# Phase 8: Destructive Execution (Upload + Delete Verification) - Context

**Gathered:** 2026-07-07
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers `sync ... --apply`/`--yes`: the code path that actually executes
the plan Phase 7 could only ever print. It uploads new local files to the targeted
frame (`select_asset → S3 → SQS → batch_update`, live-verified for the first time in
this codebase's ~3-year history) and removes frame photos no longer present locally
via `remove_asset` (the confirmed-safer of the two delete primitives). `delete_asset`
is live-verified against a disposable test asset but is NOT wired into the `--apply`
execute path this phase — it stays a documented, unreachable finding. This phase also
fixes the hardcoded SQS queue id in `Aura.get_sqs()` (WRITE-04) so uploads work for
any frame, not just the original test frame, and extends fail-loud error handling to
the write/delete endpoints with per-file attribution (WRITE-05).

In scope: `--apply`/`--yes` flag wiring and confirmation UX, `execute_plan()` (the
mutating counterpart to Phase 7's `compute_plan()`), the upload round-trip, the
`remove_asset` delete round-trip, a one-time live `delete_asset` probe against a
throwaway asset, the SQS queue-id fix, and per-file fail-loud error handling with a
continue-past-failures execution model.

Out of scope: wiring `delete_asset` into any executable path (documented only), a
`--max-delete` circuit breaker (SYNC-05, deferred to v2 per REQUIREMENTS.md), `--json`
output (SYNC-06, deferred to v2), watch/daemon mode (explicitly out of scope for the
whole v2.0 milestone per REQUIREMENTS.md).

</domain>

<decisions>
## Implementation Decisions

### Apply Confirmation UX
- **D-01:** Two-flag model. `--apply` alone prints the full plan (reusing Phase 7's
  untruncated upload/delete listing, D-07) and then prompts `Proceed? [y/N]`. `--yes`
  (combinable with `--apply`, e.g. `sync ... --apply --yes`) skips that interactive
  prompt for scripting/CI use. This mirrors common apply/confirm CLI conventions
  (terraform apply, npm init -y) and is a deliberate escalation beyond Phase 7's
  passive dry-run-only safety: this is the first phase where a wrong answer is
  irreversible.
- **D-02:** One confirmation gate covers the whole plan — uploads and deletes are
  not gated separately. The full-listing plan (D-07 carried from Phase 7) already
  puts every delete candidate in front of the user before they type `y`; a second,
  delete-specific gate was explicitly rejected as redundant friction.
- **D-03:** When `--apply` runs non-interactively (no TTY) without `--yes`, it fails
  closed: print an error (e.g. `--apply requires --yes when running
  non-interactively`) and exit non-zero without touching anything. A scripted/cron
  invocation must never silently hang on an unanswerable prompt, nor silently proceed
  unattended on its first-ever live run.
- **D-04:** The confirmation prompt always echoes the resolved frame's name + id
  (e.g. `About to apply this plan to "Cadre de Fabrice" (id: c063b384-...). Proceed?
  [y/N]`) — even though the plan header above it already shows this per Phase 7 — as
  a deliberate redundant guard against `--frame`'s substring-match resolution (Phase 6
  D-01) landing on an unintended frame right before an irreversible action.

### Delete-Primitive Live Verification
- **D-05:** `delete_asset`'s live behavior is probed using a **dedicated disposable
  test asset** — a throwaway test photo uploaded specifically to be sacrificed to this
  probe — never a real photo the user cares about. Same live-spike-via-real-usage
  methodology as Phase 6's `md5_hash` spike (D-12/13) and Phase 7's hash-convention
  validation (D-09): confirm the actual behavior, document the finding, no permanent
  automated fixture.
- **D-06:** `--apply`'s delete path calls `remove_asset` exclusively. `delete_asset`
  is live-verified and its confirmed behavior is documented (per D-05) but has **no
  reachable code path from `--apply`** this phase — not even behind an undocumented
  flag. This locks in the ROADMAP's stated safe default structurally, the same way
  Phase 7 structurally excluded any mutating call from the dry-run path.
- **D-07:** If the live `delete_asset` probe reveals more destructive behavior than
  its docstring suggests (e.g. it actually reaches S3/Glacier, not just the frame
  association), **stop the live-verification checkpoint immediately** and report
  exactly what was observed — do not proceed to wire anything or draw further
  conclusions until reviewed. Mirrors Phase 7's "if mismatch, STOP and report"
  precedent for its own live checkpoint (07-03-PLAN.md).

### Failure Handling Mid-Apply
- **D-08:** Execution continues past a single item's failure rather than aborting the
  whole run. Every remaining planned upload/delete is still attempted; a final summary
  reports what succeeded and what failed (per-file, satisfying WRITE-05's
  attribution requirement), and the process exits non-zero if anything failed. A
  transient failure on one file must not strand an otherwise-good batch.
- **D-09:** Within a run, all uploads are attempted before any deletes. This leaves
  the frame in the safer partial-failure state if the run is interrupted or aborted
  midway: new content has been added, nothing has yet been removed.
- **D-10:** The end-of-run failure summary reports uploads and deletes in **separate
  sections** (e.g. `Uploads: 8 succeeded, 1 failed` / `Deletes: 3 succeeded, 0
  failed`), each with its failed items individually named — mirroring Phase 7's plan
  output already separating upload/delete/unchanged counts (D-07 there).

### SQS Queue Targeting Fix (WRITE-04)
- **D-11:** User deferred the fix approach entirely to Claude's discretion — this is
  a straightforward parameterization bug fix (`get_sqs()` should resolve the queue
  for whatever frame is being synced, not the hardcoded original-test-frame id),
  with no product-level UX tradeoff. `SQSClient.get_queue_url(frame_id)` already
  accepts a `frame_id` parameter — `Aura.get_sqs()` just needs to stop hardcoding
  the argument it passes in.

### Claude's Discretion
- Exact wording of the `--apply`/`--yes` confirmation prompt and the plan-header
  frame echo, following D-01–D-04's content requirements and Phase 5's concise,
  no-table output style (D-05 there).
- How `execute_plan()` is structured relative to Phase 7's `compute_plan()` (e.g.
  whether it takes a `SyncPlan` directly, or a lower-level per-item execution
  helper) — as long as it stays a distinct function/path from the read-only diff
  engine, preserving the structural (not `if apply:`-flag-based) separation
  PROJECT.md's Key Decisions already commit to.
- How the disposable test asset for the `delete_asset` probe (D-05) is created/
  sourced and how the SQS fix (D-11) is implemented and tested offline.
- Exact construction of upload identity (`local_identifier`, etc.) for local files
  that have no pre-existing Aura asset record — `Aura.upload_image()`'s current
  implementation assumes an existing `Asset.local_identifier`, which syncing a
  never-before-seen local file won't have. Research/planning must resolve this;
  it wasn't raised as a user-facing decision because it has no UX-visible
  tradeoff — whatever identity scheme is chosen, the user only ever sees the
  photo appear on the frame.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project & milestone scope
- `.planning/PROJECT.md` — Current Milestone section (`sync --apply`/`--yes` target
  feature, live verification of `select_asset → S3 → SQS → batch_update` and the
  delete/remove path); Context section's Phase 7 entry documents the confirmed
  byte-identical hash convention this phase's diff engine already trusts.
- `.planning/REQUIREMENTS.md` — **SYNC-03** (execute path: upload new, remove
  gone-locally via `remove_asset`), **SYNC-04** (plan output before applying + non-zero
  exit on failure), **WRITE-01** (upload round-trip live verification), **WRITE-02**
  (`remove_asset` live verification), **WRITE-03** (`delete_asset` live verification),
  **WRITE-04** (SQS hardcoded frame-id fix), **WRITE-05** (fail-loud write/delete error
  handling) are this phase's requirements. v2 Requirements' **SYNC-05** (`--max-delete`
  circuit breaker) is explicitly deferred — do not build it here.
- `.planning/ROADMAP.md` §"Phase 8: Destructive Execution (Upload + Delete
  Verification)" — goal + the 5 success criteria.
- `.planning/STATE.md` Blockers/Concerns — "Delete-primitive ambiguity (Phase 8)" and
  "Hardcoded SQS frame ID (Phase 8, WRITE-04)" entries are the direct motivation for
  D-05–D-07 and D-11 respectively.

### Prior phase context (patterns to follow)
- `.planning/phases/07-sync-diffing-engine-dry-run-only/07-CONTEXT.md` — D-07/D-08
  (full untruncated plan listing; delete candidates shown as id + taken_at date, no
  filename/hash) and D-09 (live-spike-via-real-usage methodology) carry forward
  directly. `compute_plan()`'s pure-function shape is the model `execute_plan()`
  should sit alongside, not replace.
- `.planning/phases/06-inspect-frame-resolution/06-CONTEXT.md` — D-01–D-05 (frame
  resolution by name/id, ambiguous/not-found handling) is reused as-is for `sync
  --apply --frame`; D-12/13's live-spike documentation pattern is the direct
  precedent for D-05 here.
- `.planning/phases/05-cli-skeleton-status/05-CONTEXT.md` — D-08 (fail-loud,
  non-zero exit convention) carries forward and is extended by D-08–D-10 here to
  per-file granularity.

### Codebase analysis (structure/architecture already mapped)
- `.planning/codebase/ARCHITECTURE.md` — Image Upload Flow section documents the
  existing (currently broken/unguarded) `select_asset → SQS poll → select_asset →
  S3 upload → batch_update → SQS poll` sequence in `Aura.upload_image()`; "Unguarded
  Post-Login State" anti-pattern flags `self.sqsClient` only being assigned inside
  `get_sqs()` with no `login()` guard — relevant to how `execute_plan()`'s upload path
  should be structured to avoid the same `AttributeError` risk. "Silent Error Handling
  in API Responses" anti-pattern is the direct target of WRITE-05.
- `.planning/codebase/INTEGRATIONS.md` — AWS S3/SQS integration details: bucket
  `images.senseapp.co`, two separate Cognito identity pools (upload vs. SQS polling),
  SQS queue naming convention `frame-{frame_id}-client`, and the currently-hardcoded
  queue id `4ab446b4-33a7-4a76-881d-d545d153ab5a` in `Aura.get_sqs()` (WRITE-04's
  exact target).

### Files that will change
- `auraframes/aura.py` — `upload_image()` needs rework for syncing arbitrary local
  files (no pre-existing `Asset`/`local_identifier`); `get_sqs()` needs the
  hardcoded frame id removed (WRITE-04) per D-11.
- `auraframes/cli.py` — `sync` subparser gains `--apply`/`--yes`; `run_sync()` (or a
  new handler) gains the confirmation-prompt flow (D-01–D-04) and calls
  `execute_plan()` when `--apply` is set instead of only printing.
- `auraframes/sync.py` — add `execute_plan()` alongside Phase 7's `compute_plan()`;
  this is the only place a mutating call may appear in this module going forward.
- `auraframes/api/frameApi.py` — `remove_asset()` reused as-is; `select_asset()`
  reused as-is for upload association.
- `auraframes/api/assetApi.py` — `batch_update()` reused as-is; `delete_asset()`
  called only from the one-time live-verification checkpoint, not from `execute_plan()`.
- `auraframes/aws/s3client.py`, `auraframes/aws/sqsclient.py` — reused as-is
  (`upload_file`, `get_queue_url`); no changes expected beyond how `get_sqs()` calls
  `get_queue_url()` with the correct frame id.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `FrameApi.select_asset(frame_id, AssetPartialId)` / `FrameApi.remove_asset(frame_id,
  AssetPartialId)` (`auraframes/api/frameApi.py:105,135`) — the two frame-association
  endpoints the upload and delete paths need; both already exist and are typed.
- `AssetApi.batch_update(asset)` (`auraframes/api/assetApi.py:9`) — posts metadata
  after S3 upload; already restricts the payload to a safe field allowlist.
- `AssetApi.delete_asset(asset)` (`auraframes/api/assetApi.py:74`) — exists but its
  docstring says "Currently unknown if this is used... maybe this deletes it from
  S3/Glacier" — exactly the ambiguity D-05–D-07 resolve live.
- `S3Client.upload_file(data, extension)` / `S3Client.get_md5` (`auraframes/aws/
  s3client.py:14,30`) — already used by Phase 7's `scan_directory` for local hashing;
  `upload_file` returns `(filename, md5)` ready to populate `Asset.file_name`/
  `Asset.md5_hash` before `batch_update`.
- `SQSClient.get_queue_url(frame_id)` (`auraframes/aws/sqsclient.py:23`) — already
  parameterized by `frame_id`; `Aura.get_sqs()` just needs to pass the real target
  frame's id instead of the hardcoded constant (D-11).
- `SyncPlan` / `compute_plan()` (`auraframes/sync.py`, Phase 7) — `to_upload: list[Path]`
  and `to_delete: list[Asset]` are exactly the inputs `execute_plan()` iterates over.

### Established Patterns
- Fail-loud, non-zero exit (Phase 5 D-08, extended to per-file granularity by D-08
  here) — `run_sync`'s existing `except Exception as e: print(...); return 1` pattern
  (`auraframes/cli.py`) is the model for the top-level catch; per-file errors need
  their own try/except inside the upload/delete loop so one failure doesn't propagate
  and abort the whole batch (per D-08).
- Structural dry-run/execute separation (PROJECT.md Key Decisions, realized in Phase 7
  as `compute_plan()` with no mutating counterpart) — `execute_plan()` is the first
  function in this codebase allowed to call a mutating primitive; Phase 7's grep-gate
  precedent (no `put_object`/`select_asset`/etc. in `compute_plan()`/`scan_directory`)
  should now instead assert those calls exist ONLY inside `execute_plan()`.
- `resolve_frame()` / DI seam (`Aura(client=...)`) / `tests/offline.py` — same offline
  test harness Phases 5-7 used; `execute_plan()`'s S3/SQS calls will need their own
  mockable seam (existing `S3Client()`/`SQSClient()` are constructed directly inside
  `Aura.upload_image()` today, not injected — worth noting for planning, not decided
  here).

### Integration Points
- `auraframes/cli.py`'s `sync` subparser (Phase 7) needs `--apply` and `--yes`
  arguments added; `main()`'s dispatch branch is unchanged in shape.
- `Aura.upload_image()` is today's only upload orchestration code and is broken for
  this use case (assumes `asset.local_identifier` from an existing local Aura asset,
  calls `self.sqsClient` unguarded, opens the image via PIL only to read
  width/height) — expect significant rework here, not simple reuse.

</code_context>

<specifics>
## Specific Ideas

- The user's exact framing for why deletions don't get a second confirmation gate:
  the full plan listing (already showing every delete candidate) is itself the
  review step — a second gate was seen as redundant with what Phase 7's D-07 already
  guarantees is visible before `y` is typed.
- The "stop and report immediately" instinct for an unexpectedly-destructive
  `delete_asset` finding is a direct continuation of Phase 7's own live-checkpoint
  precedent (07-03-PLAN.md: "If it shows as an upload... STOP and report; the
  engine's assumption is broken") — same reflex, applied to a scarier endpoint.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. No scope-creep items arose; all four
discussed areas (apply confirmation UX, delete-primitive live testing, failure
handling, SQS queue fix) were implementation/UX decisions for this phase's execute
path itself.

### Reviewed Todos (not folded)
None — no pending todos matched Phase 8 (`todo.match-phase` returned zero matches).

</deferred>

---

*Phase: 8-Destructive Execution (Upload + Delete Verification)*
*Context gathered: 2026-07-07*
