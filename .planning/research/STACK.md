# Stack Research

**Domain:** Google Photos album ingestion + write-path reliability, added to an existing sync/httpx/pydantic-v2 Python 3.14 CLI
**Researched:** 2026-09-03
**Confidence:** HIGH on library versions/wheel availability (verified via PyPI); HIGH on the Google Photos API access model (verified via current developers.google.com pages, dated); MEDIUM on a few Picker API edge cases Google's own docs don't spell out (marked below)

## The critical finding first

**Google's March 2025 restriction is real, still in effect in 2026, and there is no allowlist path back to broad read access.** `photoslibrary.readonly` / `.sharing` / (bare) `photoslibrary` scopes stop working with `403 PERMISSION_DENIED` after March 31, 2025 (VERIFIED, developers.google.com/photos/support/updates, page last updated 2025-08-28). The Library API's remaining scopes (`photoslibrary.appendonly`, `photoslibrary.readonly.appcreateddata`, `photoslibrary.edit.appcreateddata`) only ever see **content the calling app itself created** — never a user's pre-existing albums (VERIFIED, developers.google.com/photos/overview/authorization). There is no documented allowlist, exception request, or "trusted tester" program to get `albums.list`/`mediaItems.search` back for a general app (VERIFIED by absence — the updates page and authorization page describe the change as unconditional and permanent, no appeal path listed).

The only remaining route to a user's *existing* Google Photos content is the **Picker API** (`photospicker.googleapis.com`, scope `photospicker.mediaitems.readonly`), and it has a fundamentally different shape than `albums.list` ever did:

