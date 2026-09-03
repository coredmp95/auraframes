# Phase 11: Write-Path Reliability & Format Support - Context

**Gathered:** 2026-09-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Make the already-proven write path (`sync --apply` / `push`) fail *honestly* instead of
*spuriously*, and widen it to the file types a Google album actually contains.

Concretely, this phase delivers:
- A transient HTTP 401 no longer ends a live run — it is retried once, safely, without
  creating a duplicate frame asset, and with its budget cost decided on purpose.
- Every write failure carries its true name: a genuine authentication failure, an
  anti-abuse trip, and a silently-dropped `batch_update` id are three different things
  and are reported as three different things.
- `.png` uploads end-to-end and is verified live; `.heic` is resolved explicitly — either
  it really uploads or it is refused with a message naming the actual reason.
- The 58 stuck placeholder rows on the live frame are counted and reported, and removed
  if a working mechanism exists.
- The default test suite runs green.

**Not this phase:** anything Google-side (Phases 12-15), the album-access mechanism spike
(Phase 12), the `google_media_id → md5_hash` manifest (Phase 14), many-to-many pair
mapping (Phase 15), MOD-02/MOD-04 hardening (Phase 15), and MOD-01's async migration
(deferred indefinitely). Placeholder reconciliation is deliberately **outside** the sync
loop — it is data hygiene on existing bad state, not a sync-time concern.

</domain>

<decisions>
## Implementation Decisions

### 401 retry & duplicate safety (REL-01, REL-02, REL-04)

- **D-01:** The retry is **verify-then-retry**, never blind. On a 401, re-login, then probe
  each item in the failed chunk with the already-existing
  `AssetApi.get_asset_by_local_identifier()` and re-send **only** the items that genuinely
  are not there. This makes REL-02 structural rather than hopeful: an upload whose response
  was lost but which actually landed cannot be re-sent, so the retry cannot manufacture the
  very duplicate placeholder rows REL-05 is cleaning up in this same phase. The extra cost
  is one read per item, and reads are demonstrably not the constrained surface — writes are.
  — **Reversibility:** reversible — it is an added guard in one code path, removable without
  touching the endpoints or any persisted format.

- **D-02:** **The re-login is the auth-vs-anti-abuse discriminator** (REL-04). Two outcomes,
  two names:
  - Re-login **fails** → a genuine authentication failure (bad or revoked credentials).
    Abort the run loudly. Never retry, never soften.
  - Re-login **succeeds** but the write 401s again → this is **not** authentication at all.
    Classify it as the anti-abuse trip and hand it to the existing
    `ConsecutiveWriteFailureError` backstop (`auraframes/sync.py:127`).

  This is the point of the phase: v2.0 lost a debug session to a 401 that was neither an auth
  problem nor a geofence. A failure that cannot say what it is, is the defect.
  — **Reversibility:** reversible.

- **D-03:** The retry lives **in `execute_plan`, per write chunk** — the same injectable seam
  Phase 9 chose for `budget` / `geo_check` (its Approach A). A client-level interceptor is
  explicitly rejected again for the same reasons Phase 9 rejected its Approach C: it would be
  invisible to `WriteBudget` accounting and to per-file attribution, and it would silently
  replay reads too. Login and the read path are untouched.
  — **Reversibility:** costly — moving the retry later would mean rethreading budget
  accounting and per-file attribution, both of which sit in `execute_plan` by design.

- **D-04:** **One retry per chunk, one shared re-login, continue past failure.** A chunk gets
  exactly one verify-and-retry. The refreshed session is reused by every subsequent chunk —
  no re-login storm. A chunk that still fails has its items attributed as failed and the run
  continues (carrying Phase 8 D-08 forward verbatim), with `ConsecutiveWriteFailureError`
  remaining the ultimate abort and a non-zero exit code at the end.
  — **Reversibility:** reversible.

### Retry budget accounting (REL-03)

- **D-05:** **A retry is charged at full write cost** — 2 for an upload chunk, 1 for a delete
  chunk, exactly as a first attempt. The requests really were sent and really did hit the
  anti-abuse surface; Phase 9 already observed that *failed* attempts appear to consume
  server-side budget too. Charging the retry keeps the local estimate honest at the price of
  a shorter effective run. This is REL-03's "deliberate decision, not an accident".
  — **Reversibility:** reversible — a cost constant, not a persisted format change.

