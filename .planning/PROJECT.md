# Aura Frames Python Client — Revive & Verify

## What This Is

An unofficial, reverse-engineered Python client for the Aura Frames (Pushd) digital
photo-frame cloud API. It authenticates with an Aura *account* and pulls/pushes photos
through the cloud API (`api.pushd.com/v5`) plus AWS S3/SQS — it does not talk to the
frame over the local network. **v1.0 (shipped 2026-06-30)** revived the ~3-year-old
codebase so it runs again on a current toolchain (Python 3.14 + `uv`, pydantic v2) and
verified the core read flow (login → list → download) still works end-to-end against the
live service. **v1.1 (shipped 2026-07-05)** added a `Client`/`Aura` dependency-injection
transport seam and a reusable offline `httpx.MockTransport` test harness, lifting most of
the read-path test suite off the live network while a byte-identical `@live` suite
remains the drift oracle.

## Core Value

Prove the existing client still works end-to-end (login → list → download) on a current
Python toolchain, so we know exactly what survives before building anything new.

> ✓ **Achieved in v1.0.** The read path is proven live (login → list → 77-asset cursor
> drain → image download with EXIF intact). **v1.1** made that proof cheap to re-run
> (offline, no credentials) without weakening it — the `@live` suite still exists as the
> ground truth. **v2.0** shifts the core value: prove the **write path** the same way,
> and turn that proof into a real usable capability — syncing a local photo directory to
> a frame — rather than another internal-only verification pass.

## Current Milestone: v2.0 Directory-to-Frame Sync

**Goal:** Ship a real, usable CLI — mirror a local photo directory to an Aura frame,
plus diagnostics — verifying the write path live for the first time.

**Target features:**
- `sync <dir> --frame <name/id>` — full mirror (upload new, delete removed), content-hash
  diffing, dry-run by default, `--apply`/`--yes` to execute
- `inspect --frame <name/id>` — list photos currently on the frame + frame metadata
  (name, owner, member count, stats)
- `status` — config/auth health check (creds set? login succeeds? which account?) +
  account info (frames on the account); storage/quota added only if research finds an
  actual API field for it
- Live verification: `select_asset → S3 → SQS → batch_update` upload path, plus the
  delete/remove path, proven against a real account/frame
- Frame targeting by name or ID (explicit `--frame` arg)

**Key context:** No CLI exists today (`main.py` is a demo only) — this is the first
user-facing entry point. Full-mirror deletion is destructive, so dry-run-first is a hard
safety default. Done = a real round-trip on the user's live frame with a test directory,
verified visually + via `inspect`.

## Requirements

### Validated

<!-- Inferred from existing code (April 2023). Built and shipped previously; working
     status against the *current* stack/API is what this milestone verifies. -->

