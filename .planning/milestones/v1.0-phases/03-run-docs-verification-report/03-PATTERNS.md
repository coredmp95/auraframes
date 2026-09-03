# Phase 3: Run Docs & Verification Report - Pattern Map

**Mapped:** 2026-06-29
**Files analyzed:** 3 (1 edit-flesh, 1 edit-reconcile, 1 create)
**Analogs found:** 3 / 3 (the one code file has strong in-repo analogs; the two doc files have a content analog or are pure prose)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `main.py` (edit — flesh stub → read-path demo) | entry-point / orchestrator | request-response + file-I/O | `tests/test_read_path.py` (selection + download) + `tests/conftest.py` (credential guard) | role-match (a test orchestrates the same facade calls; demo is non-asserting) |
| `VERIFICATION-REPORT.md` (create — repo root) | doc / report | n/a (content) | `.planning/phases/02-live-read-path-verification/02-LIVE-EVIDENCE.md` | content-analog (restructure + cite, do not re-derive) |
| `README.md` (edit — reconcile to reality) | doc | n/a (content) | none (pure prose; authoritative facts from `settings.py` / `02-LIVE-EVIDENCE.md`) | no code analog |

**Scope note:** This is a documentation + tiny-demo phase. The only code edit is `main.py`, and D-07 forbids new client logic — it may only sequence existing `Aura` facade methods. The two `.md` deliverables copy *content structure*, not code.

## Pattern Assignments

### `main.py` (entry-point, request-response + file-I/O)

**Analogs:** `tests/conftest.py` (credential guard), `tests/test_read_path.py` (asset selection + download), `auraframes/aura.py` (the facade methods to call).

**Credential-guard + clean-exit pattern** — mirror `tests/conftest.py:23-26` (the test `pytest.skip`; the demo prints + `sys.exit(0)` instead):
```python
# tests/conftest.py:23-26 (analog — replace pytest.skip with a print + clean exit)
email = os.getenv("AURA_EMAIL")
password = os.getenv("AURA_PASSWORD")
if not email or not password:
    pytest.skip("AURA_EMAIL/AURA_PASSWORD not set; skipping live Aura API tests")
```
Demo adaptation (D-07): keep the same env-detection, but exit cleanly instead of skipping:
```python
if not os.getenv("AURA_EMAIL") or not os.getenv("AURA_PASSWORD"):
    print("AURA_EMAIL / AURA_PASSWORD not set — set them (or a local .env) to run the demo.")
    sys.exit(0)   # clean exit, NOT an error
```
Note: `Aura.login()` already defaults its args to `os.getenv('AURA_EMAIL'/'AURA_PASSWORD')` (`auraframes/aura.py:36`), so the guard only detects-and-messages; `login()` reads the env itself.

**Facade-orchestration pattern** — the exact methods the demo must reuse (no new logic), from `auraframes/aura.py`:
```python
# auraframes/aura.py — method surface the demo sequences verbatim
def login(self, email=os.getenv('AURA_EMAIL'), password=os.getenv('AURA_PASSWORD')):  # :36
def get_all_assets(self, frame_id: str, limit: int = 1000, page_delay: float = 0.0):   # :55  (cursor loop, READ-03)
def download_images_from_assets(self, assets: list[Asset], base_path: str):            # :82  (tqdm + per-asset get_image_from_asset, swallows failures)
```
`frame_api.get_frames()` returns `list[Frame]` (see `tests/test_read_path.py:32,49,79`). The login → list → fetch → download sequence is shown end-to-end in `tests/test_read_path.py:79-97`.

**Asset-selection pattern** — copy from `tests/test_read_path.py:10-14, 79-94` (first frame → first geo image asset → fallback chain):
```python
# tests/test_read_path.py:10-14  (image-asset predicate)
def _is_image_asset(asset) -> bool:
    return bool(asset.thumbnail_url) and not asset.video_url and not asset.is_live

# tests/test_read_path.py:79-94  (selection: geo image > image > first asset)
frame = aura.frame_api.get_frames()[0]
assets = aura.get_all_assets(frame.id)
image_assets = [a for a in assets if _is_image_asset(a)]
geo_image_assets = [a for a in image_assets if a.location_name]
asset = (geo_image_assets or image_assets or assets)[0]
```