- **D-06:** **Verify reads are free; the re-login costs 1 token.** Reads demonstrably kept
  working throughout v2.0's write lockouts, so a *write* budget rightly ignores them — and
  charging them would make a 50-item chunk's verification cost 50 tokens, which would defeat
  D-01. The re-login is charged because the v2.0 incident escalated from write 401s to a
  *login* lockout: the login endpoint is on the anti-abuse surface and has already bitten
  this project once.
  — **Reversibility:** reversible.

- **D-07:** **A retry obeys the same wait policy as any other write.** It calls
  `budget.acquire()` normally — waits up to `max_wait_seconds`, honours `--no-wait`,
  `--max-wait` and `--ignore-budget`. One policy, already user-configurable since Phase 9;
  no second hidden rule for the user to discover mid-run.
  — **Reversibility:** reversible.

- **D-08:** **Retries are visible at runtime.** The end-of-run summary reports how many chunks
  were retried and how many items the verify probe found already-landed (i.e. duplicates
  prevented) — the single most useful signal for judging whether the 401 problem is actually
  fixed, and the reason it must not hide behind `--debug`. The costing rule itself is
  documented as a comment beside the constant, matching this codebase's existing
  heavy-rationale convention (see `WRITE_CHUNK_DELAY_SECONDS`, `auraframes/sync.py:95`).
  — **Reversibility:** reversible.

### Format support (FMT-01, FMT-02, FMT-03)

- **D-09:** **`pillow-heif` is added as a dependency, and HEIC uploads as-is.** Verified during
  this discussion: `pillow-heif==1.6.0` resolves cleanly on this project's Python 3.14 with a
  prebuilt wheel — no build toolchain required. `data_uti` becomes `public.heic` and the
  original bytes go to S3 untouched. Transcoding to JPEG was explicitly **rejected**: it would
  make the uploaded bytes differ from the source file, so `md5_hash` diffing would compare a
  local original against a transcoded remote and every run would risk seeing every photo as
  changed — the exact re-upload-forever failure mode SPK-04 exists to prevent in Phase 12.
  — **Reversibility:** costly — the `data_uti` value and the uploaded bytes are what land on
  the frame; changing the scheme after photos are uploaded means the existing HEIC assets no
  longer match anything a later run computes.

- **D-10:** **HEIC-as-is requires a live verification checkpoint**, because whether the frame
  actually *renders* a HEIC asset is unknown. **Pre-authorized fallback if it does not:**
  refuse `.heic` at `_prep_upload` with a message naming the real reason — *the frame does not
  accept HEIC*, not "missing decoder" — record the finding for Phases 12/14, and let the phase
  complete. Deliberately not a stop-and-report: the Phase 7/8 stop-and-report precedent is for
  *destructive surprises*, and a format the frame will not render is a capability gap, not a
  destructive one. FMT-03's "never a silent failure" is satisfied on either branch.
  — **Reversibility:** reversible.

- **D-11:** **`data_uti` is derived from the decoded image's real format, not the filename.**
  `_prep_upload` already calls `Image.open()` for dimensions (`auraframes/sync.py:363`), so
  `image.format` is free. Map that (JPEG / PNG / HEIF) to the UTI through an **explicit table
  that still fails closed** on anything unmapped — preserving today's fail-closed behaviour
  while removing the filename as a trust anchor. A `.jpg` that is really a PNG can no longer be
  mislabeled server-side; the bytes decide.
  — **Reversibility:** reversible.

- **D-12:** **Scope holds to exactly JPEG / PNG / HEIF** — the set `ELIGIBLE_EXTENSIONS`
  already declares (`auraframes/sync.py:55`) and the set this phase live-verifies. WebP was
  considered and deferred: Google Photos does serve it in some paths, but shipping it here
  would be unverified write surface, and Phase 12 has not yet established what bytes the album
  mechanism actually delivers. Unknown formats keep failing closed with a named reason.
  — **Reversibility:** reversible.

### Placeholder reconciliation (REL-05)

- **D-13:** **A new `reconcile` CLI verb, plus a one-line count in `inspect`.** The verb does
  the work (reports by default; removal behind an explicit flag); `inspect` gains a single
  line — "N placeholder rows" — so the user discovers the problem without having to know the
  verb exists. This follows `research/ARCHITECTURE.md` §Placeholder-row reconciliation: a
  separate `auraframes/reconcile.py`, decoupled from both the Aura write path and the Google
  integration, because it is data hygiene on existing frame state, not a sync-time concern.
  Folding a mutating action into `inspect` was rejected — `inspect`'s whole identity so far is
  read-only.
  — **Reversibility:** reversible.

