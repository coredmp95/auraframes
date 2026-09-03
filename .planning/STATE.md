---
gsd_state_version: 1.0
milestone: v3.0
milestone_name: Google Photos Album Sync
status: planning
last_updated: "2026-09-03T05:56:52.034Z"
last_activity: 2026-09-03
progress:
  total_phases: 0
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-02)

**Core value:** The write path is proven live and shipped as a real CLI. The value now
shifts from *proving* it to making it boringly reliable — absorbing the transient 401s,
stuck placeholder rows, and server-side pagination inconsistency the live runs surfaced.
**Current focus:** Planning next milestone — run `/gsd-new-milestone`.

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-09-03 — Milestone v3.0 started

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

Resolved v2.0 blockers have been cleared at milestone close — their full live-findings
detail is preserved in [`milestones/v2.0-phases/`](./milestones/v2.0-phases/) (`*-LIVE-FINDINGS.md`,
`*-VERIFICATION.md`) and summarised in PROJECT.md Context. Still open:

- **Intermittent write 401s — OPEN, severity major (found Phase 10 UAT, 2026-08-25):** ~4 of
  ~10 live `sync --apply` runs failed with HTTP 401 and succeeded on an immediate re-run, with
  no config/geo/credential change. Not endpoint-specific (`select_asset`, `remove_asset`,
  `delete_asset` all hit it) and **not** a geofence — that theory was disproven from a French
  residential IP. The client has no retry, so users see spurious failures and a non-zero exit.
  **Recommended fix: retry once on 401 with a fresh login inside `execute_plan` before
  attributing an item as failed.** Fails loud and safe today — never silently skips work.
  See `milestones/v2.0-phases/10-*/10-LIVE-FINDINGS.md` addendum.
- **Placeholder rows are unremovable — OPEN, severity minor (found Phase 10 UAT, 2026-08-25):**
  assets created by a `select_asset` call whose upload never completed (no `uploaded_at`/
  `file_name`/`md5_hash`) cannot be removed — `delete_asset` returns 200 and removes nothing,
  `remove_asset` returns 404. 58 such rows are permanently stuck on the live frame. Fails
  toward *not* deleting, so the destructive direction is safe. Operational lesson: never call
  `select_asset` with a `local_identifier` you do not intend to upload.
- **`num_assets` vs drained-pages mismatch — OPEN, severity minor:** `get_frame()` reports
  `num_assets: 171` while a paginated drain returns 149; `tests/test_read_path.py::test_read_03_pagination`
  fails on this (the suite's only failure: 208 passed, 1 failed). **Measured 2026-08-25:** a
  single `limit=1000` call returns 154 and a paginated drain returns 149, the 5 missing rows
  being exactly the newest placeholders — a server-side pagination inconsistency, not a client
  bug. Impact is low today since `get_all_assets` defaults to `limit=1000`. The test asserts
  equality between two counts the server does not keep consistent.
- **API drift risk (standing):** the Pushd API is undocumented and may change without notice.
  Phase 10 hit this live — `Frame.smart_adds` stopped being returned and broke hydration for
  every CLI verb until patched to `Field(default_factory=list)`.

### Quick Tasks Completed

v2.0-era quick tasks archived to [`milestones/v2.0-quick/`](./milestones/v2.0-quick/).

| # | Description | Date | Commit |
|---|-------------|------|--------|

## Deferred Items

Items acknowledged and deferred at milestone close, most recent first:

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| — | _None. v2.0 closed as a **verified closeout**: 0 open artifacts, 0 newly acknowledged, 0 carried forward from a prior close._ | — | 2026-09-02 | v2.0 |
| Testing | Lift-tests-off-network candidates #2 (authenticated value) + #4 (injected config) → TEST-01 | Deferred | v1.1 close | v1.1 |
| Hardening | MOD-01 async, MOD-02 config-ize AWS pool IDs/bucket, MOD-03 typed exceptions, MOD-04 loguru sink leak | Deferred | v1.1 close | v1.1 |

Note: the v1.1 rows above are planning-level carry-forwards recorded before the
`audit-open acknowledge` mechanism existed; they are tracked in PROJECT.md Active, not
suppressed audit items. The v2.0 audit itself was clean.

## Session Continuity

Last session: 2026-09-02
Stopped at: v2.0 milestone closed and archived
Resume file: none — start the next cycle with `/gsd-new-milestone`

## Operator Next Steps

- **v2.0 is closed and archived.** Merge PR #1 on GitHub to land the milestone on `master`.
- Then run `/gsd-new-milestone` to open the next cycle. Strongest candidate, in order:
  1. Retry-once-on-401-with-fresh-login inside `execute_plan` (~4 in 10 live runs fail spuriously)
  2. Placeholder-row reconciliation (58 stuck rows; also fixes `test_read_03_pagination`)
  3. Triage the 3 open Phase 8 code-review findings (`08-REVIEW.md`, now in `milestones/v2.0-phases/`)
