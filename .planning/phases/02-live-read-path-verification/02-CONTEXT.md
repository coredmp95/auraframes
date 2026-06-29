# Phase 2: Live Read-Path Verification - Context

**Gathered:** 2026-06-29
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase **proves the revived client performs the full read path against the live
Aura API** using real account credentials. The read path is, in order:

1. **Login** (READ-01) — authenticate against `api.pushd.com/v5/login.json`, obtain
   `auth_token` + `user.id`, inject `x-token-auth` / `x-user-id` headers.
2. **List frames** (READ-02) — `GET /frames.json`, print frame names + ids.
3. **Fetch assets** (READ-03) — `GET /frames/{id}/assets.json`, iterating **all** pages
   via cursor-based pagination.
4. **Download one image** (READ-04) — pull one asset from the image proxy to disk with
   **EXIF datetime + GPS readable** in the saved file.

In scope: a live integration test that exercises and asserts each step, plus the
**minimal, targeted code changes needed to make verification trustworthy** (error
surfacing, pagination parametrization, secret redaction, EXIF-failure surfacing) — see
Implementation Decisions.

Out of scope: the upload round-trip (UP-01), async migration (MOD-01), AWS pool-ID
config (MOD-02), a full typed exception hierarchy (MOD-03), and the run docs +
verification report (Phase 3). Mode: **MVP** — change only what's needed to prove the
read path.

</domain>

<decisions>
## Implementation Decisions

### Verification Harness & Evidence
- **D-01:** Verify via a **live pytest integration test** (e.g. `tests/test_read_path.py`)
  run with `uv run pytest`, **reusing the Phase 1 test harness** (pytest already in the
  dev extra). The pytest pass/fail output is the evidence consumed by the Phase 3 report.
- **D-02:** **Gate live tests so a credential-less run stays green.** Mark them (e.g.
  `@pytest.mark.live`) and **auto-skip when `AURA_EMAIL`/`AURA_PASSWORD` are unset**, so
  the default `uv run pytest` still passes on a clean checkout (Phase 1's import smoke
  test must not break). Live verification runs only when credentials are present.
- **D-03:** **One test per READ requirement** (READ-01/02/03/04), sharing a single
  authenticated session via a **login fixture**. Each requirement passes/fails
  independently → cleanest 1:1 evidence mapping for the Phase 3 verification report.

### Pagination Rigor (READ-03)
- **D-04:** **Genuinely exercise the cursor loop.** The default `limit=1000` means a
  small account returns a single page and the cursor branch never runs. The test must run
  the fetch with a **small `limit`** so multiple pages are traversed and the cursor
  handoff is asserted (>1 page seen).
- **D-05:** **Parametrize `Aura.get_all_assets`** — add an optional `limit` parameter so
  the test drives the **real production helper** end-to-end (rather than re-implementing
  pagination in the test). Also **shorten or drop the unconditional `time.sleep(1)` between
  pages** (`auraframes/aura.py:60`) so a small-limit drain isn't painfully slow.
  *Consideration for planner:* draining ALL pages at a tiny limit on a very large frame is
  still many HTTP calls — pick a sensible test `limit` (e.g. 2–3) and a reasonable target
  frame; the goal is proving the cursor mechanism, not stress-testing.

### Error & Drift Surfacing (verification trustworthiness)
- **D-06:** **Minimal error surfacing so a real failure can't masquerade as success.**
  Add `raise_for_status()` in the `Client` request methods (`auraframes/client.py`
  `get`/`post`/`put`/`delete`) **before** `response.json()`, and convert the silent
  `pass`-on-`error`-key spots on the read path (`accountApi.login`, `frameApi.get_assets`)
  into a raised error / explicit log. **No full typed exception hierarchy** — that remains
  MOD-03 / out of scope.
- **D-07:** **Redact secrets from logs.** `client.py` logs the full request body at INFO
  and response at DEBUG, so a live login currently writes the **plaintext password** and
  **`auth_token`** to `logs/file_{time}.log`. Scrub `password` / `auth_token` /
  `x-token-auth` from request+response logging before running live (secrets-out-of-VCS
  constraint).
