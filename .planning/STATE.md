---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Directory-to-Frame Sync
current_phase: 10
current_phase_name: hide-instead-of-delete-sync-mode
status: phase-complete
stopped_at: Phase 10 UAT complete (20/20 pass, 2 open defects logged)
last_updated: "2026-08-25T08:05:00.000Z"
last_activity: 2026-08-25
last_activity_desc: Phase 10 UAT complete — all write paths verified end-to-end; 2 defects logged
progress:
  total_phases: 6
  completed_phases: 6
  total_plans: 17
  completed_plans: 17
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-06)

**Core value (v2.0):** Prove the write path the same way v1.0/v1.1 proved the read path, and turn that proof into a real usable capability — mirroring a local photo directory to an Aura frame.
**Current focus:** Phase 10 — hide-instead-of-delete-sync-mode

## Current Position

Phase: 10 (hide-instead-of-delete-sync-mode) — COMPLETE
Plan: 4 of 4
Status: Phase 10 complete — all 4 plans executed, HIDE-01..HIDE-08 satisfied
Last activity: 2026-08-25 — Phase 10 complete (hide default shipped end-to-end)

Progress: [██████████] 100% (4/4 plans complete)

## Performance Metrics

**Velocity:**

- Total plans completed: 8 (across v1.0 + v1.1)
- Average duration: — min
- Total execution time: — hours

**By Phase (shipped milestones):**

| Phase | Milestone | Plans | Status |
|-------|-----------|-------|--------|
| 1-3 | v1.0 | 5 | Complete |
| 4 | v1.1 | 3 | Complete |
| 5 | v2.0 | 2/2 | Complete |
| 6-8 | v2.0 | TBD | Not started |

*Updated after each plan completion*
| Phase 05 P01 | 3min | 3 tasks | 3 files |
| Phase 05 P02 | 21min | 2 tasks | 2 files |
| Phase 06 P01 | 4min | 3 tasks | 4 files |
| Phase 06 P02 | 8min | 2 tasks | 2 files |
| Phase 07 P01 | 2min | 2 tasks | 2 files |
| Phase 07 P02 | 6min | 2 tasks | 2 files |
| Phase 07 P02 | 6min | 2 tasks | 2 files |
| Phase 07 P03 | 3min | 1 tasks | 2 files |
| Phase 08 P01 | 11min | 3 tasks | 6 files |
| Phase 08 P03 | 10min | 2 tasks | 2 files |
| Phase 09 P01 | 12m | 2 tasks | 2 files |
| Phase 09 P02 | 12min | 3 tasks | 8 files |
| Phase 10 P01 | 55min | 2 tasks | 3 files |
| Phase 10 P02 | 20min | 3 tasks | 4 files |
| Phase 10 P03 | 25min | 3 tasks | 5 files |
| Phase 10 P04 | 30min | 3 tasks | 4 files |

## Accumulated Context

### Roadmap Evolution

- Phase 9 added (2026-07-09): Proactive Write Rate-Limiter & Geo Guard — proactive client-side request budget (token bucket, persisted + reconciled) + geo pre-flight guard to make the anti-abuse write-lockout structurally unreachable. Root cause reframed this session: the persistent 401 write-lockout was largely a VPN geo mismatch (Belgium≠France), on top of a real but generous request-rate limit (~42 write requests / ~40 min recovery, measured live). Design spec: docs/superpowers/specs/2026-07-09-write-rate-limiter-design.md
- Phase 10 added (2026-07-09): Hide-instead-of-delete sync mode — `sync --apply` should default to hiding removed photos (marking them invisible on the frame) instead of deleting/removing them, with an opt-in flag for real deletion. Rationale (user): the frame has no photo-count limit, so preservation is the safer default and a mistaken sync should never destroy photos. Open question for planning: which API mechanism backs the app's "make invisible" action and how it maps onto the existing remove_asset/delete_asset/batch_update write path.

### Decisions

Decisions are logged in PROJECT.md Key Decisions table. Recent decisions affecting current work:

