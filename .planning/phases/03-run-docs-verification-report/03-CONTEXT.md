# Phase 3: Run Docs & Verification Report - Context

**Gathered:** 2026-06-29
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers **two documentation artifacts** for the revived client — no runtime
behavior is being changed (one small entry-point demo aside, see D-07):

1. **Developer setup/run docs (ENV-04)** — a developer following only the documented `uv`
   commands can, from a clean checkout, set up the environment and run the client. Docs
   list the required env vars (`AURA_EMAIL`/`AURA_PASSWORD`, optional
   locale/device/app identifiers) and the exact `uv` commands.
2. **Verification report (DOC-01)** — a standalone report recording each read-path step
   (login → list → fetch → download) as working or drifted, with evidence, plus any API
   drift and silent-error masking discovered during verification.

**In scope:** reconciling `README.md` to verified reality; a repo-root verification
report; fleshing `main.py` into a runnable read-path demo (reusing the existing `Aura`
facade only); a fresh live verification run to back the report.

**Out of scope:** the upload round-trip (UP-01), async migration (MOD-01), AWS pool-ID
config (MOD-02), typed exception hierarchy (MOD-03), fixing the deferred GPS lat/long
swap. Mode: **MVP** — document what is, prove it still runs, don't refactor.

</domain>

<decisions>
## Implementation Decisions

### README Treatment
- **D-01:** **Reconcile `README.md` to reality.** Rewrite it to reflect the verified
  state: correct the env var (`AURA_USERNAME` → actual **`AURA_EMAIL`**, per
  `auraframes/utils/settings.py` and `.env.sample`), add `uv` setup/run instructions, and
  clearly mark what is **VERIFIED** (the read path) vs **UNVERIFIED** (upload/device flow).
- **D-02:** **Keep the upload-flow content, but mark it unverified.** The iOS/Android
  upload-image flow (sequence diagram + 10 steps) is accurate to the 2023 code but was
  **not verified this milestone**. Retain it, flagged clearly as
  *"documented from code, NOT verified in this revive milestone"* so readers don't trust it
  as proven. Same treatment for the existing TODOs / SQS notes.
- **D-03:** **README carries a one-line status + link, not a duplicated table.** Show a
  brief line like *"Read path: VERIFIED — see `VERIFICATION-REPORT.md`"* and link out. The
  repo-root report is the single source of truth for the per-step detail; do not duplicate
  the status table in README.

### Verification Report Location & Form
- **D-04:** **Standalone repo-root report** (e.g. `VERIFICATION-REPORT.md` at the project
  root) so it is developer-visible in a normal checkout (not buried in `.planning/`). It
  **consolidates and cites** the already-captured raw evidence in
  `.planning/phases/02-live-read-path-verification/02-LIVE-EVIDENCE.md` rather than
  replacing it. (Exact filename is Claude's discretion — `VERIFICATION-REPORT.md` or
  `STATUS.md`.)

### "Run the Client" Entry Point
- **D-05:** **Document two run paths:** `uv run python main.py` (the human-runnable demo)
  **and** `uv run pytest -m live` (the asserted proof). Both must be in the setup/run docs.
- **D-06:** **Flesh out `main.py` into a real read-path demo.** Currently it is a near-empty
  stub (`login()` + `get_frames()`, no output). Make it run the full read path:
  **login → list frames → fetch assets → download one image with EXIF**, printing a concise
  summary.
