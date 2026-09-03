# Architecture Research: Google Photos Album Sync onto the v2.0 Pipeline

**Domain:** Adding a second read-side source (Google Photos album) to an existing
facade/Client/DI-seam Python CLI whose write path (`compute_plan`/`execute_plan`) is
already live-verified.
**Researched:** 2026-09-03
**Confidence:** HIGH for everything grounded in the current source tree (cited by
file:line below); MEDIUM for the Google Photos API mechanism itself (albums.list vs
Picker API vs allowlist — that determination is out of this document's scope and is
flagged as a gating unknown in the build order).

## Recommendation Snapshot

1. New `auraframes/google/` package mirrors the `Client`/`BaseApi` DI seam exactly —
   fully offline-testable via a second `httpx.MockTransport` router in `tests/offline.py`.
2. The user's "download to cache dir, reuse the pipeline unchanged" decision **holds for
   `compute_plan`/`execute_plan` but not for `scan_directory`**. A pruned cache dir cannot
   by itself distinguish "already synced, still in the album" from "removed from the
   album" — both look like "absent from the directory." A small persisted
   `google_media_id → md5_hash` manifest is the missing piece; it lets a NEW function
   reconstruct a `ScanResult`-shaped local-hashes dict without needing every previously
   synced file physically present, so `compute_plan` is genuinely reused **verbatim**, not
   `scan_directory`.
3. Identity: persist the manifest at upload time (from bytes you already hashed to
   upload), don't re-derive it by re-downloading every run. Re-download only for
   media items the manifest has never seen.
4. `compute_plan`'s existing 4-way classifier (`auraframes/sync.py:222-297`) needs **zero
   changes** for mirror semantics — "removed from album" and "re-added to album" are just
   two different `demand` dict outcomes, which the classifier already handles.
5. One `WriteBudget` per run (not per pair), because the anti-abuse surface is
   per-*account*, not per-frame — confirmed by `_build_write_budget` keying the state
   file on `sha1(email)` (`auraframes/cli.py:284-300`), not on frame id.
6. The 401-retry fix splits across two layers by necessity, not preference: `Client`
   classifies (parallel to its existing 429/475 handling), `execute_plan` (or a small
   shared helper) orchestrates the relogin, because only the `Aura`/caller layer can
   reach `aura.login()`.
7. Reliability work (401 retry, placeholder reconciliation, `.png`/`.heic` upload
   support) must land **before** Google integration — not as a preference, but because
   `_prep_upload` (`auraframes/sync.py:348-377`) currently raises closed on both
   extensions Google albums will routinely contain.

---

## 1. Where the Google client lives, and its shape

### Existing pattern being mirrored

The Aura side has exactly one DI seam, and it is narrow and disciplined:

- `Client.__init__(self, history_len=30, transport: httpx.BaseTransport | None = None)`
  (`auraframes/client.py:101`) wraps a single `httpx.Client(transport=transport, ...)`.
  Nothing above it constructs `httpx.Client` directly.
- `Aura.__init__(self, client: Client | None = None)` (`auraframes/aura.py:25`) accepts
  an already-built `Client`, defaulting to a real one only when none is passed.
- `BaseApi` (referenced throughout `auraframes/api/*.py`) holds the injected `Client`
  and does nothing else.
- `tests/offline.py:offline_aura()` (line 62) composes `Aura(client=Client(transport=
  httpx.MockTransport(make_router(...))))` — the exact two-seam composition every
  offline test in `tests/test_*.py` uses.

This is the template to mirror exactly, not just "be inspired by."

### Proposed layout

```
auraframes/google/
    __init__.py
    client.py       # GoogleClient — same shape as auraframes/client.py:Client
    auth.py         # OAuth loopback flow, refresh-token load/save/refresh
    api.py          # GooglePhotosApi (or split album.py / mediaitem.py) — mirrors
                     #   auraframes/api/frameApi.py's role: thin REST wrapper, hydrates
                     #   typed results, zero business logic
    manifest.py      # google_media_id -> md5_hash persisted mapping (answers Q2/Q3)
    download.py       # concurrent media-item download into the cache dir (answers Q7)
    config.py         # N-albums-to-N-frames mapping load/save (answers Q5)
```

`GoogleClient` should be **structurally identical** to `auraframes/client.py:Client`:

```python
class GoogleClient:
    def __init__(self, token_provider, history_len: int = 30,
                 transport: httpx.BaseTransport | None = None):
        self.http_client = httpx.Client(
            base_url='https://photoslibrary.googleapis.com/v1',
            transport=transport,
        )
        self._token_provider = token_provider  # zero-arg callable -> bearer token str
```

The one deliberate deviation from `Client`: Aura's `Client` mutates its own header dict
once, after login (`Aura.login`, `auraframes/aura.py:49-52`, calling
`Client.add_default_headers`). Google's bearer token can expire and refresh **mid-run**
(access tokens are short-lived; only the refresh token is long-lived), so `GoogleClient`
should pull a fresh token per request via an injected `token_provider()` callable rather
than a one-time header mutation. That callable is exactly the injection seam that keeps
this offline-testable: tests pass `token_provider=lambda: 'fake-token'` and never touch
`auth.py`'s real OAuth flow at all.

`GooglePhotosApi` mirrors `FrameApi`/`AssetApi`: constructor takes the `GoogleClient`,
methods return typed results (a lightweight `MediaItem` dataclass — pydantic is fine too,
matching the project's existing "pydantic for API DTOs" convention from
`auraframes/models/`), zero mutation of anything Aura-side.

### Extending the offline harness

`tests/offline.py` currently has one router (`make_router`, lines 22-59) keyed on Aura's
`/v5/...` paths, and one composer (`offline_google_aura`, wait — `offline_aura`, line 62).
Add a parallel, independent pair:

```python
def make_google_router(overrides: dict | None = None):
    # same shape as make_router: dispatch on request.url.path, canned JSON fixtures
    ...

def offline_google(overrides: dict | None = None):
    from auraframes.google.client import GoogleClient
    transport = httpx.MockTransport(make_google_router(overrides))
    return GooglePhotosApi(GoogleClient(token_provider=lambda: 'fake-token', transport=transport))
```

