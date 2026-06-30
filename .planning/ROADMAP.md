# Roadmap: Aura Frames Python Client — Revive & Verify

## Milestones

- ✅ **v1.0 Revive & Verify** — Phases 1-3 (shipped 2026-06-30)
- 📋 **v2.0 (next)** — write/upload path verification + deferred hardening (not yet scoped — run `/gsd-new-milestone`)

## Phases

<details>
<summary>✅ v1.0 Revive & Verify (Phases 1-3) — SHIPPED 2026-06-30</summary>

Full detail archived in [`milestones/v1.0-ROADMAP.md`](./milestones/v1.0-ROADMAP.md).

- [x] Phase 1: Toolchain Revival (2/2 plans) — completed 2026-06-29 — installs/imports on Python 3.14 via `uv`, model layer on pydantic v2
- [x] Phase 2: Live Read-Path Verification (2/2 plans) — completed 2026-06-29 — login, list frames, paginated asset fetch, image download with EXIF verified live
- [x] Phase 3: Run Docs & Verification Report (1/1 plan) — completed 2026-06-29 — documented `uv` setup/run + repo-root VERIFICATION-REPORT.md

</details>

### 📋 v2.0 (next milestone — not yet scoped)

Candidates carried forward (commit via `/gsd-new-milestone`):

- [ ] Verify the write/upload round-trip live (select_asset → S3 → SQS → batch_update)
- [ ] Deferred hardening: MOD-01 async HTTP, MOD-02 config-ize AWS pool IDs/bucket, MOD-03 typed exception hierarchy

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Toolchain Revival | v1.0 | 2/2 | Complete | 2026-06-29 |
| 2. Live Read-Path Verification | v1.0 | 2/2 | Complete | 2026-06-29 |
| 3. Run Docs & Verification Report | v1.0 | 1/1 | Complete | 2026-06-29 |
