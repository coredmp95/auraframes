---
phase: 05-cli-skeleton-status
verified: 2026-07-06T14:05:00Z
status: human_needed
score: 9/9 must-haves verified
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 9/9
  gaps_closed:
    - "CLI-02: `aura-cli status` no longer leaks verbose loguru INFO/DEBUG request/response bodies to stderr by default (root cause: Aura._init_logger()'s commented-out logger.remove() left loguru's default stderr handler active alongside the INFO sink; fixed from the CLI boundary via _configure_cli_logging())"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Run `uv run aura-cli status` (or the installed `aura-cli status`) against a real Aura account with valid AURA_EMAIL/AURA_PASSWORD in the environment or a local .env"
    expected: "Prints only the concise lines: `AURA_EMAIL: set`, `AURA_PASSWORD: set`, `Logged in as <email>`, `N frames:`, one `  - <name> (id: <id>)` line per real frame; exits 0; no loguru INFO/DEBUG request/response dump on stderr"
    why_human: "Live login/list against api.pushd.com cannot be exercised by an automated verifier without real credentials touching the live, undocumented API (T-05-03 'accept' disposition scopes this to a single deliberate, human-run call). The original UAT session already proved the live login+listing mechanics work correctly against the real account (05-UAT.md test 1) — the only open question is whether the now-quiet stderr behavior holds on that same live path, since the fix was verified via the offline harness and a real subprocess (not literally against api.pushd.com)."
---

# Phase 5: CLI Skeleton + Status Verification Report (Re-verification after gap closure)

**Phase Goal:** Users have a runnable CLI whose `status` command reports whether they are configured and authenticated, exercising only the already-live-verified login/list path.
**Verified:** 2026-07-06T14:05:00Z
**Status:** human_needed
**Re-verification:** Yes — after gap closure (05-02-PLAN.md, gap_closure: true)

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can invoke the CLI as a packaged command distinct from `main.py`, sees usage/help output (Success Criterion 1, CLI-01) | ✓ VERIFIED | `uv run aura-cli --help` → exit 0; output: `usage: aura-cli [-h] {status} ...` and lists `status  Check config/auth health and list account frames`. `main.py` is a separate, unmodified file. |
| 2 | Running `status` reports whether `AURA_EMAIL`/`AURA_PASSWORD` are set (Success Criterion 2, CLI-02) | ✓ VERIFIED | `auraframes/cli.py:61-64` prints literal `AURA_EMAIL: set/NOT SET` and `AURA_PASSWORD: set/NOT SET`; confirmed by direct offline run and by `test_status_missing_creds_exits_nonzero_no_network` (passing). |
| 3 | Running `status` attempts login and reports success/failure plus which account authenticated (Success Criterion 3, CLI-02) | ✓ VERIFIED | `run_status()` calls `aura.login()` in a `try/except`; on success prints `Logged in as <email>` (`cli.py:85`); on failure prints `Login failed: {e}` and returns 1 (`cli.py:81`). Confirmed by `test_status_success_lists_frames_and_never_prints_password` and `test_status_login_failure_exits_nonzero` (both passing), and originally live-confirmed in 05-UAT.md test 1 (`Logged in as coredmp95@gmail.com`). |
| 4 | `status` lists the frames on the authenticated account (Success Criterion 4, CLI-02) | ✓ VERIFIED | `cli.py:86-88` prints `{len(frames)} frames:` then `  - {name} (id: {id})` per frame; confirmed offline and originally live-confirmed in 05-UAT.md test 1 (`Cadre de Fabrice (id: c063b384-...)`). |
| 5 | `aura-cli status` (default) emits no loguru INFO/DEBUG request/response output to stderr — only concise lines print (closes the UAT gap, CLI-02) | ✓ VERIFIED | Re-ran the exact regression directly (not via pytest capsys): `run_status(aura=offline_aura())` with real subprocess stdout/stderr redirection → stdout has the 5 concise lines, **stderr is completely empty**. `test_status_quiet_by_default_suppresses_verbose_stderr` passes. |
| 6 | `aura-cli status --debug` restores loguru's full INFO/DEBUG stderr output (opt-in) | ✓ VERIFIED | Re-ran `run_status(aura=offline_aura(), debug=True)` in a real subprocess: stderr contains the full `POST request to /login.json` / `Response (200), body: ...` / `GET request to /frames.json` dump. `test_status_debug_flag_restores_verbose_stderr` passes. |
| 7 | On-disk logging to `logs/file_*.log` continues in both quiet and `--debug` modes | ✓ VERIFIED | Directly observed: a quiet-mode run created a fresh `logs/file_<ts>.log` containing the full INFO/DEBUG request+response lines (file sink still gets everything even though stderr is suppressed); a debug-mode run likewise wrote a populated log file. This closes the `human_judgment: true` gap the 05-02-SUMMARY.md itself flagged as unverified. |
| 8 | The fix lives entirely in `auraframes/cli.py` + tests; `auraframes/aura.py` and `main.py` remain byte-for-byte unchanged (D-04) | ✓ VERIFIED | `git diff --name-only -- auraframes/aura.py main.py` → empty output; `git status --short` shows no modifications to either file. |
| 9 | `tests/test_cli_status.py` asserts on captured stderr (not just stdout), so the regression is caught going forward | ✓ VERIFIED | `test_status_quiet_by_default_suppresses_verbose_stderr` and `test_status_debug_flag_restores_verbose_stderr` both read `capsys.readouterr().err` and assert presence/absence of the `request to` / `Response (` markers; an autouse `_reset_loguru` fixture keeps assertions deterministic across the module. |

