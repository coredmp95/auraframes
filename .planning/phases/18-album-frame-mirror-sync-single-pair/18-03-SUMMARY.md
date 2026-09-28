---
phase: 18-album-frame-mirror-sync-single-pair
plan: 03
subsystem: sync-engine, cli
tags: [google-sync, cli, safe-gates, hide-only, offline-tested]
requires:
  - auraframes/gsync.py (plan-computing half — 18-02)
  - auraframes/google/cache.py + manifest.py (18-01)
  - auraframes/sync.py (execute_plan — reused unchanged with removal_mode='hide')
  - auraframes/cli.py (build_parser/main dispatch, resolve_frame, confirmation gates)
provides:
  - auraframes/gsync.py (run_google_sync, GOOGLE_SYNC_REMOVAL_THRESHOLD, _threshold, default_cache_dir)
  - auraframes/cli.py (google-sync subcommand: album + --frame/--apply/--yes/--debug)
  - auraframes/google/cache.py (download_to_cache progress callback — CSE-08 seam)
affects: [19 (debt closeout on a stable surface), live UAT (criterion 4)]
tech-stack:
  added: []
  patterns:
    - progress-callback attribution (execute_plan's per-item progress drives manifest persistence)
    - manifest entry from EITHER evidence — confirmed upload this run OR the frame's own listing already reporting the md5
key-files:
  created:
    - tests/test_gsync_execute.py
  modified:
    - auraframes/gsync.py
    - auraframes/google/cache.py
    - auraframes/cli.py
key-decisions:
  - "Manifest persistence honors the entry's MEANING ('bytes live on the frame') from either evidence: progress-confirmed uploads or the frame's listing reporting that md5_hash — the uploads-only rule re-downloaded frame-held photos every run (caught by the steady-state test, fixed)"
  - "removal_mode='hide' is passed unconditionally — no delete tier exists on the google-sync surface (CSE-06/SAFE-03)"
  - "SAFE-02 threshold (0.2 default, AURA_GOOGLE_SYNC_REMOVAL_THRESHOLD override) echoes BOTH counts and requires y/N; non-interactive without --yes fails closed before it (v2.0 D-03 discipline, is_interactive DI seam)"
  - "SAFE-01 empty/truncated listing prechecks run BEFORE any frame contact — no frame reads on a listing that cannot be trusted"
requirements-completed: [CSE-06, CSE-08, SAFE-02, SAFE-03]
coverage:
  - deliverable: Dry-run is structural — without --apply the verb prints the plan and calls zero mutating functions (CSE-05 enforced end to end)
    verification:
      - kind: test
        ref: tests/test_gsync_execute.py#test_dry_run_prints_plan_and_executes_nothing
        status: pass
    human_judgment: false
  - deliverable: Apply uploads/hides through the REAL execute_plan, persists manifest for confirmed+frame-held items, prunes after
    verification:
      - kind: test
        ref: tests/test_gsync_execute.py#test_apply_uploads_hides_persists_manifest_and_prunes
        status: pass
      - kind: test
        ref: tests/test_gsync_execute.py#test_second_run_zero_uploads_and_zero_downloads
        status: pass
    human_judgment: false
  - deliverable: SAFE-02 mass-hide gate — both counts echoed, abort on non-y, env-overridable threshold
    verification:
      - kind: test
        ref: tests/test_gsync_execute.py#test_safe02_threshold_gate_aborts_on_non_yes
        status: pass
      - kind: test
        ref: tests/test_gsync_execute.py#test_threshold_env_override_is_honored
        status: pass
    human_judgment: false
  - deliverable: Hide-only removal — no delete tier reachable from google-sync (CSE-06/SAFE-03)
    verification:
      - kind: command
        ref: "source assertion: run_google_sync passes removal_mode='hide' unconditionally; parser registers no --delete/--hard-delete flags on the verb"
    human_judgment: false
  - deliverable: Failed downloads never persisted, reported for retry (SAFE-04 end to end)
    verification:
      - kind: test
        ref: tests/test_gsync_execute.py#test_failed_download_never_reaches_manifest
        status: pass
    human_judgment: false
  - deliverable: Progress on downloads and apply (CSE-08)
    verification:
      - kind: test
        ref: tests/test_gsync_execute.py#test_apply_requires_yes_non_interactive
        status: pass
      - kind: command
        ref: "tqdm bars wired on stderr for both download and apply phases (disable=not stderr.isatty()); per-item progress drives the bar and the manifest attribution"
    human_judgment: false
  - deliverable: Criterion 4's live manifestation — remove/re-add over two REAL runs hides then re-shows without re-uploading
    verification: []
    human_judgment: true
    rationale: "The logic is offline-proven (to_reshow-not-reupload, hide-not-delete, second-run zero work) but the criterion 'only manifests over two runs' on the REAL pair — routed to 18-UAT.md as the phase's operator-gated live test, per the 16-03 consent precedent."
duration: 90 min
completed: 2026-09-28
---

# Phase 18 Plan 03: google-sync CLI (Mutating Half) Summary

The single-pair mirror, end to end: `aura-cli google-sync <album> --frame <frame>`
plans structurally dry-run, gates apply behind SAFE-02 + v2.0's y/N discipline,
executes through the REAL `execute_plan` (hide-only), persists the manifest for
proven-on-frame items, prunes the cache, and reports progress throughout.

## Accomplishments

- `run_google_sync` composing every phase-18 piece with DI seams (session/aura/
  s3/sqs/budget/input_fn/is_interactive/threshold/list_shared) — offline-testable
  end to end over the real v2.0 `execute_plan`.
- `google-sync` CLI verb (album positional, --frame/--apply/--yes/--debug) with
  phase-17 resolution UX (numbered ambiguity, exit 2).
- SAFE-02 mass-hide gate; hide-only removal; fail-closed non-interactive apply.
- Manifest persistence from confirmed uploads OR frame-held md5 evidence.
- 7 new end-to-end offline tests; suite 390 passing offline (was 349 at phase start).

## Deviations from Plan

- [Rule 1 - Design fix caught by tests] Manifest persistence rule — Found during:
  Task 1 steady-state test | Issue: persisting ONLY this-run uploads re-downloaded
  frame-held photos on every subsequent run (criterion 3 violated) | Fix: entries
  also written when the frame's listing already reports the md5 | Files: gsync.py |
  Verification: test_second_run_zero_uploads_and_zero_downloads (zero =d requests) |
  Commit 4674477.
- [Test-authoring] is_interactive DI seam added instead of monkeypatching sys.stdin
  (pytest's capture makes isatty() False); the SAFE-02 test now drives the gate
  interactively with a fake input_fn.

## Issues Encountered

None outstanding.

## Self-Check: PASSED