- Done bar shifts to the **write path** for v2.0 — upload + delete verified live, delivered as a real `sync`/`inspect`/`status` CLI (not another internal-only pass)
- Safety-first roadmap ordering: Phases 5-7 touch only already-live-verified read endpoints; all new write-path risk is sequenced into Phase 8
- Dry-run is a structural default (separate `compute_plan()`/`execute_plan()`), not an `if apply:` flag — decided at research time, to be enforced in Phase 7
- Additive `Client(transport=...)` / `Aura(client=...)` DI seam (from v1.1) is available to drive the CLI/sync stack offline in tests
- [Phase 05-01]: run_status() never calls sys.exit — returns an int exit code; main() is the only sys.exit boundary, keeping the handler synchronously testable via capsys — Mirrors the Aura(client=...) DI seam pattern established in v1.1 so CLI handlers are testable offline without invoking load_dotenv() or process exit
- [Phase 05-02]: Because `aura.py`'s `_init_logger()` is frozen (D-04), the verbose-stderr UAT gap is fixed from the CLI boundary — `_configure_cli_logging()` calls `logger.remove()` then re-adds the file sink + a WARNING-level stderr sink after `Aura()` construction, rather than editing the frozen file
- [Phase 06-01]: N=10 for the inspect default first-N photo truncation; a trailing +K more line prints when a frame has more assets
- [Phase 06-01]: resolve_frame() returns a status discriminator (resolved/ambiguous/not_found), not a raised exception, per deferred MOD-03
- [Phase 06-02]: md5_hash content-hash diffing is scoped to photos only for Phase 7 - populated for 101/101 photo assets but null for 5/5 video assets on a real frame; a local-manifest fallback is only required scope if video sync enters Phase 7/8 scope
- [Phase 07-01]: scan_directory hashes only jpg/jpeg/png/heic (case-insensitive), reusing S3Client.get_md5 verbatim; non-eligible files counted in skipped_non_image, never erroring
- [Phase 07-01]: compute_plan matches local hashes (demand=1 each, post-dedupe) against frame assets count-for-count (multiset): surplus frame-side duplicate assets beyond local demand become delete candidates; hashless frame assets (videos) excluded from unchanged/delete via frame_no_hash
- [Phase 07-02]: run_sync has structurally no path to a mutating primitive -- no --apply/--yes flag exists, and the function body only calls scan_directory/compute_plan/print (T-07-04)
- [Phase 07-02]: Plan output prints full upload/delete lists with no truncation (D-07), unlike inspect's first-N convention, since a sync review needs every item visible before Phase 8's --apply lands
- [Phase 07-03]: Live validation performed via METHOD A (piggyback on the shipped sync feature itself) rather than a throwaway comparison script, per D-09's precedent of proving via real usage instead of adding a permanent automated fixture
- [Phase 08]: AssetPartial added via make_partial(Asset, "AssetPartial") mirroring FramePartial, no change to Asset.id's type
- [Phase 08]: select_asset/remove_asset raise on nonzero number_failed (not just error envelope) since each call carries exactly one AssetPartialId, making attribution unambiguous (WRITE-05)
- [Phase 08]: batch_update's type hint widened to Asset | AssetPartial rather than a new method, since .dict(include={...}) works unchanged on both
- [Phase 08-02]: execute_plan preserves the double select_asset call + first discarded SQS poll unchanged (RESEARCH.md Pitfall 4) for the first live attempt, rather than collapsing it
- [Phase 08-02]: Partial-failure tests monkeypatch aura.asset_api.batch_update/aura.frame_api.remove_asset directly rather than relying on httpx.MockTransport per-payload discrimination, since MockTransport routes only by path
- [Phase 08-03]: Real S3Client()/SQSClient() are constructed at the CLI boundary only, on confirmed --apply; execute_plan() itself never constructs AWS clients, extending Plan 02's offline-testability seam to the CLI
- [Phase 08-03]: A single confirmation gate covers the whole plan (uploads + deletes together, D-02); apply/confirm/execute logic lives inside run_sync's existing try/except so an execute_plan failure surfaces through the same fail-loud catch as the dry-run path
- [Phase 09-01]: check_geo's resolver keyword defaults to _default_resolver so production wiring needs no explicit resolver, while every test injects a fake explicitly
- [Phase 09-01]: WriteBudget.save() takes no path argument -- it always writes to self.path set at construction, so 09-02's execute_plan integration can call a bare budget.save()
- [Phase 09-01]: TDD gate applied per task (not per plan): Task 1 (WriteBudget) got its own RED/GREEN commit pair, then Task 2 (check_geo) got a second RED/GREEN pair on top
- [Phase 09-02]: settings.py uses bare float(os.getenv(...)) for the four numeric budget settings (no helper needed); only AURA_WRITE_BUDGET_WAIT/AURA_GEO_FAIL_OPEN need the new _bool_env helper since Python's bool('false') is True
- [Phase 09-02]: budget/geo_check are constructed and forwarded for BOTH push --apply and sync --apply by default (built in run_sync from settings env) -- sync gets the same anti-abuse protection as push with zero new sync-only flags
- [Phase 09-02]: execute_plan's budget.save() runs after every normally-returning chunk (success OR ordinary caught failure), but not the upload loop's 'if not prepped: continue' early-exit; reconcile_tripped()+save() fires from 3 sites (2 RateLimitError branches + inside note_failure()'s ConsecutiveWriteFailureError raise)

### Pending Todos

- None currently pending. "Promote `--debug` flag to a global CLI convention" was folded into and resolved by Phase 06-01 (`--debug` is now a root-level `aura-cli` flag) — see `.planning/todos/completed/2026-07-06-promote-debug-flag-to-a-global-cli-convention.md`.

### Blockers/Concerns

- **Phase 6 live spike (hard dependency for Phase 7 design) — RESOLVED 2026-07-06:** confirmed live via `aura-cli --debug inspect` against a real frame (106 paginated assets): `md5_hash` is **populated** (non-null base64) for all 101/101 pre-existing photo (`.jpg`) assets, but **not populated** (null) for all 5/5 video (`.mp4`) assets. Phase 7 consequence: content-hash diffing via `md5_hash` is viable for photos with no fallback needed; a local-manifest/alternate-hash fallback is only required scope if video sync ever enters Phase 7/8 scope.
- **Hash-format mismatch risk (Phase 7) — RESOLVED 2026-07-07:** confirmed live via METHOD A (`aura-cli sync ./data/ --frame "Cadre de Fabrice"`, frame id `c063b384-38fa-4324-aaf8-319d17a5867a`) — dry-run reported "Unchanged: 1" for a directory containing one file with an original that already existed on the frame and one file that did not; the matching file was classified unchanged (not upload), confirming local `get_md5(original_bytes)` equalled that frame asset's `md5_hash` byte-for-byte (SYNC-02 success criterion 3 satisfied), while the other, non-matching file correctly fell into "To upload" — proving the hashing/matching logic discriminates rather than trivially matching everything. Caveat: per D-08's minimal-disclosure convention, the dry-run report only lists upload/delete items in full and reports unchanged as a count, so the specific matched asset's id is not available to cite — the confirmation is the "Unchanged: 1" count itself, corroborated by the other file's correct "To upload" classification in the same run.
- **Delete-primitive ambiguity (Phase 8) — RESOLVED 2026-07-07:** confirmed live against "Cadre de Fabrice" — `remove_asset` disassociates an asset from the target frame only (72 real deletes succeeded live with no side effects observed outside the frame); `delete_asset`, probed directly (never via `--apply`) against a dedicated disposable throwaway image, hit the asset-scoped `DELETE /assets/{id}.json` endpoint (not frame-scoped) and made the asset vanish entirely — confirming it is broader than `remove_asset`, matching (not exceeding) its docstring's suspected worst case. `remove_asset` is reaffirmed as `--apply`'s safe default (D-06); `delete_asset` remains completely unwired. See `08-LIVE-FINDINGS.md`.
- **Hardcoded SQS frame ID (Phase 8, WRITE-04) — RESOLVED 2026-07-07:** `Aura.get_sqs(frame_id)` parameterized and confirmed live — the upload round-trip correctly targeted "Cadre de Fabrice"'s own queue, not the original hardcoded test-frame id. See `08-LIVE-FINDINGS.md`.
- **Phase 10 hide-mechanism live gate (blocked Plans 10-02..04) — RESOLVED 2026-08-25:** the 8-step live probe ran end-to-end against "Cadre de Fabrice" with disposable 8x8 throwaways. **Verdict PASS, no STOP tripwire.** `exclude_asset` hides non-destructively (asset REMAINS in `get_assets?filter=all`, D-06 holds), `select_asset` re-shows it, both accept the batch shape `{"assets":[{"asset_id":...},...]}`, and `delete_asset` re-confirmed asset-scoped (before/after inventory diff: exactly 1 of 158 removed, no drift since Phase 8, HIDE-07 satisfied). **Correction gating Plan 10-02:** the visibility flag is `asset_settings[asset_id].selected`/`.hidden` (a parallel array in the same response), NOT `Asset.selected` — `asset.selected` stayed `true` through every hide/re-show cycle. See `10-LIVE-FINDINGS.md`.
- **Write "geofence" lockout (paused Phase 10 on 2026-07-10) — RESOLVED/REFRAMED 2026-08-25:** writes are NOT geo-locked. From a French residential IP the first `push --apply` still 401'd on `select_asset.json`, then the identical call succeeded minutes later and 11 subsequent live writes all returned HTTP 200. The 401 is **transient auth-token expiry** (same signature as the Phase 8 mid-batch incident) — remedy is retry with a fresh login, not changing VPN country. Future hardening candidate: token refresh / retry-once-on-401.
- **Live API drift — `Frame.smart_adds` (Phase 10) — FIXED 2026-08-25:** the live API stopped returning `smart_adds`, a required field on the `Frame` model, breaking pydantic hydration and therefore EVERY CLI verb (`status`/`inspect`/`sync`/`push`). Patched to `Field(default_factory=list)` per the Phase 2 drift convention. It was the only missing required field; 7 other new keys are additive.
- **`num_assets` vs drained pages mismatch (found Phase 10, NOT investigated):** `get_frame()` reports `num_assets: 171` while draining all `get_assets` pages returns 149 — `tests/test_read_path.py::test_read_03_pagination` fails on this. 58/158 listed assets are placeholder rows with no `uploaded_at`/`file_name`/`md5_hash`, created by `select_asset` calls whose upload never completed. Out of scope for Phase 10; candidate for a future reconciliation phase. **Update 2026-08-25:** very likely explained by the unremovable-placeholder defect above — the placeholders accumulate and are counted inconsistently.
- **Intermittent write 401s (found in Phase 10 UAT, 2026-08-25) — OPEN, severity major:** ~4 of ~10 live `sync --apply` write runs failed with HTTP 401 and succeeded on an immediate re-run, with no config/geo/credential change. Not endpoint-specific (`select_asset`, `remove_asset`, `delete_asset` all hit it) and not the geofence. The client has no retry, so users see spurious failures and a non-zero exit. **Recommended fix: retry once on 401 with a fresh login inside `execute_plan` before attributing an item as failed.** See `10-LIVE-FINDINGS.md` addendum.
- **Placeholder rows are unremovable (found Phase 10 UAT, 2026-08-25) — OPEN, severity minor:** assets created by a `select_asset` call whose upload never completed (no `uploaded_at`/`file_name`/`md5_hash`) cannot be removed: `delete_asset` returns HTTP 200 and removes nothing (silent no-op), `remove_asset` returns 404. 58 such rows have accumulated on the live frame and are permanently stuck — the likely cause of the `num_assets` vs drained-pages mismatch below. Operational lesson: never call `select_asset` with a local_identifier you do not intend to upload.
- API is undocumented and may have drifted since April 2023; the write path has never been exercised live in three years — as of Phase 8, upload/remove_asset/delete_asset have now all been live-verified at least once.

### Quick Tasks Completed

| # | Description | Date | Commit |
|---|-------------|------|--------|
| 260630-qs8 | main.py loads a local .env at startup so the read-path demo picks up creds without exporting them; python-dotenv promoted to a runtime dep | 2026-06-30 | cd9ab6b |
| 260708-dt9 | Add progress feedback to aura-cli sync --apply write loop (tqdm-based, injectable reporter in execute_plan) | 2026-07-08 | dd92c9e |
| 260708-fyr | Batch refactor of sync --apply write path: select_asset/remove_asset/batch_update accept single-or-list, execute_plan chunks at WRITE_BATCH_SIZE=50 (~3N to ~2 Pushd write calls per chunk), per-file attribution via batch_update successes | 2026-07-08 | af344fa, 52eaf80 |
| (fast) | Add 5s inter-chunk pause (WRITE_CHUNK_DELAY_SECONDS) with visible on_wait countdown to batched sync --apply — human-pacing between chunks after live evidence of cumulative anti-abuse trip | 2026-07-08 | 59b28ca |

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Testing | Lift-tests-off-network candidates #2 (authenticated value) + #4 (injected config) → TEST-01 (v2) | Deferred | v1.1 close |
| Hardening | MOD-01 async, MOD-02 config-ize AWS pool IDs/bucket, MOD-03 typed exceptions, MOD-04 loguru sink leak | Deferred | v1.1 close |

## Session Continuity

Last session: 2026-07-09T12:22:44.413Z
Stopped at: Phase 10 context gathered
Resume file: .planning/phases/10-hide-instead-of-delete-sync-mode/10-CONTEXT.md

## Operator Next Steps

- Phase 5 (CLI Skeleton + Status) is complete — `aura-cli status` is packaged, tested offline, quiet by default with an opt-in `--debug` flag, the UAT gap is closed and live-reconfirmed, and `05-SECURITY.md` shows 0 open threats. Run `/gsd-discuss-phase 6` to begin Phase 6: Inspect + Frame Resolution (or `/gsd-plan-phase 6` to skip discussion).
