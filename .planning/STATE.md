---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Directory-to-Frame Sync
current_phase: 09
status: executing
stopped_at: Phase 10 context gathered
last_updated: "2026-07-10T15:04:26.211Z"
last_activity: 2026-07-09
last_activity_desc: Phase 09 complete
progress:
  total_phases: 6
  completed_phases: 5
  total_plans: 13
  completed_plans: 13
  percent: 83
current_phase_name: proactive-write-rate-limiter-geo-guard
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-06)

**Core value (v2.0):** Prove the write path the same way v1.0/v1.1 proved the read path, and turn that proof into a real usable capability — mirroring a local photo directory to an Aura frame.
**Current focus:** Phase 09 — proactive-write-rate-limiter-geo-guard

## Current Position

Phase: 09
Plan: Not started
Status: Ready to execute
Last activity: 2026-07-09 — Phase 09 complete

Progress: [█████████░] 91% (10/11 plans complete)

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
