---
phase: 07-sync-diffing-engine-dry-run-only
verified: 2026-07-07T09:44:27Z
status: passed
score: 3/3 must-haves verified
behavior_unverified: 0
overrides_applied: 0
---

# Phase 7: Sync-Diffing Engine (Dry-Run Only) Verification Report

**Phase Goal:** Users can preview a full-mirror sync plan for a directory against a frame, with zero possibility of a write.
**Verified:** 2026-07-07T09:44:27Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `sync <dir> --frame <name\|id>` prints a plan of upload/delete/unchanged with counts and executes nothing; dry-run is structurally enforced | ✓ VERIFIED | `run_sync()` in `auraframes/cli.py:219-301` calls only `resolve_frame`, `aura.get_all_assets` (read), `scan_directory`, `compute_plan`, and `print` — no `--apply`/`--yes` flag exists in `build_parser()`. Grep gate confirms zero mutating call tokens (`put_object`, `upload_file`, `select_asset`, `remove_asset`, `delete_asset`, `.post(`, `.put(`, `.delete(`) in both `auraframes/sync.py` and the `run_sync` function body. 19 offline tests in `tests/test_sync_engine.py`/`tests/test_cli_sync.py` pass; full non-live suite (49 tests) is green. I additionally reproduced the post-code-review CR-01 fix live: pointing `run_sync` at a nonexistent directory now raises `NotADirectoryError` inside `scan_directory` (caught by `run_sync`'s nested `except OSError`), printing `Failed to scan {dir}: ...` and returning `1` — it no longer silently produces a false "delete everything" plan with exit 0 (the bug the code-review found and the fix commits closed). |
| 2 | The plan correctly classifies files by comparing local content-hashes to frame asset `md5_hash` values (never by filename) | ✓ VERIFIED | `compute_plan()` in `auraframes/sync.py:80-120` partitions purely on `asset.md5_hash` vs. a demand map keyed by local content hash; hashless (video) assets are excluded into `frame_no_hash`; multiset surplus frame-side duplicates become delete candidates without deduping. 11 unit tests in `tests/test_sync_engine.py` cover every branch (local-only→upload, matched→unchanged, multiset surplus→delete, orphaned frame hash→delete, hashless→excluded, skipped-count passthrough) and all pass. CLI-level tests in `tests/test_cli_sync.py` confirm end-to-end classification against injected frame assets (by hash, with a `secret-name-should-not-appear.jpg` filename that correctly never appears in output — proving classification/print is hash-driven, not filename-driven). |
| 3 | Local hashing uses the same base64-MD5 convention as `S3Client.get_md5`, validated equal against a real downloaded asset before diffing is trusted | ✓ VERIFIED | `auraframes/sync.py:16` imports and calls `get_md5` directly from `auraframes.aws.s3client` — no reimplementation (confirmed by reading the import and the single call site at line 65). The required one-time LIVE validation (Plan 07-03, `checkpoint:human-verify`) was performed by the operator via METHOD A (`aura-cli sync ./data/ --frame "Cadre de Fabrice"` against real frame id `c063b384-38fa-4324-aaf8-319d17a5867a`) and confirmed equal — I independently read the resulting entries in `.planning/STATE.md` ("Hash-format mismatch risk (Phase 7) — RESOLVED 2026-07-07") and `.planning/PROJECT.md` (Phase 7 Context entry), both of which record the method, frame id, and the discriminating result (one file "Unchanged", a second non-matching file correctly "To upload" — proving the match isn't trivial). |

**Score:** 3/3 truths verified (0 present, behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `auraframes/sync.py` | `ELIGIBLE_EXTENSIONS`, `ScanResult`, `SyncPlan`, `scan_directory`, `compute_plan` | ✓ VERIFIED | All five present; substantive (real algorithms, not stubs); wired into `auraframes/cli.py` via import at line 12 and called in `run_sync`. |
| `auraframes/cli.py` (`sync` subparser, `run_sync`, `main()` dispatch) | positional `dir` + required `--frame`, no apply/yes flag, dispatch branch | ✓ VERIFIED | `build_parser()` lines 41-43; `run_sync` lines 219-301; `main()` dispatch line 312-313. Confirmed parsing via direct invocation: `dir`/`frame` attributes present, no `apply`/`yes` attributes. |
| `tests/test_sync_engine.py` | offline unit-test suite | ✓ VERIFIED | 11 tests, all pass offline (`uv run pytest tests/test_sync_engine.py -q`). |
| `tests/test_cli_sync.py` | offline CLI-level tests | ✓ VERIFIED | 8 tests, all pass offline (`uv run pytest tests/test_cli_sync.py -q`). |
| `.planning/STATE.md` / `.planning/PROJECT.md` (SYNC-02 live finding) | documented live hash-convention validation | ✓ VERIFIED | Both files contain a dated, detailed Phase 7 entry recording method, frame id, and the equal/discriminating result. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `scan_directory` | `S3Client.get_md5` | direct import + call | ✓ WIRED | `from auraframes.aws.s3client import get_md5` (line 16); called at line 65 on raw file bytes. No reimplementation of hashlib/base64 logic anywhere in `sync.py`. |
| `run_sync` | `resolve_frame` / `aura.get_all_assets` (Phase 6) | reused verbatim | ✓ WIRED | Ambiguous/not_found branches and messages copied verbatim from `run_inspect`; `aura.get_all_assets(frame.id)` supplies the frame-side asset list to `compute_plan`. |
| `run_sync` | `scan_directory` + `compute_plan` (Plan 07-01) | direct call | ✓ WIRED | `scan = scan_directory(Path(dir_arg))`; `plan = compute_plan(scan.local_hashes, assets, scan.skipped_non_image)` — lines 268/273. |
| `main()` | `run_sync` | dispatch branch | ✓ WIRED | `if args.command == 'sync': return run_sync(args.dir, args.frame, debug=args.debug)` — line 312-313. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `run_sync` plan output | `assets` | `aura.get_all_assets(frame.id)` — real paginated API call (mocked only in offline tests via `offline_aura`) | Yes | ✓ FLOWING |
| `run_sync` plan output | `scan.local_hashes` | `scan_directory(Path(dir_arg))` reading real local file bytes via `p.read_bytes()` | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full offline suite passes | `uv run pytest -q -m "not live"` | `49 passed, 4 deselected` | ✓ PASS |
| No mutating call token in `sync.py` | `grep -vE '^\s*#' auraframes/sync.py \| grep -qE 'put_object\|upload_file\|select_asset\|remove_asset\|delete_asset\|\.post(\|\.put(\|\.delete('` | no match | ✓ PASS |
| No mutating call token in `run_sync` body | `sed -n '/^def run_sync/,/^def main/p' auraframes/cli.py \| grep -vE '^\s*#' \| grep -E '...'` | no match | ✓ PASS |
| CR-01 fix: nonexistent dir fails loudly, not silently-empty | manual invocation of `run_sync('/tmp/this-dir-does-not-exist-abc123', 'Fake', aura=<mocked frame w/ 1 hashed asset>)` | `Failed to scan /tmp/this-dir-does-not-exist-abc123: ... is not an existing directory` / `rc=1` (previously: silent `To delete: 1`, `rc=0`) | ✓ PASS |
| WR-01 fix: symlinked file inside scan root excluded | manual invocation of `scan_directory` on a dir containing a symlink to an outside file | `ScanResult(local_hashes={}, skipped_non_image=0)` — link neither hashed nor counted | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| SYNC-01 | 07-01, 07-02 | Dry-run full-mirror plan (upload/delete/unchanged) by content-hash, executing nothing | ✓ SATISFIED | `compute_plan` + `run_sync`, tested and behaviorally confirmed. Marked `[x]` complete in REQUIREMENTS.md and mapping table. |
| SYNC-02 | 07-01, 07-03 | Content-hash comparison reuses `S3Client.get_md5`'s exact convention, validated against a real downloaded asset | ✓ SATISFIED | Direct reuse (no reimplementation) + live-confirmed equal per Plan 07-03's checkpoint, documented in STATE.md/PROJECT.md. Marked `[x]` complete in REQUIREMENTS.md and mapping table. |

No orphaned requirements — both IDs declared across plans (`07-01: [SYNC-01, SYNC-02]`, `07-02: [SYNC-01]`, `07-03: [SYNC-02]`) match the two IDs mapped to "Phase 7" in REQUIREMENTS.md's tracking table.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `tests/test_sync_engine.py`, `tests/test_cli_sync.py` | n/a | No automated regression test exercises `scan_directory`/`run_sync` against a nonexistent/invalid `dir` (the exact scenario CR-01 fixed) | ℹ️ Info | Reviewed and explicitly scoped out of the code-review auto-fix pass (`07-REVIEW-FIX.md` frontmatter: `findings_in_scope: 5`, IN-01 excluded). I independently re-verified the fixed behavior manually (see Behavioral Spot-Checks) and it is currently correct, but a future regression could silently reintroduce CR-01's bug since nothing pins it in CI. Not a blocker for this phase's goal — recommend adding `IN-01`'s suggested test in a follow-up. |
| `auraframes/cli.py:277, 280` | n/a | Grammatically-incorrect pluralization (e.g. "1 non-photo files skipped") pinned by test assertions | ℹ️ Info | Cosmetic only (already flagged as IN-02 in `07-REVIEW.md`, out of auto-fix scope). Does not affect correctness of the dry-run plan. |
| `auraframes/cli.py:25` | 25 | Historical comment mentioning a "folded todo" from a prior phase | ℹ️ Info | Refers to already-resolved Phase 5 work, not live debt in this phase's scope. |

No 🛑 blockers and no unresolved debt markers (`TBD`/`FIXME`/`XXX`) in any file this phase modified.

### Human Verification Required

None. The one item that structurally requires human/live confirmation (SYNC-02's live hash-convention proof) was already completed as a `checkpoint:human-verify` gate during phase execution (Plan 07-03) and is documented with concrete evidence (method, frame id, discriminating result) in `.planning/STATE.md` and `.planning/PROJECT.md`, which I independently read and confirmed.

### Gaps Summary

None. All three ROADMAP success criteria are met in the current (post-code-review-fix) state of `auraframes/sync.py` and `auraframes/cli.py`. The critical bug the code review found (CR-01 — silent "delete everything" plan on a bad `dir` argument) has been fixed and I independently reproduced the corrected behavior (fails loudly, exit 1, no plan printed). All four review warnings (WR-01 symlink exclusion, WR-02 distinct local-vs-remote error messages, WR-03 deterministic upload ordering, WR-04 test log-file isolation) are present in the current code and confirmed working. The three remaining info-level findings (IN-01/02/03) are cosmetic or test-coverage-gap items that do not block goal achievement.

---

_Verified: 2026-07-07T09:44:27Z_
_Verifier: Claude (gsd-verifier)_