- **D-08 (must-fix to run):** `_init_logger()` writes to `logs/file_{time}.log` but the
  `logs/` directory is never created → **`FileNotFoundError` on first live run**
  (CONCERNS.md). Ensure `logs/` exists at startup (`os.makedirs('logs/', exist_ok=True)`)
  and that `logs/` (and `cache/`, `asset_images/` output) are **gitignored**.

### EXIF / GPS Strictness & Asset Selection (READ-04)
- **D-09:** **Datetime is mandatory; GPS is conditional.** Always assert
  `DateTimeOriginal` is written and **read it back** from the saved file (reuse
  `exif.get_readable_exif` / piexif load). Require GPS **only when the chosen asset has
  location data**; if no geo-tagged asset exists, assert the GPS-write path ran and
  document the data gap rather than failing.
- **D-10:** **Asset selection is automatic.** Use the **first frame** from `get_frames`;
  from its assets pick the **first with a non-null `location_name`** (so GPS is actually
  exercised), falling back to the first asset if none has a location. No manual config.
- **D-11:** **Surface silent download/EXIF failures + fix the geocoder UA.** The bare
  `except:` blocks in `auraframes/exif.py` (geocode ~line 45, `piexif.insert` ~line 91)
  currently log and return possibly-empty EXIF, so a broken save can look fine — make the
  EXIF-write failure **surface** (don't silently return empty bytes for the verified
  download). Replace the ToS-violating Nominatim `user_agent="Upload Scripting Test"` with
  a proper identifier (e.g. `auraframes-python-client/1.0`).

### Claude's Discretion
- The exact pytest mechanics: fixture scoping, the `live` marker registration, the chosen
  small `limit` value, and how the login fixture exposes the session to the 4 tests.
- Which frame/asset edge cases to tolerate (e.g. video assets — see Deferred); default to
  picking an image asset for the READ-04 download.
- Whether to opportunistically close **D-05 from Phase 1** (the deferred `.dict()` →
  `.model_dump()` migration in `assetApi.py` / `frameApi.py:90`). **It is NOT on the read
  path** (those sites are in update/upload code), so it is optional here — migrate only if
  trivial, otherwise leave for the upload milestone.
- Exact redaction mechanism for D-07 (log filter vs. sanitizing the payload dict).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project & milestone scope
- `.planning/PROJECT.md` — what the client is, core value (login → list → download), the
  in/out-of-scope boundary for this revive milestone.
- `.planning/REQUIREMENTS.md` — **READ-01, READ-02, READ-03, READ-04** are this phase's
  requirements (ENV-04 + DOC-01 are Phase 3). v2/Out-of-Scope lists confirm MOD-01/02/03
  and upload are deferred.
- `.planning/ROADMAP.md` §"Phase 2: Live Read-Path Verification" — goal, the 4 success
  criteria, and the two planned plans (02-01 login+list, 02-02 paginated fetch+download).

### Codebase analysis (read-path mechanics + landmines already mapped)
- `.planning/codebase/INTEGRATIONS.md` — **primary endpoint/auth map.** Documents the
  `/login.json` flow (`auth_token` + `user.id` → `x-token-auth`/`x-user-id` headers),
  `/frames.json`, `/frames/{id}/assets.json`, the image-proxy URL pattern
  `{IMAGE_PROXY_BASE_URL}/{asset.user_id}/{asset.file_name}`, and the required/optional
  env vars.
- `.planning/codebase/CONCERNS.md` — **primary risk map for verification.** Silent error
  handling (no `raise_for_status`, `pass` on `error`), plaintext-credential logging,
  `logs/`/`cache/` dirs never created, the 1s pagination sleep, bare `except:` in
  `exif.py`, ToS-violating Nominatim user-agent.
- `.planning/phases/01-toolchain-revival/01-CONTEXT.md` — Phase 1 decisions; notes the
  **deferred runtime `.dict()` migration (its D-05)** and the established pytest smoke-test
  pattern this phase reuses.

### Read-path source files (will be read; some lightly changed)
- `auraframes/aura.py` — `login()`, `get_all_assets()` (parametrize + de-sleep per D-05),
  `dump_frame()`/`download_images_from_assets()`, `_init_logger()` (D-08).
- `auraframes/client.py` — add `raise_for_status()` + secret redaction (D-06/D-07).
- `auraframes/api/accountApi.py` — `login()`, surface `error` (D-06).
- `auraframes/api/frameApi.py` — `get_frames()`, `get_frame()`, `get_assets()` (cursor),
  surface `error` (D-06).