| Property | Verified behavior | Source |
|---|---|---|
| Selection unit | User picks individual photos/videos in a search-driven UI. **There is no one-click "select this whole album" affordance** — the Picker UI explicitly does not surface albums/favorites as browsable categories; users must search, then multi-select results | developers.google.com/photos/picker/guides/picking-experience (fetched 2026-09-03) |
| Session lifetime | `PickingSession.expireTime` — sessions expire **~24 hours** after creation | developers.google.com/photos/picker/reference/rest/v1/sessions + corroborating third-party report; VERIFIED field exists, INFERRED exact "~24h" figure (Google's own reference page doesn't print a number, but a session's expiry is a real timestamp field, not "forever") |
| `baseUrl` lifetime | **60 minutes**, shorter if the user revokes access in their Google Account | developers.google.com/photos/picker/guides/media-items (VERIFIED) |
| Re-fetching after expiry | `mediaItems.list` requires the **sessionId** — once a session's `expireTime` passes, its picked items are no longer retrievable through that session. A stored `mediaItem.id` is not documented as independently resolvable outside its session | developers.google.com/photos/picker/reference/rest/v1/mediaItems + guide text ("store IDs... URLs expire") — VERIFIED that IDs are scoped to sessions, INFERRED (by absence of any cross-session `mediaItems.get`) that there is no way to resolve a picked item after its session dies |
| Download fidelity | `=d` suffix on `baseUrl` downloads original bytes "retaining all EXIF metadata **except location**" for images; video download uses `=dv` and is explicitly a **transcoded** version, not original bytes | developers.google.com/photos/picker/guides/media-items (VERIFIED for photos; video-original-bytes question explicitly unanswered by docs — INFERRED transcoded-only from the `=dv` "transcoded version" wording) |
| Stable identity / hash | `PickedMediaItem.mediaFile` exposes `id`, `baseUrl`, `mimeType` — **no content hash field of any kind** is documented | developers.google.com/photos/picker/reference/rest/v1/mediaItems (VERIFIED) |
| Scope tier | `photospicker.mediaitems.readonly` requires OAuth **verification review**; evidence points to "sensitive" tier (verification, no CASA) rather than "restricted" tier (verification + paid annual CASA security assessment), but Google's own scope-tier list wasn't found published for this specific scope | developers.google.com/identity/protocols/oauth2/production-readiness/sensitive-scope-verification (VERIFIED verification is required in some form); INFERRED tier |

**What this means for the milestone's "persisted, repeatable album→frame mapping" requirement: it does not fit the Picker API's model as designed.** A Picker session is a one-shot, ~24-hour-lived, user-attended browser interaction that yields item references good for ~60 minutes of downloading. It cannot be silently re-polled next week to detect "3 new photos added to the album" — Google's own model assumes the picker is invoked again, by a human, each time you want fresh content, and there is no "album ID" object exposed to the general app that a script could hold onto across runs.

### Three ways to reconcile this with the milestone, with consequences

**Option A — Redefine "album sync" as "picker session sync," re-run interactively.** Each `aura-cli google-sync` invocation opens (or reuses within its ~24h/60min windows) a fresh Picker session; the user re-selects the same photos (Google Photos' picker does support searching/filtering so re-selecting a known set is fast, if tedious) or a growing manifest of items. The persisted config stores **Picker session bookkeeping is not persisted at all** — what *is* persisted is your own manifest of "photo identity → last-synced-hash" keyed by something you compute yourself (e.g., a content hash of the downloaded bytes, exactly like the existing `md5_hash` diff engine), so re-picking the same photos twice is idempotent even though Google gives you a new opaque `id` each session. This preserves "one run = fully reconciled," but **cannot run unattended** (a human must click through the picker UI every run) and **cannot detect "album now has N new photos"automatically** — the user must remember to re-pick.

**Option B — Scope the milestone to "one-time transfer," not "ongoing sync."** Treat each album as migrated once via a Picker session; subsequent frame content lives independently of the Google album afterward (no more polling Google at all). This satisfies "sync an album to a frame" literally but drops "mirror semantics" (album as ongoing source of truth) to a one-shot import. Simplest to build, weakest match to the milestone's stated goal.

**Option C — Apply for restricted-scope verification to regain `photoslibrary.readonly`-equivalent access.** Google's restriction is aimed at *general* apps; a verified, published app with a legitimate use case can still request sensitive/restricted scopes through the standard OAuth verification flow (VERIFIED such a flow exists for other restricted scopes — developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification; NOT verified specifically that Google still grants `photoslibrary.readonly` itself through this path post-March-2025, and the updates page's phrasing ("you will only be able to access content created by your application") reads as an unconditional platform change, not a scope you can apply your way back into). If broad read truly is unconditionally gone (most likely reading of the source), Option C is a dead end for this exact scope; it is listed for completeness and because "restricted scope verification" processes do exist for *other* Google APIs and it's worth a 15-minute confirmation call/ticket to Google before ruling it out entirely, given how much it would simplify the milestone if wrong.

**Recommendation for the roadmapper: build to Option A.** It is the only one of the three that still uses official, документable, non-allowlisted APIs and roughly honors "album is source of truth" — it just needs the requirement's language changed from *unattended, poll-based* sync to *user-invoked, re-pick-driven* sync, with the local content-hash manifest (reusing the exact `md5_hash`-diff machinery already proven in v2.0) doing the "did anything actually change" work that Google no longer exposes an API for. Flag this explicitly back to requirements/roadmap — it changes what "many-to-many mapping, reconciled in a single run" can mean (it becomes "the user re-opens the picker for each mapped album, in one CLI invocation that walks the config's album list sequentially," not "the CLI silently notices new photos on its own").

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `google-auth` | 2.57.0 (released 2026-08-24) | OAuth2 credential object, token refresh (`Credentials.refresh()`), loopback-flow support classes | The only piece of the Google Python stack you actually need — a `Credentials` object plus refresh logic. Supports Python 3.10–3.14 per PyPI classifiers (VERIFIED); pure-Python + small C-free deps (`cachetools`, `pyasn1`, `pyasn1-modules`, `rsa`) — all have universal or 3.14 wheels |
| `google-auth-oauthlib` | 1.4.1 (released 2026-08-24) | `InstalledAppFlow.run_local_server()` — the loopback-redirect installed-app OAuth dance, PKCE handled internally | Purpose-built for exactly this flow; supports Python 3.10–3.14 per PyPI classifiers (VERIFIED). Thin wrapper over `google-auth` + stdlib `wsgiref`/`http.server` for the local callback listener — no heavy transitive deps |
| `httpx` (already a dependency, 0.28) | — | Drive the Photos Picker REST API (`photospicker.googleapis.com/v1/...`) directly, and do the Google Photos downloads | The Picker API is new enough that it is **not** in `google-api-python-client`'s bundled discovery cache (VERIFIED via that library's discovery-fallback mechanism existing at all — `static_discovery=False` is the documented workaround for exactly this "API missing from local cache" situation). Since you'd have to fight the discovery client anyway, and the project already has a battle-tested `httpx.Client`/DI-seam/`MockTransport` offline-test harness, raw REST calls through the existing `Client` abstraction (or a small sibling `GooglePhotosClient` built the same way) is strictly less new surface area than adding a second, differently-shaped HTTP client |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `tomli-w` | 1.2.0 (2025-01-15) | Write the album↔frame mapping config back to TOML after reconciliation | Only needed if the config must be machine-rewritten (e.g., pruning a mapping, recording last-synced state). Pure-Python universal wheel (VERIFIED, `py3-none-any`), zero transitive deps. Pairs with stdlib `tomllib` (read-only, 3.11+) for parsing |
| `tenacity` | 9.1.4 (2026-02-07) | *Optional* — only if the reliability pass grows beyond "retry once on 401" | Python 3.14 wheel confirmed (VERIFIED — 9.1.3 added 3.14 support, 9.1.4 carries it forward). See "What NOT to add" — for the milestone's actual stated scope (retry exactly once, with a fresh login, on 401) this is very likely unnecessary weight; a 12-line hand-rolled retry is more legible and matches the project's existing minimal-deps convention |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `httpx.MockTransport` (already in harness) | Offline-test the new `GooglePhotosClient` the same way `Client`/`Aura` are tested today | Fixture the Picker session-create/session-poll/mediaItems.list/download responses as synthetic JSON, exactly like the existing sanitized Aura fixtures — no live Google credentials needed for the test suite |
| Fake `Credentials` object / injected `google.auth.credentials.Credentials` subclass | Test the auth layer without hitting Google's token endpoint | `google-auth`'s `Credentials` is a plain class with a `refresh(request)` method and a `token` attribute — trivial to stub in tests, no network mocking library needed |

