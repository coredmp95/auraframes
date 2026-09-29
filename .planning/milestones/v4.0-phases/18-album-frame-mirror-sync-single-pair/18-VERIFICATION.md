---
status: passed
verified: 2026-09-28
phase: 18-album-frame-mirror-sync-single-pair
score: "5/5 success criteria (criterion 4's live manifestation routed to 18-UAT.md)"
human_verification:
  - "Two-run live UAT on the real pair: remove → HIDE, re-add → RE-SHOW without re-uploading (see 18-UAT.md; operator-gated per the 16-03 precedent)"
---

# Phase 18 — Verification Report

**Phase:** 18-album-frame-mirror-sync-single-pair
**Verified:** 2026-09-28
**Status:** PASSED (offline) — 1 live item routed to the operator (18-UAT.md)

## Success Criteria (ROADMAP §Phase 18)

### 1. Full plan printed without touching the frame; videos counted/named; download progress — PASS

- `run_google_sync` without `--apply` prints the complete plan and returns 0;
  the offline test proves ZERO write calls reached the fake frame endpoints
  (structural dry-run, CSE-05).
- Videos skipped are reported from the live-proven metadata delta
  (`videos_skipped` → plan report sentence), never silently (CSE-07).
- tqdm bars on stderr for both downloads and apply (CSE-08).

Evidence: `tests/test_gsync_execute.py::test_dry_run_prints_plan_and_executes_nothing`,
`tests/test_gsync_engine.py::test_video_delta_reported_through_the_plan`.

### 2. Concurrent Google downloads; sequential WriteBudget-paced frame writes — PASS

- `download_to_cache` runs a bounded ThreadPoolExecutor (default 4, injectable)
  over the Google session's httpx client only; the module's AST import graph is
  pinned to exclude the sync/apply side (CSE-01).
- Every frame write goes through v2.0's `execute_plan` unchanged — synchronous,
  `WriteBudget`/geo-gated, `removal_mode='hide'`.

Evidence: `tests/test_google_cache.py#test_concurrent_workers_stage_all_items_order_independently`,
`tests/test_google_cache.py#test_cache_module_has_no_aura_side_imports`.

### 3. Second run reports zero to upload EVEN THOUGH the cache was pruned — PASS (the load-bearing criterion)

- Proven twice: at the engine level (full manifest + empty cache →
  `to_upload == []`, `unchanged == N`) and end-to-end through the CLI
  (run 2 issues ZERO `=d` download requests against the Google router).
- The plan is rebuilt from the album listing plus the persisted manifest —
  `gsync.py` contains no cache walk (grepped; `prune_cache` deletes by name).
- Steady-state disk after pruning = zero staged files (pruned to
  manifest-backed ids only).

Evidence: `tests/test_gsync_engine.py::test_second_run_zero_upload_with_pruned_cache`,
`tests/test_gsync_execute.py::test_second_run_zero_uploads_and_zero_downloads`,
`tests/test_gsync_engine.py::test_manifest_member_with_pruned_cache_asserts_md5_via_sentinel`.

### 4. Remove → hides; re-add → re-shows without re-uploading — OFFLINE HALF PASS, live manifestation UAT

- Offline: a listing minus an item yields that frame asset as a hide candidate
  (never delete); a hidden asset whose item returns yields `to_reshow` with
  `to_upload == []`; second-run zero-upload proves no re-uploaded bytes.
- The criterion "only manifests over two REAL runs" (ROADMAP Notes verbatim):
  routed to `18-UAT.md` as the phase's operator-gated live test — the 16-03
  consent precedent (no live write without explicit operator approval, and
  never on an agent's own authority).

Evidence: `tests/test_gsync_engine.py::test_removed_item_hides_not_deletes`,
`tests/test_gsync_engine.py::test_readded_hidden_item_reshows_without_reupload`.

### 5. SAFE gates: empty/truncated aborts, threshold-gated removals, opt-in deletion, failed downloads — PASS

- SAFE-01: named aborts (empty listing / not exhausted cleanly / empty frame
  listing — the live-observed get_assets drift) fire BEFORE any plan output.
- SAFE-02: hide count over 20% of hash-bearing frame assets (env-overridable)
  echoes BOTH counts and requires y/N; non-interactive without `--yes` fails
  closed.
- SAFE-03: no delete tier exists on the google-sync surface
  (`removal_mode='hide'` unconditionally; no `--delete`/`--hard-delete` flags
  registered on the verb); v2.0's own gated surfaces are untouched.
- SAFE-04: failed/truncated downloads never written, never hashed, never
  planned from; nothing persisted to the manifest.

Evidence: `test_safe01_*` (×3), `test_safe02_threshold_gate_aborts_on_non_yes`,
`test_threshold_env_override_is_honored`, `test_failed_download_never_reaches_manifest`,
`test_failed_download_never_writes_never_hashes`.

## Requirement Traceability

CSE-01..08 and SAFE-01..04 — all 12 mapped IDs marked Complete in
REQUIREMENTS.md, each carried by the plan whose frontmatter claimed it and
verified above.

## Test Suite

390 passed, 6 deselected (live-marked), zero network in the default run
(TEST-02 held throughout the phase: 349 → 390 offline tests).

## Human Verification (routed)

1. Two-run live UAT on the real pair ("Cadre" → Cadre de Fabrice): sync with
   `--apply`; remove a photo from the Google album; re-run (must HIDE, not
   delete); re-add; re-run (must RE-SHOW without re-uploading a byte). See
   `18-UAT.md`. Operator-gated per the 16-03 precedent.
