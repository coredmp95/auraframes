# Roadmap: Aura Frames Python Client — Revive & Verify

## Milestones

- ✅ **v1.0 Revive & Verify** — Phases 1-3 (shipped 2026-06-30) — the ~3-year-old codebase runs again on Python 3.14/`uv`/pydantic v2, read path proven live
- ✅ **v1.1 Client Transport Seam** — Phase 4 (shipped 2026-07-05) — additive DI seam + offline `httpx.MockTransport` harness, lifting most read-path tests off the live network
- ✅ **v2.0 Directory-to-Frame Sync** — Phases 5-10 (shipped 2026-09-02) — a real `status`/`inspect`/`sync`/`push` CLI that mirrors a local photo directory to a live Aura frame, with the write path proven live for the first time and hide-by-default removal

## Phases

<details>
<summary>✅ v1.0 Revive & Verify (Phases 1-3) — SHIPPED 2026-06-30</summary>

Full detail archived in [`milestones/v1.0-ROADMAP.md`](./milestones/v1.0-ROADMAP.md).

- [x] Phase 1: Toolchain Revival (2/2 plans) — completed 2026-06-29 — installs/imports on Python 3.14 via `uv`, model layer on pydantic v2
- [x] Phase 2: Live Read-Path Verification (2/2 plans) — completed 2026-06-29 — login, list frames, paginated asset fetch, image download with EXIF verified live
- [x] Phase 3: Run Docs & Verification Report (1/1 plan) — completed 2026-06-29 — documented `uv` setup/run + repo-root VERIFICATION-REPORT.md

</details>

<details>
<summary>✅ v1.1 Client Transport Seam (Phase 4) — SHIPPED 2026-07-05</summary>

Full detail archived in [`milestones/v1.1-ROADMAP.md`](./milestones/v1.1-ROADMAP.md).

- [x] Phase 4: Client Transport Seam for Offline Testability (3/3 plans) — completed 2026-07-05 — additive `Client(transport=...)`/`Aura(client=...)` DI seam, reusable offline `httpx.MockTransport` harness + sanitized fixtures, lifting most of `test_read_path.py` off the live network

</details>

<details>
<summary>✅ v2.0 Directory-to-Frame Sync (Phases 5-10) — SHIPPED 2026-09-02</summary>

Full detail archived in [`milestones/v2.0-ROADMAP.md`](./milestones/v2.0-ROADMAP.md).
Requirements archived in [`milestones/v2.0-REQUIREMENTS.md`](./milestones/v2.0-REQUIREMENTS.md).

Safety-first, read-before-write: every phase before Phase 8 touched only already-live-verified read endpoints, sequencing all genuine new write-path risk into a single, well-prepared phase.

- [x] Phase 5: CLI Skeleton + Status (2/2 plans) — completed 2026-07-06 — packaged `aura-cli` entrypoint, `status` reports config/auth health and account frames, quiet by default with opt-in `--debug`
- [x] Phase 6: Inspect + Frame Resolution (2/2 plans) — completed 2026-07-07 — `inspect --frame <name|id>` with name-substring/exact-ID resolution; live spike answered the `md5_hash`-on-read question that shaped Phase 7
- [x] Phase 7: Sync-Diffing Engine (Dry-Run Only) (3/3 plans) — completed 2026-07-07 — `compute_plan()` content-hash diffing with structurally no reachable mutating primitive; hash format confirmed byte-identical live
- [x] Phase 8: Destructive Execution (Upload + Delete Verification) (4/4 plans) — completed 2026-07-08 — `--apply`/`--yes` runs the plan for real; upload round-trip, `remove_asset` and `delete_asset` blast radius all proven live for the first time
- [x] Phase 9: Proactive Write Rate-Limiter & Geo Guard (2/2 plans) — completed 2026-07-09 — `auraframes/ratelimit.py`: persisted `WriteBudget` token bucket + fail-open `check_geo` pre-flight, wired as the default for every `--apply`
- [x] Phase 10: Hide-instead-of-delete sync mode (4/4 plans) — completed 2026-08-25 — `sync --apply` hides removed photos via `exclude_asset` and re-shows restored ones; the two destructive tiers are opt-in and count-gated

**Milestone outcome:** 28/28 requirements complete, all 6 phases verified, closed as a verified closeout with 0 open artifacts. Live evidence corrected two working theories along the way: the visibility flag lives in `asset_settings[asset_id].selected` (not `Asset.selected`), and the write "geofence" was disproven — the 401 lockout is transient auth-token expiry.

**Known defects carried forward (open, non-blocking):** intermittent write 401s clearing on retry (~4 in 10 live runs); 58 unremovable placeholder rows from incomplete `select_asset` calls; `test_read_03_pagination` asserting `drained == num_assets`, two counts the server does not keep consistent.

</details>

## Backlog

_No items currently in backlog._