- ✓ Authenticate to the Aura cloud API via email/password token auth — existing
- ✓ List and fetch frames and their assets (cursor-based pagination) — existing
- ✓ Download frame images via the image proxy with EXIF (datetime + GPS) injection — existing
- ✓ Upload images mimicking the device flow (select_asset → S3 → SQS → batch_update) — existing
- ✓ AWS Cognito anonymous auth for S3/SQS access — existing
- ✓ Pydantic DTO model layer hydrating API responses — existing
- ✓ Environment-variable based configuration — existing
- ✓ Project installs and imports on Python 3.14 managed by `uv` — Validated in Phase 1: Toolchain Revival
- ✓ Dependencies resolve and build on Python 3.14 (pydantic v1→v2 migration; pillow 12, httpx 0.28, boto3 1.43) — Validated in Phase 1: Toolchain Revival
- ✓ Dependency manifest migrated from the UTF-16 `requirements.txt` to `pyproject.toml` + `uv.lock` — Validated in Phase 1: Toolchain Revival
- ✓ Login verified against the live API with real account credentials (READ-01) — Validated in Phase 2: Live Read-Path Verification
- ✓ Listing frames verified against the live API (READ-02) — Validated in Phase 2: Live Read-Path Verification
- ✓ Fetching a frame's assets with cursor pagination verified live — 77 assets across multiple pages (READ-03) — Validated in Phase 2: Live Read-Path Verification
- ✓ Downloading one image with EXIF (datetime + GPS) read back from disk verified live (READ-04) — Validated in Phase 2: Live Read-Path Verification
- ✓ Documented `uv` setup/run commands + env vars and a repo-root VERIFICATION-REPORT.md recording read-path status and API drift (ENV-04, DOC-01) — Validated in Phase 3: Run Docs & Verification Report
- ✓ `Client`/`Aura` dependency-injection transport seam (`Client(transport=...)`, `Aura(client=...)`) plus a reusable offline `httpx.MockTransport` test harness and sanitized fixtures, lifting most of `test_read_path.py`'s assertions off the live network while leaving the `@live` suite untouched as the drift oracle (R4-SEAM-CLIENT, R4-SEAM-AURA, R4-FIXTURES, R4-FIXTURE-VALIDITY, R4-HARNESS, R4-OFFLINE-TESTS, R4-LIVE-UNCHANGED) — Validated in Phase 4: Client Transport Seam for Offline Testability
- ✓ Packaged `aura-cli` entrypoint distinct from `main.py`, with a `status` subcommand reporting config/auth health, login result, and the account's frames — quiet by default with an opt-in `--debug` flag for verbose loguru output (CLI-01, CLI-02) — Validated in Phase 5: CLI Skeleton + Status
- ✓ `inspect --frame <name|id>` resolves a frame by case-insensitive name substring or exact ID, displays its photos and metadata (name, owner, contributor count, asset count), and gives a clear disambiguation error on ambiguous name matches; `--debug` promoted to a root-level flag (CLI-03, CLI-04) — Validated in Phase 6: Inspect + Frame Resolution
- ✓ `sync <dir> --frame <name|id>` computes and prints a full upload/delete/unchanged dry-run plan by content-hash diffing (never filename), with zero mutating call reachable from the command — structurally dry-run only, no `--apply`/`--yes` path exists yet (SYNC-01, SYNC-02) — Validated in Phase 7: Sync-Diffing Engine (Dry-Run Only)
- ✓ `sync --apply`/`--yes` executes the computed plan for real — uploads new local files (`select_asset` → S3 → `batch_update`) and removes gone-locally frame photos via `remove_asset`; prints upload/delete/unchanged counts before applying and exits non-zero on any execution failure (SYNC-03, SYNC-04) — Validated in Phase 8: Destructive Execution (Upload + Delete Verification)
- ✓ Image upload round-trip verified live against a real account/frame (WRITE-01) — Validated in Phase 8: Destructive Execution (Upload + Delete Verification)
- ✓ `remove_asset`'s real behavior verified live — disassociates from the frame only (WRITE-02) — Validated in Phase 8: Destructive Execution (Upload + Delete Verification)
- ✓ `delete_asset`'s real behavior verified live — asset-scoped `DELETE /assets/{id}.json`, broader than `remove_asset`, correctly left unwired from `--apply` (WRITE-03) — Validated in Phase 8: Destructive Execution (Upload + Delete Verification)
- ✓ Hardcoded frame ID in the SQS upload-confirmation lookup fixed and confirmed live for an arbitrary frame (WRITE-04) — Validated in Phase 8: Destructive Execution (Upload + Delete Verification)
- ✓ Fail-loud error handling extended to the write/delete endpoints (WRITE-05) — Validated in Phase 8: Destructive Execution (Upload + Delete Verification)
- ✓ Proactive client-side write rate-limiter (`WriteBudget` token bucket, persisted per-account + reconciled on real anti-abuse trips) that waits/stops before tripping the Pushd limit, plus a configurable geo pre-flight guard (`check_geo`, fail-open by default) that refuses writes when the exit-IP country differs from the account's country — wired into `execute_plan`/`run_sync`/CLI as a true no-op when unconfigured, 100% offline-tested (ANTI-01..ANTI-07) — Validated in Phase 9: Proactive Write Rate-Limiter & Geo Guard

### Active

<!-- v1.0, v1.1, and v2.0 (Directory-to-Frame Sync) fully validated as of Phase 8;
     v2.x anti-abuse hardening (ANTI-01..ANTI-07) validated as of Phase 9.
     Milestone completion review is a separate step — see /gsd-complete-milestone. -->

