# Browser Automation for Google Photos Album Sync — Research

**Scope:** Browser-automation ("UI robot") approaches only, for the v3.0 Google Photos
album sync milestone. Non-automation paths (shared-album link parsing, Takeout→Drive,
Aura's own Google integration) are covered by a separate researcher — not repeated here.
**Researched:** 2026-09-03. Claims are marked **VERIFIED** (source + date, or a live
empirical test run in this session) or **INFERRED** (reasonable but not independently
confirmed).

---

## Verdict — Up Front

**Browser automation is a reasonable, non-trap engineering choice for this milestone, but
not as a hand-built Playwright scraper.** The right shape is a **hybrid**, and it is
narrower than "drive a browser":

1. **Don't write a DOM scraper.** Two independent, working 2026 implementations already
   call Google Photos' internal `batchexecute` RPC directly once a session exists —
   `hensenx/gphotohandler` (Playwright-driven session bootstrap, then RPC calls) and
   `xob0t/google_photos_web_client` (cookie-file bootstrap, pure RPC client, no browser at
   runtime). This validates the user's stronger question in §3 directly: yes, you can skip
   DOM scraping entirely once you hold session cookies. That is both more robust (RPC
   contracts change less often than CSS/DOM structure) and a much smaller thing to build
   or maintain than a scroll-and-scrape engine.
2. **Use a real, persistent, already-logged-in browser profile for the *session
   bootstrap only*, not for ongoing scraping.** Point Playwright (headed, or a
   long-lived Xvfb-backed "headed" session, never headless) at a Chrome profile the user
   already uses daily, extract cookies once, then talk to `batchexecute`/the `=d` download
   URL directly over plain HTTP for every subsequent run. This sidesteps Google's bot
   detection almost entirely, because there is no automated *login* — only automated
   *cookie extraction* from a session Google already trusts.
3. **This still needs a browser dependency and periodic manual re-auth** — it is not
   zero-touch, and it is **permanently outside CI** (see §4). That is the real cost, and
   it is worth naming plainly rather than discovering it mid-build.
4. **Byte-fidelity for this project's diff engine is NOT primarily a download-mechanism
   question** — it is a Google-account-setting question, resolved once, independent of
   whether you scrape, call the API, or use Takeout (see §3.4). This changes the shape of
   the risk from "browser automation might corrupt bytes" to "check one account setting
   before trusting any download path, including this one."
5. If the team wants to spend zero build effort at all: **`spraot/gphotos-sync`** is a
   maintained, Docker-packaged, album-scoped successor to the archived `gphotos-sync`,
   built on exactly the CDP approach described above, updated as recently as 2026-06-29.
   Shelling out to it (or its underlying `spraot/gphotos-cdp` Go binary) is a legitimate,
   much-lower-effort alternative to building any Python browser code in this repo at all
   — traded against giving up control of the exact download/EXIF behavior and taking on
   an external, out-of-this-project's-control moving part.

**Recommendation for this milestone:** build the narrow **RPC-after-cookie-bootstrap**
client in Python (§6), not a DOM scraper, and not a full Playwright-driven scrape loop.
Isolate the browser dependency behind a leaf module so it never appears in an import graph
the test suite touches, exactly as the existing `ARCHITECTURE.md` already isolates
`GoogleClient`/`GooglePhotosApi`. Accept, explicitly, that this component's live
correctness can only ever be verified by a human running it locally — write that into the
roadmap as a recurring manual-verification task, not a solvable CI gap.

---

## 1. Existing Tools Survey

| Tool | Language | Last code push | Album support | Approach | License | Verdict |
|---|---|---|---|---|---|---|
| `perkeep/gphotos-cdp` | Go (chromedp) | **2024-06-30** (VERIFIED, GitHub API, 2026-09-03) — over 2 years stale | **No** — README states explicitly it "does not support... albums" (VERIFIED) | DOM scrape of the library timeline | Apache-2.0 | Reference implementation only; don't build on the stale upstream |
| `spraot/gphotos-cdp` (fork) | Go (chromedp) | **2026-06-29** (VERIFIED, GitHub API) — active | **Yes** — adds a `-album <id>` flag (VERIFIED, README) | DOM scrape, album-scoped | Apache-2.0 (inherited) | The one CDP fork actually worth shelling out to if going the binary route |
| `msfjarvis/gphotos-cdp` (fork) | Go (chromedp) | **2026-08-30** (VERIFIED, GitHub API) — most recently pushed of the three | Inherits perkeep's no-album limitation (not added in this fork) | DOM scrape | Apache-2.0 | "[VERY LIGHTLY MAINTAINED]" by its own README label; active but narrow scope |
| `spraot/gphotos-sync` | Shell + Docker, wrapping `spraot/gphotos-cdp` | **2026-06-29** (VERIFIED, GitHub API) | **Yes** — `ALBUMS` env var, comma-separated album IDs or `ALL` (VERIFIED, README) | Docker-packaged CDP scrape, `gphotos-sync`-shaped CLI/env ergonomics | None specified | **The de facto community successor** to the archived `gilesknap/gphotos-sync`; lowest-effort "just run a container" option |
| `gilesknap/gphotos-sync` (original) | Python, Google Photos Library API | Archived **2026-10-04** — wait, VERIFIED as **2024-10-04** (GitHub repo archive banner + linked discussion, both consistent) | Was API-based, not automation | N/A — dead | Apache-2.0 | Archived because the March-2025 scope change made API-based sync impossible (VERIFIED, `gilesknap/gphotos-sync-discussion#1`); superseded in spirit by `spraot/gphotos-sync` above |
| `hensenx/gphotohandler` | Python (Playwright + playwright-stealth + `requests`) | 2026-04-11 (VERIFIED, GitHub API) — created 2026-04-09, i.e. ~5 months old | **Yes** — "All Photos" or a specific album after "Refresh Albums" (VERIFIED, README) | Playwright bootstraps a persistent Chromium session/cookies once, then calls the internal `batchexecute` web API directly for enumeration and `=d`/`=dv` for original-quality download | **None specified** (all-rights-reserved by default) | Technically the closest match to what this project needs; **0 stars/forks, single-author, 5 months old** — unproven, and no license means it can be run/shelled-out-to but not vendored |
| `xob0t/google_photos_web_client` | Python | 2026-06-04 (VERIFIED, GitHub API) | Enumeration via `batchexecute` payloads confirmed (`GetLibraryPageByTakenDate`); album-specific payload not directly confirmed in the README excerpt fetched — **INFERRED** likely present given the same RPC surface, not verified by name | **No browser at runtime at all** — auth is a one-time cookie export (browser extension), then pure HTTP RPC client | MIT | The leanest possible "RPC after cookie bootstrap" reference; low adoption (33 stars) but active |
| `xob0t/gpmc` (mobile client) | Python | 2026-09-01 (VERIFIED, GitHub API) — most recently pushed of everything surveyed | N/A | Reverse-engineered **mobile** API; auth requires extracting `androidId` + token from a rooted or ReVanced-patched Android device via ADB (VERIFIED, README) | MIT | **Upload-only**, not useful for downloading an album; included here only to show the reverse-engineered-API approach has real community traction (341 stars, 24 open issues, very active) despite a much heavier and riskier auth bootstrap than the web client |
| `immich-go` | Go | 2026-06-25 (VERIFIED, GitHub API) | N/A to this scope | **Not browser automation** — imports Google Takeout ZIP archives offline. Out of this document's scope by design (covered by the other researcher); noted here only to draw the boundary: it never talks to a live Google account, so it answers a different requirement (bulk historical import) than "keep an album in sync going forward" | AGPL-3.0 | Not a candidate for this section |
| Playwright/Puppeteer/Selenium generic scrapers (`austenstone/google-photos-scraper`, `alexcrist/scrape-google-photos`, `AlbertRtk/google_albums_downloader`) | TypeScript / Python | Not independently dated; low-adoption side projects | `alexcrist` and `AlbertRtk` are album-scoped; `austenstone` targets *public shared* albums only | DOM/preview-quality scraping (several explicitly note "preview-quality," not originals) | MIT (where checked) | Low-confidence, thin projects; useful only as evidence that "scrape a Google Photos album" is a well-trodden path with many independent small attempts, not as a dependency to adopt |

**Reading the table as a maintenance signal:** the projects that are both *recently
pushed* and *album-capable* (`spraot/gphotos-cdp`, `spraot/gphotos-sync`) are forks built
specifically in response to the March-2025 API cull, by one active maintainer, in the last
few months relative to today. The *older*, higher-star projects (`perkeep/gphotos-cdp` at
689 stars, `gilesknap/gphotos-sync` before archival) are either stale or dead. This is
consistent with the domain's real shape: the whole ecosystem pivoted to browser automation
recently and is still young, not battle-hardened over years the way, say, `yt-dlp` is.

---

## 2. Login and Session Handling

### Persistent profile reuse — the practical answer

**VERIFIED (by direct implementation evidence):** `hensenx/gphotohandler` implements
exactly this pattern today — a persistent Chromium profile directory under
`~/.gphotohandler/`, first-run manual headed login, subsequent runs reuse the saved
profile/cookies without re-authenticating. This is the standard, working shape.

Concrete mechanics and gotchas:

- **Chrome profile locking.** Pointing `--user-data-dir` (or Playwright's
  `launch_persistent_context(user_data_dir=...)`) at a profile directory that a *real,
  currently-running* Chrome window also has open will fail or corrupt state — Chrome
  places a lock on the profile directory. **INFERRED from well-established Chrome
  behavior**, not specific to this project. Practical consequence for the user: either (a)
  close their everyday Chrome before running a sync that reuses their real profile, which
  is disruptive, or (b) maintain a **separate, dedicated automation profile** that gets
  logged in once and never touched by the user's daily browsing — this avoids the lock
  entirely at the cost of a one-time separate login.
- **Headless vs headed and bot detection.** **VERIFIED:** Google explicitly detects and
  challenges automated browsers at login with "This browser or app may not be secure"
  (Google's own Chrome community support thread, and multiple independent
  Playwright/Selenium-automation write-ups from 2026 describe the same block). The
  practical mitigation converged on across sources: never run **headless** for anything
  touching Google auth; use a headed (or virtual-display, e.g. Xvfb-backed "headed")
  browser, and — critically — **avoid the automated-login step altogether** by only ever
  reusing an already-authenticated profile/cookie jar rather than scripting the login form
  itself. This is why the recommended design in §"Verdict" treats login as a **manual,
  human-in-the-loop, one-time bootstrap**, not something the code ever automates.
- **Session lifetime.** `gphotohandler`'s README claims sessions last "several months"
  before requiring re-authentication — this is a **self-reported claim from a single
  5-month-old, 0-star project**, not independently corroborated data, and should be
  treated as an optimistic anecdote, not a guarantee. What's better established
  (**VERIFIED**, Playwright's own docs and multiple session-management write-ups): the
  session dies whenever Google forces re-auth server-side — a new device/location
  signature, a security checkup Google decides to trigger, a long idle period, or a
  password/2FA change — not on a fixed TTL. **Realistic cadence for the user:** expect an
  occasional (weeks-to-months, unpredictable) interactive step where they have to open the
  automation's browser profile themselves and click through a Google "verify it's you"
  prompt before the next scheduled sync can proceed. This is not catastrophic, but it is
  not zero-touch, and any design that assumes a fully unattended cron job forever is
  building on an assumption none of the surveyed tools actually deliver on.
- **`storage_state` vs full profile.** Playwright's lighter-weight `storage_state()`
  (cookies + localStorage snapshot, no full browser profile) is documented as needing
  "regular regeneration" for sites with server-side session invalidation (**VERIFIED**,
  Playwright ecosystem write-ups, 2026). For a service as aggressive about session
  validation as Google, a full persistent profile directory (which also carries device
  fingerprint signals Google's risk engine has already seen and trusts) is the more
  robust choice over a bare cookie/storage-state export — this is exactly why
  `gphotohandler` uses a full Chromium profile dir rather than `storage_state()` alone.

### What the user would concretely have to do

1. **Once, at setup:** run a one-time interactive command that opens a real (headed)
   Chromium window pointed at a dedicated automation profile, log into Google manually
   (including any 2FA), then close it. The tool saves that profile directory.
2. **Every sync run:** the tool launches that same profile headed-but-invisible (Xvfb) or
   headed-minimized, harvests fresh cookies, and does the rest over plain HTTP — no
   visible browser window needed in steady state.
3. **Occasionally (unpredictable, weeks-to-months):** the harvested cookies stop working;
   the tool should detect this (an auth-shaped failure from the RPC calls) and tell the
   user plainly to re-run the interactive step, rather than fail silently or retry forever.

---

## 3. Album Enumeration Mechanics

### 3.1 Virtualized grid scrolling (the DOM-scrape technique, for context)

Google Photos renders its grid virtualized — off-screen items are not in the DOM. The
technique every DOM-scraping tool surveyed uses (gphotos-cdp family) is: scroll to the
bottom, wait for new grid-item nodes to mount, extract a stable identifier from each
item's link `href` (which embeds the media key), dedupe against already-seen keys, repeat
until a scroll produces no new items. This is a known-working but inherently fragile
technique tied to CSS class names and DOM shape, which is exactly why the RPC route below
is preferable if you're going to build anything new.

### 3.2 The internal RPC (`batchexecute`) — investigated seriously, as asked

**This is real, documented by multiple independent parties, and already implemented
twice for Google Photos specifically.**

- **VERIFIED (general mechanism):** `batchexecute` is Google's generic internal RPC
  framework used across many Google products (Search, Play Store, Photos, etc.), not
  Photos-specific. The response envelope is a well-documented, fixed shape: a `)]}'`
  anti-hijacking prefix, followed by size-prefixed lines, each containing a JSON array
  whose positional elements map to response fields. Independent reverse-engineering
  write-ups exist for Google Image Search (`kennedn/google_batchexecute`) and the Play
  Store's internal top-charts API (Benjamin Altpeter's public write-up), both describing
  the identical envelope format — this is a genuinely stable, cross-product protocol
  shape, not a one-off.
- **VERIFIED (Photos-specific):** Two independent 2026 Python projects call this RPC
  directly against Google Photos once session cookies exist: `hensenx/gphotohandler`
  (`GetLibraryPageByTakenDate`-style payloads for enumeration) and
  `xob0t/google_photos_web_client` (same payload family, pure-HTTP client with no browser
  at runtime once cookies are exported). Both are active as of mid-2026.
- **Robustness tradeoff, stated honestly:** RPC IDs and request nonces (e.g.
  `grid_state`, page-cursor nonces inferred from the previous response's
  `AF_initDataCallback`) can change when Google redeploys the Photos frontend, without
  notice — this is explicitly called out in the general `batchexecute` write-ups as the
  known failure mode. The advantage over DOM scraping is not immunity to breakage, it's
  that **RPC payload/response shapes change less often than CSS class names and DOM
  structure**, and when RPC breaks, it breaks loudly (a parse failure on malformed JSON)
  rather than silently (a scraper "finding" zero items because a `div` class renamed).

**Answer to the user's direct question:** yes, calling the internal RPC directly once you
hold session cookies is a real, working, currently-demonstrated technique — not a
theoretical one. It is the recommended approach over DOM scraping (§ Verdict).

### 3.3 From grid item to full-resolution original

**VERIFIED:** the `=d` (photo) / `=dv` (video) URL-suffix convention for retrieving an
original-quality asset is the same mechanism the official Photos Library API's `baseUrl +
"=d"` download pattern uses, and it's what both `gphotohandler` and the CDP-family tools
key their "download original" step on. In a browser-automation-with-RPC design, once you
have a media item's `baseUrl` from the `batchexecute` response, appending `=d`/`=dv` and
fetching it directly (with the harvested session cookies attached) yields the original
file — no further browser interaction needed per item.

### 3.4 Byte fidelity — the load-bearing question, answered directly

This project's diff engine matches base64-MD5 of local bytes against the frame's reported
hash; a systematic re-encode on download would make every sync re-upload everything
forever. Investigated directly:

**The determining factor is NOT the download mechanism (browser vs API vs Takeout). It is
the Google Photos *backup quality setting the user chose at upload time*, which is
permanent and irreversible:**

- **VERIFIED** (Google's own support documentation, and independently corroborated by
  multiple 2026 technical write-ups): Google Photos has always offered "Original
  quality" (exact bytes, byte-for-byte, as uploaded) versus a compressed tier
  ("Storage saver," formerly "High quality") that **downsizes the image at upload/ingest
  time**. Once a photo is stored in the compressed tier, **no download method —
  Takeout, the official Library API, or any browser-automation tool — can recover the
  original bytes**, because the original was already discarded server-side. This is
  stated as explicitly irreversible ("no undo, no grace period, no restore").
- **Consequence for this project:** if the Google account/album in question was backed up
  at "Original quality," any correctly-implemented download path (browser-automation-via-
  `=d`, official API, or Takeout) should yield byte-identical originals, and the existing
  MD5-diff engine should behave exactly as it does for the local-directory case today.
  If backed up at "Storage saver," **the bytes are already lossy at the source**, no sync
  mechanism can fix that, and a first sync will legitimately produce different bytes than
  whatever the user considers "the original" — this is a pre-existing condition of the
  Google account, not a defect to chase in this project's downloader.
- **A secondary, narrower concern — GPS stripping:** one issue in the `gphotos-cdp`
  tracker (`perkeep/gphotos-cdp#30`) reports that **shared** photos/links have no useful
  EXIF at all on download; `gphotohandler`'s own README separately claims GPS is stripped
  even for the owner's own library download via its method. These two claims describe
  different surfaces (shared-link downloads vs. owner's-own-library `=d` downloads) and
  are not fully reconciled by the sources surveyed — this is a genuine open question, not
  a settled one.
- **Recommendation, matching this project's own established pattern:** this codebase has
  three times already (Phase 6 `md5_hash` nullability, Phase 7 hash-convention match,
  Phase 10 visibility-flag location) resolved exactly this kind of "does the assumed
  mechanism actually behave as documented" question with a **cheap live spike before
  building on it**, per `PROJECT.md`'s own Key Decisions log ("Trust live probes over
  model assumptions — verify the mechanism before building on it"). The same discipline
  applies here directly: before building the sync pipeline on top of any download path
  (this one included), do a one-photo live spike — download via the chosen mechanism,
  compute its MD5, and diff its EXIF against a known-original copy of the same photo — the
  same shape of spike this project has already paid off with three times.

---

## 4. Integration Into This Project

### 4.1 Library choice — Playwright, with a concrete Python 3.14 finding

**VERIFIED empirically, this session (2026-09-03):** in this exact repo's toolchain
(`uv`, Python 3.14.4), `uv add playwright` resolves and `import playwright` succeeds
cleanly with **zero build/compile step**. The installed wheel (`playwright==1.62.0`) is
`py3-none-any` — a pure-Python package with no C-extension ABI dependency — because
Playwright's actual browser-driving work happens in a bundled multi-platform Node.js
driver binary, not compiled Python. This matters because the open upstream question
("Is Python 3.14 support planned?", `microsoft/playwright-python#3066`, closed/withdrawn
without a public commitment as of this research) reads more alarming than the practical
reality: there is no official 3.14 test-matrix entry, but the wheel's architecture makes
version-specific breakage unlikely, and it is demonstrated working here, not just argued
to be likely.

**Selenium** also supports Python 3.14 (VERIFIED — Selenium 4.37 added 3.14 support per
selenium.dev's own release/blog material), but Selenium's operational model (managing
separate driver binaries, even with Selenium Manager automating that) and its
async/sync story are both worse fits than Playwright's for a codebase that has
deliberately stayed synchronous (`sync_playwright()` mirrors this project's existing
sync-only `httpx.Client` posture exactly, and MOD-01's async migration is explicitly out
of scope per `PROJECT.md`).

**Raw CDP (e.g. `pychrome`)** is not recommended for hand-building: it would mean
reimplementing auto-waiting, session/profile management, and stealth behavior that
Playwright already provides. If avoiding a from-scratch Python browser layer entirely is
preferred, **shelling out to `spraot/gphotos-cdp`** (a single statically-linked Go binary,
Apache-2.0, actively maintained, already has `-album` support) via `subprocess.run(...)`
and consuming its output directory is the lower-effort alternative — see §"Verdict" point 5.

**Given the §"Verdict" recommendation (RPC-after-cookie-bootstrap, not ongoing DOM
scraping), Playwright's actual runtime role shrinks to a small, infrequent job: launch the
persistent profile, harvest cookies, close.** The bulk of the sync logic (RPC calls,
`=d` downloads) is then plain `httpx`/`requests` code with zero browser dependency at
request time — which is good for both testability (§4.2) and packaging weight (§4.3).

### 4.2 The offline-testability seam — concrete, not hand-waved

The existing `ARCHITECTURE.md` for this milestone already sketches a `GoogleClient`/
`GooglePhotosApi` pair mirroring the codebase's `Client`/`BaseApi` DI seam, assuming an
official-API-shaped source. That seam design **still applies almost unchanged** if the
underlying transport is "RPC after cookie bootstrap" instead of the official Library API
— the RPC calls are still plain HTTP requests once cookies are held, so `GoogleClient` can
still be an `httpx`-based, `transport=`-injectable class exactly as already designed.

**What's new here is isolating the one piece that genuinely needs a real browser: the
cookie-bootstrap step.**

```
auraframes/google/
    client.py          # GoogleClient(transport=...) — httpx-based RPC calls, UNCHANGED
                        #   design from ARCHITECTURE.md, offline-testable via MockTransport
    cookie_bootstrap.py  # the ONLY file that imports playwright, and only inside functions,
                          #   never at module scope
```

```python
# auraframes/google/cookie_bootstrap.py

def harvest_cookies(profile_dir: Path) -> dict[str, str]:
    """Launch the persistent profile headed, extract cookies, close. The only
    function in this codebase that imports playwright — imported locally so the
    rest of the package (and every test) never needs the dependency installed."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(str(profile_dir), headless=False)
        page = context.pages[0] if context.pages else context.new_page()
        page.goto('https://photos.google.com')
        cookies = {c['name']: c['value'] for c in context.cookies()}
        context.close()
    return cookies
```

`GoogleClient` never calls `harvest_cookies` itself — the CLI boundary does (exactly the
existing convention: `S3Client()`/`SQSClient()` real construction is confined to
`run_sync`'s apply path only, never inside `execute_plan`, per `ARCHITECTURE.md` §6). Tests
inject a fixed `cookies: dict[str, str]` fake directly into `GoogleClient`, and
`tests/test_google_*.py` **never imports `cookie_bootstrap.py` or `playwright` at all** —
matching `tests/offline.py`'s existing pattern where the real OAuth loopback code (in the
originally-sketched design) "is never imported or exercised by the offline suite."

**The concrete guarantee this buys:** `auraframes/google/client.py`,
`auraframes/google/download.py` (RPC calls, `=d` fetches, manifest logic — everything
from the existing `ARCHITECTURE.md` design) stay 100% offline-testable via
`httpx.MockTransport`, identical in spirit to the Aura side. Only `cookie_bootstrap.py`
is untestable-without-a-real-browser-and-a-real-Google-session — and that module is
intentionally tiny (one function, no business logic) precisely so there is as little
surface as possible that can only be verified live.

### 4.3 Packaging weight — measured, not guessed

**VERIFIED, measured in this session:** the `playwright` pip package alone (before any
browser binary download) occupies **134 MB** in a fresh `uv`-managed virtualenv on this
machine — the bulk of that is bundled multi-platform Node.js driver executables inside the
wheel. A subsequent `playwright install chromium` step (not run in this session to avoid
an unnecessary large download, but well-documented) adds a further **~150–300 MB**
depending on OS/architecture for the Chromium binary itself. **Total realistic footprint:
roughly 250–450 MB**, entirely for a component that runs rarely (once per profile
bootstrap, not per sync run, under the recommended design).

**This should be an optional extra**, not a base dependency: `uv add --optional
google-browser playwright` (or a dependency group), with `playwright install chromium`
documented as an explicit one-time setup command the user runs only if they choose the
browser-bootstrap path, not something triggered automatically at import or install time.
This keeps `aura-cli`'s base install light for every user who only ever does directory-to-
frame sync.

### 4.4 CI implications — a permanent limitation, not a temporary gap

Playwright itself runs headless in CI trivially — that is its whole design point for
*testing your own app*. **That is not the blocker here.** The blocker is that Google's
own bot-detection actively fights unattended login from exactly the kind of fresh,
no-established-trust environment CI provides (§2) — there is no secrets-safe way to hand a
CI runner a working, trusted Google session the way `httpx.MockTransport` gives you a
free, safe fake Aura backend. Even a scripted OAuth-token refresh (for the official-API
path this milestone's `ARCHITECTURE.md` also considers) doesn't have this problem, because
OAuth refresh tokens are designed to be used unattended — but a **browser session cookie
harvested from an interactive login is explicitly not designed for that**, and Google's
detection is tuned accordingly.

**Concretely:** the offline test suite (§4.2) can and should run in CI, giving full
confidence in this project's own orchestration logic (RPC payload construction, manifest
handling, `compute_plan` integration). **The one thing CI can never verify is "does
`cookie_bootstrap.py` still successfully get a working session against the real Google
Photos site"** — that remains a manual, local-only, human-in-the-loop capability
permanently, for the same reason the existing `@live` pytest suite already requires real
`AURA_EMAIL`/`AURA_PASSWORD` credentials and is never run in CI. The difference here is
that the Aura `@live` suite's credentials *can* in principle be provisioned as CI secrets
(username/password auth), whereas a Google browser session fundamentally resists that —
so this isn't a slightly-worse version of the existing pattern, it's a strictly harder one
that should be documented as "manual live verification, forever" up front rather than
discovered as a surprise gap later.

---

## 5. Risk Assessment

**Google's ToS position, stated once:** Google's Terms of Service (VERIFIED,
`policies.google.com/terms`, fetched 2026-09-03) prohibit "using automated means to access
content from any of our services in violation of the machine-readable instructions on our
web pages (for example, robots.txt files that disallow crawling...)," among other
automated-access restrictions. This is a contractual term, not a criminal-law question,
and the account being accessed is the user's own.

**Real-world account-flagging reports — searched for, not found.** A targeted search for
concrete first-hand reports of Google account suspension specifically from Photos-
automation tools (`gphotos-cdp`, `gphotos-sync`, and variants) turned up **no direct
reports** in the issue trackers, discussions, or general web search surveyed for this
research. Given `perkeep/gphotos-cdp` alone has 689 stars and multiple years of real usage
(VERIFIED, GitHub metadata) with no surfaced "my account got locked" issue among its 18
open issues, the practical signal is: **this appears to be a theoretical/contractual risk
that this research could not corroborate as an observed one at meaningful scale**, not a
"never happens" claim — absence of reports in a search is weak evidence, not strong
evidence, and should be presented as such.

**Brittleness — the best available signal, from the issue trackers directly:**
`perkeep/gphotos-cdp`'s open issues include direct hits on exactly the failure modes this
research is concerned with: "Will gphotos-cdp continue to work after Google's API change
announcement?" (Jan 2025), "Cannot seem to get this or any of the forks to work right"
(Feb 2026), "Google Prevents Login from Automated Test Software" (May 2023), and "Is this
project still alive?" (Jan 2024) (VERIFIED, GitHub issue titles + dates fetched directly).
That's roughly a third of its currently-open issues directly about breakage, login
detection, or maintenance-status uncertainty — a real, non-trivial brittleness signal from
the single most established tool surveyed.

**Maintenance burden the user would sign up for:** whichever variant is chosen, this is a
component whose correctness depends on Google's frontend/RPC surface, which the surveyed
evidence shows changes at least a few times a year (the March-2025 API scope cull being
the largest, forcing a whole ecosystem pivot). Realistic expectation: periodic (order of
months, not years) breakage requiring a fix — either upstream (if shelling out to
`spraot/gphotos-cdp`/`gphotos-sync`) or in this project's own RPC-call code (if built
in-house).

**Rate limiting on bulk download:** no concrete, quantified rate-limit numbers were found
for Google Photos bulk download specifically (unlike this project's own well-measured
~42-write/~40-min Pushd limit). This is an **open gap** — treat it as unknown risk and
apply the same proactive-throttling discipline this project already built for the Aura
write path (`WriteBudget`) rather than assuming safety, until a live spike measures it.

---

## 6. Bottom Line

Browser automation is **not a trap** for this milestone, but a **naive "build a Playwright
scraper" implementation would be** — it would duplicate work two other people have already
done more robustly (calling `batchexecute` directly), inherit DOM-scraping's worse
brittleness for no benefit, and risk becoming the first permanently-live-only,
un-isolated component in a codebase whose entire testing philosophy is offline-first.

**The specific approach to build, if the team proceeds:**

1. **Library:** Playwright-Python (VERIFIED working on this project's exact Python
   3.14/`uv` toolchain), used for exactly one narrow job — persistent-profile cookie
   bootstrap (§4.2) — packaged as an optional extra (§4.3), imported only inside that one
   leaf module.
2. **Technique:** RPC-after-cookie-bootstrap, not ongoing DOM scraping. Harvest cookies
   from a real, manually-authenticated persistent Chrome/Chromium profile; use them to
   call Google Photos' internal `batchexecute` RPC for album enumeration and the `=d`/
   `=dv` URL convention for full-resolution download — both independently demonstrated
   working in 2026 by `hensenx/gphotohandler` and `xob0t/google_photos_web_client`.
3. **Seam:** `GoogleClient(transport=...)` (already sketched in `ARCHITECTURE.md`) stays
   the offline-testable core, unchanged in shape; `cookie_bootstrap.py` is the one
   playwright-importing module, called only from the CLI boundary, never from
   `execute_plan`/`compute_plan`/tested code paths — mirroring the existing
   `S3Client()`/`SQSClient()` construction-confinement convention already in this
   codebase.
4. **What must be accepted, not solved:** periodic manual re-authentication
   (weeks-to-months cadence, unpredictable); permanent absence of CI coverage for the live
   Google-facing path; ongoing maintenance exposure to Google frontend changes at a
   pace the evidence suggests is "several times a year, not once and done."
5. **Fallback if the team wants to spend zero build effort:** shell out to
   `spraot/gphotos-sync` (Docker, `ALBUMS` env var, actively maintained as of 2026-06-29)
   and treat this project's job as "consume files this container already downloaded,"
   trading control of exact download/EXIF behavior for near-zero build cost.
6. **Load-bearing correctness check before trusting any of this:** run this project's own
   established "live spike before building on an assumption" pattern (§3.4) — download one
   photo via whichever mechanism is chosen, hash it, and diff its EXIF against a
   known-original — before wiring the sync pipeline's diff engine to depend on it.

---

## Sources

All URLs fetched or searched 2026-09-03 unless otherwise noted. GitHub metadata (stars,
push dates, license, open-issue counts) pulled via `api.github.com` REST responses,
treated as HIGH confidence / primary source.

- `perkeep/gphotos-cdp`, `spraot/gphotos-cdp`, `msfjarvis/gphotos-cdp` — repos, READMEs,
  issue lists, GitHub API metadata
- `spraot/gphotos-sync` — repo, README, GitHub API metadata
- `gilesknap/gphotos-sync`, `gilesknap/gphotos-sync-discussion#1`, `gilesknap/gphotos-sync
  issue #511` — archival status, reasoning, dates
- `hensenx/gphotohandler` — repo, README, GitHub API metadata
- `xob0t/google_photos_web_client`, `xob0t/google_photos_mobile_client` (`gpmc`) — repos,
  READMEs, GitHub API metadata
- `simulot/immich-go` — repo, GitHub API metadata (boundary-drawing only, out of scope)
- `kennedn/google_batchexecute`; Benjamin Altpeter, "Accessing Android app top charts by
  reverse-engineering an internal batchexecute Play Store API" — general `batchexecute`
  protocol mechanism, MEDIUM-HIGH confidence (independent corroboration across two
  unrelated Google products)
- `policies.google.com/terms` — ToS automated-access clause, direct fetch, HIGH confidence
- `support.google.com/photos/answer/6220791`; howtogeek.com; thats.be — Google Photos
  backup-quality (Original vs Storage Saver) mechanics, MEDIUM-HIGH confidence
  (independently corroborated across official + third-party sources)
- Google Chrome Community support thread on "This browser or app may not be secure" for
  automated logins — bot-detection-on-login behavior, MEDIUM confidence (community-sourced
  but consistent with multiple independent 2026 automation write-ups)
- `microsoft/playwright-python#3066` — Python 3.14 support status (inconclusive publicly;
  superseded in this document by a direct empirical test, HIGH confidence)
- Empirical test, this session: `uv add playwright` + `import playwright` on Python 3.14.4
  in this repo's own toolchain; `du -sh` measurement of the resulting virtualenv — HIGH
  confidence, primary/first-party verification
- selenium.dev release notes — Selenium 4.37 Python 3.14 support, MEDIUM confidence
  (search-result-summarized, not directly fetched)

---
*Research for: v3.0 Google Photos Album Sync milestone, Aura Frames Python Client*
*Researched: 2026-09-03*
