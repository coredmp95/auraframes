---
status: diagnosed
phase: 05-cli-skeleton-status
source: [05-VERIFICATION.md]
started: 2026-07-06T12:51:41Z
updated: 2026-07-06T13:02:41Z
---

## Current Test

[testing complete]

## Tests

### 1. Run `uv run aura-cli status` (or the installed `aura-cli status`) against a real Aura account with valid AURA_EMAIL/AURA_PASSWORD in the environment or a local .env
expected: Prints `AURA_EMAIL: set`, `AURA_PASSWORD: set`, `Logged in as <email>`, `N frames:` and one `  - <name> (id: <id>)` line per real frame; exits 0
result: issue
reported: "well .. realy to verbose, maybe add a --debug to get all the answer .. [pasted terminal output: AURA_EMAIL: set / AURA_PASSWORD: set / full loguru INFO+DEBUG request/response dump for /login.json and /frames.json / then 'Logged in as coredmp95@gmail.com' / '1 frames:' / '  - Cadre de Fabrice (id: c063b384-38fa-4324-aaf8-319d17a5867a)']"
severity: minor

## Summary

total: 1
passed: 0
issues: 1
pending: 0
skipped: 0
blocked: 0

## Gaps

- truth: "status prints only the concise status/login/frame-listing lines, matching the format already covered by tests/test_cli_status.py"
  status: failed
  reason: "User reported: the live run is too verbose — the existing loguru INFO/DEBUG sink (configured in Aura._init_logger(), inherited unchanged from main.py per D-04) prints full request/response bodies (headers, cookies, entire frames.json payload) to stderr/stdout above the intended concise output. Suggests a --debug flag so verbose logging is opt-in rather than always-on."
  severity: minor
  test: 1
  root_cause: "Aura._init_logger() (auraframes/aura.py:136-145, frozen per D-04) adds an INFO-level stderr sink but never calls the commented-out logger.remove() (line 140), so loguru's own auto-registered default stderr handler (no level ceiling, passes DEBUG) stays active alongside it. Every Client.get/post/put/delete call in auraframes/client.py logs via logger.info(...)/logger.debug(...) with full request context and response bodies, so both handlers fire on every HTTP call run_status() makes (login + get_frames), doubling and expanding the stderr output around the CLI's own concise stdout prints."
  artifacts:
    - path: "auraframes/aura.py"
      issue: "Aura._init_logger() line 140 has `# logger.remove()` commented out, leaving loguru's default DEBUG-level stderr handler active alongside the intentional INFO handler. Frozen per D-04 — cannot be edited directly."
    - path: "auraframes/client.py"
      issue: "logger.info(...)/logger.debug(...) in get/post/put/delete emit per-request context and full response bodies; amplified by having two active stderr handlers rather than the intended one."
    - path: "auraframes/cli.py"
      issue: "run_status()/main() construct a real Aura() with no logging-level control; the only place a fix can land without violating D-04 is neutralizing/releveling the stderr sink(s) loguru accumulates, gated behind an opt-in --debug flag (default: quiet stderr)."
  missing:
    - "In cli.py, strip or relevel loguru's stderr handler(s) after Aura() construction (e.g. logger.remove() + re-add a stricter-level sink) while leaving the file sink intact"
    - "Add an argparse --debug flag to the status subcommand: default suppresses verbose stderr, --debug leaves loguru's sinks as-is"
    - "Extend tests/test_cli_status.py to assert on captured stderr (not just stdout) so this regression is caught in the future"
  debug_session: ".planning/debug/cli-status-verbose-logging.md"
