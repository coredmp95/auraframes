---
status: complete
phase: 05-cli-skeleton-status
source: [05-VERIFICATION.md]
started: 2026-07-06T12:51:41Z
updated: 2026-07-06T12:56:56Z
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
  root_cause: ""
  artifacts: []
  missing: []
  debug_session: ""