**Download + EXIF pattern** — reuse `export.get_image_from_asset` (single asset) or `aura.download_images_from_assets` (list); do NOT hand-roll. From `tests/test_read_path.py:97` and `auraframes/export.py:41-53`:
```python
# tests/test_read_path.py:97  — single-asset download into a dir (note trailing os.sep)
export.get_image_from_asset(asset, str(out_dir) + os.sep, aura.exif_writer)
```
```python
# auraframes/export.py:41-53  — signature + cache behavior to be aware of
def get_image_from_asset(asset, path, exif_writer=None, ignore_cache=False):
    new_filename = os.path.join(path, f'{_get_path_safe_datetime(asset.taken_at_dt)}-{asset.file_name}')
    if os.path.isfile(new_filename) and not ignore_cache:
        with open(new_filename, 'rb') as in_file:
            return in_file.read()   # ← returns cached bytes if file already exists (Pitfall 4)
    ...
```
`get_image_from_asset` does not return the saved path; if the demo wants to print it, glob the (gitignored) output dir as the test does at `tests/test_read_path.py:99-104`.

**Output dir (gitignored):** write to `asset_images/` — already in `.gitignore` (research `[VERIFIED: .gitignore grep]`, lines ~91-94). No new ignore rule needed. Create the dir before download (`os.makedirs(..., exist_ok=True)`), mirroring `Aura._init_logger`'s `os.makedirs('logs/', exist_ok=True)` at `auraframes/aura.py:135`.

**Imports pattern** — `main.py` should follow the repo's stdlib-then-package grouping (see `auraframes/aura.py:1-20`); the demo needs `os`, `sys`, `from auraframes.aura import Aura`, and `from auraframes import export` (per `tests/test_read_path.py:1,5`).

---

### `VERIFICATION-REPORT.md` (doc / report — repo root, CREATE)

**Content analog:** `.planning/phases/02-live-read-path-verification/02-LIVE-EVIDENCE.md` — this is a restructure-and-cite job (D-04), not new investigation. Every section below already has its source there.

**Status-table pattern** — copy/refresh the READ-01..04 table verbatim from `02-LIVE-EVIDENCE.md:25-30`:
```markdown
| Req | Test | Result | Evidence |
|-----|------|--------|----------|
| READ-01 | test_read_01_login | PASS | Login injected x-token-auth + x-user-id onto the shared session |
| READ-02 | test_read_02_list_frames | PASS | Listed frame "Cadre de Fabrice" (c063b384-…) |
| READ-03 | test_read_03_pagination | PASS | get_all_assets(limit=38) drained 77 assets across pages, len==total==77 |
| READ-04 | test_read_04_download_exif | PASS | Downloaded asset 46407e1c-… via image+location_name; DateTimeOriginal read back; GPS IFD "Oo, France" |
```

**Drift-catalog pattern** — the 4 schema drifts repaired are written verbatim at `02-LIVE-EVIDENCE.md:43-61` (User Optional fields; `Feature` enum `_missing_`→UNKNOWN; `Asset.unglacierable` nullable; `total_asset_count`→`frame.num_assets`).

**Deferred-drift pattern** — GPS lat/long swap, `02-LIVE-EVIDENCE.md:63-67` (readable but transposed; deferred).

**Security/redaction-proof pattern** — cite the grep *proof* (counts), never raw secrets, from `02-LIVE-EVIDENCE.md:32-41` (0 plaintext password occurrences; `auth_token': '***REDACTED***'` marker present).

**Recommended section order** (from RESEARCH.md §"Verification Report Structure"): Header (date + one-line verdict) → How verified (the `uv run --extra dev pytest -m live -s` command + summary line + pointer to `02-LIVE-EVIDENCE.md`) → READ-01..04 table → drift repaired → drift deferred → silent-error masking removed (criterion 4) → caveats (pagination/limit, no retry/backoff) → what is NOT verified (upload/async/AWS config/typed exceptions).

**Fresh-run line (D-08):** prepend a dated result line from a fresh `uv run --extra dev pytest -m live -s` run (expected shape "4 passed, 9 deselected", per `02-LIVE-EVIDENCE.md:18-21`).

