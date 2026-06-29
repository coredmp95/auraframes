# Aura Frames Python Client — Revive & Verify

## What This Is

An unofficial, reverse-engineered Python client for the Aura Frames (Pushd) digital
photo-frame cloud API. It authenticates with an Aura *account* and pulls/pushes photos
through the cloud API (`api.pushd.com/v5`) plus AWS S3/SQS — it does not talk to the
frame over the local network. This milestone revives the ~3-year-old codebase so it runs
again on a current toolchain and verifies the core read flow still works against the live
service.

## Core Value

Prove the existing client still works end-to-end (login → list → download) on a current
Python toolchain, so we know exactly what survives before building anything new.

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

### Active

<!-- This milestone: revive the toolchain and verify the read path. -->

- [ ] Project installs and runs on Python 3.14 managed by `uv`
- [ ] Dependencies resolve and build on Python 3.14 (pydantic v1→v2 migration, newer pillow/httpx/boto3 as needed)
- [ ] Dependency manifest migrated from the UTF-16 `requirements.txt` to `pyproject.toml`
- [ ] Login verified against the live API with real account credentials
- [ ] Listing frames verified against the live API
- [ ] Fetching a frame's assets verified against the live API
- [ ] Downloading one image with EXIF intact verified end-to-end
- [ ] Documented status of what still works vs. where the API has drifted

### Out of Scope

- Device-on-LAN / MITM traffic capture — deferred to a later reverse-engineering milestone
- Reversing the frame's own rendering process / firmware — later milestone
- Verifying the upload round-trip — the done bar is the read path; upload verification deferred
- SQS push-flow deep-dive (the TODO to map the real SQS behaviour) — later milestone
- Async migration of the HTTP client — not required to revive; existing sync client is fine

## Context

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
| Adopt `uv` as package manager | Fast, manages venv + deps + interpreter via `pyproject.toml`; replaces broken UTF-16 `requirements.txt` | — Pending |
| Target Python 3.14 (not pin an older interpreter) | Stay on the installed runtime; accept the dep upgrades it forces | — Pending |
| Accept pydantic v1→v2 migration as a consequence of 3.14 | pydantic 1.10.4 won't build on 3.14; v2 is the supported path | — Pending |
| Done bar = read path only (login → list → download) | Smallest proof the client is alive; upload deferred | — Pending |
| Pragmatic modernization, not full cleanup | Goal is "verify where we are," not a rewrite | — Pending |

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
*Last updated: 2026-06-29 after initialization*