**Score:** 9/9 truths verified (0 present-but-behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `auraframes/cli.py` | `--debug` flag on `status` subparser + `_configure_cli_logging()` helper, `run_status(debug=...)` | ✓ VERIFIED | All present; `build_parser().parse_args(["status","--debug"]).debug is True`, `parse_args(["status"]).debug is False` (confirmed by source read); `_configure_cli_logging` no-ops on `debug=True`, calls `logger.remove()` + re-adds file + WARNING-stderr sinks on `debug=False`. |
| `tests/test_cli_status.py` | Stderr-quiet + `--debug`-verbose tests, autouse loguru-reset fixture | ✓ VERIFIED | 5 tests total (3 original + 2 new); all pass (`uv run pytest tests/test_cli_status.py -m "not live" -q` → `5 passed`). |
| `pyproject.toml [project.scripts]` (from 05-01, unmodified by 05-02) | `aura-cli = "auraframes.cli:main"` | ✓ VERIFIED | Table present and unchanged; `uv run aura-cli --help` resolves and runs. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| status subparser `--debug` | `main()` reads `args.debug` | `run_status(debug=args.debug)` | ✓ WIRED | `cli.py:97-98`: `if args.command == 'status': return run_status(debug=args.debug)`. |
| `run_status()` | `_configure_cli_logging(debug)` | Called after `aura = aura or Aura()`, before `aura.login()` | ✓ WIRED | `cli.py:71-77` — confirmed by source read and by the manual subprocess check (quiet mode suppresses the noise that `Aura()` construction + `aura.login()`/`get_frames()` would otherwise emit). |
| `cli.py` (from 05-01) | `Aura.login()` / `aura.frame_api.get_frames()` | Direct calls in `run_status` | ✓ WIRED | Unchanged from 05-01; still present at `cli.py:77,84`. |

### Data-Flow Trace (Level 4)

Not applicable in the dynamic-data-rendering sense (no DB/API-shaped dashboard) — the "data flow" of interest for this re-verification cycle is the loguru sink lifecycle, which was traced directly:

| Concern | Source | Produces Real Behavior | Status |
|---------|--------|------------------------|--------|
| Quiet-mode stderr suppression | `_configure_cli_logging(False)` → `logger.remove()` + re-added file/WARNING sinks | Confirmed: real subprocess run produced **zero** stderr bytes while `logs/*.log` received full INFO/DEBUG content | ✓ FLOWING |
| `--debug` verbose restoration | `_configure_cli_logging(True)` → no-op | Confirmed: real subprocess run produced full loguru dump on stderr | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| CLI packaged, shows help | `uv run aura-cli --help` | exit 0, lists `status` | ✓ PASS |
| Quiet-mode real stderr suppression (subprocess, not capsys) | `uv run python -c "...run_status(aura=offline_aura())..." 2>err.log 1>out.log` | stdout: 5 concise lines; **stderr: empty** | ✓ PASS |
| `--debug` real stderr restoration (subprocess) | same, with `debug=True` | stdout: same 5 concise lines; stderr: full loguru INFO/DEBUG dump (login + frames) | ✓ PASS |
| File sink populated in quiet mode | Inspected newest `logs/file_*.log` after a quiet-mode run | Contains full INFO/DEBUG request+response lines despite stderr being silent | ✓ PASS |
| `tests/test_cli_status.py` full file | `uv run pytest tests/test_cli_status.py -m "not live" -q` | `5 passed` | ✓ PASS |
| Full offline regression suite | `uv run pytest -m "not live" -q` | `24 passed, 4 deselected` | ✓ PASS |
| `main.py` / `auraframes/aura.py` untouched (D-04) | `git diff --name-only -- auraframes/aura.py main.py` | empty | ✓ PASS |
| No debt markers introduced | `grep -nE "TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER" auraframes/cli.py tests/test_cli_status.py` | no matches | ✓ PASS |
| Commits exist as claimed in SUMMARYs | `git log --oneline -- auraframes/cli.py tests/test_cli_status.py pyproject.toml` | `5bfab50`, `7313a85`, `aedc140`, `97ddd44`, `ac9fafa` all present | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|--------------|------------|--------------|--------|----------|
| CLI-01 | 05-01-PLAN.md | CLI entrypoint packaged, distinct from `main.py` | ✓ SATISFIED | `aura-cli` console script installed and runnable; `--help` lists `status`; `main.py` untouched. Marked `[x]` complete in REQUIREMENTS.md. |
| CLI-02 | 05-01-PLAN.md, 05-02-PLAN.md (gap closure) | `status` reports config/auth health + which account + frames, without leaking verbose logging | ✓ SATISFIED | All 3 exit paths (missing creds / success / login failure) implemented and tested offline; the verbosity gap found in 05-UAT.md is now closed and re-confirmed via direct subprocess stderr capture. Marked `[x]` complete in REQUIREMENTS.md. |

No orphaned requirements: `REQUIREMENTS.md` maps only CLI-01 and CLI-02 to Phase 5; both appear in `05-01-PLAN.md` frontmatter `requirements: [CLI-01, CLI-02]`, and CLI-02 is also declared in `05-02-PLAN.md` frontmatter (gap-closure plan, same requirement, no new ID introduced).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `auraframes/cli.py` | 84-88 | `aura.frame_api.get_frames()` and the frame-print loop remain unguarded by the `try/except` that wraps only `aura.login()` (unchanged since 05-01, not addressed by 05-02) | ⚠️ Warning (carried forward, WR-01 in `05-REVIEW.md`) | A post-login failure (bad `/frames.json` response, API-shape drift) still raises an unhandled exception instead of the intended `print(...); return 1` contract. Does not block any of the 9 must-have truths verified above (all satisfied); not in scope for either 05-01 or 05-02's must_haves. Still worth a fast-follow. |
| `auraframes/cli.py` | 97-98 | `main()` still has no `else`/`raise` branch for an unmatched `args.command` | ℹ️ Info (carried forward, WR-02 in `05-REVIEW.md`) | Currently unreachable (argparse `required=True` rejects anything else). Becomes a silent-success trap once `inspect`/`sync` are added in Phase 6+. No impact on this phase's goal. |
| `auraframes/cli.py` | 86 | `f'{len(frames)} frames:'` always plural, prints "1 frames:" | ℹ️ Info (carried forward, IN-01 in `05-REVIEW.md`) | Cosmetic; does not affect goal achievement. |

No debt markers (`TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER`) found in `auraframes/cli.py` or `tests/test_cli_status.py`.

### Human Verification Required

### 1. Final live confirmation of quiet-by-default `status` output

**Test:** Run `uv run aura-cli status` (or the installed `aura-cli status`) with real `AURA_EMAIL`/`AURA_PASSWORD` in the environment or a project `.env`, against the real Aura account.
**Expected:** Only the concise lines print — `AURA_EMAIL: set`, `AURA_PASSWORD: set`, `Logged in as <real-email>`, `N frames:`, one `  - <name> (id: <id>)` line per real frame; exits 0; no loguru INFO/DEBUG request/response dump interleaved on stderr.
**Why human:** Login/list against `api.pushd.com` is a live network call against an undocumented API with real credentials — CLAUDE.md and the phase's own threat model (T-05-03) scope this to a deliberate, human-run check, not something an automated verifier performs. The underlying login/list mechanics were already live-verified once in 05-UAT.md's test 1 (successful login, correct frame listed), and the logging fix itself was independently confirmed via a real subprocess (not pytest's capsys) reproducing the identical sink-construction/removal sequence `Aura()`+`aura.login()`+`get_frames()` would trigger live — but a final live pass closes the loop the user originally opened the UAT gap on.

### Gaps Summary

No gaps remain. The single diagnosed UAT gap from the previous cycle — verbose loguru INFO/DEBUG request/response output leaking to stderr on `aura-cli status` — is closed:

- Root cause (frozen `Aura._init_logger()` leaving loguru's default stderr handler active) is compensated for entirely from the CLI boundary via `_configure_cli_logging()`, called after `Aura()` construction and before the first HTTP call.
- Verified not just via the plan's own offline pytest assertions but via a fresh, independent real-subprocess check in this re-verification pass: quiet mode produced **zero** stderr bytes while still writing full detail to `logs/file_*.log`; `--debug` mode restored the full verbose dump on stderr.
- `auraframes/aura.py` and `main.py` remain byte-for-byte unchanged (D-04 held across both plans).
- All 4 ROADMAP success criteria, all 9 consolidated must-have truths (5 from 05-01 + 4 gap-closure-specific from 05-02, deduplicated with the roadmap SCs above), both requirement IDs (CLI-01, CLI-02), and the full offline test suite (24 tests, zero regressions) are verified.

One item remains routed to human verification: a final live confirmation that the quiet-by-default fix holds against the real account, since automated verification must not perform live network calls with real credentials. This is a routine confirmation, not a re-diagnosis — the mechanism has been independently and directly observed working in this verification pass. Three pre-existing Warning/Info-level code-review findings (WR-01, WR-02, IN-01) remain unresolved but are out of scope for both 05-01 and 05-02's stated must-haves and do not block phase goal achievement.

---

_Verified: 2026-07-06T14:05:00Z_
_Verifier: Claude (gsd-verifier)_