- `auraframes/export.py` — `get_image_from_asset()` (download + save path).
- `auraframes/exif.py` — `write_exif()`, bare-except surfacing + UA fix (D-11),
  `get_readable_exif()` (reuse for read-back assertion).
- `auraframes/models/asset.py` — `Asset` fields used: `taken_at`/`taken_at_dt`,
  `location_name`, `location`, `file_name`, `user_id`, `thumbnail_url`.
- `tests/test_imports.py` — existing Phase 1 smoke test; new live test sits alongside it.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Phase 1 pytest harness** (`tests/`, pytest in dev extra, `uv run pytest`) — the live
  test plugs straight in (D-01).
- **`Aura` facade** (`auraframes/aura.py`) already wires every API client and exposes
  `login()`, `get_frames` (via `frame_api`), `get_all_assets()`, `dump_frame()`,
  `download_images_from_assets()` — the read path is fully present, just unverified.
- **`exif.get_readable_exif(path)`** — loads EXIF from a saved file via piexif; reuse it to
  read back and assert `DateTimeOriginal` (+ GPS) for READ-04 (D-09).
- **`export.get_image_from_asset(asset, path, exif_writer)`** — downloads from the image
  proxy and writes the EXIF-injected file to disk; the single-image download verified in
  READ-04 runs through this.

### Established Patterns
- API methods hydrate pydantic models from JSON (`Frame(**...)`, `Asset(**...)`) and
  return them — tests assert on typed model fields, not raw dicts.
- Cursor pagination is **manual**: `get_assets` returns `(assets, next_page_cursor)` and
  callers loop until the cursor is falsy (`get_all_assets`).
- Auth state lives on the shared `Client` session (headers mutated after `login()`), so a
  single login fixture authenticates all 4 tests (D-03).

### Integration Points
- Live network to `api.pushd.com` (REST) **and** `imgproxy.pushd.com` (image proxy) **and**
  Nominatim/OpenStreetMap (geocoding for GPS) — all hit during a full read-path run.
- Image-proxy download is an **unauthenticated** direct `httpx.get` (no token needed),
  unlike the REST calls.
- AWS S3/SQS + Cognito are **not** on the read path (upload-only) — ignore for Phase 2.

</code_context>

<specifics>
## Specific Ideas

- The verification bar is deliberately **"trustworthy pass," not "green at any cost"**:
  every minimal code change (D-06, D-07, D-11) exists so a real API failure or a broken
  save **cannot** silently report success — directly countering the "silent error handling
  can mask API drift" blocker recorded in STATE.md.
- Pagination proof is about the **mechanism** (cursor handoff across ≥2 pages via a small
  limit), not draining a huge frame (D-04/D-05).
- READ-04 is verified by **reading EXIF back from the file on disk** (D-09), not by
  trusting the write call returned — the strongest available proof for "EXIF readable in
  the saved file."

</specifics>

<deferred>
## Deferred Ideas

- **`.env` loader for credentials** — came up as adjacent; not adopted. The constraint and
  existing code use plain shell env vars (`AURA_EMAIL`/`AURA_PASSWORD`); Phase 3 docs will
  cover them. Add a dotenv loader only if a later phase wants the convenience.
- **Video / non-image assets** — the download verification targets an image asset; video
  asset handling (`video_url`, live photos) is not in the read-path proof.
- **Full typed exception hierarchy (MOD-03)** and **AWS pool-ID config (MOD-02)** —
  explicitly out of scope (REQUIREMENTS.md v2). Phase 2 does only the minimal
  `raise_for_status` + error surfacing of D-06.
- **Async HTTP migration (MOD-01)** and the **upload round-trip (UP-01)** — later
  milestones.
- **Phase 1 deferred `.dict()` → `.model_dump()` migration** — optional here since it's not
  on the read path (see Claude's Discretion); otherwise belongs with the upload work.
- **Retry/backoff on transient network/429 errors** — not built; if the live run is flaky,
  note it for the Phase 3 report rather than adding retry logic now.

None of the above expanded the phase scope — discussion stayed within read-path
verification.

</deferred>

---

*Phase: 2-Live Read-Path Verification*
*Context gathered: 2026-06-29*
