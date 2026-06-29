# Phase 3: Run Docs & Verification Report - Research

**Researched:** 2026-06-29
**Domain:** Developer documentation (`uv` setup/run) + verification reporting; small read-path demo wiring
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Reconcile `README.md` to reality. Fix env var `AURA_USERNAME` → **`AURA_EMAIL`** (per `settings.py`/`.env.sample`), add `uv` setup/run instructions, clearly mark VERIFIED (read path) vs UNVERIFIED (upload/device flow).
- **D-02:** Keep the iOS/Android upload-flow content (sequence diagram + 10 steps) but flag it *"documented from code, NOT verified in this revive milestone"*. Same treatment for existing TODOs / SQS notes.
- **D-03:** README carries a one-line status + link (e.g. *"Read path: VERIFIED — see `VERIFICATION-REPORT.md`"*), not a duplicated table. The repo-root report is the single source of truth for per-step detail.
- **D-04:** Standalone repo-root report (e.g. `VERIFICATION-REPORT.md`) so it's developer-visible in a normal checkout (not buried in `.planning/`). It **consolidates and cites** `.planning/phases/02-live-read-path-verification/02-LIVE-EVIDENCE.md` rather than replacing it. (Exact filename is Claude's discretion.)
- **D-05:** Document two run paths: `uv run python main.py` (human demo) **and** `uv run pytest -m live` (asserted proof). Both in the setup/run docs.
- **D-06:** Flesh `main.py` from the near-empty stub into a real read-path demo: **login → list frames → fetch assets → download one image with EXIF**, printing a concise summary.
- **D-07 (demo behavior):** Drive the read path **only through existing `Aura` facade methods** (`login`, `frame_api.get_frames`, `get_all_assets`, `dump_frame`/`download_images_from_assets`) — no new client logic. Download to a **gitignored** output dir. If `AURA_EMAIL`/`AURA_PASSWORD` unset, **exit cleanly with a helpful message** (mirror Phase 2's credential-less skip).
- **D-08:** Re-run live verification during Phase 3; capture fresh, dated evidence (`uv run pytest -m live`) so the report proves the read path still works **today** and catches new drift since Phase 2's 2026-06-29 run.
- **D-09:** Full catalog in the report: per-step status table (READ-01..04); the 4 schema drifts repaired in Phase 2; the GPS lat/long swap (deferred); the silent-error-masking fixes (`raise_for_status`, secret redaction, EXIF-failure surfacing, geocoder UA fix); the pagination caveat.

### Claude's Discretion
- Exact report filename (`VERIFICATION-REPORT.md` vs `STATUS.md`) and section ordering.
- Exact `main.py` console output format, which frame/asset it picks, and the gitignored download path (reuse Phase 2 conventions if convenient).
- Whether the fresh live run reuses the Phase 2 test command verbatim or adds a thin evidence-capture wrapper — as long as dated pass/fail output lands in the report.
- How much of README's existing read/download narrative to keep vs trim while reconciling.

### Deferred Ideas (OUT OF SCOPE)
- Fix the GPS lat/long swap in `exif.build_gps_ifd` (document only).
- Verify the upload round-trip (UP-01).
- `.env` loader as a first-class app feature (currently dev/test-only via python-dotenv).
- A `[project.scripts]` console entry point (e.g. `aura = ...`). `main.py` via `uv run python main.py` is sufficient for ENV-04.
- SQS flow mapping / frame rendering reverse-engineering.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ENV-04 | A developer can set up the environment and run the client using documented `uv` commands | Verified `uv` command surface below (Standard Stack / Code Examples); authoritative env-var list from `settings.py`/`.env.sample`; fleshed `main.py` demo using existing facade methods |
| DOC-01 | A verification report records what still works and where the live API has drifted | `02-LIVE-EVIDENCE.md` provides the complete status table + drift catalog; report structure + fresh-run capture procedure below |
</phase_requirements>

## Summary

This is a documentation + tiny-demo + re-run-tests phase. No runtime behavior changes except fleshing `main.py` into a read-path demo that calls **only existing `Aura` facade methods**. The work splits cleanly into three deliverables: (1) reconcile `README.md` to verified reality (fix the `AURA_USERNAME` bug, add `uv` commands, add the VERIFIED/UNVERIFIED framing); (2) write a standalone repo-root `VERIFICATION-REPORT.md` that consolidates and cites the already-complete `02-LIVE-EVIDENCE.md`; (3) flesh `main.py` and re-run `uv run pytest -m live` to capture fresh dated evidence.

The single most important technical finding: **`pytest` lives in `[project.optional-dependencies].dev`, which uv does NOT install by default.** A clean checkout therefore needs `uv sync --extra dev` (or `uv run --extra dev pytest ...`) before the live tests run. The currently-installed `.venv` already has the dev extra, which is why Phase 2's bare `uv run pytest -m live` worked — but the documented clean-checkout commands must include `--extra dev` or they will fail for a new developer. Running the client itself (`uv run python main.py`) needs only the default runtime deps. This is the one genuine landmine in the phase.

Everything else is well-grounded: the env-var truth is in `settings.py`/`.env.sample`, the facade method signatures are confirmed, the live test command is confirmed to collect 4 tests, and the entire drift catalog is already written in `02-LIVE-EVIDENCE.md`. uv 0.11.7 and Python 3.14.4 are installed; `uv.lock` and `.python-version` (pinned `3.14`) are committed.

**Primary recommendation:** Document `uv sync` (run client) and `uv sync --extra dev` (run tests) as two distinct setup steps; flesh `main.py` to mirror the Phase 2 test's read-path sequence (first frame → first geo image asset → download to a gitignored dir); write `VERIFICATION-REPORT.md` as a direct restructuring of `02-LIVE-EVIDENCE.md` plus a fresh dated run line.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Documented setup/run commands (ENV-04) | Docs (`README.md`) | — | Developer-facing prose; no runtime code |
| Verification report (DOC-01) | Docs (repo-root `VERIFICATION-REPORT.md`) | `.planning/` evidence | Standalone status snapshot; cites raw evidence |
| Read-path demo orchestration | Entry point (`main.py`) | `Aura` facade | `main.py` only sequences existing facade calls (D-07) |
| Login / list / fetch / download | `Aura` facade + `*Api` + `export`/`exif` | Live API + image proxy + Nominatim | Already implemented & verified in Phase 2; demo reuses verbatim |
| Credential loading | Shell env vars (runtime); `.env` via python-dotenv (tests only) | `settings.py` | App reads `os.getenv`; dotenv is dev/test convenience, not a runtime feature (deferred) |

## Standard Stack

### Core (already in place — this phase adds no dependencies)
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| `uv` | 0.11.7 (installed) | Env/dependency/interpreter management | User decision (CLAUDE.md); `uv.lock` + `.python-version` already committed `[VERIFIED: uv --version]` |
| Python | 3.14.4 (installed) | Runtime | `requires-python = ">=3.14"`; `.python-version` pins `3.14` `[VERIFIED: pyproject.toml, .python-version]` |
| `pytest` | 9.1.1 (installed) | Live read-path test runner | In `dev` extra; the `live` marker gates the 4 read-path tests `[VERIFIED: uv run pytest --version]` |
| `python-dotenv` | >=1.0 (dev extra) | Loads `.env` for live tests in `conftest.py` | Established in Phase 2; shell vars still win `[VERIFIED: pyproject.toml, conftest.py]` |

### Supporting (facade/runtime deps the demo exercises — no changes)
| Library | Purpose | When Used |
|---------|---------|-----------|
| `httpx[http2]` | REST + image-proxy HTTP | login/list/fetch + image download |
| `piexif` / `Pillow` | EXIF read/write + thumbnails | download step (READ-04) |
| `geopy` | Nominatim geocode for GPS IFD | download step when asset has `location_name` |
| `loguru` | Structured logging to `logs/` + stderr | all calls (secrets already redacted, Phase 2) |

**Installation:** No new packages. Setup is `uv sync` / `uv sync --extra dev` only.

## Package Legitimacy Audit

**Not applicable.** This phase installs **no external packages**. All dependencies are already present in `pyproject.toml` + `uv.lock` from Phases 1–2. slopcheck gate skipped (nothing to check).

## Architecture Patterns

### System Architecture Diagram (read-path demo `main.py` will drive)

```
shell env / .env ──> AURA_EMAIL, AURA_PASSWORD
        │
        ▼
   main.py (orchestrator, D-07: no new logic)
        │  guard: both creds set? ──no──> print helpful msg, sys.exit(0)  ← clean exit
        │ yes
        ▼
   Aura()                          # __init__ creates logs/, wires API clients
        │
        ├─> aura.login()                       ──> POST /login.json ──> x-token-auth + x-user-id on session  (READ-01)
        │
        ├─> aura.frame_api.get_frames()        ──> GET /frames.json  ──> list[Frame]                          (READ-02)
        │
        ├─> aura.get_all_assets(frame.id,      ──> GET /frames/{id}/assets.json (cursor loop) ──> list[Asset] (READ-03)
        │       limit=...)
        │
        └─> export.get_image_from_asset(asset, ──> GET imgproxy.pushd.com/{user_id}/{file_name}               (READ-04)
                out_dir, aura.exif_writer)         + Nominatim geocode ──> write EXIF ──> file on disk (gitignored dir)
                                                   └─ or aura.download_images_from_assets([asset], out_dir)
        │
        ▼
   print concise summary (frame name/id, asset count, saved path, EXIF datetime/GPS)
```

File-to-implementation mapping is in the table below; the diagram shows data flow only.

### Component Responsibilities (files this phase touches)
| File | Action | Notes |
|------|--------|-------|
| `README.md` | Edit (reconcile) | D-01/02/03 — fix env var, add uv commands, VERIFIED/UNVERIFIED framing, one-line status + link |
| `VERIFICATION-REPORT.md` (new, repo root) | Create | D-04/09 — consolidate + cite `02-LIVE-EVIDENCE.md` |
| `main.py` | Edit (flesh out) | D-06/07 — read-path demo via facade only |
| `.gitignore` | Possibly edit | Ensure the demo's download dir is ignored (`asset_images/` already ignored — reuse it) |
| `.planning/...` evidence | Re-run + capture | D-08 — fresh dated `uv run pytest -m live` output |

### Pattern 1: Credential-guard + clean exit (D-07)
**What:** Mirror the Phase 2 test skip philosophy in `main.py`.
**When:** At the top of `main.py` before instantiating `Aura()`.
**Example:**
```python
# Source: pattern mirrors tests/conftest.py:23-26 (verified in-repo)
import os, sys

email = os.getenv("AURA_EMAIL")
password = os.getenv("AURA_PASSWORD")
if not email or not password:
    print("AURA_EMAIL / AURA_PASSWORD not set — set them (or a local .env) to run the demo.")
    sys.exit(0)   # clean exit, not an error
```
Note: `Aura.login()` already defaults its args to `os.getenv('AURA_EMAIL'/'AURA_PASSWORD')` (`aura.py:36`), so the guard only needs to detect-and-message; `login()` reads the env itself.

### Pattern 2: Asset selection mirrors the live test (D-07, Claude's discretion)
**What:** Pick the first frame, then the first downloadable image asset that has a `location_name` (so GPS is exercised), falling back to the first image asset.
**Example:**
```python
# Source: tests/test_read_path.py:10-14, 79-94 (verified in-repo)
def _is_image_asset(a):
    return bool(a.thumbnail_url) and not a.video_url and not a.is_live

frame = aura.frame_api.get_frames()[0]
assets = aura.get_all_assets(frame.id)              # full drain (or pass limit= to demo the cursor)
image_assets = [a for a in assets if _is_image_asset(a)]
geo = [a for a in image_assets if a.location_name]
asset = (geo or image_assets or assets)[0]
```

### Anti-Patterns to Avoid
- **Reintroducing `AURA_USERNAME`** in README — the real var is `AURA_EMAIL` (`settings.py` reads it via `aura.py:36`/`conftest.py`). This is the documentation bug being fixed; do not copy it anywhere.
- **Documenting bare `uv run pytest` for the live suite as the clean-checkout command** — pytest is an *extra*, not installed by default. Use `uv sync --extra dev` first or `uv run --extra dev pytest`.
- **Writing secrets to the report or committing `.env`** — the report cites redaction proof; never paste real tokens/passwords. `.env` is gitignored (`.gitignore:89`).
- **Adding new client logic to `main.py`** — D-07 forbids it; orchestrate existing facade methods only.
- **Duplicating the status table in README** (D-03) — link to the report instead.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Pagination in the demo | Manual cursor loop | `aura.get_all_assets(frame_id, limit=...)` | Production helper already proven in READ-03 |
| Image download + EXIF | New download code | `export.get_image_from_asset(asset, path, aura.exif_writer)` or `aura.download_images_from_assets([asset], path)` | Proven in READ-04; handles EXIF + thumbnail |
| Credential loading for tests | Custom parser | python-dotenv `load_dotenv()` (already in `conftest.py`) | Established Phase 2 pattern; shell vars still win |
| Interpreter install/pin | Manual pyenv | `uv` + committed `.python-version` (`3.14`) | uv auto-resolves/downloads the pinned interpreter |
| Re-deriving the drift catalog | New investigation | Cite `02-LIVE-EVIDENCE.md` | The catalog is complete and dated; report consolidates it |

**Key insight:** The entire read path and its evidence already exist. Phase 3 is assembly and prose, not engineering.

## Runtime State Inventory

This phase is documentation + a demo, not a rename/refactor/migration. The one runtime artifact created is the demo's downloaded image file.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | Demo writes one image to a download dir (e.g. `asset_images/`) | Ensure dir is gitignored (already covered) |
| Live service config | None | None — no service config changes |
| OS-registered state | None | None |
| Secrets/env vars | `AURA_EMAIL`/`AURA_PASSWORD` read at runtime; `.env` for tests | `.env` already gitignored (`.gitignore:89`); docs must reference `.env.sample`, never real values |
| Build artifacts | None | None — no package metadata renamed |

**Download dir:** `asset_images/`, `logs/`, and `cache/` are already gitignored (`.gitignore:91-94`). Reuse `asset_images/` (or a subdir) for the demo output so no new ignore rule is strictly required — but the planner should confirm the exact path matches a gitignore entry. `[VERIFIED: .gitignore grep]`

## Common Pitfalls

### Pitfall 1: `uv run pytest` fails on a clean checkout
**What goes wrong:** A new developer runs the documented `uv run pytest -m live` and gets `pytest: command not found` (or uv errors that the dev extra isn't synced).
**Why it happens:** `pytest`/`python-dotenv` are in `[project.optional-dependencies].dev`. uv installs the default dependency set on `uv sync`/`uv run`; **optional-dependency extras are opt-in.** The current `.venv` already has them, masking the issue locally.
**How to avoid:** Document `uv sync --extra dev` as the test-setup step, OR document the test command as `uv run --extra dev pytest -m live`. Verified: `uv run --extra dev pytest --collect-only -m live` → 4 tests collected. `[VERIFIED: uv run --extra dev pytest --collect-only]`
**Warning signs:** Docs that show `uv run pytest` without any `--extra dev` mention.

### Pitfall 2: README reintroduces or leaves `AURA_USERNAME`
**What goes wrong:** Reader exports `AURA_USERNAME`, login silently authenticates as nobody / fails confusingly.
**Why it happens:** The stale README (line 8) documents `AURA_USERNAME`; the code reads `AURA_EMAIL` (`aura.py:36`, `conftest.py:23`).
**How to avoid:** Single source of truth = `settings.py` + `.env.sample`. Required: `AURA_EMAIL`, `AURA_PASSWORD`. Optional w/ defaults: `AURA_LOCALE` (`en-US`), `AURA_APP_IDENTIFIER` (`com.pushd.client`), `AURA_DEVICE_IDENTIFIER` (`0000000000000000`). `[VERIFIED: settings.py, aura.py:36]`
**Warning signs:** The string `AURA_USERNAME` surviving anywhere in README.

### Pitfall 3: Live run flakiness misread as drift
**What goes wrong:** Nominatim rate-limiting or a transient network error on the fresh D-08 run looks like API drift.
**Why it happens:** No retry/backoff exists (deferred, per Phase 2). Geocode failure is *tolerated* (logged, returns None) — GPS may be absent without it being drift.
**How to avoid:** In the report, distinguish "API schema drift" (model-level) from "transient network/geocode miss." If the fresh run flakes, note it as a transient and re-run, rather than logging it as new drift.
**Warning signs:** A single failed run with a network/Nominatim traceback rather than a Pydantic `ValidationError`.

### Pitfall 4: Demo download path not gitignored / cache short-circuit
**What goes wrong:** Demo writes the downloaded image into a tracked path, or re-runs return the cached file silently.
**Why it happens:** `get_image_from_asset` returns the cached bytes if the target file already exists (`export.py:43-45`); and only the dirs in `.gitignore` are safe.
**How to avoid:** Write to `asset_images/` (gitignored). For a deterministic "fresh" demo, accept the cache behavior (it's correct) or note it; do not pass `ignore_cache` unless needed.

## Code Examples

### Documented `uv` command surface (clean checkout → run)
```bash
# Source: verified against installed uv 0.11.7 + pyproject.toml/.python-version

# 1. (If 3.14 not present) uv auto-installs the pinned interpreter on first sync,
#    or explicitly:
uv python install 3.14

# 2. Install runtime dependencies (creates .venv, respects uv.lock + .python-version):
uv sync

# 3a. Run the client demo (runtime deps only):
uv run python main.py

# 3b. Run the live verification suite (needs the dev extra for pytest):
uv sync --extra dev
uv run pytest -m live            # 4 live tests; needs AURA_EMAIL/AURA_PASSWORD
# — or, in one shot without a separate sync:
uv run --extra dev pytest -m live

# Credential-less default suite stays green (live tests deselected):
uv run pytest -m "not live"
```

### Capturing fresh dated evidence (D-08)
```bash
# Source: command form proven in 02-LIVE-EVIDENCE.md; -s surfaces the print() lines
uv run --extra dev pytest -m live -s
# Expected shape (from Phase 2): "4 passed, 9 deselected"
# The -s flag prints per-test detail (frame name/id, asset count, selected asset, GPS line)
# Paste the dated command + summary line into VERIFICATION-REPORT.md.
```
Note: collection confirmed this session — `uv run --extra dev pytest --collect-only -m live` → `4/13 tests collected (9 deselected)`. `[VERIFIED: this session]`

### `.env` for credentials (docs should point at `.env.sample`)
```bash
# .env.sample exists with AURA_EMAIL / AURA_PASSWORD keys (gitignored .env)
cp .env.sample .env
# edit .env with real credentials; conftest.py load_dotenv() picks it up for tests
# (shell-exported vars override .env). main.py reads the same env vars at runtime.
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `AURA_USERNAME` env var (README) | `AURA_EMAIL` (code) | Pre-existing code reality | README must be corrected (D-01) |
| `requirements.txt` (UTF-16) + pip | `uv` + `pyproject.toml` + `uv.lock` | Phase 1 | Docs use `uv` commands exclusively |
| pydantic v1 | pydantic v2 | Phase 1 | n/a for docs; report can note it as completed context |
| `main.py` 4-line stub | Read-path demo | This phase (D-06) | New documented entry point |
| Silent error handling (no `raise_for_status`, bare `except:`, plaintext secret logging) | `raise_for_status` + error surfacing + secret redaction + EXIF-failure raise + proper Nominatim UA | Phase 2 | Report's "silent-error masking" section (criterion 4) |

**Deprecated/outdated in README (to fix or flag):**
- `AURA_USERNAME` → `AURA_EMAIL` (fix).
- Upload-image flow + SQS TODOs → keep but flag *documented-from-code, NOT verified this milestone* (D-02).

## Verification Report Structure (recommended, grounded in `02-LIVE-EVIDENCE.md`)

Recommended `VERIFICATION-REPORT.md` (repo root) section order:

1. **Header** — title, date of fresh run, account (email is fine; never the password), one-line verdict ("Read path PROVEN end-to-end against `api.pushd.com/v5`").
2. **How this was verified** — the exact command (`uv run --extra dev pytest -m live -s`), result summary line, and a pointer that raw evidence lives in `.planning/phases/02-live-read-path-verification/02-LIVE-EVIDENCE.md` (D-04).
3. **Per-step status table (READ-01..04)** — Req | Step | Status | Evidence. Copy/refresh from `02-LIVE-EVIDENCE.md` "Results" table.
4. **Live API drift discovered & repaired** — the 4 schema drifts (User Optional fields; `Feature` enum `_missing_`→UNKNOWN; `Asset.unglacierable` nullable; `total_asset_count`→`frame.num_assets`).
5. **Drift recorded but NOT fixed** — GPS lat/long swap in `exif.build_gps_ifd` (GPS still readable, coordinates transposed; deferred).
6. **Silent-error masking removed (trustworthiness, criterion 4)** — `raise_for_status` in all 4 `Client` methods; secret redaction (`password`/`auth_token`/`x-token-auth`); EXIF-write failure now raises; geocode failure tolerated+logged; Nominatim UA fixed to `auraframes-python-client/1.0`; `logs/` auto-created.
7. **Caveats** — pagination cursor exercised via small `limit` (small accounts return a single page); no retry/backoff (transient network/Nominatim misses are not drift); upload/device flow unverified.
8. **What is NOT verified** — upload round-trip (UP-01), async, AWS pool config, typed exceptions.

Every row in §3–§6 already has a source in `02-LIVE-EVIDENCE.md` / `02-VERIFICATION.md` / `02-CONTEXT.md`. The report is a restructure + a fresh-run line, not new investigation.

## Project Constraints (from CLAUDE.md)

- **Tech stack:** Python 3.14 + `uv` only — docs must use `uv` commands, not `pip`/`venv`/`poetry`.
- **Secrets out of VCS:** `AURA_EMAIL`/`AURA_PASSWORD` must stay out of version control; report/docs cite redaction, never paste real secrets. `.env` gitignored.
- **Pragmatic modernization scope:** Change only what's needed; no broad refactors. The demo reuses the facade; the GPS swap stays deferred.
- **Naming conventions:** Utility/entry modules `snake_case`; `main.py` follows existing `snake_case` + 4-space PEP 8. Demo print output is incidental (no convention constraint), but use existing method names verbatim.
- **Error handling reality:** Read-path error surfacing exists (Phase 2); the demo need not add new exception handling beyond the credential guard (don't expand scope).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | uv installs `[project.optional-dependencies].dev` only when `--extra dev`/`--all-extras` is passed (not by default) | Pitfall 1 / Code Examples | LOW — if uv auto-synced extras, the `--extra dev` is harmless/redundant. Verified empirically that the live tests collect under `--extra dev`; the default-exclusion is standard uv behavior for *extras* (vs dependency-groups). |
| A2 | The fresh D-08 live run will pass as in Phase 2 (account still has frames/assets, API unchanged) | Report §2/§3 | MEDIUM — the API is undocumented and can drift between runs; that is exactly what D-08 re-run catches. If it drifts, the report documents the new drift (still a valid DOC-01 outcome). |
| A3 | Reusing `asset_images/` as the demo download dir satisfies the gitignored-output requirement | Runtime State Inventory / Pitfall 4 | LOW — `asset_images/` is already in `.gitignore`; any chosen path just needs a matching ignore entry. |

## Open Questions

1. **Exact report filename + demo download path** — Claude's discretion (D-04). Recommendation: `VERIFICATION-REPORT.md` at repo root; download to `asset_images/` (already gitignored). No blocker.
2. **Whether to add `--extra dev` to the documented test command vs a two-step `uv sync --extra dev` then `uv run pytest`** — both correct; planner picks. Recommendation: show the two-step in setup, and the one-shot `uv run --extra dev pytest -m live` as the copy-paste run command. No blocker.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `uv` | All setup/run docs | ✓ | 0.11.7 | — |
| Python | Runtime | ✓ | 3.14.4 (pinned 3.14) | uv auto-installs pinned interpreter |
| `pytest` | Live verification (D-08) | ✓ (dev extra) | 9.1.1 | `uv sync --extra dev` installs it |
| `python-dotenv` | `.env` loading in tests | ✓ (dev extra) | >=1.0 | shell env vars |
| Live Aura API + image proxy + Nominatim | Fresh D-08 run + `main.py` demo | requires network + real creds | — | Credential-less run cleanly skips (tests) / clean-exits (demo) |
| Real Aura credentials | D-08 fresh evidence | user-supplied | — | If unavailable, report cites Phase 2's 2026-06-29 run and notes D-08 could not refresh (planner should flag) |

**Missing dependencies with no fallback:** None — all tooling is installed. The only external requirement is live credentials + network for the D-08 refresh; without them, the report falls back to citing the existing Phase 2 evidence (a documented degradation, not a hard block).

## Security Domain

This phase changes no runtime behavior beyond a demo that calls already-verified facade methods; the read-path security hardening was completed in Phase 2. The applicable controls here are about **not leaking secrets through docs/evidence**.

| ASVS Category | Applies | Standard Control (already in place / doc duty) |
|---------------|---------|-----------------------------------------------|
| V2 Authentication | yes | `AURA_EMAIL`/`AURA_PASSWORD` via env; token headers injected post-login (Phase 2) |
| V6 Cryptography / Secret mgmt | yes | Secrets out of VCS: `.env` gitignored; logs redact `password`/`auth_token`/`x-token-auth` (Phase 2). Docs/report must never paste real secrets. |
| V7 Error/Logging | yes | `raise_for_status` + redaction completed Phase 2; report documents this (criterion 4) |

| Pattern | STRIDE | Mitigation |
|---------|--------|------------|
| Plaintext credential in committed `.env`/README example | Information Disclosure | `.env` gitignored; docs reference `.env.sample` placeholders only |
| Secret leaking into `VERIFICATION-REPORT.md` (pasted log output) | Information Disclosure | Cite the redaction *proof* (0 occurrences), not raw log lines; account email is acceptable, password/token never |

## Sources

### Primary (HIGH confidence)
- In-repo files (read this session): `pyproject.toml`, `.python-version`, `auraframes/utils/settings.py`, `auraframes/aura.py`, `auraframes/api/frameApi.py`, `auraframes/export.py`, `tests/test_read_path.py`, `tests/conftest.py`, `.env.sample`, `.gitignore`, `README.md`, `main.py`.
- `.planning/phases/02-live-read-path-verification/02-LIVE-EVIDENCE.md` — complete status table + drift catalog (the report's source material).
- `.planning/phases/02-live-read-path-verification/02-VERIFICATION.md` — 10/10 truths verified, artifact list.
- `.planning/phases/02-live-read-path-verification/02-CONTEXT.md` — silent-error-masking decisions (D-06/07/11).
- `.planning/codebase/INTEGRATIONS.md`, `.planning/codebase/CONCERNS.md` — authoritative env-var/endpoint map + masking landmines.
- Live tool checks this session: `uv --version` → 0.11.7; `python3 --version` → 3.14.4; `uv run --extra dev pytest --collect-only -m live` → 4 tests collected.

### Secondary (MEDIUM confidence)
- uv extras-vs-default-sync behavior (Pitfall 1 / A1) — standard uv semantics (optional-dependencies extras are opt-in), corroborated empirically by the dev-extra-gated collection.

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all tools installed and version-checked this session.
- Architecture / facade method signatures: HIGH — read directly from source (`aura.py`, `frameApi.py`, `export.py`).
- `uv` command surface: HIGH — verified against installed uv 0.11.7 + committed `uv.lock`/`.python-version`; one nuance (dev extra) verified empirically.
- Drift catalog: HIGH — already documented and dated in `02-LIVE-EVIDENCE.md`.
- D-08 fresh-run outcome: MEDIUM — depends on live API + credentials at execution time.

**Research date:** 2026-06-29
**Valid until:** 2026-07-29 (stable; the only volatile element is the live API, which D-08 re-checks)
