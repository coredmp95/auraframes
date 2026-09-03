---
phase: 06-inspect-frame-resolution
verified: 2026-07-07T00:00:00Z
status: passed
score: 4/4 must-haves verified
behavior_unverified: 0
overrides_applied: 0
---

# Phase 6: Inspect + Frame Resolution Verification Report

**Phase Goal:** Users can inspect a specific frame's contents and metadata by name or ID, and the diff engine's core `md5_hash` assumption is confirmed against the live API before Phase 7 is designed.
**Verified:** 2026-07-07
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth (Success Criterion) | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can run `inspect --frame <name>` or `--frame <id>` and see the frame's photos (id/filename/date) | ✓ VERIFIED | `run_inspect()` in `auraframes/cli.py:149-211` calls `resolve_frame()` then `aura.get_all_assets(resolved.frame.id)` and prints `asset.id | asset.file_name | asset.taken_at_dt` for each of the first `INSPECT_PHOTO_LIMIT=10` assets (cli.py:197-204). `build_parser()` wires a required `--frame` arg on an `inspect` subparser (cli.py:37-38) that accepts either a name or an id (resolution logic below). Proven offline by `test_inspect_success_unique_name_match` and `test_inspect_id_fallback_when_no_name_matches` (both pass — see Behavioral Spot-Checks). Live-smoke confirmed per 06-01-SUMMARY.md ("A live smoke run ... executed against the real account ... correctly printed a not-found error listing the real frame"). |
| 2 | `inspect` shows frame metadata: name, owner, contributor count, and asset count | ✓ VERIFIED | cli.py:190-195 prints `Frame: {name} (id: {id})`, `Owner: {user.name} <{user.email}>`, `Contributors ({len}):` with each contributor's name/email, and `Assets: {total_asset_count}` sourced from `get_frame()`'s second return value (not re-derived from `frame.num_assets`, matching D-11). Proven by `test_inspect_success_unique_name_match` asserting `'Fake Tester'`, `'fake-user@example.invalid'`, `'Fake Contributor'`, and `'Assets: 3'` all appear in stdout. |
| 3 | Targeting a frame by an ambiguous name produces a clear error directing the user to use the ID instead | ✓ VERIFIED | `resolve_frame()` (cli.py:120-146) returns `status='ambiguous'` when >1 case-insensitive substring match on `Frame.name`, without attempting the id fallback (D-03). `run_inspect()` prints `"'{frame_arg}' matches more than one frame name — re-run with --frame <id>:"` followed by each candidate's name+id, then returns 1 (cli.py:175-179). Proven by `test_inspect_ambiguous_name_lists_names_and_ids`, which asserts both names, both ids, rc==1, and that no metadata/photo block (`'Owner:'`, `'Photos'`) leaked through. |
| 4 | It is confirmed live whether `md5_hash` is populated on read for pre-existing (non-client-uploaded) assets, documented as the input to Phase 7's design | ✓ VERIFIED | Plan 02's `checkpoint:human-verify` task (`gate="blocking"`) ran `aura-cli --debug inspect --frame "Cadre de Fabrice"` live and inspected the `--debug`-logged asset JSON across 106 paginated assets. The finding — `md5_hash` populated for 101/101 photo assets, null for 5/5 video assets — is recorded consistently in both canonical Phase-7-facing locations: `.planning/STATE.md:83` ("Phase 6 live spike ... RESOLVED 2026-07-06 ... `md5_hash` is **populated** ... for all 101/101 pre-existing photo (`.jpg`) assets, but **not populated** ... for all 5/5 video (`.mp4`) assets") and `.planning/PROJECT.md:132-140` (matching dated 2026-07-06 note with the same 101/5/106 figures). The two documents agree numerically, which is strong evidence the underlying live check actually happened rather than being asserted only in the SUMMARY. |