This is additive — it does not touch `make_router`/`offline_aura`, matching the
project's own precedent of `tests/offline.py`'s docstring ("this is a plain module of
functions... `tests/conftest.py`'s existing `aura` fixture... is a separate concern and
is left untouched," `tests/offline.py:1-8`). A test that exercises a full album→frame
pair composes **both** fixtures independently — `offline_aura()` for the frame side,
`offline_google(...)` for the album side — and calls the new integration function with
both, exactly as real code will.

**Why this matters (the downstream consumer's stated concern):** every write-path test
in this codebase (`test_execute_plan.py`, `test_cli_apply.py`, `test_write_throttling.py`,
etc.) is offline today because of this exact DI pattern. A Google client that can only be
exercised against the live API would be the first architectural regression in the
project's history — it would force `@live`-only testing for the one part of the system
that changes most (album membership, a moving target by definition, more so even than
the Aura API).

---

## 2. The source abstraction — the most important question

### The user's decision, stated precisely

> "download to a local cache dir, then reuse the proven v2.0 content-hash diff/upload
> pipeline unchanged; cache pruned once uploads confirm"

Two claims are bundled here: (a) reuse `compute_plan`/`execute_plan` unchanged, and (b)
prune the cache once uploads confirm. Claim (a) is correct and achievable. Claim (b), if
implemented naively by literally re-running `scan_directory()` over a pruned cache dir
every run, **breaks the diff's correctness**. They are not in tension once you see why —
but confusing them (as "just call scan_directory on the cache dir" would) is the exact
bug this document exists to prevent shipping.

### Should there be a generic "PhotoSource" abstraction?

No — and the reasoning matters more than the conclusion. Look at what `compute_plan`
actually consumes:

```python
def compute_plan(local_hashes: dict[str, list[Path]], frame_assets: list,
                  skipped_non_image: int = 0) -> SyncPlan:
```

(`auraframes/sync.py:222`). It takes a `dict[str, list[Path]]` — a hash-to-paths map —
and a count. That's it. `scan_directory()` (`auraframes/sync.py:162-200`) is *one producer*
of that shape; it is not the shape's owner, and `compute_plan` has no dependency on
`scan_directory` beyond consuming its `ScanResult.local_hashes` field. A "PhotoSource"
protocol with a `.scan() -> ScanResult` method would just rename this already-minimal
seam without adding anything — `compute_plan`'s signature *is* the abstraction. Building
a formal `Protocol`/ABC on top would be over-engineering for two producers, and it would
tempt someone to also route `Path`-shaped items through a generic "MediaRef" wrapper,
which then has to leak all the way down into `_prep_upload` (`auraframes/sync.py:348-377`,
takes a literal `Path`) and `execute_plan` (`auraframes/sync.py:380-389`, `plan.to_upload:
list[Path]`) for zero behavioral gain. **Don't build it.** Instead, write a new function
that *produces the same shape `scan_directory` produces*, and hand its output to the
existing `compute_plan` call site unchanged.

### Where "reuse unchanged" breaks: the pruned-cache correctness problem

Confront it directly. `scan_directory`'s contract is: *walk this directory; whatever
files are physically present ARE the desired state.* That contract is sound for a
user-owned photo directory (v2.0's actual use case) because the user IS the source of
truth — a file's absence unambiguously means "I don't want this here."

A Google album cache dir violates that contract the moment pruning is introduced,
because absence from the cache dir becomes **ambiguous** between two states that must be
classified oppositely:

| Cache dir state | What actually happened | Correct classification |
|---|---|---|
| File absent (pruned after a *previous* successful upload) | Media item is **still in the album**, just already synced and its local copy was reclaimed | `unchanged` (or `to_reshow` if hidden) — do NOT touch the frame |
| File absent (never downloaded, or pruned, and the item **left the album**) | Media item is **no longer in the album** | `to_delete`/hide candidate |

If you literally call `scan_directory(cache_dir)` after pruning, both rows above produce
the *identical* signal — "this hash is not in `local_hashes`" — because the file isn't
there either way. Fed into `compute_plan`, case 1 silently regresses into case 2: **every
already-synced photo gets hidden on the frame on the very next run**, the run after its
cache copy is reclaimed, even though it never left the album. This is not a hypothetical
edge case; it is the *steady state* of the feature once caching is working as designed
(most items, most runs, will be "already synced, cache pruned").

The cache directory alone cannot resolve this. Resolving it requires a second signal
that survives pruning: **the album's own current listing**, cross-referenced against a
**persisted record of what you already know the hash of**. That's the manifest.

### The fix: a manifest-backed `local_hashes` builder, not a directory walk

New function, `auraframes/google/download.py:build_wanted_hashes()` (naming is the
planner's call; shape is what matters), returning the exact `ScanResult`-compatible pair
`compute_plan` already expects:

```python
def build_wanted_hashes(album_items: list[MediaItem], manifest: AlbumManifest,
                         cache_dir: Path, google_client, *, max_workers: int = 8
                         ) -> tuple[dict[str, list[Path]], int]:  # (local_hashes, skipped_non_image)
    local_hashes: dict[str, list[Path]] = {}
    skipped = 0
    to_download = []
    for item in album_items:
        if not item.mime_type.startswith('image/'):
            skipped += 1
            continue
        known_hash = manifest.hash_for(item.id)
        if known_hash is not None:
            # Already synced at some point AND still present in the album's
            # current listing right now -- contributes demand WITHOUT needing
            # the file to exist in the (possibly pruned) cache dir at all.
            local_hashes.setdefault(known_hash, []).append(_placeholder_path(item))
        else:
            to_download.append(item)  # new to us -- must download to learn its hash

    downloaded = download_concurrently(to_download, cache_dir, google_client, max_workers)
    for item, path in downloaded:
        h = get_md5(path.read_bytes())          # same helper scan_directory uses
        manifest.record(item.id, h)               # persist for future runs
        local_hashes.setdefault(h, []).append(path)

    manifest.save()
    return local_hashes, skipped
```

This is the load-bearing design point: the function above iterates the **album's current
listing**, not the filesystem. A media item's absence from the album listing is now the
*only* thing that removes its hash from `local_hashes` — cache pruning has no bearing on
correctness at all, because a pruned-but-still-in-album item contributes its hash from
`manifest.hash_for(item.id)` without ever touching disk. This is exactly what makes
"not in album" and "not downloaded yet" distinguishable: the manifest is keyed by
`google_media_id` (a stable identity Google *does* provide — see §3), so an item's hash
is either known (regardless of local file presence) or unknown (must download once,
never again).

`compute_plan(local_hashes, frame_assets, skipped_non_image)` is then called **exactly
as `run_sync` calls it today** (`auraframes/cli.py:392`) — genuinely verbatim, no new
parameter, no branch inside `compute_plan` for "this came from Google." That is the
concrete, checkable meaning of "reuse the pipeline unchanged": it is true of
`compute_plan`/`execute_plan`, and false of `scan_directory`, and the roadmap should say
so explicitly rather than imply `scan_directory` itself gets called on a cache dir.

### Why not the alternative ("never prune the cache")?

The simplest fix to the correctness problem above is to just never prune — keep every
downloaded file forever, so the cache dir genuinely is a durable mirror and
`scan_directory` stays correct unchanged. This is architecturally the *simplest* option
and worth naming as the fallback if the manifest is deprioritized. It loses to the
manifest approach on two counts the user's own requirement text raises: (1) it
contradicts the explicit decision ("cache pruned once uploads confirm" is stated as a
requirement, not an implementation detail up for grabs), and (2) it doesn't bound disk
usage — a large album re-synced over years accumulates full-resolution image bytes
forever, where the manifest accumulates one hash string (~32 bytes) per media item
forever. The manifest is the `WriteBudget`-shaped answer: small, JSON, atomic-written,
corrupt-tolerant (see `auraframes/ratelimit.py:136-178`'s save/load pattern, which
`AlbumManifest` should copy near-verbatim) — cheap enough to keep forever even though the
images themselves are not.

### `frame_no_hash` / video handling folds in for free

`compute_plan` already excludes hashless frame assets from both `unchanged` and
`to_delete`, counting them separately (`auraframes/sync.py:263-268`,
`frame_no_hash`). The Google side's `build_wanted_hashes` mirrors this by filtering
non-`image/*` mime types into its own `skipped` counter (matching `ScanResult.
skipped_non_image`, `auraframes/sync.py:157-159`) before they ever reach the demand
dict — exactly the "photos only, videos skipped with a reported count" requirement,
using the same reporting shape `run_sync` already prints (`auraframes/cli.py:442-446`).

---

## 3. Identity and the content-hash diff

Google Photos Library API `mediaItem`s have a stable `id` and rich `mediaMetadata`, but
— unlike Aura's `Asset.md5_hash` (`auraframes/models/asset.py`, populated server-side
and exposed directly) — **no MD5 or other content hash in the API response.** Two ways
to establish the hash `compute_plan` needs:

**Option A — hash by downloading before diffing.** Download every album item's bytes on
every run, hash locally with the same `get_md5()` (`auraframes/aws/s3client.py:15-16`)
`scan_directory` already uses, discard bytes if unwanted. Correct by construction — you
always know the true current hash.

**Option B — persist `google_media_id -> md5_hash` after the first successful hash
(download-once or upload-once), reuse it on every subsequent run.** This is the manifest
from §2.

**Recommendation: B, with A as the unavoidable fallback for items the manifest has never
seen.** Consequences, worked through against the three concerns raised:

- **(a) Dry-run accuracy.** Both are accurate in the common case. B is *cheaper* accuracy
  — a dry-run touches zero bytes for anything the manifest already knows, only network
  calls for the album *listing* (cheap) plus downloads for genuinely new items. A dry-run
  under Option A must download the **entire album** just to report what would happen,
  which is a strange cost model for a command whose whole point is "safe to run
  speculatively."
- **(b) Re-download cost when the cache is pruned.** This is the decisive difference. B
  pays for a re-download of previously-synced items **zero times** after the first sync —
  exactly the payoff the "cache pruned once uploads confirm" decision is trying to buy
  (bounded disk, not bounded network). A pays for it **every run, for every item**,
  which defeats the pruning decision entirely: if you have to re-download the whole
  album to know what's in it, pruning saved you disk at the cost of re-spending the
  network/API-quota bill you were trying to avoid by caching in the first place.
- **(c) Google re-encodes the photo, or the user edits it.** This is B's real weak spot
  and should be named as an accepted limitation, not hidden. Google Photos Library API
  media items keep a stable `id` across edits; there is no reliable "content changed"
  signal in the metadata the Library API exposes (no content hash, and `mediaMetadata`
  fields like dimensions can be unchanged even after an edit that alters pixels, e.g. a
  filter). If the user edits a photo in Google Photos, B's manifest entry is now **stale**
  — `compute_plan` will classify the frame's copy as `unchanged` even though the Google
  original has changed, and the frame will silently keep displaying the pre-edit version
  forever. Option A does not have this problem (it always re-derives ground truth). Given
  this is a real, if secondary, correctness gap in the recommended design, the mitigation
  is an **explicit escape hatch**, not a silent gap: a `--refresh-hashes`/`--full-rehash`
  flag (or a periodic background re-hash of some fraction of the manifest per run) that
  forces Option A's behavior for a bounded slice of the album, rather than trying to
  detect edits automatically (which Google's API doesn't give you the metadata to do
  reliably). Document this limitation in the same place the existing "video sync is out
  of scope" limitation is documented (PROJECT.md Out of Scope), since it is the same
  shape of accepted-tradeoff, not a bug to chase.

---

## 4. Mirror semantics on the existing 4-way classifier

`compute_plan`'s classifier (`auraframes/sync.py:222-297`) already produces exactly the
four outcomes mirror semantics need, and it needs **no code changes** — the mapping is
direct because `build_wanted_hashes` (§2) produces the same `local_hashes` shape
`scan_directory` does, and the classifier only ever looks at that shape plus the frame's
current asset list:

| Google-side event | `demand` dict effect | `compute_plan` outcome (unchanged code) | `execute_plan` action |
|---|---|---|---|
| Photo removed from the album | Its hash drops out of `local_hashes` entirely (§2: manifest keeps the hash on file, but `build_wanted_hashes` never adds it to the returned dict for an item absent from the *current* album listing) | Frame asset with that hash, currently visible → `to_delete` (`sync.py:282-283`) | `exclude_asset` (hide, the default `removal_mode='hide'`, `sync.py:321-323`) |
| Photo re-added to the album | Its hash reappears in `local_hashes` (via the manifest — no re-download, per §3) | Frame asset with that hash, currently hidden → `to_reshow` (`sync.py:277-278`) | `select_asset` re-show (`sync.py:650-679`), which **always runs regardless of `removal_mode`** per the existing docstring (`sync.py:410-413`) |
| Photo already hidden, still absent from album | Demand stays 0, frame asset already hidden | `already_hidden`, no-op (`sync.py:284-285`) | nothing — correctly never re-issues the same hide forever |
| New photo added to album | New hash, no matching frame asset | `to_upload` (`sync.py:287`) | upload chunk (`sync.py:572-649`) |

The one thing that **must** be decided (not a code change, a config default): should the
Google-sourced sync's `removal_mode` default ever be anything other than `'hide'`? The
milestone requirement is explicit — "hidden on the frame, never deleted by default; real
deletion stays opt-in and exact-count-gated exactly as in v2.0" — so the Google sync
entry point should call `execute_plan(..., removal_mode='hide')` (or simply omit the
kwarg, since `'hide'` is already `execute_plan`'s own default, `sync.py:389`) and should
almost certainly **not** expose `--delete`/`--hard-delete` on the Google-sync command the
way `aura-cli sync` does for a human-owned directory — a scheduled/unattended album sync
is exactly the case the hide-by-default design was built for.

**What must change, concretely:** nothing in `compute_plan`, nothing in `execute_plan`'s
core loop structure. The only net-new code is upstream of both: `build_wanted_hashes`
(§2) and the manifest it reads/writes (§3). This is the payoff of designing the source
abstraction as "same output shape" rather than a parallel code path.

---

## 5. The many-to-many config

### Where it lives

Reuse `AURA_STATE_DIR` (`auraframes/utils/settings.py:32`,
`Path(os.getenv('AURA_STATE_DIR', '~/.config/auraframes')).expanduser()`) — the same
directory `WriteBudget`'s per-account state file already lives in
(`auraframes/cli.py:297`, `AURA_STATE_DIR / f'budget-{hash}.json'`). Don't invent a
second config root. Proposed: `AURA_STATE_DIR / 'google-albums.json'`, a flat list:

```json
{"pairs": [{"album_id": "...", "album_title": "Kids 2024", "frame_id": "..."}, ...]}
```

New module `auraframes/google/config.py` with `load_pairs()`/`save_pairs()`, mirroring
`WriteBudget.load`/`save`'s atomic-write-with-corrupt-fallback pattern
(`auraframes/ratelimit.py:136-178`) rather than a bare `json.loads` — this file is
hand-editable/growable and deserves the same "one bad file must never brick every
subsequent run" guarantee the budget state already has.

### Reconciling all pairs in one run

**Each pair gets an independent plan and independent execution**, matching the
project's existing per-item continue-past-failure convention at one level up. The
precedent is direct: `execute_plan` already catches a per-chunk failure and continues to
the next chunk rather than aborting the whole plan (`auraframes/sync.py:633-640` for
uploads, `:702-709` for deletes), and `Aura.download_images_from_assets` collects
per-asset failures into `failed_to_retrieve` rather than raising
(`auraframes/aura.py:86-94`). The new run-all-pairs loop should do the same one layer
up: wrap each pair's (list album → build_wanted_hashes → compute_plan → execute_plan) in
its own try/except, accumulate a `list[PairResult]`, and report a summary with a
non-zero exit if any pair failed — never let pair 2's failure hide whether pair 1
succeeded, and never let it abort pair 3.

One thing that **should not** carry the per-item convention: `RateLimitError` and
`ConsecutiveWriteFailureError` are deliberately *whole-batch* aborts within a single
`execute_plan` call, precisely because they signal an account-wide lockout
(`auraframes/sync.py:127-153`, `:497-502`). If pair 1's `execute_plan` raises
`RateLimitError`, that is evidence the **account**, not just that frame, is throttled —
continuing straight into pair 2's `execute_plan` would just re-trip the same lockout
immediately. The pair-loop's per-pair catch should treat `RateLimitError`/
`ConsecutiveWriteFailureError` specially: log it, and either abort the remaining pairs
outright or (more in keeping with "continue past failure") skip remaining pairs' *apply*
phase but still run their dry-run diff/report, so the operator sees the full picture
without hammering a throttled account further.

### The shared `WriteBudget`

**One `WriteBudget` instance for the whole run, not one per pair.** Confirmed by how the
budget is currently keyed: `_build_write_budget(email, ignore_budget)`
(`auraframes/cli.py:284-300`) derives the state-file name from `sha1(email)[:12]` alone —
there is no frame id anywhere in that key. This is not an oversight; it reflects reality
measured in Phase 09/10 (`PROJECT.md`: "a real ~42-write/~40-min request limit measured
live" and the anti-abuse trip escalating to reject *login* itself, i.e. it's an
account-level lockout, not a per-frame one). Writing to frame A and frame B in the same
run consumes the same account-level Pushd rate-limit bucket, so they must share one
`WriteBudget` instance, constructed once by the new "sync all pairs" command and threaded
into every pair's `execute_plan(..., budget=write_budget, ...)` call. Giving each pair
its own fresh budget would let N pairs collectively spend N× the real per-account
tolerance before any of them individually notices — reintroducing exactly the lockout
the budget exists to prevent.

**Ordering/fairness consequence:** since budget is shared and finite, pair order
determines who gets served first. The simplest, safest default for v3.0 is sequential
processing in config-file order — document plainly that a large first album can exhaust
the run's budget and leave later pairs waiting (or stopping, per `wait_on_budget`).
Round-robin, chunk-by-chunk fairness across pairs is a real architectural improvement
but a materially bigger change (`execute_plan` would need to become chunk-resumable
across pair boundaries, not just within one plan) — flag it as explicit future work
rather than building it into v3.0's first cut.

---

## 6. Credential/token storage

Aura's credential handling is intentionally simple: env vars, read at call time inside
`Aura.login()` (`auraframes/aura.py:42-45`, `os.getenv('AURA_EMAIL')` /
`os.getenv('AURA_PASSWORD')`) — not at import time, which is exactly the fix already
applied for the historical `load_dotenv()` ordering bug (PROJECT.md: "`Aura.login` now
resolves credentials at call time rather than import time"). A Google refresh token is a
different shape of secret: it's obtained once via an interactive OAuth loopback flow and
must be persisted to survive across runs (there's no equivalent of "just re-type your
password" for a headless cron-style sync).

**Where:** `AURA_STATE_DIR / 'google-token.json'` — the same directory as the write
budget and the new album-pairs config, keeping every piece of this tool's mutable local
state under one root the user already knows about and can `.gitignore` once.

**How it's written:** copy `WriteBudget.save()`'s atomic-write pattern exactly — temp
file in the same directory, then `os.replace()` (`auraframes/ratelimit.py:146-153`) — so
an interrupted write (crash mid-refresh) never leaves a truncated, unparseable token
file. **Unlike** `WriteBudget`'s state file, which the module docstring is explicit is
NOT a secret (`auraframes/ratelimit.py:19-22`, "never the email, password, or any auth
token"), the Google token file genuinely *is* a secret, so it additionally needs
`os.chmod(path, 0o600)` right after the `os.replace()` — `WriteBudget` has no equivalent
because it never needed one.

**Kept out of version control:** the project already has the `.env` precedent for
`AURA_EMAIL`/`AURA_PASSWORD` (loaded via `load_dotenv()` in `cli.py:main`, line 602) — add
`AURA_STATE_DIR`'s default location pattern (or the specific filename) to `.gitignore`
the same way, and document it next to the existing env-var docs.

**How `aura-cli status` reports link state without leaking it:** mirror the existing
convention exactly. `run_status` (`auraframes/cli.py:134-169`) never prints the password
value, only `'set' if password_set else 'NOT SET'` (lines 140-143). A Google line should
follow the identical shape: `Google account: linked (token file present, refreshed
<timestamp>)` or `Google account: not linked` — never print the token, refresh token, or
raw file contents. A stronger check (attempt a real token refresh) is possible but should
be presented as a **separate, explicit** step (e.g. `aura-cli status --check-google`)
rather than folded silently into `status`'s default fast path, since `status` today is
deliberately cheap (config check, then one login call) and a Google token refresh is a
second network round-trip to a second provider.

**Staying injectable for offline tests:** exactly like `run_status(aura=None)`
(`auraframes/cli.py:134`) and `run_inspect`/`run_sync` all accept an injected `Aura`, the
Google-aware status/sync handlers should accept an injected `google_client=None` /
`google_auth=None`, constructed via a factory function analogous to how `Aura()` is only
ever constructed for real inside the CLI handler bodies. Tests inject a fake token
provider (`lambda: 'fake-token'`) and a `MockTransport`-backed `GoogleClient` — the real
`auth.py` OAuth loopback code (browser launch, local HTTP callback listener) is never
imported or exercised by the offline suite, matching how `S3Client()`/`SQSClient()` real
construction is confined to `run_sync`'s apply path only (`auraframes/cli.py:482-483`)
and never appears inside `execute_plan` itself.

---

## 7. Concurrent downloads

Scoped narrowly and deliberately, per the user's decision: concurrency lives **only** in
the Google media-item download step, entirely upstream of `compute_plan`/`execute_plan`.

```
auraframes/google/download.py
    download_concurrently(items, cache_dir, google_client, max_workers=8) -> list[(item, Path)]
```

Implementation: `concurrent.futures.ThreadPoolExecutor` is the right tool here (not
asyncio) — `httpx.Client` instances are thread-safe for concurrent requests from multiple
threads (this is httpx's documented supported usage), so no rewrite of `GoogleClient`
itself is needed, and it keeps this module consistent with the rest of the codebase's
avoidance of an async rewrite (`MOD-01` stays explicitly out of scope per PROJECT.md).

**The seam that keeps this from leaking:** `download_concurrently`'s return value feeds
directly into `build_wanted_hashes` (§2), whose own return value (`local_hashes`,
`skipped_non_image`) is indistinguishable in shape from `scan_directory`'s
`ScanResult`. By the time `compute_plan(local_hashes, frame_assets, skipped)` is called
(`auraframes/sync.py:222`), every trace of "this came from N concurrent HTTP requests" is
gone — `compute_plan` is pure and synchronous exactly as it is today, and
`execute_plan`'s upload loop (`auraframes/sync.py:572-649`) processes `plan.to_upload`
sequentially, chunked, throttled — **unchanged**, because those `Path` objects are
already-downloaded local files by the time `execute_plan` ever sees them. Concurrency
never touches the Aura `Client` (`auraframes/client.py`) or the Pushd write surface at
all; it only ever talks to `photoslibrary.googleapis.com`.

---

## 8. Reliability changes: where they belong

### Retry-once-on-401-with-fresh-login

This genuinely needs **both** layers, not as a hedge but because of a real dependency
the two layers don't share.

**What `Client` can and can't do.** `Client._raise_if_rate_limited`
(`auraframes/client.py:164-192`) already turns two specific status codes (429, 475 —
`_RATE_LIMIT_STATUS_CODES`, line 25) into a named `RateLimitError` before the generic
`response.raise_for_status()` runs. A plain 401 is *not* in that set, so today it
surfaces as a bare `httpx.HTTPStatusError` from `raise_for_status()` — an anonymous,
unclassified exception a caller has to string-match or status-code-sniff to recognize.
`Client` has everything it needs to **classify** a 401 the same deliberate way it already
classifies 429/475: add a parallel check, raise a new named `AuthExpiredError` (or
similar) carrying the status code, mirroring `RateLimitError`'s shape
(`auraframes/client.py:28-55`). This benefits every caller uniformly, read paths
included, for the cost of one more `if` branch next to an existing one.

What `Client` **cannot** do is the actual fix: refreshing the token requires calling
`AccountApi.login()` again (`auraframes/api/accountApi.py`), which requires credentials
and constructs a new `User`/token — that is `Aura`-level orchestration, and `Client` has
no reference to `Aura`, deliberately (`BaseApi` injects `Client` downward, never the
reverse — see `ARCHITECTURE.md`'s own "Circular imports: None detected" constraint,
`.planning/codebase/ARCHITECTURE.md`). Giving `Client` a callback into `Aura.login()`
would invert that dependency and smuggle Aura-specific business logic (what does
"login" even mean, generically, to an HTTP client?) into the one layer the codebase has
kept deliberately dumb. **Don't do it.**

So the relogin *orchestration* has to live where `aura` is already in scope —
`execute_plan` already takes `aura` as a parameter (`auraframes/sync.py:380`), which is
exactly STATE.md's own recommendation ("retry once on HTTP 401 with a fresh login inside
`execute_plan`"). Concretely: a small internal helper inside `auraframes/sync.py`,

```python
def _with_relogin_retry(fn, aura):
    try:
        return fn()
    except AuthExpiredError:
        aura.login()          # mutates Client.http2_client.headers in place
        return fn()             # retried once; a second failure propagates
```

wrapping each of `execute_plan`'s four write call sites (`select_asset` for uploads
`sync.py:595-597`, `batch_update` `sync.py:604`, `select_asset` for reshows `sync.py:658`,
and the removal primitive `sync.py:692`). `aura.login()` mutating
`Client.http2_client.headers` **in place** (`auraframes/aura.py:49-52`,
`add_default_headers`) is what makes this transparent to already-constructed
`aura.frame_api`/`aura.asset_api` objects — they hold the same shared `Client` reference
via `BaseApi`, so nothing needs to be re-wired after a relogin.

**Offline-testability preserved:** `execute_plan` already accepts `aura` as an injected
fake (every test in `test_execute_plan.py` does exactly this via `offline_aura()`), and
STATE.md's own Phase 08-02 decision already establishes the precedent this reuses
("Partial-failure tests monkeypatch `aura.asset_api.batch_update`/`aura.frame_api.
remove_asset` directly rather than relying on `httpx.MockTransport` per-payload
discrimination"). A 401-retry test monkeypatches one of those methods to raise
`AuthExpiredError` once then succeed, and asserts `aura.login` was called exactly once —
zero network, zero real OAuth, consistent with every other test in this suite.

### Placeholder-row reconciliation

Scoped narrowly: this is cleanup of **existing bad data**, not part of the ongoing sync
loop, and it does not threaten the Google-source design in §2-4 — `compute_plan` already
excludes hashless assets (no `md5_hash`) from both `unchanged` and `to_delete`, counting
them separately as `frame_no_hash` (`auraframes/sync.py:263-268`). Placeholder rows (no
`uploaded_at`/`file_name`/`md5_hash`) are hashless by definition, so they're already
invisible to the diff engine — Google-sourced syncs inherit that same correct exclusion
for free, with no additional code.

Since neither existing primitive clears them (`delete_asset` 200-and-no-op,
`remove_asset` 404 — PROJECT.md), this needs a genuinely new mechanism, which is
unknown pending further research (possibly no client-side fix exists at all, and the
honest answer is "report clearly, cannot remove"). Recommend a small, separate module
(e.g. `auraframes/reconcile.py`) and CLI verb, decoupled from both the Aura write path
and the Google integration — it's useful regardless of whether Google sync ships, and
bundling it into either would blur its actual scope (data hygiene on existing frame
state, not a sync-time concern).

---

## New vs. Modified — Explicit Breakdown

**New files:**

| File | Purpose |
|---|---|
| `auraframes/google/__init__.py` | package marker |
| `auraframes/google/client.py` | `GoogleClient` — transport-injectable HTTP wrapper, mirrors `auraframes/client.py:Client` |
| `auraframes/google/auth.py` | OAuth loopback flow, refresh-token load/save/refresh |
| `auraframes/google/api.py` | `GooglePhotosApi` — thin REST wrapper (list album items, etc.), mirrors `auraframes/api/frameApi.py` |
| `auraframes/google/manifest.py` | `google_media_id -> md5_hash` persisted mapping; atomic save/load mirroring `WriteBudget` |
| `auraframes/google/download.py` | `download_concurrently()` + `build_wanted_hashes()` — the source-shape producer that replaces `scan_directory` for this source |
| `auraframes/google/config.py` | N-albums↔N-frames pair config load/save |
| `auraframes/reconcile.py` | Placeholder-row identification/reporting (independent of Google work) |
| `tests/offline.py` additions | `make_google_router()`, `offline_google()` — additive, alongside existing `make_router`/`offline_aura` |
| `tests/test_google_*.py`, `tests/test_reconcile.py` | new offline test files |

**Modified files:**

| File | Change |
|---|---|
| `auraframes/client.py` | Add `AuthExpiredError` classification for HTTP 401, parallel to the existing `_raise_if_rate_limited` 429/475 handling (`client.py:164-192`) |
| `auraframes/sync.py` | Add `_with_relogin_retry` helper; wrap the four write call sites in `execute_plan`; add `_DATA_UTI_BY_SUFFIX` entries (or a Pillow-based UTI resolution) for `.png`; `.heic` needs a decoder dependency decision (no Pillow HEIC support in this environment today — a real, separate blocker, not just a mapping-table edit) |
| `auraframes/cli.py` | New subcommand(s) for Google album sync / status extension; construct `GoogleClient`/`WriteBudget` at the CLI boundary only, mirroring existing `S3Client()`/`SQSClient()` construction confinement (`cli.py:482-483`) |
| `auraframes/utils/settings.py` | Possibly new `AURA_GOOGLE_*` env vars (client id/secret if user-supplied OAuth app, though Google Installed-App flow does not require a client secret to be kept confidential the way a server app would) |
| `.gitignore` | Add the Google token file / confirm `AURA_STATE_DIR`'s default location is covered |
| `pyproject.toml` | New dependency: `google-auth-oauthlib` (or equivalent) for the loopback flow; `httpx` alone is enough for the REST calls once a token exists |

**Explicitly NOT modified:** `auraframes/sync.py:compute_plan` (§2, §4),
`auraframes/sync.py:scan_directory` (kept as-is for the local-directory use case —
`aura-cli sync <dir>` is unaffected), `auraframes/ratelimit.py` (§5 — reused as a shared
instance, no code change), `auraframes/aws/*` (Google downloads never touch S3/SQS —
uploads to the frame still go through the existing `S3Client`/`SQSClient` regardless of
source).

---

## Data Flow: One Album → Frame Sync Run

```
1. CLI entry point reads auraframes/google/config.py's pairs list
   (AURA_STATE_DIR/google-albums.json)

2. For each (album_id, frame_id) pair, independently (§5):

   a. aura.login()                                   [existing, auraframes/aura.py:35]
      -- once per run if reused across pairs; Client's shared header mutation
         means subsequent pairs' Aura calls are already authenticated

   b. GooglePhotosApi.list_album_items(album_id)      [NEW, auraframes/google/api.py]
      -- paginated, mirrors FrameApi.get_assets's cursor loop shape

   c. build_wanted_hashes(items, manifest, cache_dir, google_client)
                                                       [NEW, auraframes/google/download.py]
      -- for each item already in the manifest: contribute its known hash,
         no download (§2/§3)
      -- for each item NOT in the manifest: download concurrently (§7),
         hash with the existing get_md5() [auraframes/aws/s3client.py:15],
         record in the manifest
      -- returns (local_hashes, skipped_non_image) -- ScanResult-shaped

   d. assets = aura.get_all_assets(frame_id)          [existing, auraframes/aura.py:59]

   e. plan = compute_plan(local_hashes, assets, skipped_non_image)
                                                       [existing, UNCHANGED, sync.py:222]

   f. write_budget = shared WriteBudget for the whole run (constructed once,
      before the pair loop, keyed by account email)   [existing, cli.py:284-300]
      geo_check = shared, if configured               [existing, cli.py:303-312]

   g. result = execute_plan(plan, aura, frame_id,
                             s3_client=S3Client(), sqs_client=SQSClient(),
                             budget=write_budget, geo_check=geo_check,
                             removal_mode='hide')       [existing, UNCHANGED, sync.py:380]
      -- internally now includes the 401-relogin-retry wrapper (§8) on every
         write call site

   h. manifest.save()  -- persist any newly-learned hashes even if execute_plan
      partially failed, so a re-run doesn't re-download successfully-hashed
      items

   i. record PairResult (succeeded/failed + counts); continue to next pair
      regardless of outcome, EXCEPT a RateLimitError/ConsecutiveWriteFailureError
      escalates to "stop applying further pairs this run" (§5)

3. Print a per-pair summary + aggregate exit code (0 only if every pair's
   execute_plan had zero failures)
```

---

## Suggested Build Order

Respects two constraints simultaneously: the user's explicit reliability-first
sequencing, and the hard technical dependency that nothing Google-shaped can be tested
end-to-end before the OAuth/client plumbing exists.

**Phase A — Write-path reliability (blocks everything after it that writes)**

1. `Client` 401 classification (`AuthExpiredError`) + `execute_plan` relogin-retry
   helper. Do this first, not last, because every subsequent phase's live testing will
   otherwise keep hitting the same ~4-in-10 spurious failure the fix removes — doing it
   last means debugging Google integration issues through a noise floor that didn't need
   to be there.
2. `.png`/`.heic` upload support (`_DATA_UTI_BY_SUFFIX`, `_prep_upload`,
   `auraframes/sync.py:64,357-359`) — **hard-blocks** Google sync, not just "nice to
   have": Google albums routinely contain both, and `_prep_upload` currently raises
   `ValueError('Unsupported upload extension')` for both. Note `.heic` is not just a
   mapping-table edit — Pillow has no HEIC decoder in this environment (module docstring,
   `sync.py:58-63`), so this item may itself split into "add a HEIC decoder dependency"
   as its own sub-task.
3. Placeholder-row reconciliation (`auraframes/reconcile.py`) — independent of Google,
   sequenced early per the user's stated priority and because it also fixes
   `test_read_03_pagination`.
4. (Optional, lower priority) `batch_update` partial-success validation code-review
   finding — can slide past the phases below if time-constrained.

**Phase B — Google client plumbing (no album logic yet)**

5. `auraframes/google/client.py` (`GoogleClient`), `auraframes/google/auth.py` (OAuth
   loopback + token persistence per §6), `tests/offline.py` extensions
   (`make_google_router`/`offline_google`). Validate via a link-state check
   (`aura-cli status`-shaped), no album/sync code yet.
6. **Gating research spike, not a build task:** resolve the album-discovery mechanism
   (true `albums.list` vs Picker API "choose once, remember it" vs allowlist
   application). This determines whether `auraframes/google/api.py` needs a
   `list_albums()` method at all, or whether album selection is a one-time interactive
   step whose result (an opaque album reference) gets written straight into
   `google-albums.json` (§5) without ever enumerating "all my albums." Do not finalize
   `api.py`'s shape before this resolves.

**Phase C — Source integration on a single pair (proves the hard part before scaling)**

7. `auraframes/google/manifest.py` (§2/§3) + `build_wanted_hashes()`
   (`auraframes/google/download.py`) — the crux piece. Prove `compute_plan` is reused
   genuinely unchanged against Google-sourced `local_hashes` for one hard-coded
   album/frame pair before generalizing.
8. Concurrent download (§7) inside `download.py` — layer this in after step 7's
   correctness is proven sequentially; concurrency is a performance concern, not a
   correctness one, and should not be debugged simultaneously with the manifest logic.
9. Live UAT of one album → one frame, including a deliberate "remove a photo from the
   album, re-run, confirm it hides not deletes; re-add it, re-run, confirm it re-shows
   without re-upload" pass — this is the single most important live verification in the
   whole milestone, since it's the one behavior (§4) that only manifests over two runs.

**Phase D — Many-to-many + polish**

10. `auraframes/google/config.py` (N-pairs) + the per-pair loop with shared `WriteBudget`
    (§5).
11. `aura-cli status` Google link-state line (§6); video-skip-with-count reporting
    wiring (already free per §2, just needs CLI plumbing).
12. Full live UAT across multiple pairs, including one deliberately-failing pair to
    confirm the continue-past-failure contract (§5) holds.

**Why this order and not, say, Google-first:** Phase A's items are cheap, already fully
specified (STATE.md already names the exact fix), and every later phase's live testing
benefits from them being done — building Google integration on top of the current
401-flaky write path means every live test run has a coin-flip-shaped false-failure mode
baked in, which is expensive noise during the hardest, most novel part of this milestone
(§2/§3's manifest design). Phase B before Phase C is a hard dependency (nothing to sync
without a client). Phase C proves the single-pair case before Phase D generalizes to N
pairs, matching this project's own established precedent (v2.0 proved single-item
sync/execute before Phase 9 added batching/anti-abuse hardening on top) — many-to-many
is additive risk, not foundational risk, and should not be built before the foundation
it multiplies is trusted.

---

## Anti-Patterns to Avoid

**Calling `scan_directory()` directly on the Google cache dir.** The single most
tempting shortcut this document argues against (§2) — it is the literal reading of
"reuse the pipeline unchanged" and it is wrong the moment the cache is pruned. Use
`build_wanted_hashes()` instead; it produces the same shape but sources demand from the
album listing + manifest, not a directory walk.

**A generic `PhotoSource` protocol/ABC.** Over-engineering for two producers of one
already-minimal shape (`dict[str, list[Path]]` + a count). Adds indirection without
adding testability or flexibility `compute_plan`'s existing signature doesn't already
provide.

**Giving `Client` a callback into `Aura.login()`.** Inverts the codebase's one clean
dependency direction (`BaseApi`/`Client` never know about `Aura`) to solve a problem
(relogin orchestration) that belongs one layer up anyway.

**A `WriteBudget` per album/frame pair.** Defeats the budget's entire purpose — the
anti-abuse surface it protects against is account-wide, confirmed by how the existing
code keys the budget's state file (email hash, not frame id).

**Treating placeholder-row reconciliation as part of the sync loop.** It's data hygiene
on existing bad state, decoupled from both the Aura write path's ongoing operation and
the Google integration; bundling it into either blurs a already-narrow, already-risky
scope.

---

## Open Questions / Gating Unknowns

- **Album discovery mechanism** (Picker API vs `albums.list` vs allowlist) — resolves
  the actual shape of `GooglePhotosApi`'s album-listing surface (or absence thereof) and
  whether "many albums" config entries come from enumeration or one-time interactive
  picks. This document's design is written to be indifferent to the answer (the manifest/
  `build_wanted_hashes` design only needs "list the current media items of a known album
  reference," not "enumerate all my albums"), but the CLI UX for *adding* a pair to the
  config differs materially between the two mechanisms.
- **HEIC decode support.** No Pillow HEIC decoder is present in this environment today
  (`auraframes/sync.py:58-63`'s own comment). Google Photos albums will contain `.heic`
  files from iPhone users; `_prep_upload` needs *some* way to read dimensions
  (`Image.open(path).size`, `sync.py:362-363`) even if the UTI mapping problem is solved
  separately. This is a dependency decision (e.g. `pillow-heif`) that Phase A item 2
  should surface explicitly rather than assume away.
- **Edited-photo staleness** (§3c) — accepted as a documented limitation with an
  escape-hatch flag rather than solved; worth a deliberate product decision (how
  aggressively to auto-invalidate manifest entries, if at all) rather than leaving it
  implicit.

---

## Sources

- Direct source reads (all file:line citations above): `auraframes/sync.py`,
  `auraframes/client.py`, `auraframes/aura.py`, `auraframes/cli.py`,
  `auraframes/ratelimit.py`, `auraframes/utils/settings.py`, `auraframes/api/frameApi.py`,
  `auraframes/models/asset.py`, `auraframes/aws/s3client.py`, `auraframes/aws/awsclient.py`,
  `auraframes/export.py`, `tests/offline.py`, `tests/conftest.py`,
  `tests/test_execute_plan.py`, `pyproject.toml` — HIGH confidence, primary source.
- `.planning/PROJECT.md`, `.planning/STATE.md`, `.planning/codebase/ARCHITECTURE.md`,
  `.planning/codebase/INTEGRATIONS.md` — HIGH confidence for decisions/history already
  recorded by this project; `INTEGRATIONS.md` is stale (dated 2026-06-29, predates the
  DI seam and v2.0) and was used only for the pre-v1.1 baseline picture, not for current
  behavior.
- Google Photos Library API's lack of a content-hash field in `mediaItem`/`mediaMetadata`
  and the March 2025 scope restriction are asserted per this milestone's own PROJECT.md
  framing ("Google restricted the Photos Library API's broad read scope around March
  2025") — MEDIUM confidence, not independently re-verified against current Google
  documentation in this pass; the mechanism itself is explicitly flagged above as a
  gating unknown for a dedicated research pass, not resolved here.

---
*Architecture research for: Google Photos album sync integration onto the Aura Frames
Python client (v3.0 milestone)*
*Researched: 2026-09-03*
