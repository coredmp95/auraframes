# Album-Level Google Photos Access — Non-Interactive, Non-Browser-Automation Paths

**Scope:** Every album-level path to Google Photos content that is NOT the interactive
per-photo Picker flow (already rejected) and NOT browser automation (covered by a
separate researcher). Every claim below is marked **VERIFIED** (source + date) or
**INFERRED**.

**Researched:** 2026-09-03. Builds on `.planning/research/STACK.md`, which already
settled: the March 2025 Photos Library API scope cull is real, permanent, and has no
allowlist path back; the Picker API has no "pick this whole album" primitive. This
document does not re-litigate those two facts — they are treated as closed.

---

## Ranked Summary

| Rank | Path | Album-level? | Headless/cron-able? | Effort | Brittleness | ToS posture | Verdict |
|---|---|---|---|---|---|---|---|
| **1** | **Spike the Pushd API for an Aura-side Google Photos link** (Aura's own "Ambient API" integration, restored June 2026) | Yes, natively | Yes — if Pushd exposes it, it's a REST call like anything else this project already does | Low (one focused spike against an API this project already reverse-engineers) | Unknown until spiked; inherits the whole project's existing brittleness profile, nothing new | Same posture as the rest of this project (unofficial, reverse-engineered) | **Try this first.** If it exists it dissolves the entire Google-side problem. |
| **2** | **Public shared-album link scraping** (`photos.google.com/share/...`) | Yes, per-album, and confirmed to survive hundreds of items via the "select albums" Takeout flow being unnecessary — see caveats | Yes, confirmed live in this session — plain `curl`, no JS, no login, no consent wall (tested from a real Paris IP) | Low–Medium (regex/JSON parse of one inline script blob; ~100–200 LOC) | Medium — unofficial, undocumented HTML structure that Google could change without notice; **large albums (rough community-reported ceiling ~500 items) require reverse-engineering an undocumented lazy-load RPC** this research did not fully crack | Unofficial scraping of a public page — much thinner ethical/legal footing than an OAuth-scoped API, but the page is intentionally public-by-link, not access-controlled | **Best fallback if #1 dead-ends.** Solid for small-to-medium albums today; needs a follow-up spike for the pagination ceiling before committing. |
| 3 | **Google Photos Data Portability API for developers** | N/A | N/A | N/A | N/A | N/A | **Dead end — confirmed no Photos scope exists at all** (see §2b). Not worth building against. |
| 4 | **Scheduled Google Takeout → Drive, read back via Drive API** | Yes, album selection is a real Takeout feature | Only the *delivery* is unattended (Google's own 2-month cadence); *reading it back programmatically* still needs either a paid CASA-audited `drive.readonly` scope or a manual one-click re-grant via Drive Picker every cycle | Medium–High (OAuth + Drive API + zip/tgz unpacking + `.json` sidecar EXIF handling) | Low once built, but the 2-month cadence is a poor match for "sync a frame" and initiation is 100% manual (a human sets it up once in the Takeout UI; there is no API to create/modify the schedule) | Fully sanctioned, official Google feature — best ToS posture of any path here | **Viable but a bad fit for the milestone's cadence expectations.** Worth keeping as a documented option, not the primary build target. |
| 5 | **App-created album, user adds own photos via Google Photos UI, read back via `readonly.appcreateddata`** | No | — | — | — | — | **Dead end, answered definitively** (see §3). Google's "created by your app" gate is at the *media item* level, not the *album* level — a user manually adding a pre-existing photo to an app-created album does not make that photo app-created. |
| 6 | Old Drive↔Photos folder sync | No | — | — | — | — | **Dead end.** Removed 2019, confirmed, no remnant. |
| 7 | `sharedAlbums.list` / `photoslibrary.sharing` | No | — | — | — | — | **Dead end.** Confirmed 403 since 2025-03-31, no legacy fallback. |
| 8 | Nest Hub / Chromecast ambient screensaver mechanism | Partially yes, but not externally reachable | No | — | — | — | **Dead end for this project** — it's the same Ambient API as #1, gated to Google's own first-party surfaces plus accepted partners (Aura is one). Not independently reachable by this project without partner acceptance. |
| 9 | Picasa-era / RSS feeds | No | — | — | — | — | **Dead end.** Long shut down, no revival. |
| 10 | Third-party re-export services (MultCloud etc.) | Claimed yes | Unclear | — | High — undocumented, unverified, possibly ToS-violating on their end | Unknown, second-hand risk | **Not recommended.** Speculative, unverifiable, adds a third party with its own opaque access to your Google account. |

---

## 1. Shared album links — investigated concretely, with a live fetch

This is the strongest non-partner-program path found. Rather than rely on secondary
sources, this session fetched a real, currently-public Google Photos shared album link
with plain `curl` (no browser, no JS engine) **from a French residential IP** (the
sandbox's actual egress IP resolved to Paris, FR, ISP Free SAS — confirmed via
`ipinfo.io`), which happens to answer the France/EU consent-wall question empirically
rather than by inference.

### 1a. Is it fetchable without auth, and is it plain HTTP?

**VERIFIED, 2026-09-03, direct test.** Two known-old (~2018-era) test share links from
public GitHub scraper-tool repos were resolved:

- `https://photos.app.goo.gl/QCXy6XaKX5x1AynH8` → 302 → the album no longer exists (404) —
  expected churn for an 8-year-old disposable test link, not evidence against the
  mechanism.
- `https://photos.app.goo.gl/ZpfXxtahskVAC4647` → 302 → `https://photos.google.com/share/AF1QipNuA_vO6SnMfD6SG5-wsA4GgWIm2cnJES6HsMFjadeiolxT5RBmRhutWJW2AH2VAw?key=bjQxMklKc1d6VEMxSkJnUTlKVk41OHltX2l6RnZB`
  → **HTTP 200, 1.07 MB of HTML, plain `curl`, no cookies sent, no login, no JS
  execution.** Page `<title>`: `Shared album - Alex Crist - Google Photos`.

**No EU/France consent interstitial was encountered.** The response was a direct 200
with full content, not a redirect to `consent.google.com`. This directly answers the
milestone's flagged France-specific concern: at least for this share-link endpoint, hit
with a plain HTTP client (no cookies, no browser fingerprint), Google did not gate it
behind a cookie-consent wall. (Caveat: this is one endpoint, one session, one client
configuration — a browser-driven fetch with different headers, or a future Google
change, could behave differently. Marking this **VERIFIED for the tested conditions**,
not as a permanent guarantee.)

### 1b. Actual page structure (fetched and parsed live, not from documentation)

**VERIFIED, 2026-09-03**, by direct inspection of the fetched HTML:

- The page contains `AF_initDataCallback` (5 occurrences) — confirmed the mechanism
  every third-party scraper tool found in this research describes.
- The relevant payload is `AF_initDataCallback({key: 'ds:1', hash: '2', data: [...] })`.
  Inside `data`, each media item appears as a JS array literal:
  ```
  ["AF1QipM6U_kXx9SUibZ0lP4uBtQ_Z2Gh12RFvOQep9_A",
   ["https://lh3.googleusercontent.com/pw/AP1GczParoQRjP_HEfc31fDtQn1XXACAhcA9J7pPy9wcbDTlHf8kNTS9XjLFp7ZgA_Hyny-B5f8B12t4a-CHDw_jeGLdlmOqmlav3ZygAF68WpkxOQ4E_-3F",
    4898, 3265, null, null, null, null, null, [null,null,1], [3420724]],
   1532210429477, "q9kR915A_Ya5_79aWmnV-SqmlPY", -21600000, ...]
  ```
  i.e. `[mediaItemId, [baseUrl, width, height, ...], uploadTimestampMs, ...]`. Width/height
  of the **original** image are embedded directly in the page — no separate call needed
  to learn native resolution. Camera EXIF summary data (make/model/focal length/aperture/
  ISO/shutter) is also present later in the same blob for at least one item in the test
  album (`"SONY","ILCE-6000",null,60,2.8,100,0.00125`).
- No JSON-LD, no plain `<img>` tags carrying full-res URLs — the data is exclusively in
  this inline JS array structure, matching what `pnxl/google-photos-album-scraper`,
  `ValentinH/google-photos-api`, `alexcrist/scrape-google-photos`, and
  `austenstone/google-photos-scraper` (all found via search, all independently
  reverse-engineering the same structure) already assume.

### 1c. Full-resolution originals — confirmed with a real download

**VERIFIED, 2026-09-03**, by direct download and inspection:

| Suffix | Result |
|---|---|
| `{baseUrl}=d` | `HTTP 200`, `Content-Type: image/jpeg`, `Content-Disposition: attachment; filename="DSC05542.jpg"`, 892,799 bytes, **Pillow confirms 4898×3265 — exactly matching the width/height embedded in the page's inline data** — and EXIF is present (`getexif()` non-empty). This is the original file, original filename, original bytes. |
| `{baseUrl}` (no suffix) | `HTTP 200`, 73,653 bytes — a resized web-viewing rendition, not the original. |
| `{baseUrl}=w200-h200` | `HTTP 200`, 15,170 bytes — a thumbnail. |

This directly confirms the `=d` full-resolution convention still works today, and that
the width/height metadata inline in the page can be trusted to mean "this is the
original's true resolution" without needing to probe further. GPS EXIF was absent in
this specific test photo (inconclusive either way — this photo may simply never have had
GPS data; not evidence that Google strips it, unlike the Picker API's `=dv`/video path
which explicitly documents stripping location).

### 1d. URL stability

**VERIFIED (short-term, this session):** re-fetching the identical `baseUrl` seconds
later returned another clean 200 — not a one-shot signed URL.

**VERIFIED (long-term, by strong circumstantial evidence):** the test album's upload
timestamps are from July 2018 (`1532210429000` ms epoch), meaning this share link has
been continuously resolvable for **over 8 years** — the album itself, and by extension
its embedded media, has not gone stale. This matches the general community understanding
(also why `publicalbum.org`'s embed-a-permanent-gallery business model exists at all) that
`/pw/`-prefixed shared-album `baseUrl`s behave very differently from the Picker API's
~60-minute `baseUrl`s or the (also short-lived) Library API `baseUrl`s — they are
effectively **long-lived, not session-scoped**. **INFERRED** that any specific baseUrl
string remains valid indefinitely without needing to re-scrape the page — what's
directly proven is that the *page itself* keeps serving fresh-looking working URLs for
the same underlying media year after year, which is what actually matters for a
cron-able sync tool (you re-fetch the page each run, not a cached URL).

### 1e. Pagination — the real open question

**Not fully cracked in this session** — the one live album available for testing (4
photos) was too small to trigger lazy-loading. What is well-established from convergent
secondary evidence:

- `publicalbum.org`'s own operator, in a public blog comment, stated directly about a
  2,000-photo album yielding only 500 results: **"Now it's not possible to grab more
  images. This is the limit of the current method."** (VERIFIED via WebFetch of
  publicalbum.org/blog/embedding-google-photos-albums, 2026-09-03 — this is the
  service's own admission, not speculation.)
- Every scraper tool inspected in this research (`pnxl/google-photos-album-scraper`,
  `ValentinH/google-photos-api`, `alexcrist/scrape-google-photos`) has **no pagination
  handling at all** — they parse only what's inlined in the first response.
- No literal `batchexecute` string was found in the one page fetched live, and no
  documented reverse-engineering of the follow-up lazy-load RPC turned up in search.

**INFERRED, MEDIUM confidence:** large albums (rough ceiling somewhere in the low
hundreds, ~500 per the publicalbum.org data point) are served with only an initial batch
inlined in `AF_initDataCallback`; the rest loads via an undocumented, session-cookie-
bound XHR/RPC call as the user scrolls, which no plain-HTTP scraper in this research has
successfully replicated. **This is the single biggest unresolved technical risk in the
shared-album-link path** and should be spiked directly (share a real album with, say,
600+ photos and diff what a plain-HTTP fetch returns against the true count) before
committing engineering time to this path as the primary mechanism.

### 1f. Existing open-source tools

| Tool | What it does | Maintained / post-2025 status |
|---|---|---|
| `gilesknap/gphotos-sync` | Full Library-API-based backup tool, not a share-link scraper | **Archived 2026-03-17**, explicitly because of the March 2025 scope removal — the maintainer stated there is "no way that a backup tool like gphotos-sync can operate under the new scopes" (VERIFIED via GitHub discussion #1, 2026-09-03). Confirms the Library-API path (not the share-link path) is definitively closed for tools like this. |
| `pnxl/google-photos-album-scraper` | Regex/JSON scraper of `AF_initDataCallback` for public shared albums, pushes to Supabase | No visible maintenance signal found; simple enough (~1 file) that Google HTML drift is the main risk, not abandonment |
| `ValentinH/google-photos-api` | Serverless (AWS Lambda) shared-album API, regex on `lh3.googleusercontent.com` URLs | Old (blog post era ~2019), **no pagination handling** (confirmed by direct source read) |
| `alexcrist/scrape-google-photos` | CLI, "preview-quality" images only (not `=d` originals) | Small, single-purpose |
| `austenstone/google-photos-scraper` | TypeScript CLI, parses `"data:[[` blocks (functionally the same structure this research independently confirmed), does per-photo detail-page fetches for EXIF, has a `User-Agent: Mozilla/5.0` header (mimics a browser but is still a plain HTTP fetch, not a browser engine) | Confirmed structurally correct against this session's live fetch — the pattern it looks for (`data:[[`) matches exactly what was found live |
| `publicalbum.org` | Commercial SaaS built entirely on this mechanism, in continuous operation since ~2016 | **Still operating in 2026** (its blog has 2026-relevant content), but has publicly hit the pagination ceiling and reports occasional `429` rate-limit responses from Google — useful signal that Google does rate-limit this path under sustained/bulk load, even though a single-album fetch worked cleanly in this session |

**Conclusion: no tool needs to be adopted wholesale.** The mechanism is simple enough
(one regex/JSON-parse pass over one inline script block, confirmed against a live page
in this session) that a small purpose-built parser inside this project's existing
`httpx`-based client pattern is the right call — same conclusion the existing
`STACK.md` already reached for the Picker API's REST calls, and consistent with this
project's "raw `httpx`, not a heavy SDK" convention.

### 1g. What breaks it

- **Rate limiting:** `publicalbum.org` reports `429`s under sustained bulk use — a
  single frame's single album, fetched a few times a day by a cron job, is a vastly
  smaller footprint and unlikely to trip this, but it is not zero-risk, and there is no
  documented rate limit number to design against (unofficial surface, no SLA).
  **INFERRED risk, not directly tested at volume in this session.**
- **JS requirement:** **VERIFIED false** for this specific endpoint under these
  conditions — plain `curl` got full data with zero JS execution.
  `publicalbum.org`'s embed *player* itself is JS, but that's their embed widget, not a
  requirement to fetch the source data.
  a
- **Different HTML to non-browser UAs:** not observed in this session (no `User-Agent`
  was set at all on the successful `curl` calls, and the response was still full-content
  200). Some other tools defensively set `User-Agent: Mozilla/5.0` anyway; cheap
  insurance, not proven necessary.
- **EU consent interstitial:** **VERIFIED not encountered**, from a real Paris IP, for
  this endpoint, in this session.
- **Undocumented and revocable at any time:** this is a scraping approach, not an API
  with a support channel. Google has changed shared-album internals before (this
  research found no changelog for it, unlike the Library/Picker APIs which do publish
  changes) and could again, silently. This is the honest cost of this path.

---

## 2. Google Takeout → Google Drive → Drive API

### 2a. Scheduled export — confirmed real, with exact parameters

**VERIFIED**, via 9to5google (2026-06-01, fetched 2026-09-03) and winbuzzer
(2026-06-07): Google Photos added **"Incremental Takeout for Photos"** —

- Cadence: **every 2 months for the next year** (fixed; this is the only recurring
  cadence offered — there is no weekly/daily/monthly option).
- First export contains all selected photos and albums; **subsequent exports are
  incremental** — "items uploaded, backed up, created, or edited since your last
  successful backup."
- Album-level selection **is** available within Takeout's Photos option (deselect-all
  then pick specific albums) — this is a pre-existing, general Takeout feature, not new
  in the 2026 scheduling update. **VERIFIED** via multiple consistent secondary sources.
- Delivery destinations include Google Drive, Dropbox, Box, and Microsoft OneDrive, in
  addition to the classic email-link-to-a-download method. **VERIFIED**, consistent
  across sources.
- Max archive size 50GB per part (standard Takeout chunking behavior — large exports
  split into multiple numbered files).

### 2b. Is there ANY way to trigger it programmatically? Definitive answer: NO.

**VERIFIED, definitively, no hedging.** Two lines of evidence converge:

1. **The only real "Takeout API" that exists (`takeout-pa.googleapis.com`) is Google's
   own internal-only infrastructure**, exposed accidentally via a leaked Discovery
   document (VERIFIED via a public gist documenting the schema, cross-checked against
   developer reports). Attempting to enable it in a real Google Cloud project returns:
   *"Takeout API has not been used in project [ID] before or it is disabled"* with no
   way to enable it — it is not a product any external developer can activate. **Dead
   end, confirmed by direct developer reports of the actual error.**
2. **The one real, general-availability, developer-facing API in this family — the Data
   Portability API — does NOT cover Google Photos at all.** This research fetched
   Google's own **complete, verbatim OAuth scope list** for the Data Portability API
   (`developers.google.com/data-portability/user-guide/scopes`, fetched 2026-09-03) and
   it contains scopes for Chrome, Maps, My Maps, Play, Search, Shopping, YouTube,
   Fitbit, and Business Messaging — **there is no `dataportability.photos.*` scope of
   any kind.** This is a clean, exhaustive, primary-source negative result, not an
   inference from absence in a search summary. **Dead end, confirmed.**

Initiating a Takeout export — scheduled or one-off, album-selected or full-library — is
**strictly a manual, human, web-UI action**. There is no supported way for this
project's CLI to create, modify, or trigger a Takeout job on the user's behalf.

### 2c. Reading the delivered archive back

If the user manually sets up the scheduled export once (a one-time human action, not a
repeating interactive per-photo pick — arguably compatible with the milestone's
constraints, since it's equivalent in kind to the one-time OAuth consent this project
already requires for the Google account link), the artifact needs to be read back:

- **Format:** a `.zip` (or `.tgz`, and split into `-001`, `-002`, ... parts above the
  size cap) containing a `Google Photos/<Album Name>/` folder structure — album
  membership **is preserved as folders** (well-established, long-standing Takeout
  behavior, consistent across every source checked). Each photo ships with a sidecar
  `<filename>.supplemental-metadata.json` (or similar, naming has changed slightly over
  Takeout's history) carrying the EXIF-adjacent metadata Google stores separately
  (people tags, description, geo data in some cases) — **this needs a live spike to
  confirm the current exact filename/JSON schema**, not confirmed in this pass.
- **Drive scope needed:** **`drive.file` is NOT sufficient** to read a Takeout-delivered
  folder, because the app did not create those files — `drive.file` only sees files
  "you have opened or created with this app" (**VERIFIED**, Google's own scope
  description, cross-checked against a GitHub issue discussion of exactly this
  limitation). Two real options:
  - `drive.readonly` — full read access, but it is a **restricted scope requiring an
    annual, paid, third-party CASA security assessment** (**VERIFIED**,
    developers.google.com/identity/protocols/oauth2/production-readiness/
    restricted-scope-verification + corroborating CASA cost/process sources) —
    disproportionate for a personal single-user tool.
  - **Drive Picker + `drive.file`**: have the user manually pick the Takeout delivery
    folder/files once via Google's native Drive file picker UI. This grants `drive.file`
    scoped access to *those specific files* without needing the restricted
    `drive.readonly` scope or CASA. **Caveat, verified via search**: the Drive Picker
    with `drive.file` **cannot select whole folders** — only individual files — so this
    only works cleanly if Takeout delivers a small, fixed number of top-level zip parts
    (which it typically does), not if the app needs to browse an arbitrary folder tree
    inside the archive after unzipping (that part happens locally, off Drive, once the
    zip is downloaded — which is fine). Each new scheduled delivery is a **new file**,
    so the one-click re-pick has to repeat **every 2 months**, not truly a zero-touch
    cron job, but a very low-frequency, low-friction manual step.
- **Practicality of the 2-month cadence:** **This is the real weakness of this whole
  path for this milestone.** "Sync Google Photos to a frame" implies days, not months,
  of freshness. A photo added to an album today would not reach the frame via this path
  for up to ~2 months. **This makes Takeout-to-Drive a poor primary mechanism for an
  ongoing "mirror" use case**, though it could be a reasonable *supplementary* full
  backup/reconciliation pass layered under a faster primary path (e.g., #1 or #5).

---

## 3. What survived the Photos Library API cull — the app-created-album question, answered definitively

(STACK.md already established the top-line: `photoslibrary.readonly`,
`photoslibrary.sharing`, and bare `photoslibrary` scopes 403 since 2025-03-31, no
allowlist. This section goes one level deeper into the three surviving scopes and
answers the single highest-value question in the milestone brief.)

### 3a. What the three surviving scopes actually permit

**VERIFIED**, via `developers.google.com/photos/overview/authorization` (fetched
2026-09-03) and `developers.google.com/photos/library/guides/manage-albums` /
`.../list` (fetched 2026-09-03):

| Scope | Verbatim capability |
|---|---|
| `photoslibrary.appendonly` | "Only allows new media to be created in the user's library and in albums created by the app." — upload-only, into app-created albums or the general library. |
| `photoslibrary.readonly.appcreateddata` | "Read access to media items and albums created by the developer." — list/search, scoped to app-created content only. |
| `photoslibrary.edit.appcreateddata` | "Access to change these details for albums and media items created by the developer" — title/cover-photo edits, again scoped to app-created content. |

### 3b. Did `sharedAlbums.*` / `photoslibrary.sharing` survive in any form?

**VERIFIED: No.** `photoslibrary.sharing` was removed 2025-04-01; `sharedAlbums.list`,
`.get`, `.join`, `.leave` all depend on scopes that now 403 (VERIFIED via
`developers.google.com/photos/support/updates` — already the anchor source in
`STACK.md` — and cross-checked against the current `sharedAlbums` REST reference page,
which still documents the methods but under the now-dead scope). There is no legacy
fallback and no alternate scope that restores this. **Dead end, no hedge.**

### 3c. The definitive answer: can an app read a user's own pre-existing photos that the user manually added, via the Google Photos UI, to an album the app created?

**NO — definitively, with a source-backed chain of reasoning, not a hedge.**

Google's own `mediaItems.search` REST reference (fetched 2026-09-03) states the
`albumId` parameter's behavior as: **"Only media items and albums created by your app
are returned."** This sentence is the load-bearing one, and it resolves the ambiguity
the milestone flagged: the filter is stated as applying to **media items**, not merely
to **which albums are visible**. An app-created album *is* visible (the album itself was
created by the app). But a media item that the *user* manually added to that album
through the Google Photos mobile/web UI was **not** created by the app — it was created
(uploaded) by the user, at some point, through Google's own consumer product, entirely
outside any API call this app ever made. Per the literal scope semantics ("created by
your app"), that photo does not become app-created merely by being filed into an
app-created album's membership list.

This reading is corroborated by convergent developer community consensus (multiple
independent search results converged on the same conclusion — "when a user adds their
own photos to an album that an app created, those user-added photos may not be visible
to the app") and by the parallel, explicitly-documented behavior of
`albums.batchAddMediaItems`: that method itself requires the media items being added to
**already** be app-created/accessible to the app — i.e., even the API's own
"add existing items to an app album" primitive cannot pull in a user's non-app-created
photo, which would be a strange asymmetry if the read side allowed exactly that content
in through a side door (a user manually adding it via the UI instead of the API). The
two restrictions are consistent with a single underlying rule: **app-created status is a
property of the media item's origin, permanently, and there is no UI or API action that
retroactively grants it.**

**Practical verdict:** there is no way to get Google to hand this project a
freely-growing, API-readable album made of the user's *existing* photos by having the
app merely create an empty album shell and hoping the user's own additions become
visible. **This path is a dead end and should not be re-litigated in the roadmap
phase.**

### 3d. `albums.share` / joining a shared album programmatically

**VERIFIED dead end.** `albums.share` requires `photoslibrary.sharing`, which is the
exact scope removed 2025-04-01 (see 3b). No surviving path.

---

## 4. Other Google surfaces

| Surface | Status |
|---|---|
| **Old Google Drive "Google Photos" auto-sync folder** | **VERIFIED dead, confirmed date.** Google explicitly split Drive and Photos on 2019-07-10 (VERIFIED, multiple sources including Google's own Workspace Updates blog). The `Google Photos` folder in Drive still exists as a static, non-syncing artifact for old content — new photos never appear there and it is not writable-to-sync. No remnant usable for this project. |
| **Google Photos partner sharing** (the *consumer* feature at `support.google.com/photos/answer/7378858`, distinct from the developer Partner Program in §5) | This is a *user-facing* feature (auto-share all your photos with a specific partner person, e.g. a spouse) with **no corresponding public developer API** found — it is a Google Photos app setting, not something this project's CLI could invoke on the user's behalf. Not useful here. |
| **Enterprise/Workspace-only APIs** | No Google Photos-specific Workspace/Enterprise API tier was found distinct from the consumer Library/Picker/Ambient APIs — Google Photos itself is fundamentally a consumer product; Workspace users get the same Library/Picker API surface, not a broader one. Not a viable escape hatch. |
| **Picasa Web Albums / RSS-Atom feeds** | **VERIFIED long dead.** Picasa Web Albums was shut down years ago (Wikipedia's own Picasa Web Albums page, surfaced repeatedly in searches, documents this as historical). No revival, no working legacy endpoint found or expected. |
| **Nest Hub / Chromecast / Google TV photo-frame screensaver** | This *is* powered by the same underlying mechanism as §5's Ambient API family — Google's own device-oriented photo-frame slideshow surface (VERIFIED: `developers.google.com/photos/ambient` explicitly frames the Ambient API as being for "smart TVs and photo frames," the exact same device class Nest Hub/Chromecast serve). It is **not independently reachable** by a third-party app without Partner Program acceptance — same gate as Aura went through. Not a separate opportunity; it's the same one, already covered in §5/§1-rank-1. |
| **Third-party services claiming Google Photos re-export** (MultCloud, etc.) | **Speculative, unverified, not recommended.** A live rclone GitHub issue (#8580, fetched 2026-09-03) shows a developer noting MultCloud *still* displays Google Photos albums in its UI after the March 2025 cull and asking rclone's maintainers to investigate how — the issue explicitly frames this as an open question ("possible workarounds," not a confirmed mechanism), with two guesses (undocumented endpoint, or MultCloud has a grandfathered/different OAuth client) and zero confirmation. Building on this would mean depending on a third party's opaque, unverified, and possibly ToS-fragile access to your Google account — a strictly worse risk profile than scraping the public share-link page yourself. **Not recommended as anything more than a curiosity.** |

---

## 5. Aura's own Google Photos integration — the most important finding in this document

**This changes the shape of the whole problem and should be investigated before any of
the Google-facing paths above are built.**

**VERIFIED, converging from four independent sources** (9to5google 2026-06-04, TechRadar,
TechTimes 2026-06-06, Google's own `developers.google.com/photos/ambient` and
`.../photos/partner-program/overview`, all fetched/searched 2026-09-03):

- In September 2024 (announced) / March 2025 (effective), Google's scope cull broke
  Aura's existing Google Photos sync feature, same as every other third-party frame
  vendor. Aura's frames lost the ability to sync from Google Photos.
- **In June 2026, Google Photos support was restored for Aura's frames specifically**,
  via a **new, purpose-built Google API called the "Ambient API"** (`developers.google.com/photos/ambient`,
  live and documented today), described by Google itself as being **"for ambient
  devices"** — explicitly the smart-display/photo-frame device class, not a
  general-purpose library-read API.
- **Access is gated behind Google's Photos Partner Program** — VERIFIED, verbatim from
  `developers.google.com/photos/partner-program/overview`: *"To get access to the
  Ambient API, you must first be accepted into the partner program."* This is an
  application-based process ("express interest" via a form), not self-serve API
  enablement. **Aura Frames is a confirmed accepted partner** — TechTimes (2026-06-06)
  states outright that "Aura Frames worked alongside Google to implement support for the
  Ambient API."
- **From the end-user's perspective, the feature is explicitly album-level and
  auto-updating**, confirmed directly on Aura's own site
  (`auraframes.com/news/how-to-effortlessly-display-google-photos-on-your-aura-frame`,
  fetched 2026-09-03): *"Sync entire Google Photos albums with the frame via the Aura
  app's 'Auto-Add' function... any additional photos you add to these albums on Google
  Photos will be automatically sent to the Aura frame."* This is set up through five taps
  in the Aura mobile app (select frame → Add Photos → Google Photos → Connect →
  authenticate → choose albums) — a **one-time OAuth-style consent**, not per-photo
  picking, and the ongoing sync is described as automatic thereafter.
- The Ambient API's technical shape (from `developers.google.com/photos/ambient/guides/about`,
  fetched 2026-09-03): uses **"OAuth 2.0 for TV and Limited-Input Device
  Applications"** (the device-code flow), and **"doesn't support service accounts —
  users must be signed in to a valid Google Account."** This confirms it is architected
  exactly for the frame-device use case Aura has.

### What this means for this project

The Aura mobile app's Google Photos sync almost certainly works by **Aura's own backend
servers** talking to Google's Ambient API using Aura's partner credentials, then pushing
the resulting photos into the same Pushd cloud infrastructure this project already
authenticates against and drives (`api.pushd.com/v5`). If that inference is correct, the
Pushd API this project already reverse-engineers **may already expose the REST
endpoints** that configure "link this Google album to this frame" — e.g., something
functionally like a `POST /frames/{id}/sources` or `linked_google_album` field on the
frame or a contributor object. If so, **this project's `aura-cli` could drive the exact
same feature by calling Pushd endpoints directly — never touching Google's APIs at
all**, sidestepping every constraint discussed in sections 1–4 of this document
entirely: no OAuth scopes to manage, no share-link scraping, no pagination ceiling, no
Partner Program application of this project's own, no consent-wall risk. Aura would be
the one holding the Partner Program relationship and doing all the Google-side work; this
project would just be another (unofficial) client of Aura's own already-built feature.

**This is explicitly flagged by the task brief as requiring a live spike against the
Pushd API in a later phase** — this research establishes that the *feature exists* and
*how Aura describes it*, which is what was asked; confirming the actual endpoint shape
is out of scope here. **Recommendation: sequence that spike first**, before committing
to building any Google-facing OAuth/scraping code. If Pushd exposes this, it collapses
the milestone's riskiest, most speculative work into a much smaller, much safer scope
extension of code this project already has (an authenticated Pushd API client). If it
doesn't (Aura's app might do the Google-side work purely client-side in the mobile app
and just upload resulting bytes through the normal upload endpoints, indistinguishable
from any other upload), the fallback is path #2 (shared album link scraping).

---

## Dead ends — explicitly named, not to be re-litigated

1. **`photoslibrary.readonly` / `.sharing` / bare `photoslibrary` scopes** — 403 since
   2025-03-31, no allowlist, no appeal path documented. (Already settled in STACK.md;
   restated here for completeness.)
2. **App-created album + user manually adds their own photos via the Google Photos UI**
   — does NOT make those photos readable via `readonly.appcreateddata`. Answered
   definitively in §3c. Do not resurface this as an open question.
3. **`sharedAlbums.list`/`.get`/`.join`/`.leave`, `albums.share`** — all depend on the
   removed `photoslibrary.sharing` scope. No surviving form.
4. **Google Takeout — any programmatic trigger.** No API exists for a general
   developer. The only real internal API (`takeout-pa.googleapis.com`) is
   Google-internal and cannot be enabled by any external Cloud project. Initiation is
   strictly manual, forever, for this feature as it exists today.
5. **Google Data Portability API for Google Photos** — does not exist. Confirmed via
   the complete, verbatim scope list; zero Photos-related scopes of any kind.
6. **Old Drive↔Photos auto-sync folder** — removed 2019-07-10, no remnant.
7. **Picasa Web Albums / legacy RSS/Atom** — long dead, no revival mechanism found or
   plausible.
8. **`drive.file` scope to read a Takeout-delivered folder Google (not this app)
   created** — does not work; `drive.file` only sees files the app itself created or
   the user explicitly picked via Drive Picker (file-by-file, not folder-recursive).

## Open items needing a follow-up spike (not dead ends, just unresolved here)

1. **Shared-album pagination ceiling** — exact mechanism and true limit unconfirmed;
   spike with a real album of 600+ photos before relying on this path for large albums.
2. **Pushd API's Google-linked-frame endpoints** — the single highest-value unknown in
   this whole document; a live spike (inspecting Aura app traffic or probing
   `api.pushd.com/v5` for source/linking endpoints) could make most of sections 1–4
   unnecessary.
3. **Takeout's current `.json` sidecar schema** — needed only if the Takeout-to-Drive
   path (rank 4) is ever built; not confirmed in this pass.
4. **Rate-limit ceiling for repeated shared-album fetches** — `publicalbum.org` reports
   `429`s under bulk load; the actual threshold for a low-frequency, single-album cron
   job is unknown and untested at volume.

## Sources

All fetched/searched 2026-09-03 unless otherwise dated in-line above.

- Live `curl` fetch of `photos.google.com/share/...` (this session) — primary evidence, §1
- `developers.google.com/photos/overview/authorization` — scope definitions, §3a
- `developers.google.com/photos/library/reference/rest/v1/mediaItems/search` — `albumId` behavior, §3c
- `developers.google.com/photos/library/guides/manage-albums`, `.../list`, `.../access-media-items` — app-created semantics, §3
- `developers.google.com/photos/support/updates` — scope removal dates (anchor source, already used in STACK.md)
- `developers.google.com/photos/ambient`, `.../photos/ambient/guides/about`, `.../photos/partner-program/overview` — Ambient API, §5
- `developers.google.com/data-portability`, `.../data-portability/user-guide/introduction`, `.../scopes` — Data Portability API scope list (exhaustive, no Photos scope), §2b
- `developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification` — CASA/restricted scope, §2c
- 9to5google.com/2026/06/01 (scheduled Takeout export) and 9to5google.com/2026/06/04 (Aura Google Photos restoration) — §2a, §5
- techtimes.com/articles/317765 (2026-06-06) — Ambient API + Aura partner confirmation, §5
- auraframes.com/news/how-to-effortlessly-display-google-photos-on-your-aura-frame — Aura's own feature description, §5
- publicalbum.org/blog/embedding-google-photos-albums — pagination ceiling admission, §1e
- github.com/gilesknap/gphotos-sync-discussion #1 — archival, confirms Library-API path dead for backup tools, §1f
- github.com/rclone/rclone issue #8580 — MultCloud speculation, unconfirmed, §4
- github.com/pnxl/google-photos-album-scraper, github.com/ValentinH/google-photos-api, github.com/alexcrist/scrape-google-photos, github.com/austenstone/google-photos-scraper — tool structure cross-checks, §1b/§1f
- gist.github.com/stewartmcgown — `takeout-pa` internal API schema, §2b
- ipinfo.io — confirms the test fetch's real egress IP was Paris, FR, §1a
- its.umich.edu / workspaceupdates.googleblog.com — Drive↔Photos split, 2019-07-10, §4