- _All v1.0, v1.1, v2.0, and v2.x (Phase 9 anti-abuse) requirements validated — see Validated above._
- ⏭ (future-milestone candidate) Complete the remaining "lift tests off the live network" slice: candidates #2 (authenticated value) and #4 (injected config)
- ⏭ (future-milestone candidate) Harden the deferred code smells (MOD-01 async, MOD-02 config-ize AWS pool IDs/bucket, MOD-03 typed exceptions, `Aura._init_logger()` loguru sink leak on repeated construction)
- ⏭ (future-milestone candidate) Phase 8 code review flagged 3 unresolved critical findings (see `08-REVIEW.md`): `AssetPartialId`'s cross-field validator is a no-op for the common construction path; `batch_update`'s partial-success response isn't validated against the requested id list; hardcoded `data_uti='public.jpeg'` will silently mis-tag/fail `.png`/`.heic` uploads (Pillow has no HEIC decoder in this project's environment)
- ⏭ (future-milestone candidate) Auth-token-expiry-mid-batch: a live incident during Phase 8 verification showed a single large `--apply` run can outlive the auth session's token lifetime (WRITE-05/D-08 handled it correctly — no data corruption — but a token-refresh-mid-batch mechanism would be a future hardening candidate)

### Out of Scope

- Device-on-LAN / MITM traffic capture — deferred to a later reverse-engineering milestone
- Reversing the frame's own rendering process / firmware — later milestone
- Verifying the upload round-trip — the done bar is the read path; upload verification deferred
- SQS push-flow deep-dive (the TODO to map the real SQS behaviour) — later milestone
- Async migration of the HTTP client — not required to revive; existing sync client is fine

## Context

### Current state (after v1.1, 2026-07-05)

- **Shipped v1.0** — read path proven live against `api.pushd.com/v5`. ~1,760 LOC Python.
- **Shipped v1.1** — `Client`/`Aura` DI transport seam + offline `httpx.MockTransport`
  harness; ~1,942 LOC Python (`auraframes` + `tests` + `main.py`).
- **Tech stack:** Python 3.14 + `uv` (`pyproject.toml` + committed `uv.lock`), pydantic v2,
  httpx 0.28, boto3 1.43, Pillow 12. Dependency manifest migrated off the broken UTF-16
  `requirements.txt`.
- **Verification:** credential-gated pytest live suite (READ-01–04) that skips cleanly
  without creds; repo-root `VERIFICATION-REPORT.md` from a live run; `main.py` facade-only
  read-path demo that loads `.env`.
- **Post-verification hardening:** `main.py` loads a local `.env`
  (`python-dotenv` promoted to a runtime dep), and `Aura.login` now resolves credentials at
  call time rather than import time — fixing an HTTP 475 caused by Python's early-bound
  default arguments evaluating `os.getenv` before `load_dotenv()` ran.
- **Phase 4 (2026-07-04):** Landed architecture-review candidate #1 — an additive DI seam
  (`Client(transport=...)`, `Aura(client=...)`, closing the old `# TODO: Can probably use DI`)
  plus a reusable offline test harness (`tests/offline.py`, `httpx.MockTransport`-backed) and
  5 sanitized JSON fixtures. Most of `test_read_path.py`'s assertions (login headers, frame
  hydration, pagination drain, both error-raise mechanisms) now run offline with zero
  credentials/network; the live `@live` suite is byte-identical and remains the drift oracle.
  Code review flagged one pre-existing bug as a warning (not fixed here): `Aura._init_logger()`
  leaks loguru sinks/log files on repeated `Aura()` construction, amplified by the new
  per-test `offline_aura()` pattern. Candidates #2 (authenticated value) and #4 (injected
  config) remain open for a future phase to complete the "lift tests off the live network" slice.
- **Known still-open tech debt (deferred, not blocking):** hardcoded AWS pool IDs / bucket
  name, unguarded post-login state, silent `pass` on some API `error` fields, sync-only HTTP.
