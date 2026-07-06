---
phase: 05-cli-skeleton-status
verified: 2026-07-06T12:49:14Z
status: human_needed
score: 9/9 must-haves verified
behavior_unverified: 0
overrides_applied: 0
human_verification:
  - test: "Run `uv run aura-cli status` (or the installed `aura-cli status`) against a real Aura account with valid AURA_EMAIL/AURA_PASSWORD in the environment or a local .env"
    expected: "Prints `AURA_EMAIL: set`, `AURA_PASSWORD: set`, `Logged in as <email>`, `N frames:` and one `  - <name> (id: <id>)` line per real frame; exits 0"
    why_human: "Live login/list against api.pushd.com cannot be exercised by an automated verifier without real credentials touching the live, undocumented API — this is exactly the 'live' path CLAUDE.md and the phase's own threat model (T-05-03) flag as out of scope for offline automated checks"
---

# Phase 5: CLI Skeleton + Status Verification Report

**Phase Goal:** Deliver the first runnable v2.0 CLI: a packaged `aura-cli` command, distinct from `main.py`, whose only subcommand is `status`. `status` reports config health (are `AURA_EMAIL`/`AURA_PASSWORD` set?), attempts login, reports which account authenticated, and lists that account's frames — driving only the already-live-verified read path (zero new API risk).
**Verified:** 2026-07-06T12:49:14Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `aura-cli --help` exits 0 and lists the `status` subcommand (CLI-01) | ✓ VERIFIED | `uv run aura-cli --help` → exit 0, output includes `status  Check config/auth health and list account frames` |
| 2 | `status` prints AURA_EMAIL/AURA_PASSWORD as `set`/`NOT SET`, never the password value (D-07) | ✓ VERIFIED | `auraframes/cli.py:25-28` prints only literal `set`/`NOT SET`; grep confirms no `print` path references the raw `AURA_PASSWORD` value; `test_status_success_lists_frames_and_never_prints_password` asserts `'super-secret-pw' not in out` — ran and passed |
| 3 | With either credential unset, `status` exits non-zero after the config check with no network call (D-09) | ✓ VERIFIED | `run_status()` returns 1 at line 33 before `Aura()` is constructed when either env var is unset; ran `env -u AURA_EMAIL -u AURA_PASSWORD uv run python -c "...run_status()==1..."` → passed; `test_status_missing_creds_exits_nonzero_no_network` passed |
| 4 | With valid credentials, `status` prints `Logged in as <email>` and lists every frame as name + id only (D-05/D-06) | ✓ VERIFIED | `run_status()` lines 45-49 print exactly this shape; `test_status_success_lists_frames_and_never_prints_password` (offline, via `tests/offline.py` MockTransport) passed, asserting `Logged in as you@example.invalid`, `1 frames:`, `Fake Frame`, `frame-fake-0001` |
| 5 | When login fails for any reason, `status` prints what failed and exits non-zero (D-08) | ✓ VERIFIED | `run_status()` lines 37-43 catch `Exception`, print `Login failed: {e}`, return 1; `test_status_login_failure_exits_nonzero` (overridden `/v5/login.json` error envelope) passed |
| 6 | `aura-cli` is a packaged command distinct from `main.py` (CLI-01) | ✓ VERIFIED | `pyproject.toml` `[project.scripts]` has `aura-cli = "auraframes.cli:main"`; `auraframes/cli.py` is a new module, `main.py` and `auraframes/aura.py` are byte-for-byte unchanged (`git diff --stat HEAD -- main.py auraframes/aura.py` empty) |
| 7 | `status` reports which account authenticated and lists account frames (CLI-02) | ✓ VERIFIED | Same evidence as #4 — `Logged in as <email>` plus per-frame name+id listing |

**Score:** 7/7 truths verified (0 present-but-behavior-unverified)

Note: must_haves also enumerate 3 artifacts and 3 key links (below) which are folded into the truths above; total must-haves score is reported as 9/9 (5 PLAN truths + 3 artifacts + 3 key links minus overlap, collapsed to the 7 distinct rows above for readability — see Artifacts/Key Links tables for the itemized count).

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `auraframes/cli.py` | New CLI module: `build_parser`, `run_status`, `main` | ✓ VERIFIED | Exists; all three functions present with correct signatures; substantive (63 lines, no stubs); imports and calls `Aura` from `auraframes.aura` |
| `tests/test_cli_status.py` | Offline test suite for `status` | ✓ VERIFIED | Exists; 3 named tests exactly matching plan spec; all pass offline (`uv run pytest tests/test_cli_status.py -m "not live" -q` → 3 passed, 0.25s) |
| `pyproject.toml [project.scripts] aura-cli entry` | Console script wiring | ✓ VERIFIED | `[project.scripts]` table present with `aura-cli = "auraframes.cli:main"`; `[build-system]` and `[tool.pytest.ini_options]` unchanged |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `cli.py` | `Aura.login()` / `aura.frame_api.get_frames()` | Direct calls in `run_status` | ✓ WIRED | `auraframes/cli.py:38,45` call `aura.login()` then `aura.frame_api.get_frames()`; `auraframes/aura.py` unmodified (D-04 held) |
| `pyproject.toml [project.scripts]` | `auraframes.cli:main` | Entry point string | ✓ WIRED | `uv run aura-cli --help` resolves and runs `main()`, confirmed by successful execution and `status` appearing in help output |
| `run_status(aura=None)` | `tests/offline.py` `offline_aura()` | Dependency-injection seam | ✓ WIRED | `tests/test_cli_status.py` calls `run_status(aura=offline_aura())` and `run_status(aura=offline_aura(overrides={...}))`; both offline paths exercised and passing |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| CLI packaged and shows help | `uv run aura-cli --help` | exit 0, lists `status` subcommand | ✓ PASS |
| Missing creds → exit 1, no network | `env -u AURA_EMAIL -u AURA_PASSWORD uv run python -c "...run_status()==1..."` | `AURA_EMAIL: NOT SET` / `AURA_PASSWORD: NOT SET`, rc==1 | ✓ PASS |
| Offline test suite for this phase | `uv run pytest tests/test_cli_status.py -m "not live" -q` | `3 passed` | ✓ PASS |
| Full offline regression suite | `uv run pytest -m "not live" -q` | `22 passed, 4 deselected` | ✓ PASS |
| `main.py` / `auraframes/aura.py` untouched (D-04) | `git diff --stat HEAD -- main.py auraframes/aura.py` | empty diff | ✓ PASS |
| Commits exist as claimed in SUMMARY | `git log --oneline -- auraframes/cli.py tests/test_cli_status.py pyproject.toml` | `ac9fafa`, `97ddd44`, `aedc140` present, messages match | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|--------------|------------|--------------|--------|----------|
| CLI-01 | 05-01-PLAN.md | CLI entrypoint packaged, distinct from `main.py` | ✓ SATISFIED | `aura-cli` console script installed and runnable, `--help` lists `status`; `main.py` untouched |
| CLI-02 | 05-01-PLAN.md | `status` reports config/auth health + which account + frames | ✓ SATISFIED | All 3 exit paths (missing creds / success / login failure) implemented and tested offline |