- **D-07 (behavior of the demo):** **Drive the read path only through existing `Aura`
  facade methods** (`login`, `frame_api.get_frames`, `get_all_assets`,
  `dump_frame`/`download_images_from_assets`) — **no new client logic**. Download to a
  **gitignored** output dir. If `AURA_EMAIL`/`AURA_PASSWORD` are unset, **exit cleanly with
  a helpful message** (mirror the credential-less skip philosophy from Phase 2's tests).

### Report Scope & Evidence Freshness
- **D-08:** **Re-run the live verification during Phase 3 and capture fresh, dated
  evidence.** Run `uv run pytest -m live` (and/or `main.py`) so the report proves the read
  path still works **today** and catches any new drift since Phase 2's 2026-06-29 run.
- **D-09:** **Full catalog in the report.** Include: the per-step status table
  (READ-01..04); the **4 schema drifts repaired** in Phase 2 (`User` Optional fields,
  `Feature` enum `_missing_` → UNKNOWN, `Asset.unglacierable` nullable,
  `total_asset_count` → `frame.num_assets`); the **GPS lat/long swap** (deferred, GPS still
  readable); the **silent-error-masking fixes** that made verification trustworthy
  (`raise_for_status`, secret redaction, EXIF-failure surfacing, geocoder UA fix); and the
  **pagination caveat** (small accounts return a single page, so the cursor was exercised
  with a small `limit`). Criterion 4 explicitly wants silent-error masking documented.

### Claude's Discretion
- Exact report filename (`VERIFICATION-REPORT.md` vs `STATUS.md`) and section ordering.
- Exact `main.py` console output format, which frame/asset it picks for the demo, and the
  gitignored download path (reuse the Phase 2 conventions if convenient).
- Whether the fresh live run reuses the Phase 2 test command verbatim or adds a thin
  evidence-capture wrapper — as long as dated pass/fail output lands in the report.
- How much of the README's existing read/download narrative to keep vs. trim while
  reconciling (keep it honest and current; don't expand scope).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project & milestone scope
- `.planning/PROJECT.md` — what the client is, core value (login → list → download), the
  in/out-of-scope boundary; "Active" requirement is the documented status (Phase 3).
- `.planning/REQUIREMENTS.md` — **ENV-04** (documented `uv` setup/run) and **DOC-01**
  (verification report of what works / where the API drifted) are this phase's
  requirements. READ-01..04 and ENV-01..03 are already Complete.
- `.planning/ROADMAP.md` §"Phase 3: Run Docs & Verification Report" — goal + the 4 success
  criteria this phase must satisfy.

### Evidence the report consolidates (PRIMARY source material)
- `.planning/phases/02-live-read-path-verification/02-LIVE-EVIDENCE.md` — **the captured
  live run**: command (`uv run pytest -m live -s` → 4 passed, 9 deselected), per-READ
  results, the secret-redaction grep proof, the **4 schema drifts repaired**, the GPS swap
  deferred, and the python-dotenv/`.env.sample` tooling change. Cite this in the report.
- `.planning/phases/02-live-read-path-verification/02-VERIFICATION.md` — Phase 2 goal
  verification; corroborates the read-path status.
- `.planning/phases/02-live-read-path-verification/02-CONTEXT.md` — the trustworthy-pass
  rationale and the full list of silent-error-masking fixes (D-06/D-07/D-11 there) that the
  report's "masking" section should summarize.

### Codebase analysis (env vars, endpoints, known concerns to document)
- `.planning/codebase/INTEGRATIONS.md` — endpoint/auth map + **required/optional env vars**
  (authoritative source for the docs' env-var list).
- `.planning/codebase/CONCERNS.md` — the silent-error / masking landmines the report
  documents as discovered-and-addressed.

### Files this phase reads / edits
- `README.md` — reconcile to reality (D-01/02/03); currently has the wrong `AURA_USERNAME`
  var and unverified upload-flow content.
- `main.py` — flesh into the read-path demo (D-06/D-07); currently a 4-line stub.
- `auraframes/utils/settings.py` — authoritative env-var names + defaults
  (`AURA_EMAIL`/`AURA_PASSWORD`, `AURA_LOCALE`, `AURA_DEVICE_IDENTIFIER`,
  `AURA_APP_IDENTIFIER`).
- `auraframes/aura.py` — the `Aura` facade methods the demo reuses (`login`,
  `get_all_assets`, `dump_frame`/`download_images_from_assets`).
- `pyproject.toml` — `uv` project + deps + the `live` pytest marker (source for run
  commands). `.env.sample` — the env template the docs reference.
- `tests/test_read_path.py`, `tests/conftest.py` — the live suite + dotenv loading that the
  fresh evidence run (D-08) executes.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`Aura` facade** (`auraframes/aura.py`) — exposes the entire read path; `main.py` just
  orchestrates calls (D-07), no new logic.
- **Live test suite** (`tests/test_read_path.py`, `-m live`, auto-skips without creds) —
  the fresh evidence run (D-08) is just re-running it; its dated output is the report's
  evidence.
- **`02-LIVE-EVIDENCE.md`** — pre-written status table, drift list, and security-grep proof;
  the repo-root report consolidates/cites it rather than re-deriving.
- **`.env.sample` + python-dotenv** (dev extra, `conftest.py`) — already establishes the
  credential pattern the docs document.

### Established Patterns
- Env-var configuration read at import time in `settings.py`; **`AURA_EMAIL`** is the real
  var name (README's `AURA_USERNAME` is stale — a documentation bug to fix).
- Credential-less runs stay green via the `live` marker auto-skip — the demo's no-creds
  exit (D-07) mirrors this.
- `logs/`, `cache/`, asset-image output dirs are gitignored (Phase 2) — the demo's download
  target follows suit.

### Integration Points
- Live network to `api.pushd.com`, `imgproxy.pushd.com`, and Nominatim during a full run —
  the fresh evidence run (D-08) and `main.py` demo both hit these.

</code_context>

<specifics>
## Specific Ideas

- The report's job mirrors Phase 2's "trustworthy pass, not green at any cost" ethos:
  document not just that the read path passes, but the **silent-error masking that was
  removed** so a real failure can't hide (criterion 4).
- README must be **honest about boundaries**: the read path is proven; upload/device flow
  is documented-from-code only. The "VERIFIED vs UNVERIFIED" framing is the throughline.
- The verification report should read as a standalone status snapshot a new developer (or
  future-you) can trust without spelunking `.planning/`.

</specifics>

<deferred>
## Deferred Ideas

- **Fix the GPS lat/long swap** in `exif.build_gps_ifd` — only documented in the report as
  a known limitation this milestone; the actual fix belongs to a later milestone.
- **Verifying the upload round-trip (UP-01)** — README documents it as unverified; proving
  it is a separate milestone.
- **`.env` loader as a first-class app feature** — currently dev/test only via
  python-dotenv; promoting it to the runtime client is out of scope.
- **A `[project.scripts]` console entry point** (e.g. `aura = ...`) — `main.py` via
  `uv run python main.py` is sufficient for ENV-04; packaging a CLI entry is future work.
- **SQS flow mapping / frame rendering reverse-engineering** — README TODOs carried as
  unverified notes, not this milestone's work.

None of the above expanded the phase scope — discussion stayed within docs + verification.

</deferred>

---

*Phase: 3-Run Docs & Verification Report*
*Context gathered: 2026-06-29*
