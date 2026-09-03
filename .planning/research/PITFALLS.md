# Pitfalls Research: v3.0 Google Photos Album Sync

**Domain:** Adding a Google Photos album source (OAuth + Library/Picker API + content-hash
diff + hide-on-removal mirroring) to an already-live, already-hardened Aura Frames sync CLI
**Researched:** 2026-09-03
**Confidence:** MEDIUM overall — Google API behavior claims are cross-checked against 2+
independent sources (official `developers.google.com` docs plus community/issue-tracker
reports) but none are HIGH per this project's `classify-confidence` seam, since no
authenticated live spike against the real Google Photos API has been run yet. Codebase/
Pushd-side claims are HIGH — read directly from `.planning/PROJECT.md`'s validated Key
Decisions and Context entries for phases 6-10.

This document assumes the reader already knows the hard-won Pushd-side findings listed in
`PROJECT.md` (visibility flag location, `remove_asset` vs `delete_asset` blast radius,
transient-401-not-geofence, the 58 stuck placeholder rows, `WriteBudget`, `md5_hash` null
for video). Those are **not** re-derived here; they are treated as constraints the new
Google-side pitfalls must not violate.

---

## Critical Pitfalls

### Pitfall 1: The milestone's "discover albums" requirement is already broken by Google's March 2025 API change — and the break is worse than "unresolved," it's "the wrong shape"

**What goes wrong:**
`PROJECT.md` flags album discovery as "mechanism unresolved" but frames it as a research
question to settle. It is not open — it is answered, and the answer reshapes the feature:

- **VERIFIED** (Google Developers Blog + `developers.google.com`, effective 2025-03-31):
  the Library API's `photoslibrary.readonly`/`.sharing`/`photoslibrary` scopes were removed.
  `albums.list` and `mediaItems.search` are now restricted to **content the calling app
  itself created** — a general third-party app can no longer enumerate a user's
  pre-existing albums or library photos via the Library API. Shared-album endpoints return
  `403 PERMISSION_DENIED`.
- **VERIFIED** (same sources): the replacement is the Picker API, which requires the user
  to interactively open a Google-hosted picker UI and manually select items — **there is no
  "select this whole album" one-click action**; users search/select individual photos, even
  when picking "from an album."
- **VERIFIED** (Picker API `sessions` reference docs): a picking session expires within
  ~24 hours, and once the user hits "Done" the session's `pickerUri` is dead — a fresh
  session (fresh user interaction, browser tab, click-through) is required to pick again.

Net effect: there is no scriptable, unattended, re-runnable "give me this album's current
contents" call available to a general app anymore. The requirement as written — "N albums
mapped to N frames, reconciled in a single unattended run" — assumes exactly the mechanism
Google removed.

**Why it happens:**
The milestone was scoped from `main.py`-era assumptions about the Library API (pre-2025
docs/tutorials/StackOverflow answers overwhelmingly describe the old `albums.list`
behavior); the March 2025 change is recent enough that most public tutorials, and even some
still-open Google-authored blog posts, are inconsistent about what "app-created" actually
excludes.

**Prevention:**
Do the live spike **before** designing the sync engine — this project has a strong,
repeatedly-vindicated precedent for exactly this move (Phase 6 `md5_hash`, Phase 7 hash
format, Phase 10 visibility flag). Concretely, in the reliability/foundation phase or a
dedicated "Google mechanism spike" phase:
1. Create a throwaway Google Cloud project + OAuth client, authenticate with your own
   account, and call `albums.list` against a real *pre-existing, not-app-created* album.
   Confirm it 403s (or doesn't — verify, don't assume the blog post).
2. Run one full Picker API round-trip (`sessions.create` → poll → `mediaItems.list`) and
   record: can items be filtered by album in the picker UI at all, or only searched by
   date/keyword? How many clicks does re-syncing an "album" require?
3. Based on that, write the *actual* buildable requirement — most likely one of: (a) an
   app-created album that the user populates via `batchAddMediaItems` (requires its own
   UI/flow, and only works for photos the app itself uploaded to Google, which is circular
   for this use case), or (b) accept that "sync" means "user re-opens the picker and
   re-selects the album's current photos each run" rather than a headless list call, or
   (c) narrow v3.0 scope to "one-time import via Picker" and cut the "many-to-many
   unattended reconciliation" promise until Google restores a scriptable path.
**Do not build the many-to-many persisted-mapping reconciler until this spike returns.**

**Warning signs:** Any phase plan that calls `albums.list` or `mediaItems.search` against a
user's non-app-created album and expects success; any design doc that describes "sync"
running without a browser/user-interaction step for existing (not-app-created) albums.

**Phase to address:** A dedicated Google-mechanism spike phase, sequenced immediately after
the reliability-pass phases and *before* "Link a Google account" is built out further than
the OAuth handshake itself — this can invalidate or reshape "Discover albums," "Sync album →
frame," and "Many-to-many mapping" simultaneously.

---

