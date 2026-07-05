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
> ground truth. The natural next core value is proving the **write/upload path**
> (select_asset → S3 → SQS → batch_update) the same way.

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

### Active

<!-- v1.0 and v1.1 fully validated. The next milestone starts fresh via /gsd-new-milestone;
     the items below are candidates carried forward, not yet committed scope. -->

- _All v1.0 and v1.1 requirements validated — see Validated above._
- ⏭ (next-milestone candidate) Verify the **write/upload** round-trip live: select_asset → S3 → SQS → batch_update
- ⏭ (next-milestone candidate) Complete the remaining "lift tests off the live network" slice: candidates #2 (authenticated value) and #4 (injected config)
- ⏭ (next-milestone candidate) Harden the deferred code smells (MOD-01 async, MOD-02 config-ize AWS pool IDs/bucket, MOD-03 typed exceptions, `Aura._init_logger()` loguru sink leak on repeated construction)

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
*Last updated: 2026-07-05 after v1.1 milestone (Client Transport Seam for Offline Testability) shipped — added the `Client`/`Aura` DI seam and an offline `httpx.MockTransport` test harness, lifting most of `test_read_path.py` off the live network while keeping the `@live` suite as the drift oracle. Next: `/gsd-new-milestone` to scope the write/upload path, or continue the "lift tests off the live network" slice with candidates #2/#4.*
