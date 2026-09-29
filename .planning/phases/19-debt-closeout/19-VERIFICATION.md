---
status: passed
phase: 19-debt-closeout
verified: 2026-09-29
requirements: [TEST-01, MOD-02, MOD-04]
---

# Phase 19 Verification: Debt Closeout

**Status: PASSED** — all three ROADMAP success criteria proven offline; the
milestone's last three open requirements close here.

## Criterion 1 — Default suite green with no credentials and no network, including the two candidates

**PASS.** `uv run pytest -q -m "not live"` → **401 passed, 6 deselected** (floor
390 + 11 new across the two plans), zero live network anywhere in the default
suite. The two v1.1 candidates are closed by name:

- Candidate #2 (authenticated value): exact fixture values asserted post-login
  (`fake-auth-token-0001` / `user-fake-0001`) AND propagated onto a subsequent
  request's wire headers (`test_offline_login_sets_exact_authenticated_values`,
  `test_authenticated_headers_propagate_to_subsequent_requests`).
- Candidate #4 (injected config): `Client(base_url=…)` additive seam, injected
  host+path asserted offline (`test_client_base_url_is_injectable`).

## Criterion 2 — AWS pool IDs and bucket from configuration, no behavior change when unset

**PASS.** The three values live in `auraframes/utils/settings.py`
(`AURA_AWS_S3_BUCKET` / `AURA_AWS_UPLOAD_POOL_ID` / `AURA_AWS_SQS_POOL_ID`)
with defaults equal to the shipped literals (asserted byte-for-byte in
`test_aws_settings_default_to_the_shipped_literals`). Repo grep: **0**
occurrences of any literal outside settings.py. `pool_id` constructor seams
untouched; `test_aws_literals_stay_out_of_aws_modules` gates reintroduction.

## Criterion 3 — Repeated Aura() construction no longer accumulates sinks/log files

**PASS.** Module-level `_LOGGER_READY` guard (research-amended D-03 scope).
Direct check: 3 offline constructions in a tmp cwd → exactly **1** log file
(pre-fix: 3). Logging still flows through the surviving sink
(`test_logging_still_flows_after_guard`); `cli.py`'s wholesale reconfigure
works with the guard active (`test_cli_reconfigure_still_works`); zero
`logger.remove` in aura.py (grep = 0).

## Traceability

| Requirement | Evidence |
|-------------|----------|
| MOD-02 | settings entries + defaults-tests + repo-literal grep 0 + hasattr gate (commit b712a21) |
| MOD-04 | `_LOGGER_READY` guard + 1-file-per-process check + reconfigure contract test (commit d46e7a8) |
| TEST-01 | 5 new offline tests closing candidates #2 and #4 (commits d46e7a8) |

## Human-verification item

None required — this phase is deliberately behavior-neutral (unset-env
byte-identical; logging configuration identical for the first construction).
The existing `--debug` CLI path is covered offline.

## Notes

- One order-dependence interaction was caught and fixed during execution
  (`test_cli_status`'s reset fixture now also resets the guard flag) —
  documented in 19-02-SUMMARY.
- Live suite untouched (6 deselected, byte-identical).
