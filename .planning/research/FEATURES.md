# Feature Research

**Domain:** Cloud photo-album → device/frame sync (Google Photos → Aura Frames CLI)
**Researched:** 2026-09-03
**Confidence:** HIGH on Google API mechanics and comparable-tool conventions (multiple independent sources, official docs); MEDIUM on exact UX polish choices (extrapolated from adjacent tools, not user-tested)

## Headline Finding (reshapes everything below)

Google restricted the Photos Library API's broad read scopes on **31 March 2025**
(`photoslibrary`, `photoslibrary.readonly`, `photoslibrary.sharing` all now return
403 `PERMISSION_DENIED` for anything the calling app didn't itself create). This is not
a rumor — it is documented in Google's own migration notes, and it killed or crippled
real tools: **`gphotos-sync` archived its repo** on 2024-10-24 citing the change as
unworkable for a backup tool, and **rclone's Google Photos backend became read-only for
app-created content only**, requiring `rclone config reconnect` and a rewrite around the
new **Picker API**.
[developers.google.com/photos/support/updates](https://developers.google.com/photos/support/updates),
[developers.googleblog.com Picker API launch post](https://developers.googleblog.com/en/google-photos-picker-api-launch-and-library-api-updates/),
[gilesknap/gphotos-sync](https://github.com/gilesknap/gphotos-sync),
[rclone/docs googlephotos.md](https://github.com/rclone/rclone/blob/master/docs/content/googlephotos.md).

The replacement, the **Picker API**, is fundamentally **session-based and interactive**,
not a queryable album handle:

- `sessions.create` → app shows the user a `pickerUri` → user picks in the Google Photos
  app/web UI → app polls `sessions.get` until `mediaItemsSet: true` → app calls
  `mediaItems.list(sessionId=...)` to get the picked items.
  [developers.google.com/photos/picker/guides/sessions](https://developers.google.com/photos/picker/guides/sessions)
- **The picker UI does not expose "albums" as a browsable/pickable unit.** It shows recent
  photos plus a search box; a user can *search* by album title and multi-select the results,
  but there is no "pick this whole album" primitive returned by the API — the API's return
  type is `PickedMediaItem`, a flat list of individually selected media items.
  [developers.google.com/photos/picker/guides/picking-experience](https://developers.google.com/photos/picker/guides/picking-experience)
- **Once a session's picking is done (`Done` tapped), that `pickerUri` is dead.** A brand
  new session + new browser round-trip is required to pick again — there is no
  "reopen and add more" or "re-sync this same selection" mechanism.
  [developers.google.com/photos/picker/reference/rest/v1/sessions](https://developers.google.com/photos/picker/reference/rest/v1/sessions)
- Content access is doubly time-boxed: the **session** has an `expireTime`, and even within
  an active session the **media item `baseUrl` is separately valid for only 60 minutes**
  (shorter if the user revokes access). Media item **IDs** can be stored longer-term, but
  practical re-fetch of content after the session/URL window closes is not a supported,
  documented path. [developers.google.com/photos/picker/guides/media-items](https://developers.google.com/photos/picker/guides/media-items)

**Consequence for this milestone:** there is no world in which `aura-cli` can silently
"check the album for changes" the way `sync <dir>` checks a local directory. Branch (b)
(Picker-only, which all current evidence says is the real branch — see FEASIBILITY notes
in STACK research) requires **a human at a browser for every reconciliation run**, and each
run's "album contents" is only ever what the human just re-selected, not a live queryable
truth. This directly threatens the "N-album→N-frame mapping reconciled in a single
[automated] run" phrasing in PROJECT.md and must be corrected in requirements: "reconciled
in a single **CLI invocation with interactive picking steps**," not "single unattended run."

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete or unsafe.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| `aura-cli google link` (or similar) — OAuth loopback flow | Every comparable tool (rclone, `gcloud auth login`, gphotos-sync) does browser-based OAuth with a local redirect server; users expect "opens a browser, I approve, done" | MEDIUM | rclone runs a local webserver at `127.0.0.1:53682/auth` during `rclone authorize`; `google-auth-oauthlib`'s `InstalledAppFlow.run_local_server()` is the Python-standard equivalent. Persist refresh token like `AURA_EMAIL`/`AURA_PASSWORD` — out of VCS, same posture. |
| `aura-cli status` extended to show Google link state | Existing `status` is the established "is everything healthy" surface (config/auth/frames); users will look there first for Google auth health too, not a separate command | LOW | Wire-up of an existing pattern, not new UX. Show: linked account email, token validity, last successful pick/sync per album mapping. |
| Explicit re-auth / unlink path | Users need a way to fix a broken link (revoked/expired refresh token) without hand-editing files, and a way to disconnect | LOW–MEDIUM | Mirror `gcloud auth application-default revoke` — deletes the local credential, does not touch Google-side grant (user still must revoke in their Google Account settings for a *server-side* revoke). Docs should say this explicitly — "unlink" ≠ "Google forgets this app." |
| Dry-run by default for the Google sync path too | This is the project's single strongest existing convention (`sync <dir>` is dry-run by default, structural not flag-based); a second sync command with different defaults would be a glaring inconsistency | LOW (reuse) | The compute/execute split already exists (`compute_plan`/`execute_plan`) — the new code should produce the *same* plan shape from a different data source, not invent new confirmation semantics. |
| Reported skip count for videos/unsupported media, never silent | PROJECT.md already commits to this; users of any sync tool (rclone, immich-go) expect "N items skipped, see below" rather than a photo silently vanishing | LOW | `immich-go` explicitly reports what it discarded (lower-res duplicates, unsupported types) rather than silently dropping. |
| Per-album/per-frame mapping persisted across runs | Nobody wants to re-type "which album goes to which frame" every invocation; this is exactly what a config file is for | LOW–MEDIUM | Same class of thing as rclone's `rclone.conf` remotes — a named, reusable mapping. Given Picker API's interactive nature, this config must store *frame identity + last-known picked-item-ID set*, not a live "album ID" (no such stable handle exists for a user's own album post-March-2025 restriction). |
| Confirmation before hiding a large batch of photos | v2.0 already gates real deletion behind an exact-count prompt; hiding many photos in one run because of a bad/partial pick session is a plausible failure mode unique to this feature (see Sync Semantics below) | LOW (reuse pattern) | Extend the existing exact-count-gate pattern to "N photos will be hidden this run" — cheap because hide is already the safe default, but a huge N in one run is a new kind of surprising event worth a threshold prompt even in hide mode. |
| Progress bar during download of a large album | `tqdm` is already a dependency and used for batch downloads; album sync will often move far more data than a local-directory sync | LOW (reuse) | Wire the existing `tqdm` usage pattern onto the new Google-side download loop. |
| Disk-space sanity check before bulk download | Standard expectation for any tool that stages large media locally before uploading elsewhere; silent `ENOSPC` mid-run is a known bad experience across every download tool | LOW–MEDIUM | rclone and most backup tools warn/abort rather than fail obscurely mid-transfer; a simple `shutil.disk_usage()` check against estimated album size before starting is enough — no need for a live monitor. |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valuable given this project's stated strengths (safety-first, dry-run discipline, reuse of a proven pipeline).

| Feature | Value Proposition | Complexity | Notes |
|---------|--------------------|------------|-------|
| Plan preview that works *without* a fresh Picker session every time | Most comparable tools force a full re-auth-and-re-pick dance to see "what would change." A cached last-known-picked-item-ID-set lets `aura-cli` show a **diff against the previous pick** as a dry-run, and only prompt for a fresh picker session when the user actually wants to reconcile new album state | MEDIUM | This is a genuine differentiator: it turns an interactive-only API into something that *feels* like a repeatable sync by separating "refresh what I know about the album" (interactive, occasional) from "show/apply the plan" (offline, cheap, dry-run-friendly) — directly aligned with the project's compute/execute philosophy. |
| Reuse of the proven v2.0 content-hash diff/upload engine unchanged | Almost all the risky code (upload round-trip, hide/re-show, rate limiting, geo guard) is already live-verified; wiring a new source into an existing sink is much lower risk than a parallel implementation | LOW (already decided, just execution) | This *is* the project's stated strategy already — call it out as the safety differentiator versus a hypothetical from-scratch Google-native sync. |
| Many-to-many album↔frame mapping in one config, one invocation | Comparable single-purpose tools (rclone remotes, gphotos-sync) are typically one-source-to-one-destination per invocation; reconciling several album→frame pairs in one CLI call with one combined report is more convenient than N separate tool invocations | MEDIUM | Real complexity is in aggregating N interactive pick steps (if Picker-only) into one coherent run report, not in the mapping data structure itself. |
| Clear, itemized "why" for every hide/re-show decision, carried over from v2.0's 4-way classifier | v2.0 already built re-show / unchanged / removal-candidate / already-hidden classification for local-directory sync; extending the same classifier vocabulary to Google-sourced items keeps the mental model identical across both sync sources | LOW (reuse) | Users who already trust `sync <dir>`'s plan output get the same trust for `sync --google` without learning new semantics. |
| Named, resumable local cache with content-hash reuse across albums | If the same photo appears in two synced albums, caching by hash rather than by album means it is downloaded once, not once per album — direct benefit of the "reuse the proven content-hash pipeline" decision | MEDIUM | Requires the cache key to be content-hash (or Google media item ID mapped to hash after first download), not per-album path, to realize this savings. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems — flagged explicitly because PROJECT.md's own semantics choices touch several of these.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|------------------|-------------|
| "Live" auto-syncing album (background watcher, no user action) | Users of consumer sync tools (Dropbox, Google Drive desktop) expect changes to propagate automatically without ever running a command | The Picker API has **no webhook, no change feed, no polling-for-membership-changes primitive** — Google removed exactly the capability (`albums.list`/`albumMediaItems`) that would make this possible for a general app. Building "auto" on top of a manual-pick API means either (a) silently re-showing the picker on a timer, which is not headless at all, or (b) faking liveness with a stale cache, which will surprise users when the frame doesn't reflect an album change they made minutes ago | Be explicit that sync is user-invoked ("run `aura-cli sync --google` to check for changes"), not automatic. Document this loudly — it is the single most likely source of user confusion given how "photo frame sync" reads on the tin. |
| Real deletion as the default removal behavior | "Album is the source of truth" reads to some users as "delete anything not in the album," matching how Google Photos' own web UI trash behaves | PROJECT.md has already correctly rejected this (hide-by-default, deletion opt-in and count-gated) — flagging here only to confirm the decision matches the domain's own hard lessons: v2.0's Phase 8 live incident (a near-empty local dir triggering a 72-item delete plan) is exactly the failure mode a "album is truth, delete the rest" default would reproduce with Google as the source instead of a local dir | Keep hide-as-default; this decision is validated by the project's own history, not just external convention. |
| Streaming Google Photos bytes straight into S3, skipping local disk | Seems more "elegant" / lower-latency than a local cache | PROJECT.md has already rejected this in favor of a pruned local cache — correctly, since it would mean *replacing* the proven v2.0 content-hash pipeline (which hashes local bytes) with a new streaming-hash strategy that has never been live-verified. It would also make interrupted-transfer resumability much harder (no partial file to inspect/resume; a half-streamed S3 object is a different failure mode than a half-downloaded local file) | Local cache dir + reuse of existing pipeline, exactly as decided. Flagging only as confirmation this decision avoids real, observed pitfalls. |
| Enumerating a user's own existing albums via a "simple API call" (`albums.list`) | This is the most natural mental model — "just list my albums like the app does" — and is exactly what pre-2025 tools like `gphotos-sync` did | This scope was revoked for general apps in March 2025; building against it (or against undocumented workarounds) is building on sand — Google has already demonstrated willingness to pull this capability with a hard deadline, and `gphotos-sync`'s maintainers concluded there was no viable path and archived rather than chase it | Design for the Picker-only branch as the default assumption (see STACK research for exact verification); treat any working `albums.list` access as a bonus fallback, not the baseline plan. |
| Full video sync via a fallback hashing mechanism | "Just handle video too, don't leave a gap" is a natural ask once photo sync works | PROJECT.md has already scoped this out correctly: frame-side `md5_hash` is null for all video assets, so the entire content-hash diff engine — the safety mechanism this whole tool is built around — cannot see video at all. A fallback (e.g., local-manifest hashing) is a second, unverified diffing strategy bolted onto a tool whose main strength is one proven strategy | Skip video, report the count, exactly as decided. Revisit only as a distinct future milestone with its own verification pass, not a rider on this one. |
| Silent cache pruning with no re-download warning | "Just clean up after yourself" sounds purely beneficial | Pruning immediately after upload confirmation means the **next run's dry-run/plan step has nothing local to hash against** for items already on the frame — if the plan logic ever needs to re-verify a hash (e.g., after a partial failure, or to build a fresh "what's already there" comparison), it will silently re-download data that was *just* deleted, costing bandwidth and time the user won't expect. This is a real, non-obvious tension in the "download → hash → upload → prune" decision (see Caching section, Q6) | At minimum, document the tradeoff; consider pruning only entries confirmed both uploaded *and* unchanged from a prior successful run, or keep a lightweight hash-only manifest (not the image bytes) after pruning so a future plan step never needs to re-download purely to compute a hash it already knows. |

## Feature Dependencies

```
[Link a Google account (OAuth)]
    └──requires──> [Refresh-token persistence, out of VCS]

[Discover/select album contents]
    └──requires──> [Link a Google account]
    └──conflicts-with──> [Fully unattended/scheduled re-run]
                              (Picker API branch: session requires a live browser
                               interaction; there is no headless re-poll of "current
                               album contents")

[Persisted N-album↔N-frame mapping]
    └──requires──> [Discover/select album contents]  (need something to map, even if
                                                        that "something" is a picked-
                                                        item-ID snapshot, not a live
                                                        album handle)

[Sync album → frame (download+diff+upload)]
    └──requires──> [Persisted N-album↔N-frame mapping]
    └──requires──> [v2.0 content-hash diff/upload engine]   (reused unchanged)
    └──requires──> [Local cache dir with prune-after-confirm]

[Mirror semantics: hide removed-from-album photos]
    └──requires──> [v2.0 hide/re-show 4-way classifier (Phase 10)]   (reused unchanged)
    └──enhances──> [Sync album → frame]

[Photos-only, skip video with reported count]
    └──requires──> [v2.0 md5_hash-based content-hash diffing]        (reused unchanged;
                                                                        video is invisible
                                                                        to it by design)

[Write-path reliability: 401 retry, data_uti fix]
    └──enhances──> [Sync album → frame]   (Google albums routinely contain .png/.heic,
                                            making the data_uti bug load-bearing for the
                                            first time)

["Live" auto-sync, no user action]  ──conflicts-with──> [Picker API's session model]
    (anti-feature; not buildable against the documented API without a fully separate,
     unsupported change-detection mechanism)
```

### Dependency Notes

- **Discover/select album contents conflicts with fully unattended re-run:** this is the
  load-bearing dependency conflict for the whole milestone. If STACK research confirms the
  Picker-only branch (which all current external evidence points to), then "reconciled in a
  single run" must be redefined at the requirements stage as "one CLI invocation that may
  pause for interactive picking steps," not a cron-friendly headless operation. This should
  be resolved as a requirements-writing decision, not deferred further — it changes what
  "many-to-many mapping reconciled in a single run" can honestly promise users.
- **Sync album → frame requires the v2.0 engine unchanged:** this is deliberate and already
  decided (PROJECT.md), and it is the single biggest complexity-reduction available in this
  milestone — almost all the hash-matching, upload, hide/re-show, rate-limit, and geo-guard
  code is already live-proven. New code is confined to: OAuth, the picker/download step, and
  the mapping config. Keep it that way; do not let Google-specific logic leak into
  `compute_plan`/`execute_plan`.
- **Write-path reliability enhances the Google sync feature non-optionally:** the
  `data_uti='public.jpeg'` hardcoding (previously a nice-to-have finding) becomes a real bug
  the moment Google-sourced `.png`/`.heic` files reach the upload path — this is why
  PROJECT.md sequences Part 1 (reliability) before Part 2 (Google integration) rather than
  treating them as independent workstreams.

## MVP Definition

### Launch With (v1 of this milestone)

Minimum viable product for "sync a Google Photos album to a frame" — validates the concept
end-to-end without over-building around an interactive API that may still shift.

- [ ] OAuth loopback link/status/unlink — essential, matches existing credential-handling
      posture, and every dependent feature needs it
- [ ] One album → one frame, single mapping, manually re-triggered each run (interactive
      pick step accepted, not hidden) — essential to prove the mechanism works at all before
      generalizing to N:N
- [ ] Download to local cache, reuse v2.0 diff/upload pipeline unchanged — essential; this
      is the whole point of the milestone's chosen strategy (proven pipeline, new source)
- [ ] Hide-by-default mirror semantics, reusing the Phase 10 classifier — essential; matches
      the project's established safety posture, and building a second removal-semantics
      model would be pure risk with no payoff
- [ ] Skip video, print a count — essential per PROJECT.md's explicit scoping and the
      md5_hash technical constraint
- [ ] Dry-run plan visible before any Google-sourced hide/upload executes — essential,
      matches the project's core convention

### Add After Validation (v1.x)

Features to add once the one-album, one-frame path is proven live.

- [ ] N-album ↔ N-frame persisted mapping, reconciled in one invocation — add once the
      single-pair path's interactive-picking UX is validated; the multi-pair aggregation is
      mostly UX/reporting work layered on a proven mechanism, not new risk
- [ ] Cached last-known-picked-item-ID diff (the differentiator that lets dry-run work
      without a fresh browser round-trip every time) — valuable, but only once the basic
      picked-then-download-then-diff loop is trustworthy on its own
- [ ] Disk-space guard and cache-size reporting — genuinely useful once album sizes in
      practice are known from v1 usage, rather than guessed upfront

### Future Consideration (v2+)

Features to defer until the Picker-only constraint's practical impact is well understood
from real usage.

- [ ] Any workaround for closer-to-live album tracking (e.g., detecting Google's own
      allowlist/verified-app path for broader scopes) — defer; chasing broader API access is
      exactly the trap that made `gphotos-sync` unmaintainable; only worth revisiting if
      Google's policy changes again
- [ ] Video sync via an alternate hashing/manifest strategy — explicitly out of scope per
      PROJECT.md; would need its own verification milestone since it bypasses the tool's
      core safety mechanism (content-hash diffing)

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|----------------------|----------|
| OAuth link/status/unlink | HIGH | MEDIUM | P1 |
| Single album→frame sync via reused v2.0 pipeline | HIGH | LOW–MEDIUM (mostly wiring) | P1 |
| Hide-by-default mirror semantics (reused classifier) | HIGH | LOW (reuse) | P1 |
| Photos-only with reported video skip count | HIGH | LOW | P1 |
| Dry-run plan before Google-sourced execute | HIGH | LOW (reuse pattern) | P1 |
| Write-path reliability (401 retry, `data_uti` fix) | HIGH (blocks correctness of P1 items) | LOW–MEDIUM | P1 (sequenced first per PROJECT.md) |
| N-album↔N-frame mapping, one invocation | MEDIUM–HIGH | MEDIUM | P2 |
| Cached-pick diff (dry-run without fresh browser round-trip) | MEDIUM–HIGH (real differentiator) | MEDIUM | P2 |
| Disk-space guard / cache size reporting | MEDIUM | LOW–MEDIUM | P2 |
| "Live" unattended auto-sync | LOW (given API reality) — HIGH user *expectation* mismatch risk | N/A — not feasible against documented API | Anti-feature, not prioritized |
| Video sync | LOW (explicitly descoped) | HIGH (needs new diff strategy) | P3 / explicitly out of scope |

## Competitor Feature Analysis

| Feature | rclone (Google Photos backend) | gphotos-sync | immich-go | Our Approach |
|---------|-------------------------------|--------------|-----------|--------------|
| Auth | OAuth loopback (`rclone authorize`), shared client ID being retired 2026, recommends own client ID | OAuth (pre-2025 broad scope; now unmaintained/archived) | No live Google API — works from **Takeout export files**, sidestepping the API restriction entirely | OAuth loopback, own client ID from day one (avoid the shared-ID retirement rclone is now dealing with) |
| Album access post-March-2025 | Read-only, **app-created content only**; must reconnect via Picker API for user-library access | Archived — maintainers concluded no viable path under new scopes | N/A (doesn't use the live API at all — Takeout is a static export a user downloads manually) | Picker API, one-time-pick-per-run model; explicitly *not* pursuing `albums.list` |
| "Live" sync | No — user-triggered `rclone sync` runs, idempotent re-run (skips already-transferred files) | Was cron-friendly pre-2025 (incremental sync via `albums.list`); this exact pattern is what the API change killed | No — one-shot import of a point-in-time export | User-triggered `aura-cli sync --google` per mapping; loudly document it is not automatic given Picker's interactive requirement |
| Unsupported media handling | Read-only limitation surfaced as an error/warning during sync | N/A (archived before this mattered much) | Explicitly reports discarded/lower-res duplicates rather than silently dropping | Skip video, print count — never silent, matching immich-go's stated philosophy |
| Credential storage | `rclone.conf`, optional OS keyring integration, config-file encryption option | Local token file | N/A | Match existing project posture (env-var-adjacent, out of VCS); consider keyring as a stretch, not a blocker |

## Sources

- Google Photos API policy change (authoritative): [developers.google.com/photos/support/updates](https://developers.google.com/photos/support/updates), [Google Developers Blog — Picker API launch and Library API changes](https://developers.googleblog.com/en/google-photos-picker-api-launch-and-library-api-updates/)
- Picker API mechanics: [Get started with the Picker API](https://developers.google.com/photos/picker/guides/get-started-picker), [Create and manage sessions](https://developers.google.com/photos/picker/guides/sessions), [Photo picking: what users see](https://developers.google.com/photos/picker/guides/picking-experience), [List and retrieve media items](https://developers.google.com/photos/picker/guides/media-items), [sessions REST resource](https://developers.google.com/photos/picker/reference/rest/v1/sessions)
- `gphotos-sync` — archived due to March 2025 scope change: [github.com/gilesknap/gphotos-sync](https://github.com/gilesknap/gphotos-sync)
- rclone Google Photos backend, post-2025 limitations, OAuth loopback UX: [rclone.org/googlephotos](https://rclone.org/googlephotos/), [rclone forum — Add the new Google Photos Picker API to rclone](https://forum.rclone.org/t/add-the-new-google-photos-picker-api-to-rclone/47938), [rclone forum — Google photo picker](https://forum.rclone.org/t/google-photo-picker/52944)
- `immich-go` — Takeout-based workaround approach and unsupported-media reporting philosophy: [github.com/simulot/immich-go](https://github.com/simulot/immich-go)
- `gcloud auth login`/ADC as a comparable CLI OAuth link/status/revoke UX pattern: [Google Cloud — Set up ADC for local development](https://docs.cloud.google.com/docs/authentication/set-up-adc-local-dev-environment), [Best practices for mitigating compromised OAuth tokens](https://docs.cloud.google.com/architecture/bps-for-mitigating-gcloud-oauth-tokens)
- Resumable/idempotent sync conventions: general cloud-sync-tool re-run behavior (rclone compare-before-transfer model), corroborated across rclone documentation and forum discussion
- Project context: `/home/fabrice/dev/auraframes/.planning/PROJECT.md` (v3.0 milestone scope, existing v2.0 capabilities, key decisions)

---
*Feature research for: Google Photos album → Aura Frame sync (v3.0 milestone)*
*Researched: 2026-09-03*