### Pitfall 2: Building the content-hash diff on Google-downloaded bytes without first proving they're byte-identical to the frame's convention — every sync run re-uploads every photo forever

**What goes wrong:**
v2.0's entire diff engine (`compute_plan`) trusts that `S3Client.get_md5(local_bytes)`
(base64-encoded MD5 of the exact local file bytes) equals the frame's `Asset.md5_hash`.
That equality was earned, not assumed — Phase 7's live spike proved it byte-identical for
locally-authored files. Google Photos downloads are a **different byte source**, and the
assumption does not automatically transfer:

- **VERIFIED** (multiple independent reports: a long-standing `googlesamples/google-photos`
  issue thread, Google Photos Community threads, and the archived `gphotos-sync` tool's own
  README — a mature, purpose-built Google Photos backup tool that hit this exact wall):
  the `=d` "original quality" download parameter does **not** reliably return byte-identical
  original files. GPS EXIF metadata is stripped; videos are transcoded to lower quality;
  RAW/original photos may come back as Google's re-encoded "High Quality" version rather
  than the exact uploaded bytes. This has been reported since ~2018 and is not resolved in
  current docs.
- If the downloaded bytes differ from what was originally uploaded to Google *at all*
  (different MD5), then on every sync run: `compute_plan` sees "no frame asset has this
  hash" → classifies every photo as "to upload" → `execute_plan` uploads every photo again
  → the frame accumulates infinite duplicates and the `WriteBudget` gets burned every single
  run, tripping the anti-abuse mechanism on ordinary, expected usage rather than misuse.
- This is the single highest-consequence pitfall in the whole milestone: it silently
  multiplies real Pushd write volume by re-running the exact operation this project just
  spent phases 9-10 building a rate limiter to protect.

