# Roadmap: Aura Frames Python Client — Revive & Verify

## Overview

This milestone revives a ~3-year-old reverse-engineered Aura Frames cloud client and proves
its core read path still works. The journey runs in three sequential steps: first get the
project installing and importing on a current Python 3.14 / `uv` toolchain (which forces a
pydantic v1→v2 migration), then verify the live read path end-to-end against a real account
(login → list frames → fetch assets → download one image with EXIF), and finally document the
run flow and record a verification report capturing what still works versus where the
undocumented API has drifted. Each phase must complete before the next can be verified.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Toolchain Revival** - Project installs and imports on Python 3.14 via `uv` with the model layer migrated to pydantic v2 (completed 2026-06-29)
- [ ] **Phase 2: Live Read-Path Verification** - Login, list frames, fetch assets, and download one image with EXIF verified against the live API
- [ ] **Phase 3: Run Docs & Verification Report** - Documented `uv` setup/run commands plus a report of what works and where the API has drifted

## Phase Details

### Phase 1: Toolchain Revival

**Goal**: The project installs, builds, and imports cleanly on Python 3.14 managed by `uv`, with the pydantic model layer running on v2.
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: ENV-01, ENV-02, ENV-03
**Success Criteria** (what must be TRUE):

  1. `uv sync` resolves and installs every dependency on Python 3.14 with no build failures
  2. A `pyproject.toml` defines the project and dependencies, and the UTF-16 `requirements.txt` is gone
  3. `import auraframes` and all `auraframes/models/*` modules import without error under pydantic v2
  4. Partial models (e.g. `FramePartial` via the `AllOptional` metaclass) still expose all fields as optional

**Plans**: 2 plans
Plans:
**Wave 1**

- [x] 01-01-PLAN.md — Migrate dependency management to `uv` + `pyproject.toml`, resolve all deps on Python 3.14, commit `uv.lock` (ENV-01, ENV-02)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 01-02-PLAN.md — Migrate the model layer to pydantic v2 (factory, field_validator, io serialization), import-clean package + smoke test (ENV-03)

### Phase 2: Live Read-Path Verification

**Goal**: The revived client performs the full read path against the live Aura API using real credentials.
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: READ-01, READ-02, READ-03, READ-04
**Success Criteria** (what must be TRUE):

  1. The client logs in against the live API with real credentials and obtains a valid auth token / user id
  2. The client lists the account's frames and prints their names and ids
  3. The client fetches a chosen frame's assets, iterating all pages via the cursor-based pagination
  4. The client downloads one asset image to disk with EXIF datetime + GPS readable in the saved file

**Plans**: 2 plans

Plans:

- [ ] 02-01: Verify login (READ-01) and frame listing (READ-02) against the live API
- [ ] 02-02: Verify paginated asset fetch (READ-03) and image download with EXIF (READ-04)

### Phase 3: Run Docs & Verification Report

**Goal**: A developer can set up and run the client from documented `uv` commands, and a report records the verified read-path status and any API drift.
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: ENV-04, DOC-01
**Success Criteria** (what must be TRUE):

  1. A developer following only the documented `uv` commands can set up the environment and run the client from a clean checkout
  2. Docs list the required env vars (`AURA_EMAIL`/`AURA_PASSWORD`, optional locale/device) and the exact `uv` run commands
  3. A verification report records each read-path step (login, list, fetch, download) as working or drifted, with evidence
  4. Any API drift or silent-error masking discovered during verification is documented with specifics

**Plans**: 1 plan

Plans:

- [ ] 03-01: Write developer setup/run docs (ENV-04) and the read-path verification report (DOC-01)

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Toolchain Revival | 2/2 | Complete   | 2026-06-29 |
| 2. Live Read-Path Verification | 0/2 | Not started | - |
| 3. Run Docs & Verification Report | 0/1 | Not started | - |