- **Phase 5 (2026-07-06):** Shipped the packaged `aura-cli` entrypoint with a `status`
  subcommand (config health, login, frame listing), offline-tested via the v1.1 DI seam.
  A live UAT pass flagged verbose loguru request/response noise leaking to stderr; closed
  in the same phase (05-02, gap closure) with a quiet-by-default `_configure_cli_logging()`
  helper and an opt-in `--debug` flag, re-confirmed live. Threat register (6 threats,
  T-05-01–05 + T-05-SC) fully mitigated/accepted — see `05-SECURITY.md`. A todo carries
  forward the idea of promoting `--debug` to a global flag once Phase 6 designs `inspect`.
- **Phase 6 (2026-07-06):** Shipped `aura-cli inspect --frame <name|id>` (frame resolution
  by name or ID, metadata + first-N photo listing), and folded the `--debug`-promotion todo
  into it (`--debug` is now a root-level `aura-cli` flag). Live spike (Success Criterion 4,
  hard Phase 7 dependency): ran `inspect --debug` against a real frame (106 paginated assets)
  and inspected the logged asset JSON — `md5_hash` is **populated** (non-null base64) for
  101/101 pre-existing photo (`.jpg`) assets, but **not populated** (null) for 5/5 video
  (`.mp4`) assets. Consequence for Phase 7: content-hash diffing via `md5_hash` is viable for
  photos with no fallback needed; a local-manifest/alternate-hash fallback is only required
  scope if video sync ever enters scope.
- **Phase 7 (2026-07-07):** Shipped the dry-run sync-diffing engine (`auraframes/sync.py`
  + `aura-cli sync <dir> --frame <name|id>`), structurally incapable of mutating (no
  `--apply`/`--yes` flag exists yet). Live validation (SYNC-02 success criterion 3, D-09
  precedent from Phase 6's `md5_hash` spike): ran `aura-cli sync ./data/ --frame "Cadre de
  Fabrice"` against a real frame — one local file with a matching original already on the
  frame was correctly classified "Unchanged" while a second, non-matching local file was
  correctly classified "To upload". This confirms the base64-MD5 convention is **byte-identical**
  between local `S3Client.get_md5(original_bytes)` hashing and the frame's reported
  `md5_hash`, making the dry-run diff engine's core content-hash matching assumption sound.
  Unblocks Phase 8 (the write/upload/delete path) to trust the diff without re-deriving
  the hash convention.
- **Phase 8 (2026-07-08) — v2.0 milestone complete:** Shipped `sync --apply`/`--yes`,
  the first mutating path in this codebase's ~3-year history. `execute_plan()` (the
  mutating counterpart to `compute_plan()`) uploads new local files (`select_asset` → S3
  → `batch_update`, via a new `AssetPartial` identity model) and removes gone-locally
  photos via `remove_asset`, with uploads-before-deletes ordering and per-item
  continue-past-failure. Fixed the hardcoded SQS frame-id bug (WRITE-04) and extended
  fail-loud error handling to all write/delete endpoints (WRITE-05). Live-verified
  against "Cadre de Fabrice": the upload round-trip, `remove_asset`, and a standalone
  `delete_asset` probe against a disposable asset all confirmed working as designed —
  `delete_asset` is asset-scoped (`DELETE /assets/{id}.json`, broader than `remove_asset`'s
  frame-scoped disassociation) and remains structurally unreachable from `--apply` (D-06).
  A live-verification incident (an operator run against a near-empty local directory
  triggered a 72-item delete plan against the standing test frame; 25 of 72 deletes hit a
  mid-batch auth-token expiry) validated WRITE-05/SYNC-04's fail-loud, continue-past-failure,
  non-zero-exit design under a real partial-failure condition — no data was lost (photos
  independently backed up) and a fresh re-run completed cleanly. Code review flagged 3
  unresolved critical findings (see Active, future-milestone candidates) that do not block
  this milestone's must-haves but should be triaged before further write-path work.

### Original baseline

- Codebase last touched April 2023; project mapped 2026-06-29 (see `.planning/codebase/`).
- Development machine runs Python 3.14.4; no virtualenv exists yet.
- `requirements.txt` is UTF-16 encoded, which can break tooling; pins are 2022-era
  (`pydantic~=1.10.4`, `pillow~=9.5.0`, `httpx==0.23.1`, `boto3==1.26.38`) and several
  will not build on Python 3.14.