---

### `README.md` (doc — EDIT / reconcile)

**No code analog** — pure prose. Authoritative facts come from `auraframes/utils/settings.py` (env-var truth) and `02-LIVE-EVIDENCE.md` (verification status). Existing content is at `README.md:1-69`.

**The fix (D-01):** replace `AURA_USERNAME` (`README.md:8`) with `AURA_EMAIL`. The real var is read at `auraframes/aura.py:36` / `tests/conftest.py:23`. Required: `AURA_EMAIL`, `AURA_PASSWORD`. Optional + defaults: `AURA_LOCALE` (`en-US`), `AURA_APP_IDENTIFIER` (`com.pushd.client`), `AURA_DEVICE_IDENTIFIER` (`0000000000000000`).

**Keep-but-flag (D-02):** retain the upload-image flow + mermaid (`README.md:17-52`) and the SQS/TODO notes (`README.md:62-69`), each flagged *"documented from code, NOT verified in this revive milestone."*

**Add (D-03/D-05):** one-line status + link (*"Read path: VERIFIED — see `VERIFICATION-REPORT.md`"*, no duplicated table) and the `uv` setup/run commands (see Shared Patterns below).

## Shared Patterns

### Credential handling (env-first, secrets out of VCS)
**Source:** `tests/conftest.py:1-10, 23-26`; `auraframes/aura.py:36`
**Apply to:** `main.py` (runtime guard), `README.md` + `VERIFICATION-REPORT.md` (docs reference `.env.sample`, never real secrets)
```python
# tests/conftest.py:10 — .env load is a no-op when absent; shell vars win
load_dotenv()
# env vars read directly; missing creds → clean skip/exit, never a crash
```

### `uv` command surface (ENV-04 — the canonical run/setup commands)
**Source:** RESEARCH.md "Code Examples" (verified against installed uv 0.11.7 + `pyproject.toml`/`.python-version`)
**Apply to:** `README.md` setup section; `VERIFICATION-REPORT.md` "How verified" section
```bash
uv sync                                   # runtime deps only (run the client)
uv run python main.py                     # the human-runnable read-path demo
uv sync --extra dev                       # pytest/python-dotenv live in the dev EXTRA (opt-in!)
uv run --extra dev pytest -m live -s      # the asserted proof — 4 passed, 9 deselected
uv run pytest -m "not live"               # credential-less default suite stays green
```
**Landmine:** `pytest` is in `[project.optional-dependencies].dev` — uv does NOT install it by default. Any documented live-test command MUST include `--extra dev` or a prior `uv sync --extra dev`, or it fails on a clean checkout.

### Gitignored output dir (no tracked artifacts)
**Source:** `.gitignore` (`asset_images/`, `logs/`, `cache/` already ignored); `auraframes/aura.py:135` (`os.makedirs('logs/', exist_ok=True)`)
**Apply to:** `main.py` download target — reuse `asset_images/`; create with `os.makedirs(..., exist_ok=True)`.

### Anti-patterns to avoid (from RESEARCH.md)
- Reintroducing `AURA_USERNAME` anywhere — `AURA_EMAIL` is the only correct var.
- Documenting bare `uv run pytest` for the live suite (missing `--extra dev`).
- Pasting real tokens/passwords into the report (cite redaction proof, counts only).
- Adding new client logic to `main.py` (D-07 — orchestrate existing facade methods only).
- Duplicating the status table in README (D-03 — link to the report).

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `README.md` | doc | n/a | Pure prose reconciliation; no code analog. Facts sourced from `settings.py` + `02-LIVE-EVIDENCE.md`. |

(`VERIFICATION-REPORT.md` has a strong *content* analog in `02-LIVE-EVIDENCE.md`, so it is not listed here.)

## Metadata

**Analog search scope:** `main.py`, `tests/` (conftest, test_read_path), `auraframes/aura.py`, `auraframes/export.py`, `.planning/phases/02-live-read-path-verification/02-LIVE-EVIDENCE.md`, `README.md`
**Files scanned:** 7
**Pattern extraction date:** 2026-06-29