- **D-14:** **A placeholder is identified by the strict conjunction: `uploaded_at` AND
  `file_name` AND `md5_hash` all null.** The narrowest predicate, and it self-excludes both
  known look-alikes — videos are hashless by design but do carry `file_name` and
  `uploaded_at`, and a partially-hydrated asset trips only one of the three. Being wrong here
  means proposing to remove a real photo, so narrow beats clever. Deliberately **not** reusing
  `compute_plan`'s `frame_no_hash` bucket (`auraframes/sync.py:263-268`), which includes every
  video on the frame.
  — **Reversibility:** reversible.

- **D-15:** **Age guard on `created_at`, 24h default, overridable.** A row created seconds ago
  by a legitimate in-progress upload matches D-14's predicate exactly — `tests/test_cli_inspect.py`
  already covers a mid-server-side-processing asset that is indistinguishable from a stuck one.
  Rows younger than the threshold are reported separately as "recently created — may still be
  processing" and are **never** removal candidates. `Asset.created_at` is non-optional
  (`auraframes/models/asset.py:22`), so this costs nothing.
  — **Reversibility:** reversible.

- **D-16:** **Time-boxed live probe for a removal mechanism, then report-only if nothing works.**
  Neither existing primitive clears these rows (`delete_asset` returns 200 and removes nothing;
  `remove_asset` 404s). Probe a **bounded** set of candidates live — explicitly including
  *completing* the row rather than deleting it (`batch_update` it with real
  `file_name`/`md5_hash`/`uploaded_at` so it becomes a normal asset that the existing hide and
  remove paths already handle). If none works, ship the honest "reports the count, cannot
  remove" state with the finding written down. REL-05's own wording ("removes them **if a
  working mechanism is found**") already allows this, and `research/ARCHITECTURE.md` warns the
  honest answer may be that no client-side fix exists.
  — **Reversibility:** reversible.

### Failure attribution & test hygiene (REL-06, REL-07, REL-08, MOD-03)

- **D-17:** **REL-08 — the test asserts the cursor loop's own correctness, not the server's
  arithmetic.** `test_read_03_pagination` (`tests/test_read_path.py:64`) currently asserts
  `len(assets) == total`, which is 149 vs 171 live — two counts the server itself does not keep
  consistent. Replace with assertions on what the *client* controls: more than one page was
  fetched, no asset id appears twice, and the drained count is greater than zero and never
  exceeds `total`. That is precisely the "stopped early or double-counted" failure the original
  comment says the test was written to catch. A percentage tolerance was rejected (a magic
  number with no principled value that hides the day the drift grows), as was moving it offline
  (live cursor behaviour is the one thing this live test exists for).
  — **Reversibility:** reversible.

- **D-18:** **REL-07 — the sent-vs-acknowledged check lives in `batch_update` and is returned
  explicitly.** `AssetApi.batch_update` computes the sent-but-unacknowledged set and returns it
  as a named part of its result. `execute_plan` keeps attributing per-file exactly as it does
  today (`auraframes/sync.py:607-618`, which is already correct); the value is that
  `Aura.upload_image` — which discards the return value today, per `batch_update`'s own
  docstring — gets a real failure signal instead of silence. One definition, every caller
  covered. Raising on partial success was rejected: the endpoint's documented contract is that
  a partial `successes` list is the *normal* batch signal, and raising would abort chunks that
  are behaving exactly as designed.
  — **Reversibility:** costly — it changes a public return shape that existing callers destructure.

- **D-19:** **REL-06 — strict outbound, tolerant inbound.** Constructing an `AssetPartialId` to
  *send* with neither `id` nor `local_identifier` stays a hard validation error — that is
  REL-06's criterion, "rejected at construction instead of being sent". But the same class
  parses inbound responses (`AssetPartialId(**partial_asset_id)` in `batch_update`), and there
  a malformed entry is skipped and logged rather than raised: one junk row in a 50-item
  `successes` list must not crash a chunk mid-flight and cost the whole batch's per-file
  attribution via the generic `except Exception` branch. The API is undocumented and its shape
  drifts — Phase 10's `smart_adds` regression is the precedent.

  Note for the planner: the validator at `auraframes/models/asset.py:137` is already a
  pydantic-v2 `model_validator(mode='after')` and appears to fire on the normal construction
  path. **Verify before rewriting** — REL-06 may need a proving test plus the inbound tolerance
  rather than a new validator.
  — **Reversibility:** reversible.