**Why it happens:** Content-hash diffing was validated once, on one byte source (local
files never touched by Google's pipeline), and it is tempting to assume "the diff engine
already works" transfers to a second byte source without re-checking. It's the same shape
of mistake the visibility flag pitfall (Phase 10) already taught this project to distrust.

**Prevention:** Run the cheap live spike explicitly, matching the project's own established
pattern, before wiring Google downloads into `compute_plan`:
1. Pick one real photo already on a live Aura frame (known `md5_hash`).
2. Upload that exact file to a Google Photos album (or use one already synced there from
   the same device/backup).
3. Download it back via the Picker/Library API with the `=d` parameter, compute
   `S3Client.get_md5()` on the downloaded bytes, and compare to the frame's `md5_hash`
   directly logged (not via the diff engine — a raw comparison to isolate the variable).
4. If they mismatch (expected, per VERIFIED reports above): the diff engine cannot use
   Google-downloaded-vs-frame-hash comparison as its sole signal. Instead, key sync state
   off Google's own `mediaItem.id` in a **local sync manifest** (a persisted "Google media
   ID → frame asset ID" mapping written after a successful upload), and treat "already
   synced" as "this Google ID is in the manifest and the frame still has that asset,"
   never "does this hash exist on the frame." Content-hash diffing then only detects
   *local-cache* corruption (Pitfall 4), not "is this already on the frame."
5. Gate the entire "Sync album → frame" requirement on this spike's result — it determines
   whether v2.0's diff engine can be reused unchanged (as `PROJECT.md` currently assumes)
   or needs a manifest-based identity layer bolted in front of it.

**Warning signs:** A `sync` dry-run against a Google album that has already been fully
synced once reports "N to upload" for every photo instead of "N unchanged"; frame asset
count grows without bound across repeated runs of the same album; `WriteBudget` depletes
on every run even with no new photos added to the source album.

**Phase to address:** The same Google-mechanism spike phase as Pitfall 1 (cheap, one live
probe, blocks "Sync album → frame" design) — this is the `md5_hash`/hash-format precedent
repeated for a third time in this project's history, and should be treated with the same
seriousness.

---

### Pitfall 3: Treating an empty or partial Google album listing as "the user removed everything" — hide-on-removal mirror semantics turn a transient API failure into a mass-hide event

**What goes wrong:**
Mirror semantics as specified: "the Google album is source of truth... photos removed from
the album are hidden on the frame." The diff engine computes removals as "frame assets
mapped to this album that are no longer in the current listing." If the current listing is
empty or truncated because of *any* transient condition — an expired baseUrl/session causing
a 401/403 mid-list, a Google-side 429 on `mediaItems.list`/Picker pagination, a network
blip, or (per Pitfall 1) an ill-formed Picker session that returns zero items — the diff
engine cannot distinguish "the user genuinely emptied the album" from "the listing failed
partway through." Every mapped photo on the frame would be classified as a removal
candidate and hidden in one `--apply` run. This is the canonical catastrophic failure mode
of every mirror-sync tool (rsync `--delete`, `aws s3 sync --delete`, Google Drive sync
clients all have shipped incidents from exactly this).

**Why it happens:** "Source of truth" mirror logic is naturally written as a set-difference
(`frame_assets_for_album - current_album_items = to_hide`), which is correct only if
`current_album_items` is known to be *complete*. It is easy to plumb a partial/failed
listing straight into that difference without a completeness check, especially because
v2.0's local-directory sync never had this failure mode — a local directory listing either
succeeds outright or the whole CLI invocation errors before `compute_plan` ever runs.
Google's paginated, session-based, rate-limited listing can fail *partway*, a failure mode
the existing diff engine has never had to reason about.

**Prevention (concrete, not aspirational):**
1. **Treat an empty source listing as an error, never as an instruction**, exactly as the
   question specifies. If the Google-side fetch returns zero items for an album that
   previously had N>0 mapped assets, refuse to compute any removal plan for that
   album/frame pair and fail loud with a message naming the discrepancy — do not silently
   proceed with "0 items, so hide N."
2. **Cap removals as a fraction of the mapped set**, mirroring the `WriteBudget`/geo-guard
   posture already established in this codebase (Phase 9's fail-open-but-bounded pattern):
   e.g. refuse to execute a plan whose hide-count exceeds some threshold (a fixed count
   AND/or a percentage, e.g. "more than 50% of previously-mapped assets in one run") without
   an explicit `--force`/exact-count confirmation, the same pattern Phase 10 already uses
   for the destructive-delete tier. This is a direct extension of an existing, already-proven
   safety idiom in this codebase, not a new one.
3. **Require a completeness signal from the fetch itself**, not just "the list call didn't
   throw." For Picker API sessions, only trust `mediaItems.list` as complete once pagination
   is fully drained (`pageToken` exhausted) AND the session's `mediaItemsSet` (or equivalent
   Picker session state) confirms the user's picking action actually completed — don't treat
   a session still in a polling/incomplete state as "zero items picked."
4. **Never let this new mirror-removal path call `exclude_asset` directly from Google-side
   code.** Route it through the same `execute_plan`/hide-classification the v2.0 diff engine
   already uses, so the count-gated confirmation and dry-run-by-default guarantees apply
   uniformly regardless of source (local directory or Google album).

**Warning signs:** A dry-run plan shows a hide-count that equals or nearly equals the total
previously-synced count for an album, especially immediately after any log line indicating
a retry, rate-limit backoff, or partial pagination; the Google fetch step's item count
dropped between two consecutive runs by more than a small delta with no corresponding user
action.

**Phase to address:** The "Mirror semantics" implementation phase — must ship with the
completeness/threshold guard from day one, verified by an offline test that injects a
truncated/empty Google listing and asserts the plan refuses to execute (this is exactly the
kind of test the existing offline `httpx.MockTransport` seam and `compute_plan`/`execute_plan`
split already make cheap to write).

---

### Pitfall 4: Retrying a write on 401 by re-logging in mutates the shared `Client` mid-batch — and can duplicate an upload that actually succeeded

**What goes wrong:** The reliability-pass requirement is explicit: "retry once on HTTP 401
with a fresh login inside `execute_plan`." Two distinct failure shapes hide inside that one
sentence:
1. **Shared mutable client state.** `Client` holds auth headers/cookies as session-level
   mutable state (per `PROJECT.md`'s Architecture notes: "Auth state held inside
   `Client.http2_client.headers` and `.cookies`... session-level mutation after login").
   `execute_plan` iterates a batch of writes reusing one `Client`/`Aura` instance. If item 3
   of 10 in a batch 401s and triggers a re-login, that re-login mutates the *shared* client
   that items 4-10 (and any in-flight retry of item 3) will use next. If the retry logic
   is not carefully scoped (e.g. re-login happens inside a per-item retry wrapper that races
   against the next item's request being built from the pre-re-login headers snapshot), a
   later item can be sent with stale headers, or a concurrent SQS poll for a different
   item can start using half-updated cookies.
2. **Non-idempotent retry on ambiguous failure.** A 401 on `batch_update` (the final
   "confirm upload" call, after `select_asset` → S3 → SQS already ran) is genuinely
   ambiguous: did the write fail before reaching the server, or did it succeed server-side
   and only the *response* was lost to the expired token? Given this project's own measured
   incident — Phase 8's mid-batch token-expiry event, and Phase 10's finding that
   `select_asset` calls that don't complete leave **permanently stuck placeholder rows** —
   a naive "retry the whole `select_asset`→upload→`batch_update` sequence on 401" risks
   creating a *second* placeholder/asset row for the same photo if the first `select_asset`
   actually landed. This directly grows the already-known 58-row stuck-placeholder problem
   instead of shrinking it.
3. **Infinite retry / masked auth failure.** "Retry once" is the right instinct, but if the
   fresh login itself also 401s (e.g. credentials actually invalid, not just token expiry),
   a loose implementation could retry-on-401 recursively inside the same call stack. The
   fix must retry the *operation* at most once per operation, and must distinguish "login
   itself failed" (surface immediately, non-retryable) from "an authenticated call 401'd"
   (retryable once via fresh login).

**Why it happens:** The existing `Client` was designed as a single long-lived session for
one CLI invocation, never as something that needs to be safely re-authenticated *mid-batch*
while other operations may be in flight against it. The retry requirement is new load on an
old assumption.

**Prevention:**
1. Scope the retry narrowly: catch 401 at the single HTTP-call boundary inside `execute_plan`
   (not around the whole batch), re-login synchronously before the *next* attempt of that
   same call, and re-issue only that one call — never the whole multi-step
   `select_asset`→S3→SQS→`batch_update` sequence, and never more than once per call.
2. Before retrying a `select_asset`/upload call specifically, check whether the identity it
   would create already exists (e.g. query for an asset matching the same `local_identifier`
   /content-hash first) — cheap insurance against creating a duplicate placeholder row for
   a call whose first attempt may have silently succeeded.
3. Distinguish "re-login failed" from "re-login succeeded but retried call still 401'd":
   the former is a real credential/auth problem and should fail loud immediately with an
   actionable message (not swallowed as "just another 401"); the latter can fall through to
   the existing fail-loud/continue-past-failure behavior Phase 8 already ships.
4. Decide explicitly whether a retried call consumes a *second* `WriteBudget` token or
   reuses the one already spent for the original attempt — recommend **consuming a second
   token**, because the retry is a second real HTTP request against Pushd's anti-abuse
   surface regardless of client-side bookkeeping; under-counting here is exactly the kind
   of gap that caused the original ~42-request-bucket trip this project measured live.
5. Write this as an offline test first (this codebase's established TDD-via-`MockTransport`
   pattern): inject a transport that 401s once then succeeds, and assert (a) exactly one
   re-login happens, (b) exactly one retried call happens, (c) the `WriteBudget` reflects
   two consumed tokens, (d) a transport that 401s on both the original call and the retry
   surfaces a clear terminal error rather than looping.

**Warning signs:** Duplicate assets appearing on the frame after a run that logged a 401/
retry; the placeholder-row count (already at 58) increasing after a reliability-pass release
that was supposed to *reduce* spurious failures; a hung or very-slow `sync --apply` run
(sign of an unbounded retry loop); `WriteBudget` depleting faster than the number of
user-visible operations would suggest.

**Phase to address:** The reliability-pass phase (Part 1, "Retry once on HTTP 401" —
sequenced first per `PROJECT.md`, and correctly so: this must be solid *before* Google-side
code adds more write volume on top of it).

---

### Pitfall 5: Letting Google-side concurrency (the one place concurrency is explicitly in-scope) leak into the Aura write client

**What goes wrong:** `PROJECT.md`'s Out of Scope section carves a narrow, deliberate
exception: "concurrent downloads on the Google Photos side are in scope... it does not pull
the Aura write client into an async rewrite." The risk is that concurrent Google downloads
and the strictly-sequential, rate-limited Aura upload/hide/delete path get wired together
carelessly — e.g. a naive `asyncio.gather()` over "download from Google, then immediately
upload to Aura" per photo, which would fan out N concurrent Aura writes the moment N Google
downloads finish close together, blowing straight through `WriteBudget`'s token-bucket
pacing (`WRITE_CHUNK_DELAY_SECONDS`) that Phase 9 built specifically to *avoid* bursty
writes.

**Why it happens:** "Download and upload" reads as one pipeline step, and it's natural to
parallelize the whole thing for speed once concurrent downloads are already being built.
The Out-of-Scope note explicitly anticipates this temptation.

**Prevention:** Structurally separate the two phases so the Aura write client cannot be
called from inside the concurrent-download code: download all (or a batched window of)
Google photos into the local cache dir concurrently, complete that phase, *then* hand the
resulting file list to the existing, unmodified, sequential `compute_plan`/`execute_plan`
pipeline exactly as it already runs for local directories today. The concurrency boundary
should be a data handoff (files on disk), not a shared async call graph — this also means
the Aura side needs zero code changes to accept a Google-sourced directory, which is the
whole point of the "reuse the v2.0 pipeline unchanged" decision in `PROJECT.md`.

**Warning signs:** Any `import asyncio`/`await`/concurrent-executor code inside
`auraframes/sync.py`, `auraframes/aura.py`, or anything that calls `execute_plan`/
`WriteBudget`; a live run showing writes clustered in tight bursts rather than the
deliberate pacing `WRITE_CHUNK_DELAY_SECONDS` is supposed to enforce.

**Phase to address:** The "Sync album → frame" implementation phase — enforce via code
review / architecture check (grep for `asyncio` outside a new, isolated Google-download
module) rather than relying on developer discipline alone.

---

### Pitfall 6: The "download → prune after confirm" cache design silently breaks the assumption that the cache mirrors the album

**What goes wrong:** The chosen design downloads Google photos to a local cache dir, reuses
the v2.0 pipeline, then **prunes the cache once uploads confirm**. Several concrete failure
modes fall out of "the cache is deliberately not a stable mirror":
1. **Second-run misread.** If pruning removes a file immediately after its upload confirms,
   a second run against the *same* album (e.g. because the operator re-runs `sync` to check
   status, or a scheduled run fires again before the album changed) sees an empty or
   near-empty cache dir. If the diff engine's identity is (per Pitfall 2's likely fix) keyed
   off a manifest rather than re-deriving from cache contents, this is fine — but if any
   code path still asks "what's in the cache dir" to decide what's already synced, an empty
   cache reads as "nothing synced yet," re-triggering full re-download and (per Pitfall 2)
   potentially full re-upload.
2. **Partial/corrupted downloads hashing to garbage.** A download interrupted mid-stream
   (network blip, process killed) can leave a truncated file on disk. If nothing validates
   the download (size check, or hash against Google's reported metadata if available) before
   it's fed into `compute_plan`, a truncated file gets a real-but-wrong MD5, is diffed as "no
   match on frame," and gets uploaded as corrupt/junk data to the frame — consuming a
   `WriteBudget` token and a permanent frame asset slot for garbage.
3. **Disk exhaustion on large albums.** Downloading a whole album to disk before pruning
   means transient disk usage scales with album size, not with the sync's steady-state need.
   An album with several GB of originals (Google Photos routinely holds this) run on a
   small disk (a Raspberry Pi or similar low-resource host, plausible for a personal
   photo-frame tool) can exhaust disk mid-download, again producing partial files.
4. **Concurrent runs sharing a cache dir.** If two `sync` invocations for different
   album/frame pairs (or an accidental double-invocation of the same one) share one cache
   directory, one run's prune-after-confirm can delete files the other run is still
   mid-diff on, or two runs can write same-named temp files and corrupt each other's
   in-flight download.
5. **Cross-pair cache poisoning in many-to-many runs.** If the cache dir is not scoped
   per album/frame pair, a file downloaded for album A's sync could be present when frame B's
   sync (mapped to a different album) runs its diff, and — if identity is filename-based
   anywhere in the pipeline rather than strictly hash/manifest-based — get attributed to the
   wrong pair.

**Prevention:**
1. Use a per-(album, frame)-pair cache subdirectory, named deterministically (e.g. a hash
   of the album ID), never a single shared cache root.
2. Validate every download before it's eligible for diffing: check the downloaded byte
   count against the `Content-Length` header (or Google's reported file size if exposed),
   and reject/retry on mismatch rather than silently handing a truncated file to the hash
   step.
3. Never let "what's on disk" be the source of "what's already synced" — that's the job of
   the persisted manifest (Pitfall 2's mapping file), which survives pruning by design. The
   cache dir's only job is to hold bytes between download and upload; treat it as fully
   disposable/reconstructable at any point, and write an offline test asserting the plan
   computed from an empty cache + a populated manifest is "nothing to do," not "re-download
   everything."
4. Check available disk space against a rough album-size estimate (or download in bounded
   batches rather than the whole album at once) before starting a large download run; fail
   loud with a clear message rather than filling the disk silently.
5. Use a lockfile or PID-check per cache subdirectory to refuse a second concurrent run
   against the same album/frame pair, consistent with this project's existing "fail loud"
   posture rather than risking silent corruption.

**Warning signs:** A second consecutive `sync` run against an unchanged album reports "N to
upload" instead of "0 unchanged, 0 to upload" (cache-emptiness misread); frame assets that
fail to render/display or have implausible small file sizes (partial download uploaded);
disk-full errors surfacing as a generic exception deep in the download path rather than a
clear pre-flight message; two frames whose mapped albums are different both showing the same
unexpected file in a diff.

**Phase to address:** The "Sync album → frame" cache-and-pipeline-integration phase.
Validation logic (size check, per-pair scoping, lockfile) should ship in the same phase
that introduces the cache dir at all, not deferred — this is exactly the kind of thing that
"looks done" after a single happy-path live test but breaks on the second real-world run.

---

### Pitfall 7: The same photo in two Google albums mapped to two different frames — and re-adding a photo to an album should re-show, not re-upload

**What goes wrong:** Per Pitfall 1's VERIFIED finding, `mediaItem.id` is stable and shared
across albums for the same underlying photo. If a many-to-many config maps Album A → Frame
1 and Album B → Frame 2, and the same photo is in both albums, the sync engine will (almost
certainly correctly, if built on the manifest-based identity from Pitfall 2) try to sync it
to *both* frames independently — which is probably the desired behavior (two different
frames, two independent copies), but the design should say so explicitly, because it means
"one photo synced" is not "one upload" — it can be N uploads for N frames it's mapped to
through overlapping albums, each consuming its own `WriteBudget` token on its own frame's
account-scoped budget. Separately: if a photo is removed from an album (hidden per Pitfall 3)
and later re-added to the same album, the correct behavior — consistent with v2.0's existing
`exclude_asset`/`select_asset` re-show semantics — is to **re-show** the existing frame asset
via `select_asset`, not re-upload a duplicate. This only works automatically if the
persisted manifest (Google media ID → frame asset ID) is retained even for hidden/removed
entries rather than deleted when a photo drops out of the album — deleting the manifest
entry on removal would make a later re-add look like a brand-new photo to sync, re-uploading
a duplicate exactly like the 58 stuck placeholder rows this project already has scars from.

**Prevention:**
1. Keep manifest entries for hidden photos; only remove a manifest entry if the underlying
   frame asset is actually gone (matching the same "hide is reversible, delete is the rare
   opt-in tier" philosophy already shipped in Phase 10).
2. On seeing a Google media ID that has a manifest entry but is classified "already hidden"
   on the frame, and the media ID reappears in a fresh album listing, route it through the
   existing "re-show" (`select_asset`) path — this is a natural extension of Phase 10's
   4-way classifier (re-show / unchanged / removal-candidate / already-hidden), not a new
   mechanism.
3. Make the many-to-many config's overlap behavior an explicit, documented decision (sync
   independently per mapped pair) rather than an emergent side effect discovered in
   production, and size-check `WriteBudget` per account/frame accordingly since overlap
   multiplies write volume.

**Warning signs:** A photo present in two albums shows up as a duplicate-looking "to upload"
on both frames' plans simultaneously (expected, if intentional — but flag it visibly in the
dry-run output so it's not mistaken for a bug); a photo removed and later re-added to an
album triggers "to upload" instead of "to re-show" in the plan.

**Phase to address:** "Mirror semantics" and "Many-to-many mapping" phases — the manifest
persistence-on-hide behavior belongs in Mirror semantics; the cross-pair overlap
documentation/budget-accounting belongs in Many-to-many mapping.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|-----------------|------------------|
| Ship "Discover albums" as "user re-runs the Picker UI each sync" instead of solving headless enumeration | Unblocks the milestone without waiting on Google to restore a scriptable path | Breaks the "unattended, scheduled, many-to-many reconciliation" promise; every sync needs a human at a browser | Acceptable as an explicit v3.0 scope cut, documented in PROJECT.md, not acceptable as a silent implementation detail nobody decided on |
| Key sync identity off content-hash alone (skip the manifest) | Reuses v2.0's diff engine with literally zero new code | Re-uploads every photo forever if Google's download bytes ever differ from what the frame stores (Pitfall 2) | Never, until the live spike in Pitfall 2 proves hash-equality holds — and even then, keep the manifest as the durable source of truth, not just the hash |
| Skip per-pair cache directory scoping for a single-album MVP | Simpler cache path code for the first working demo | Silently breaks the moment a second album/frame pair is added — exactly the "many-to-many" requirement this milestone promises | Acceptable only for an internal spike/prototype never exposed as `--apply`-capable |
| Retry-on-401 without idempotency check before re-`select_asset` | Fast to implement, mirrors the literal requirement text | Grows the 58-stuck-placeholder-row problem this project already has | Never — the idempotency check is cheap (one lookup call) relative to the cost of another permanently stuck row |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|-----------------|-------------------|
| Google Photos Library API | Assuming `albums.list`/`mediaItems.search` still work for a user's pre-existing albums (pre-2025 tutorials/StackOverflow answers) | Verify live against a real, not-app-created album first (Pitfall 1); design around the Picker API's interactive, session-based model |
| Google Photos Picker API | Assuming a picker session can be "reused" or is scriptable/headless | Sessions expire ~24h and require interactive browser selection each time; treat each sync as needing a fresh session unless/until an app-created-album workaround is validated |
| Google Photos download (`=d` param) | Assuming the returned bytes are byte-identical to the originally uploaded file | Spike-verify hash equality first (Pitfall 2); expect GPS EXIF stripping and possible re-encoding; build identity on a persisted media-ID manifest, not hash-matching alone |
| Google OAuth (installed app / loopback) | Leaving the app in "Testing" publishing status for a "set and forget" personal tool | Either move to "Production" (may require Google verification for Photos scopes) or accept and document the 7-day re-auth cadence; never let it silently become a "why did sync stop working a week later" support mystery |
| Google OAuth (installed app / loopback) | Requesting `access_type=offline` without `prompt=consent` on first setup, then wondering why no refresh token comes back on a re-run during development | Use `prompt=consent` explicitly during the linking flow; store the refresh token from that first grant carefully — it may not reappear on a later re-auth without forcing consent again |
| Google OAuth loopback redirect | Hardcoding one local port with no collision handling | `run_local_server()`-style flows hang indefinitely (not fail fast) if the port is already bound (VERIFIED via `google-auth-library-python-oauthlib` issue tracker); pick an ephemeral/configurable port and add an explicit timeout, don't rely on the library's default failure behavior |
| Shared `Client`/`Aura` session (existing) | Re-login inside a retry mutating the same `Client` instance mid-batch write loop | Scope re-login + retry to the single failing call, not the whole batch; see Pitfall 4 |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|-----------------|
| Downloading a whole large Google album to disk before any upload starts | Long pause with no visible progress; disk fills | Bounded-batch downloads (download/upload/prune in windows, not all-at-once) | Albums in the low thousands of high-resolution photos/videos on a small-disk host |
| Fanning out concurrent Google downloads directly into concurrent Aura uploads | `WriteBudget` depletes in a burst; anti-abuse trip on an otherwise normal-sized sync | Hard boundary between concurrent-download phase and sequential-write phase (Pitfall 5) | Any album where concurrent download completion clusters closely in time — likely most albums, since downloads finish near-simultaneously if similarly sized |
| Re-deriving "already synced" from cache-dir contents after pruning | Full re-download + (if Pitfall 2 unmitigated) full re-upload on every run | Manifest-based identity, cache treated as fully disposable | Every run after the first, once pruning is in place |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Committing the Google OAuth client secret or the persisted refresh token to version control | Full read/write access to the user's Google Photos-adjacent OAuth grant if leaked; same class of risk this project already guards against for `AURA_EMAIL`/`AURA_PASSWORD` | Store the refresh token file with restrictive permissions (e.g. `0600`) alongside existing credential handling; add it to `.gitignore` explicitly by name, don't rely on a generic `*.env` rule; treat it with the same posture as Aura credentials per the existing constraint |
| Logging full OAuth tokens or Google API response bodies at `--debug` verbosity | Token leakage via shared debug logs/bug reports, echoing the existing "silent error handling" anti-pattern but now with credential material in scope | Redact tokens/secrets in the loguru sink the same way login headers are presumably handled today; verify explicitly, don't assume the existing redaction (built for Aura auth) automatically covers a new secret shape |
| Treating a 403 from Google (e.g. from the March 2025 scope restriction) as equivalent to "album is empty" | Feeds directly into Pitfall 3 — a permissions error masquerading as "user removed everything" | Distinguish HTTP/gRPC status codes explicitly: 403/401 must be a hard error surfaced to the operator, never silently folded into "zero items" |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-------------------|
| Silent, indefinite hang when the OAuth loopback port is already bound | User thinks the CLI is broken or frozen; no error, no explanation | Fail fast with a clear message naming the port conflict, per the VERIFIED library behavior above — don't rely on the library's default (which hangs) |
| A cryptic `invalid_grant` stack trace surfacing to the terminal | User has no idea whether to re-run, re-auth, or file a bug | Catch `invalid_grant` specifically at the token-refresh boundary and print an actionable message ("Google authorization expired or was revoked — run `aura-cli google login` again"), distinguishing it from a generic network error |
| Reporting "0 photos found" for an album without saying why | User can't tell if the album is genuinely empty, the wrong album was picked, or a permissions/API error occurred | Surface the actual signal: "album returned 0 items — refusing to compute removals; check the album still exists and re-run `google link` if this persists" (ties directly into Pitfall 3's prevention) |
| Video files silently vanishing from a Google album sync | User assumes videos are being backed up and only discovers they aren't when checking the frame | Explicit, unmissable reported count of skipped videos per run (already an explicit requirement — just don't let it regress into a quiet log line) |

## "Looks Done But Isn't" Checklist

- [ ] **Album discovery:** Often looks done after one manual demo run through the Picker
      UI — verify it also handles the "user picks 0 items and clicks Done" case, and that
      a second sync of the same album doesn't require re-authenticating from scratch.
- [ ] **Content-hash diff on Google photos:** Often looks done after one photo matches on
      the first try — verify against a photo that was edited in Google Photos, a video, and
      a RAW/HEIC original, since re-encoding risk (Pitfall 2) is exactly the kind of thing
      that passes on a lucky first sample and fails at scale.
- [ ] **Cache prune-after-confirm:** Often looks done after a single successful `--apply`
      run — verify a *second* run against the same unchanged album reports "0 to upload,"
      not a full re-sync (Pitfall 6).
- [ ] **Retry-on-401:** Often looks done after manually forcing one 401 — verify it does
      NOT create a duplicate placeholder row when the retried call is a `select_asset`, and
      verify a persistently-failing re-login surfaces a clear terminal error rather than
      looping (Pitfall 4).
- [ ] **Mirror hide-on-removal:** Often looks done after removing one photo and seeing it
      hidden — verify the threshold guard actually blocks a plan when the source listing
      comes back empty/truncated (Pitfall 3) — this needs a deliberately-injected failure
      test, not just a happy-path demo.
- [ ] **Many-to-many config:** Often looks done with two non-overlapping albums — verify
      behavior when the same photo is mapped to two frames via overlapping albums (Pitfall 7).
- [ ] **OAuth refresh token persistence:** Often looks done immediately after linking —
      verify it still works 8+ days later if the OAuth consent screen is left in "Testing"
      status (the 7-day expiry is VERIFIED current behavior and will not show up in a
      same-day demo).

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|----------------|------------------|
| Every photo re-uploaded due to hash mismatch (Pitfall 2 realized) | HIGH | Stop the sync immediately; audit the frame for duplicates via inventory diff (same technique already used for `delete_asset` blast-radius measurement); hide (not delete) the duplicates; rebuild identity on the media-ID manifest before resuming any sync |
| Mass-hide from an empty/partial listing (Pitfall 3 realized) | LOW-MEDIUM | Because removal is hide (`exclude_asset`), not delete, recovery is a `select_asset` re-show pass driven by the manifest — this is exactly why hide-by-default (already a v2.0 decision) is the correct posture for the Google integration too |
| Duplicate placeholder row from a retried non-idempotent upload (Pitfall 4 realized) | MEDIUM-HIGH | No known removal mechanism for stuck placeholders (per existing 58-row precedent) — the row is likely permanent; the only real recovery is prevention (idempotency check before retry), so treat any occurrence as a bug to fix immediately, not a state to clean up after |
| Disk exhaustion mid-download (Pitfall 6 realized) | LOW | Clear the cache dir, resume with bounded-batch downloads and a pre-flight disk-space check |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|-------------------|----------------|
| 1. Album discovery mechanism is broken as originally scoped | Google-mechanism spike (before "Link a Google account" is built past the OAuth handshake) | Live probe: `albums.list`/`mediaItems.search` against a real non-app-created album returns 403; Picker session round-trip completed and its UX/re-run cost documented |
| 2. Content-hash identity mismatch on Google downloads | Same Google-mechanism spike phase | Live probe: one photo round-tripped through Google download, MD5-compared directly against the frame's `md5_hash` (not via the diff engine) |
| 3. Empty/partial listing triggers mass-hide | "Mirror semantics" phase | Offline test: inject a truncated/empty Google listing via the mock transport seam, assert the plan refuses to execute past a threshold |
| 4. Retry-on-401 duplicates writes / mutates shared client mid-batch | Reliability-pass phase (Part 1, sequenced first) | Offline test: transport that 401s once then succeeds — assert exactly one re-login, one retry, correct `WriteBudget` accounting, no duplicate `select_asset` |
| 5. Google-side concurrency leaking into the Aura write client | "Sync album → frame" phase | Code-level check (no `asyncio`/concurrent executor reachable from `execute_plan`/`WriteBudget`); live run shows writes still paced by `WRITE_CHUNK_DELAY_SECONDS` |
| 6. Cache prune breaks second-run correctness | "Sync album → frame" cache integration phase | Test: run sync twice against an unchanged album/cache-pruned state, assert second run reports 0 to upload |
| 7. Cross-album overlap / re-add should re-show not re-upload | "Mirror semantics" + "Many-to-many mapping" phases | Test: hide a photo, re-add it to the source album, assert plan classifies it "re-show," not "to upload" |

## Sources

- `PROJECT.md` (this repo, `.planning/PROJECT.md`) — HIGH confidence, authoritative for all
  Pushd/Aura-side codebase claims (validated Key Decisions, Phase 6-10 Context entries).
- Google Developers Blog, "Updates to the Google Photos APIs: Picker API launch and Library
  API changes" — MEDIUM confidence (official, but cross-checked against `developers.google.com`
  reference docs directly, not independently reproduced live yet). Effective 2025-03-31.
- `developers.google.com/photos/library/reference/rest/v1/albums/list`,
  `/photos/overview/authorization`, `/photos/support/updates`,
  `/photos/library/guides/access-media-items`,
  `/photos/library/guides/api-limits-quotas`,
  `/photos/picker/guides/sessions`, `/photos/picker/guides/get-started-picker`,
  `/photos/picker/guides/picking-experience`,
  `/photos/picker/reference/rest/v1/mediaItems` — MEDIUM confidence, official primary source,
  not yet reproduced against a live authenticated call in this project.
- `github.com/googlesamples/google-photos` issue tracker; Google Photos Community support
  threads; `gilesknap/gphotos-sync` README (archived Oct 2024, but a mature purpose-built
  Google Photos backup tool that independently hit and documented the exact
  byte-identity/EXIF-stripping problem this project must avoid) — MEDIUM confidence,
  cross-checked across 3+ independent community sources reporting the same symptom.
- `github.com/googleapis/google-auth-library-python-oauthlib` issue tracker (`run_local_server`
  port-collision hang, redirect_uri trailing-slash mismatch) — MEDIUM confidence, official
  library issue tracker.
- Community/vendor writeups on Google OAuth `invalid_grant` causes and the 7-day
  Testing-mode refresh-token expiry (Nango, Unipile, Truto blog posts; a HomeSeer forum
  thread and Google AdWords API support-group threads independently corroborating the
  7-day behavior) — MEDIUM confidence, cross-checked across 3+ independent sources agreeing
  on the same mechanism.

---
*Pitfalls research for: v3.0 Google Photos Album Sync (Aura Frames Python Client)*
*Researched: 2026-09-03*
