---
status: testing
phase: 05-cli-skeleton-status
source: [05-VERIFICATION.md]
started: 2026-07-06T12:51:41Z
updated: 2026-07-06T12:51:41Z
---

## Current Test

number: 1
name: Run `aura-cli status` against a real Aura account
expected: |
  Prints `AURA_EMAIL: set`, `AURA_PASSWORD: set`, `Logged in as <email>`, `N frames:` and one
  `  - <name> (id: <id>)` line per real frame; exits 0.
awaiting: user response

## Tests

### 1. Run `uv run aura-cli status` (or the installed `aura-cli status`) against a real Aura account with valid AURA_EMAIL/AURA_PASSWORD in the environment or a local .env
expected: Prints `AURA_EMAIL: set`, `AURA_PASSWORD: set`, `Logged in as <email>`, `N frames:` and one `  - <name> (id: <id>)` line per real frame; exits 0
result: [pending]

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