- **D-20:** **MOD-03 — a common base plus the auth types; convert write-path `RuntimeError`s
  only.** Add an `AuraError` base, reparent the existing `RateLimitError`
  (`auraframes/client.py:28`) and `ConsecutiveWriteFailureError` (`auraframes/sync.py:127`)
  under it, and add the auth exception type(s) the D-02 classification needs. Convert the bare
  `RuntimeError`s on the write path (e.g. `batch_update`'s, `auraframes/api/assetApi.py`) and
  leave the read path alone. Enough structure for the retry logic to read clearly, no
  speculative taxonomy — MOD-03's own wording is "where it pays". A full codebase-wide
  conversion was rejected as the widest blast radius in a phase whose point is making the write
  path more *trustworthy*, not more *changed*.
  — **Reversibility:** costly — reparenting exception types changes what existing `except`
  clauses catch; the write path's `except RateLimitError` / `except ConsecutiveWriteFailureError`
  ordering in `execute_plan` is load-bearing and must not be broadened by accident.

### Claude's Discretion

- **Naming.** `AuthExpiredError` vs `AuthenticationError` vs a single type with a flag; the
  exact `AuraError` base name; the `reconcile` verb's flag names for report-vs-remove.
- **Message wording** throughout — the refusal text for an unsupported format, the retry
  summary line, the placeholder report layout — following Phase 5 D-05's concise, no-table
  output style.
- **Confirmation friction on `reconcile --remove`.** Follow Phase 10's escalating-friction
  precedent: these rows are unremovable today and the failure mode is safe (it fails toward
  *not* deleting), but the removal path is still a write and should carry a normal
  `Proceed? [y/N]` gate with `--yes` honoured, and should draw from the shared `WriteBudget`
  like any other write.
- **How the verify probe (D-01) is batched.** Whether it issues one lookup per item or exploits
  any list/filter endpoint that can answer for a whole chunk at once — no user-facing tradeoff,
  as long as it stays on the read path.
- **How the PNG live verification (FMT-02) is staged** — reuse Phase 8 D-05's
  disposable-test-asset methodology if a sacrificial asset is needed.
- **Where the retry logic physically sits** within `execute_plan` (inline vs an extracted
  helper), provided it stays injectable for offline tests per the v1.1 DI seam.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone scope and requirements
- `.planning/ROADMAP.md` §"Phase 11: Write-Path Reliability & Format Support" — the phase goal,
  its 5 success criteria, and the Notes paragraph establishing that FMT is a *blocker for
  Phase 14, not debt*, and that placeholder reconciliation stays outside the sync loop.
- `.planning/REQUIREMENTS.md` — REL-01..08 (lines 31-38), FMT-01..03 (lines 44-46), MOD-03
  (line 102). The 12 requirements this phase must close.
- `.planning/STATE.md` §"Blockers/Concerns" — the three carried v2.0 defects in their original
  measured form (~4-in-10 spurious 401s; 58 stuck placeholder rows; 171-vs-149 pagination
  mismatch), and §"Decisions" for the standing conventions this milestone must respect.

### Research (v3.0)
- `.planning/research/PITFALLS.md` — Pitfall 4 (lines 229-253) on retry-induced duplicate
  placeholder rows and the idempotency check that prevents them; line 438's explicit "never"
  verdict on retry-without-idempotency-check; line 510's risk entry noting a stuck row is
  likely permanent and prevention is the only real recovery.
- `.planning/research/ARCHITECTURE.md` §"Placeholder-row reconciliation" (lines 587-605) — the
  separate-module-and-verb recommendation, and why `compute_plan` already excludes hashless
  assets so Google-sourced syncs inherit the correct exclusion for free.
- `.planning/research/ARCHITECTURE.md` line 719 — reconciliation sequenced as independent of
  the Google work; line 797 — the named anti-pattern of treating it as part of the sync loop.

### Codebase maps
- `.planning/codebase/CONCERNS.md` line 106 — the pre-existing recommendation to track token
  age or re-authenticate on 401; line 109 — `response.json()` called unconditionally regardless
  of status code, directly relevant to how a 401 currently surfaces; line 175 — `assetApi`
  methods including `batch_update` are entirely untested.
- `.planning/codebase/TESTING.md` — the offline `MockTransport` harness conventions every new
  test in this phase must follow.
- `.planning/codebase/CONVENTIONS.md` — naming and comment-density conventions (D-08's
  documented-in-code costing rule depends on these).

### Prior phase decisions carried forward
- `.planning/milestones/v2.0-phases/09-proactive-write-rate-limiter-geo-guard/09-CONTEXT.md` —
  `WriteBudget` semantics, request-currency costing, the injectable-seam Approach A and the
  explicitly rejected client-interceptor Approach C. D-03/D-05/D-06/D-07 all build directly on it.
- `.planning/milestones/v2.0-phases/08-destructive-execution-upload-delete-verification/08-CONTEXT.md` —
  D-08 (continue past a single item's failure), D-05 (disposable-test-asset methodology),
  D-07 (stop-and-report on a destructive surprise).
- `.planning/milestones/v2.0-phases/10-hide-instead-of-delete-sync-mode/10-CONTEXT.md` —
  escalating friction by destructiveness; hide as `--apply`'s default removal mode.
- `.planning/debug/resolved/select-asset-401-unauthorized.md` — the original 401 debug session
  referenced from `auraframes/sync.py:23`; the source of the burst-volume root cause and the
  three existing layers of defence.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`AssetApi.get_asset_by_local_identifier()`** (`auraframes/api/assetApi.py`) — already
  exists; it is the verify probe D-01 depends on. No new endpoint work needed.
- **`WriteBudget` + `check_geo`** (`auraframes/ratelimit.py`) — `acquire()`, `reconcile_tripped()`,
  `save()`/`load()`, injected `clock`/`sleep`. D-05..D-07 are cost and policy decisions on top of
  an already-built mechanism.
- **`ConsecutiveWriteFailureError`** (`auraframes/sync.py:127`) — already exists specifically as
  the backstop for the plain-HTTP-401 form of the anti-abuse trip. D-02's "not auth" branch
  hands off to it rather than inventing anything.
- **`RateLimitError`** (`auraframes/client.py:28`) — 429/475, with `retry_after` and a server
  message; the reparenting target in D-20.
- **`Client(transport=...)` / `Aura(client=...)` DI seam** (v1.1) — every new behaviour in this
  phase must be exercisable offline through it. `Image.open()` is already called in
  `_prep_upload`, so D-11's format detection needs no new I/O.
- **`Asset.created_at`** (`auraframes/models/asset.py:22`) — non-optional, so D-15's age guard
  needs no new field or API call.

### Established Patterns
- **Injectable seams over interceptors.** `execute_plan` already takes `throttle_seconds`,
  `sleep`, `batch_size`, `chunk_delay_seconds`, `on_wait`, `budget`, `geo_check`,
  `wait_on_budget`, `max_wait_seconds`, `clock`, `removal_mode`. The retry follows this shape
  (D-03) rather than hiding in the transport.
- **Fail closed with a named reason.** `_prep_upload` (`auraframes/sync.py:348-360`) already
  raises on an unmapped extension and the caller catches per file so one bad file never blocks
  a chunk. D-11/D-12 preserve exactly this, only changing what decides the type.
- **Heavy rationale comments beside constants.** `WRITE_THROTTLE_SECONDS`, `WRITE_BATCH_SIZE`,
  `WRITE_CHUNK_DELAY_SECONDS` and `MAX_CONSECUTIVE_WRITE_FAILURES` each carry a paragraph
  explaining the live incident that motivated their value. D-08's costing rule is documented
  the same way.
- **Batch endpoints, per-item attribution.** `select_asset` and `batch_update` are native batch
  endpoints; the chunk loop recovers per-file outcomes from `successes[].local_identifier`.
  D-01's verify probe and D-18's unacknowledged set both operate at this same per-item grain.
- **Careful `except` ordering in the chunk loop.** `except RateLimitError` / `except
  ConsecutiveWriteFailureError` / `except Exception` at `auraframes/sync.py:617-639`, with an
  explicit comment on why the middle branch must propagate rather than be re-caught. D-20's
  reparenting must not broaden what these catch.

### Integration Points
- **`execute_plan`'s upload chunk loop** (`auraframes/sync.py:~590-650`) — where D-01's
  verify-then-retry, D-04's one-retry-per-chunk and D-05's retry costing all land. Also the
  re-show and removal chunk loops below it, which need the same retry treatment.
- **`_prep_upload` / `_DATA_UTI_BY_SUFFIX`** (`auraframes/sync.py:64`, `348`) — where D-11's
  format-derived UTI replaces the suffix map. `ELIGIBLE_EXTENSIONS` (line 55) already lists all
  four formats, so the two lists converge rather than diverge.
- **`AssetApi.batch_update`** (`auraframes/api/assetApi.py`) — D-18's return-shape change; note
  its docstring already documents partial `successes` as expected, so the docstring updates with it.
- **`auraframes/cli.py`** — verbs today are `status` / `inspect` / `sync` / `push` (lines 61-86).
  D-13 adds `reconcile` and a line to `inspect`'s output.
- **New module `auraframes/reconcile.py`** — per `research/ARCHITECTURE.md`; imports nothing
  from the Google side and is not reachable from the sync loop.
- **`pyproject.toml`** — `pillow-heif` added to `dependencies` (D-09).
- **`tests/test_read_path.py:64`** — D-17's assertion replacement.

</code_context>

<specifics>
## Specific Ideas

- The user's framing throughout was **honest attribution over successful-looking runs**: the
  point of the retry is not to make more runs pass, it is to make a failure say what it is.
  D-02's re-login-as-discriminator was chosen precisely because it gives each failure its true
  name rather than collapsing two different problems into one label.
- **The duplicate-prevention count is the headline metric** (D-08). "How many items did the
  verify probe find already-landed" is the number that tells you whether D-01 is doing real
  work — and is exactly the class of event that produced the 58 stuck rows in the first place.
- **The complete-the-row idea** (D-16) — treating a stuck placeholder as an *incomplete upload
  to finish* rather than a *bad row to delete* — reframes REL-05 around the mechanism that
  created the rows. `select_asset` created them and `batch_update` was meant to fill them in;
  filling them in now turns an unremovable row into an ordinary asset the existing hide/remove
  paths already handle.
- **Transcoding was rejected on md5 grounds, not fidelity grounds** (D-09). The user's concern
  was the diffing contract, not image quality: bytes that differ from the source file make
  every future run's content hash lie.
- Relevant memories: `[[pushd-write-geofence]]` (a write 401 is not proof of a geo block —
  retry with a fresh login **first**, which D-01/D-02 now automate), `[[pushd-batch-endpoints]]`
  (per-file calls are what trip anti-abuse; the chunk shape is load-bearing),
  `[[pushd-app-upload-mechanism]]` (the official app drip-feeds uploads, which is why the
  pacing layers exist and why D-05 charges retries honestly).

</specifics>

<deferred>
## Deferred Ideas

- **WebP upload support** — considered under D-12 and deferred. Google Photos serves WebP in
  some paths, but adding it here would ship unverified write surface before Phase 12 has
  established what bytes the album mechanism actually delivers. Revisit in Phase 13/14 if the
  selected mechanism returns WebP.
- **HEIC → JPEG transcoding** — rejected as this phase's mechanism (D-09) because it breaks the
  `md5_hash` diffing contract. If a future phase ever needs it, it must come with a
  transcoded-bytes manifest, not a naive local hash.
- **A codebase-wide typed exception hierarchy** — scoped down in D-20 to the write path.
  Converting the read path and the remaining `RuntimeError`/status-discriminator call sites is
  a reasonable later cleanup, but not in a phase about making the write path trustworthy.
- **Reporting remaining budget tokens in the run summary** — considered under D-08 and left out;
  the on-disk estimate is only ever approximate to server reality, and printing it invites the
  user to trust a number that can drift.
- **Removing Phase 9's capacity/refill defaults tuning** now that retries add load — not
  discussed in depth; if live runs show the retry meaningfully shortens usable runs, revisit
  `AURA_WRITE_BUDGET_CAPACITY` / `AURA_WRITE_BUDGET_REFILL_PER_MIN` as a quick task rather than
  as phase scope.

</deferred>

---

*Phase: 11-Write-Path Reliability & Format Support*
*Context gathered: 2026-09-03*