**Score:** 4/4 truths verified (0 present, behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `auraframes/cli.py` | `resolve_frame()`, `FrameResolution`, `run_inspect()`, root `--debug`, `inspect` subparser, dispatch | ✓ VERIFIED | All present (lines 19-39, 42-68, 109-146, 149-222). Substantive (no stubs), wired into `main()`. |
| `tests/offline.py` | `make_router()` routes `GET /v5/frames/{id}.json` to `frame_detail.json` | ✓ VERIFIED | Branch at lines 50-55, placed after the `/v5/frames.json` exact match and the `/assets.json` suffix match (ordering requirement met). See WR-02 below for a non-blocking scope-creep note on the predicate. |
| `tests/fixtures/frame_detail.json` | Full `Frame` payload + `total_asset_count`, with `contributors` populated | ✓ VERIFIED | Present; hydrates via `Frame(**body["frame"])` (confirmed by passing tests); `contributors` has one entry ("Fake Contributor"). `tests/fixtures/frames.json` confirmed unchanged (git diff scoped only to the 4 expected files). |
| `tests/test_cli_inspect.py` | 6 offline test cases per plan | ✓ VERIFIED | All 6 present and passing (`test_inspect_success_unique_name_match`, `test_inspect_id_fallback_when_no_name_matches`, `test_inspect_ambiguous_name_lists_names_and_ids`, `test_inspect_not_found_lists_available_frame_names`, `test_inspect_login_failure_exits_nonzero`, `test_inspect_quiet_by_default_suppresses_verbose_stderr`). |
| `.planning/STATE.md` | Phase 6 live spike Blockers/Concerns entry updated with confirmed finding | ✓ VERIFIED | Line 83, dated RESOLVED 2026-07-06, states finding + Phase 7 consequence. |
| `.planning/PROJECT.md` | Dated Context note recording the same finding | ✓ VERIFIED | Lines 132-140, dated 2026-07-06, matches STATE.md's figures exactly. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `main()` | `run_inspect()` | `args.command == 'inspect'` dispatch | ✓ WIRED | cli.py:220-221; unhandled command raises `ValueError` (cli.py:222), satisfying the carried-forward Pitfall 5 guard. |
| `tests/offline.py` `make_router()` | `tests/fixtures/frame_detail.json` | path-shape routing branch | ✓ WIRED | cli.py-adjacent `tests/offline.py:50-55`; confirmed via passing tests and a direct harness smoke check. |
| `run_inspect()` | `resolve_frame()` → `get_frame()` → `get_all_assets()` | in-process call chain | ✓ WIRED | cli.py:172-197 — exact sequence `get_frames()` → `resolve_frame()` → (on resolved) `get_frame(resolved.frame.id)` → `get_all_assets(resolved.frame.id)`, matching RESEARCH Pattern 1-3. |
| Phase 6 live finding | Phase 7 design input | STATE.md + PROJECT.md dated notes | ✓ WIRED | Both documents present, both dated, both numerically consistent (101/5/106). |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `run_inspect()` photo listing | `assets` | `aura.get_all_assets(resolved.frame.id)` — real paginated API call through `Aura`/`FrameApi`, no static fallback | Yes | ✓ FLOWING |
| `run_inspect()` metadata block | `frame`, `total_asset_count` | `aura.frame_api.get_frame(resolved.frame.id)` — real API call, tuple unpacked directly into print statements | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Offline inspect test suite passes | `uv run pytest tests/test_cli_inspect.py -q` | `6 passed in 0.37s` | ✓ PASS |
| Full offline suite (non-`live`) unaffected by router/`--debug` changes | `uv run pytest -q -m "not live"` | `30 passed, 4 deselected in 0.51s` | ✓ PASS |
| Root `--debug` + `inspect`/`status` argparse wiring | `build_parser().parse_args([...])` one-liner (Task 2's own verify step) | `Namespace(debug=True, command='inspect', frame='x')` / `Namespace(debug=True, command='status')` | ✓ PASS |
| No debt markers introduced | `grep -nE "TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER"` over the 4 phase-modified files | no matches | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| CLI-03 | 06-01, 06-02 | `inspect --frame <name|id>` lists photos + metadata | ✓ SATISFIED | REQUIREMENTS.md traceability marks CLI-03 "Phase 6 / Complete"; code + offline tests confirm. |
| CLI-04 | 06-01 | Frame targeting by name or ID with clear ambiguous-match error | ✓ SATISFIED | REQUIREMENTS.md traceability marks CLI-04 "Phase 6 / Complete"; `resolve_frame()` + ambiguous-branch test confirm. |

No orphaned requirements: REQUIREMENTS.md maps only CLI-03 and CLI-04 to Phase 6, and both appear in the plans' `requirements:` frontmatter.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `auraframes/cli.py` | 195-199 | `Assets: N` (from `total_asset_count`) can silently disagree with the `Photos (showing X of Y)` count with no caveat to the user (06-REVIEW.md WR-03) | ⚠️ Warning | Cosmetic/UX only — both numbers are real API-sourced data (not stubs); the phase's own SUMMARY documents this as known, accepted API drift (Phase 2 finding), not a defect. Does not block SC2 ("shows asset count" — it does). Non-blocking. |
| `tests/offline.py` | 50-55 | Frame-detail routing predicate is broader than intended and will misroute several unrelated `/frames/{id}/...json` paths once future offline tests exercise them (06-REVIEW.md WR-02) | ⚠️ Warning | Test-harness-only; does not affect current passing tests or production code; flagged as future-test-authoring risk, not a Phase 6 goal blocker. |
| `auraframes/cli.py` | 100-104 | `run_status()`'s post-login calls remain unguarded (pre-existing Phase 5 defect, not backported to `run_status` when `run_inspect` fixed the same class, 06-REVIEW.md WR-01) | ⚠️ Warning | Out of Phase 6's scope (it's a `run_status` issue, not `run_inspect`); carried forward from Phase 5's own review. Does not affect any Phase 6 success criterion. |

No 🛑 Blockers found. No unresolved TBD/FIXME/XXX debt markers in any phase-modified file.

### Human Verification Required

None. All four success criteria are either directly verifiable via automated tests/code inspection (SC1-SC3) or were already resolved through Plan 02's `checkpoint:human-verify` blocking gate, whose finding is cross-documented consistently in `STATE.md` and `PROJECT.md` (SC4).

### Gaps Summary

No gaps. All 4 roadmap Success Criteria are verified against the codebase (not just claimed in SUMMARY.md): the `inspect` subcommand, its resolution logic, and the live `md5_hash` finding are all present, substantive, wired, and covered by passing offline tests. The three code-review Warnings (WR-01, WR-02, WR-03) are legitimate but non-blocking — they concern a sibling command (`run_status`), a test-harness routing predicate not yet exercised by any failing case, and a cosmetic count-mismatch caveat — none of them prevent any of the four stated success criteria from being true today.

---

_Verified: 2026-07-07_
_Verifier: Claude (gsd-verifier)_