## Installation

```bash
# Core additions
uv add google-auth google-auth-oauthlib

# Config write support (only if the reconciliation loop rewrites the mapping file)
uv add tomli-w

# NOT added: google-api-python-client, requests-as-a-transport, aiohttp
```

(`httpx`, `pydantic`, `python-dotenv` etc. are already dependencies and need no changes for this milestone.)

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Raw `httpx` calls to `photospicker.googleapis.com` | `google-api-python-client` (`googleapiclient.discovery.build(...)`) | If the project later needs many more Google APIs with rich, auto-generated method surfaces (e.g., full Drive, Calendar, Sheets integration) where hand-rolling REST calls for each would be real duplicated effort. For *one* narrow API (Picker) plus maybe the app-created-data Library API, the discovery-client's `httplib2`/`uritemplate`/`google-api-core` dependency chain and its own request/response shape (not `httpx.Response`) buys nothing and duplicates the transport layer the project already has |
| `google-auth-oauthlib`'s `InstalledAppFlow.run_local_server()` | Hand-rolled `http.server` + manual PKCE + manual token exchange via `httpx` | If you want zero new dependencies at any cost. Rejected here: OAuth PKCE + CSRF-state handling + the loopback redirect dance is exactly the kind of security-sensitive plumbing you don't want to hand-roll when a small, actively maintained (Aug 2026 release), Google-authored library does it correctly — this is not "business logic," it's auth-protocol plumbing, which the project's own conventions (Cognito auth already delegated to `boto3`, not hand-rolled) treat differently from app code |
| `concurrent.futures.ThreadPoolExecutor` over the existing sync `httpx.Client` | Narrowly-scoped `httpx.AsyncClient` for downloads only | If a future milestone actually needs async for reasons beyond "downloads are I/O bound and embarrassingly parallel" (e.g., streaming very large media, or the Aura side eventually goes async too — explicitly out of scope here, MOD-01). `ThreadPoolExecutor` requires **zero** new dependencies, works unchanged with the existing synchronous `httpx.Client` (which is thread-safe for concurrent requests — this is documented httpx behavior, connection pooling is designed for exactly this), and needs no new test-harness shape: the same `MockTransport`-backed client, called from N threads in a test, still exercises real concurrency without an `asyncio` event loop appearing anywhere in the codebase. An `AsyncClient`-for-downloads-only design would require either two separate httpx client types side by side (inconsistent with "the project has one HTTP client pattern") or a sync-wrapping `asyncio.run()` shim at the download call site, which is more moving parts for the same result |
| `concurrent.futures.ThreadPoolExecutor` | `asyncio.to_thread` | If the surrounding code were already inside an async call stack (it isn't — the CLI, `Aura`, and `Client` are entirely synchronous today) `asyncio.to_thread` would be the more idiomatic bridge. Introducing it here would mean adding `asyncio.run()` at the CLI entry point for the sole purpose of downloading Google photos, which drags a whole event loop into an otherwise 100% sync codebase for one call site — `ThreadPoolExecutor` gets the same concurrency without that structural change |
| TOML (+ `tomli-w` for writes) for the album↔frame mapping | JSON | If write-simplicity matters more than human-editability and the file will be exclusively machine-generated/read (never hand-edited). The mapping config here is exactly the kind of file a user will want to hand-author/tweak (add an album, rename a frame) — TOML's comments and cleaner nested-table syntax beat JSON for that, and the project already treats config as human-facing (env vars, not a JSON blob). Downside acknowledged: stdlib `tomllib` is read-only (3.11+, so fine on 3.14) — writes need `tomli-w`, a 1-file pure-Python dependency, which is a small, low-risk price for round-trippable human-editable config |
| TOML | YAML (`PyYAML`/`ruamel.yaml`) | If the config needs anchors/references or deep nesting beyond what TOML tables handle gracefully. Rejected as the default here: YAML pulls in a real dependency with a C extension in some install paths (`PyYAML`'s `libyaml` bindings) for a config file that's fundamentally a flat list of `{album, frame}` pairs — no nesting complexity that would justify YAML's extra weight or its well-known footguns (implicit typing, `!!python/object` deserialization risk if ever loaded unsafely) |
| Hand-rolled single retry-on-401 (raise-log-relogin-retry-once, inline in `execute_plan`) | `tenacity` | If retry policy grows past "exactly once, only on 401, only after a fresh login" — e.g., exponential backoff across multiple transient error classes, jitter, per-call retry budgets. The milestone's own stated requirement is narrow and specific (Phase 10 measured ~4-in-10 401s that clear on an *immediate* retry with a fresh login — not a backoff problem, an auth-freshness problem). A `tenacity`-decorated function to express "try once, catch a specific 401 condition, re-login, try again, otherwise raise" is not meaningfully shorter or clearer than the equivalent 10–15 lines of plain Python, and the project's own conventions (no custom exception hierarchy yet, minimal deps, fail-loud) favor the inline version until/unless retry policy actually grows in complexity |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `google-api-python-client` | The Picker API postdates this library's bundled discovery cache and is a bad fit for its request/response shape; it also pulls in `httplib2` (a second, older HTTP stack) and `uritemplate`/`google-api-core`, none of which integrate with the project's `httpx`-based DI/`MockTransport` testing seam. Using it would mean maintaining two parallel "how do I mock an HTTP call in tests" patterns in one codebase | Raw `httpx` calls to `photospicker.googleapis.com`/`photoslibrary.googleapis.com` through the existing `Client`-style abstraction |
| Any code path assuming `albums.list` or a broad `photoslibrary.readonly`-style scope still works for a general app | It returns `403 PERMISSION_DENIED` since 2025-03-31 (VERIFIED) — building against this would fail immediately for any account other than a Google-allowlisted trusted tester, which this project is not | Picker API sessions (Option A above), scoped explicitly to what a general app can actually do in 2026 |
| `urn:ietf:wg:oauth:2.0:oob` (the old "copy-paste this code" OOB flow) | Deprecated for all clients since 2022-10-03 (VERIFIED via search of Google's own OOB migration guide); some old tutorials/StackOverflow answers still show it and will simply fail against current Google OAuth endpoints | Loopback redirect flow via `InstalledAppFlow.run_local_server()`, confirmed still supported indefinitely for Desktop-type OAuth clients (VERIFIED, Google's Loopback IP Address flow migration guide explicitly exempts Desktop app client types from the loopback deprecation that affected other client types) |
| Treating a picked `mediaItem.id` as a durable, foreign-key-like identity for the persisted config | It is scoped to its Picker session and is not documented as resolvable once that session's `expireTime` passes (~24h) — storing it as "the" identity for a config row will silently rot | Compute and store your own content hash of the downloaded bytes (reuse the exact `S3Client.get_md5`/base64-MD5 convention the v2.0 diff engine already trusts) as the durable identity; treat Google's `id`/`baseUrl` as ephemeral, session-lifetime-only values |
| `asyncio`/`httpx.AsyncClient` anywhere in the Aura write path, or as a general pattern "since we're touching HTTP anyway" | Explicitly out of scope (MOD-01 deferred by user decision); mixing one async client with the rest of the codebase's fully-sync `Client`/`Aura` risks exactly the kind of scope creep the milestone explicitly fenced off, and it doesn't compose cleanly with the existing `MockTransport` sync test harness | `ThreadPoolExecutor` over the existing sync `httpx.Client`, scoped strictly to Google Photos downloads |
| PyYAML/`ruamel.yaml` for the mapping config | Extra dependency (with optional C bindings) for a flat, non-nested config that TOML tables express just as well, plus YAML's well-known deserialization footguns if ever loaded with the wrong loader | TOML (`tomllib` read / `tomli-w` write) |
| Storing the Google refresh token or the mapping config in the same file | The mapping config (album↔frame pairs) is something a user may reasonably want to review, share, or check into a private dotfiles repo; the refresh token must never be alongside it | Two files: a secrets file (refresh token, same posture/permissions discipline as `AURA_EMAIL`/`AURA_PASSWORD` — chmod 600, `.gitignore`d, not the TOML mapping file) and the TOML mapping file (no secrets, safe to be more casually handled) |

## Stack Patterns by Variant

**If the roadmap accepts Option A (user-attended re-pick, recommended):**
- Persist per-album state as: last-known set of content-hashes synced to that album's mapped frame(s), never a Google `mediaItem.id` or `baseUrl`
- Each CLI invocation: for every configured album, open a fresh Picker session, wait for the user to re-select, download via `baseUrl=…&d`, hash, diff against the persisted hash-set using the existing v2.0 engine, upload/hide as usual
- OAuth refresh token is reused across sessions (it authenticates the *account*, not a *session* — sessions are a separate, shorter-lived resource layered on top)

**If a Google Cloud project stays in OAuth "Testing" publishing status (single-user personal tool, likely default for this project):**
- Refresh tokens expire after **7 days** (VERIFIED as still current in 2026 sources) — plan for the CLI to detect an `invalid_grant` refresh failure and cleanly re-trigger the loopback consent flow rather than crash. This is a real, current operational constraint, not a historical one Google has since relaxed
- Moving to "In production" removes the 7-day cap but requires OAuth verification review for the `photospicker.mediaitems.readonly` scope (moderate effort: consent-screen justification, possibly a demo video; likely does **not** require the paid CASA security assessment, since that applies to *restricted*-tier scopes and this scope's evidence points to *sensitive* tier — CONFIRM directly with Google Cloud Console's own scope classifier before committing, since this tier boundary wasn't found in an authoritative published list during this research pass)

**If videos are ever brought into scope (currently explicitly out of scope):**
- Picker `=dv` downloads are documented as **transcoded**, not original bytes — this breaks the "byte-identical to what's on the frame" hash assumption the whole diff engine relies on, on top of the already-known `md5_hash`-is-null-for-video problem on the Aura side. Two independent reasons video sync needs its own design, not a copy-paste of the photo path

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `google-auth` 2.57.0 | `google-auth-oauthlib` 1.4.1 | Both released same day (2026-08-24) from the same `googleapis` org; `google-auth-oauthlib` depends on `google-auth`, no version conflict at these versions |
| `google-auth` 2.57.0 | Python 3.14 | Classifier-confirmed 3.10–3.14 support (VERIFIED via PyPI project page) |
| `google-auth-oauthlib` 1.4.1 | Python 3.14 | Classifier-confirmed 3.10–3.14 support (VERIFIED via PyPI project page) |
| `tomli-w` 1.2.0 | Python 3.14 | Universal wheel (`py3-none-any`), `>=3.9` — no version-specific concern (VERIFIED) |
| `tenacity` 9.1.4 | Python 3.14 | 3.14 support landed in 9.1.3, carried into 9.1.4 (VERIFIED) — relevant only if the "what NOT to add" recommendation is overridden |
| `httpx` 0.28 (existing) | Google Picker/Library REST APIs | No SDK compatibility concern — these are plain HTTPS JSON REST APIs; `httpx` needs no Google-specific support, only a `Bearer` token from `google-auth`'s `Credentials.token` |

## Sources

- developers.google.com/photos/support/updates (fetched 2026-09-03) — scope removal, effective 2025-03-31, page last updated 2025-08-28. HIGH confidence, primary source
- developers.google.com/photos/overview/authorization (fetched 2026-09-03) — current scope table, confirms no full-library-read scope remains. HIGH confidence, primary source
- developers.google.com/photos/overview/about (fetched 2026-09-03) — API family overview (Picker vs Library). HIGH confidence, primary source
- developers.google.com/photos/picker/guides/get-started-picker (fetched 2026-09-03) — session/poll/list flow. HIGH confidence, primary source
- developers.google.com/photos/picker/guides/sessions (fetched 2026-09-03) — session resource shape, cleanup guidance. HIGH confidence, primary source; exact expiry duration not printed on this page
- developers.google.com/photos/picker/reference/rest/v1/sessions (fetched 2026-09-03) — full `PickingSession` JSON schema (`expireTime`, `pickingConfig.maxItemCount` default 2000, `pollingConfig`). HIGH confidence, primary source
- developers.google.com/photos/picker/guides/media-items (fetched 2026-09-03) — `PickedMediaItem` fields, `baseUrl` 60-minute expiry, `=d`/`=dv` download params, EXIF-minus-location preservation. HIGH confidence, primary source
- developers.google.com/photos/picker/guides/picking-experience (fetched 2026-09-03) — confirms search-driven, non-album-browsable picker UI. HIGH confidence, primary source
- developers.googleblog.com/en/google-photos-picker-api-launch-and-library-api-updates (fetched 2026-09-03) — announcement rationale, no allowlist path mentioned. HIGH confidence, primary source
- developers.google.com/identity/protocols/oauth2/resources/loopback-migration and .../oob-migration (via search, 2026-09-03) — OOB deprecated 2022-10-03; loopback flow still supported for Desktop client type. HIGH confidence, primary source
- developers.google.com/identity/protocols/oauth2/production-readiness/sensitive-scope-verification and restricted-scope-verification (via search, 2026-09-03) — verification tiers exist; exact tier for `photospicker.mediaitems.readonly` not conclusively found. MEDIUM confidence — tier classification is INFERRED, not directly quoted from an authoritative per-scope list
- Web search aggregating multiple 2026-dated sources (Unipile, others) on the 7-day refresh-token-in-Testing-mode rule — MEDIUM-HIGH confidence (consistent across multiple independent 2026 sources, but not a single Google primary-source page with the number printed verbatim in this research pass)
- pypi.org/project/google-auth/ (fetched 2026-09-03) — v2.57.0, released 2026-08-24, Python 3.10–3.14. HIGH confidence, primary source
- pypi.org/project/google-auth-oauthlib/ (fetched 2026-09-03) — v1.4.1, released 2026-08-24, Python 3.10–3.14. HIGH confidence, primary source
- pypi.org/project/google-api-python-client (via search, 2026-09-03) — v2.193.0, "maintenance mode," weekly releases. HIGH confidence, primary source (used to justify NOT adding it, not to recommend it)
- pypi.org/project/tomli-w/ (fetched 2026-09-03) — v1.2.0, released 2025-01-15, universal wheel, Python >=3.9. HIGH confidence, primary source
- pypi.org/project/tenacity (via search, 2026-09-03) — v9.1.4, released 2026-02-07, Python 3.14 support since 9.1.3. HIGH confidence, primary source
- googleapis/google-api-python-client discovery.py + GitHub issue #1594 (via search, 2026-09-03) — confirms discovery-cache-miss workaround (`static_discovery=False`) exists precisely because some APIs (like newer ones) aren't bundled. MEDIUM confidence — used as supporting evidence for the "Picker API likely isn't in the static cache" claim, not directly confirmed for `photospicker` by name

---
*Stack research for: Google Photos album sync integration + write-path reliability, v3.0 milestone*
*Researched: 2026-09-03*