- The model layer uses pydantic v1 `BaseModel` plus an `AllOptional` metaclass
  (`auraframes/models/meta.py`), so a v2 migration is non-trivial but bounded.
- Known code smells from the map: hardcoded AWS pool IDs / bucket name, unguarded
  post-login state, and silent error handling (`pass` on API `error` fields) — relevant
  because silent errors can mask API drift during verification.
- A live Aura account (credentials ready) is available to test against. An Aura frame is
  present on the local network but is not required for this cloud-API milestone.

## Constraints

- **Tech stack**: Python 3.14 with `uv` for env/dependency/interpreter management — user decision.
- **API**: Unofficial, reverse-engineered Aura/Pushd cloud API (`api.pushd.com/v5`) — undocumented and may change without notice; verification is inherently against a moving target.
- **Auth**: Requires live Aura account credentials (`AURA_EMAIL`/`AURA_PASSWORD`); secrets must stay out of version control.
- **Modernization scope**: Pragmatic — change only what's needed to run on 3.14 and prove the read path; avoid broad refactors.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Adopt `uv` as package manager | Fast, manages venv + deps + interpreter via `pyproject.toml`; replaces broken UTF-16 `requirements.txt` | ✓ Good — 37 packages resolved on 3.14, `uv.lock` committed for reproducible installs |
| Target Python 3.14 (not pin an older interpreter) | Stay on the installed runtime; accept the dep upgrades it forces | ✓ Good — all deps resolved to cp314 wheels, no sdist builds |
| Accept pydantic v1→v2 migration as a consequence of 3.14 | pydantic 1.10.4 won't build on 3.14; v2 is the supported path | ✓ Good — `AllOptional` → `make_partial` factory, `@validator` → `@field_validator`, guarded by an import smoke test |
| Done bar = read path only (login → list → download) | Smallest proof the client is alive; upload deferred | ✓ Good — read path proven live end-to-end; upload cleanly deferred to next milestone |
| Pragmatic modernization, not full cleanup | Goal is "verify where we are," not a rewrite | ✓ Good — fixed only what blocked running + masked drift (fail-loud transport, secret redaction); broad refactors left as tracked debt |
| Resolve login creds at call time, not import time | Early-bound default args evaluated `os.getenv` before `load_dotenv()`, sending null creds (HTTP 475) | ✓ Good — None-sentinel pattern + offline regression guard (debug `login-475-null-creds`) |
| Additive `Client(transport=...)` / `Aura(client=...)` DI seam, zero-arg-compatible | Closes the old DI TODO without breaking any existing caller (`main.py`, live tests) | ✓ Good — both constructors stay zero-arg; live suite byte-identical after the change |
| Fixture JSON authored entirely synthetic, not recorded from the live API | Safer sanitization posture — no real secret ever exists in a fixture to leak | ✓ Good — 5 fixtures pass model-hydration + fixture-validity tests |
| `run_status()` returns an int exit code, never calls `sys.exit`; `main()` is the sole `sys.exit` boundary | Mirrors the v1.1 `Aura(client=...)` DI seam so CLI handlers stay synchronously testable via `capsys` without invoking `load_dotenv()` or process exit | ✓ Good — Phase 5's offline test suite drives all three exit paths (missing creds / success / login failure) without subprocess spawning |
| Fix the verbose-loguru-stderr UAT gap from the CLI boundary, not `aura.py` | `Aura._init_logger()`'s `logger.remove()` is commented out and frozen (D-04); the CLI reconfigures loguru's sinks after `Aura()` construction instead of editing the frozen file | ✓ Good — quiet by default, `--debug` opt-in restores verbosity, file sink preserved in both modes; re-verified via real subprocess in 05-VERIFICATION.md |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-07-09 after Phase 9 (Proactive Write Rate-Limiter & Geo Guard) — ANTI-01..ANTI-07 validated: a persisted-per-account `WriteBudget` token bucket + `check_geo` pre-flight guard now make the anti-abuse write-lockout structurally hard to hit (a code-review blocker where the bucket over-refilled after a wait was caught and fixed pre-completion). 21/21 must-haves verified. Next: `/gsd-complete-milestone` to close out v2.0/v2.x, or triage the 3 open code-review findings from Phase 8 first.*