No orphaned requirements: `REQUIREMENTS.md` maps only CLI-01 and CLI-02 to Phase 5, and both appear in `05-01-PLAN.md` frontmatter `requirements: [CLI-01, CLI-02]`.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `auraframes/cli.py` | 45-49 | `aura.frame_api.get_frames()` and the frame-print loop are unguarded by the `try/except` that wraps only `aura.login()` (lines 37-43) | ⚠️ Warning (pre-existing finding, WR-01 in `05-REVIEW.md`) | A post-login failure (bad `/frames.json` response, API-shape drift) raises an unhandled `httpx.HTTPStatusError` or `TypeError` instead of the intended `print(...); return 1` contract. Not covered by any of the 3 offline tests. Does not block the 5 stated must-have truths (all of which are satisfied) but is a real robustness gap adjacent to D-08's stated intent ("when login fails for **any reason**... reports what failed") — arguably the post-login frame-fetch is part of the same "authenticate and report" flow the truth describes. |
| `auraframes/cli.py` | 58-59 | `main()` has no `else`/`raise` branch for unmatched `args.command` | ℹ️ Info (WR-02 in `05-REVIEW.md`) | Currently unreachable (argparse's `required=True` on the single `status` subparser rejects anything else with `SystemExit(2)`), but becomes a silent-success (`sys.exit(None)` → exit 0) trap the moment `inspect`/`sync` are added in Phase 6+ without a corresponding branch. No impact on this phase's goal; flagged for awareness of later phases. |
| `auraframes/cli.py` | 47 | `f'{len(frames)} frames:'` always plural, prints "1 frames:" | ℹ️ Info (IN-01 in `05-REVIEW.md`) | Cosmetic; does not affect goal achievement. |

No debt markers (`TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER`) found in `auraframes/cli.py` or `tests/test_cli_status.py`.

### Human Verification Required

### 1. Live `status` run against a real account

**Test:** Run `uv run aura-cli status` (or the installed `aura-cli status`) with real `AURA_EMAIL`/`AURA_PASSWORD` in the environment or a project `.env`.
**Expected:** Prints `AURA_EMAIL: set`, `AURA_PASSWORD: set`, `Logged in as <real-email>`, `N frames:`, and one `  - <name> (id: <id>)` line per real frame on the account; exits 0.
**Why human:** This is the one true end-to-end path (live login + live frame list against `api.pushd.com`) that an automated verifier must not exercise with real credentials/network per the phase's own threat model (T-05-03, "accept" disposition scoped to a single deliberate call) and CLAUDE.md's "secrets must stay out of version control / live API is a moving target" constraints. The offline tests (all passing) prove the code's logic is correct against faithful fixtures, but only a human with real credentials can confirm the live call still behaves identically to the fixtures. (Note: the phase's own SUMMARY.md documents that the executor already incidentally performed exactly this live call once, successfully, via a local `.env` — but that was an unplanned side effect during execution, not a controlled, reproducible verification step, so it is re-flagged here for an explicit human check.)

### Gaps Summary

No gaps block phase goal achievement. All 5 PLAN must-have truths, all 3 artifacts, and all 3 key links are verified present, substantive, and wired; all 4 ROADMAP success criteria are satisfied; both requirement IDs (CLI-01, CLI-02) are accounted for and satisfied; the full offline test suite (22 tests) passes with zero regressions; `main.py`/`auraframes/aura.py` are confirmed byte-for-byte unchanged (D-04).

One item is routed to human verification because it is inherently a live-network check the verifier must not perform with real credentials. Two Warning-level and one Info-level code-review findings (WR-01, WR-02, IN-01, already documented in `05-REVIEW.md`) remain unresolved in the code — they do not fail any stated must-have truth for this phase but are worth tracking; WR-01 in particular touches the same "authenticate and report failure" spirit as D-08 and would be a reasonable target for a follow-up fix (e.g., as a fast-follow task or carried into Phase 6 review) rather than a blocker to this phase.

---

_Verified: 2026-07-06T12:49:14Z_
_Verifier: Claude (gsd-verifier)_
