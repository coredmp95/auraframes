---
phase: 05
slug: cli-skeleton-status
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: 2026-07-06
---

# Phase 05 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| shell env → CLI process | `AURA_EMAIL`/`AURA_PASSWORD` (secrets) enter the process via env vars / `.env` | credentials |
| CLI process → Aura cloud API | `status` sends credentials over the network via the existing `Client`/`Aura` login path (already live-verified read path; no new endpoints) | credentials, session token |
| CLI process → terminal (stderr) | Loguru request/response logging (headers, query params, response bodies) is written to stderr | request/response metadata |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-05-01 | Information Disclosure | `run_status` config-health output | high | mitigate | `cli.py:62-64` prints only literal `set`/`NOT SET` for `AURA_PASSWORD`, never the value. Enforced by `test_status_success_lists_frames_and_never_prints_password`. | closed |
| T-05-02 | Information Disclosure | login-failure message (`f"Login failed: {e}"`) | medium | mitigate | Caught exception is `AccountApi`'s `RuntimeError`/`httpx` error text (API/status text, not credentials); login payload already redacted at the `Client` layer (`_REDACT_KEYS`). No password interpolation into any message. | closed |
| T-05-03 | Denial of Service | live login network call | low | accept | `status` makes a single synchronous login+list call on the already-verified read path; no loop, no user-supplied volume. Accepted at CLI scope. | closed |
| T-05-04 | Information Disclosure | verbose stderr from `Client.*` logging during `status` | medium | mitigate | `_configure_cli_logging()` (`cli.py:26-52`) calls `logger.remove()` by default, stripping loguru's stderr sinks so request/response bodies are not dumped to the terminal; verbose output is opt-in behind `--debug`. Secrets already redacted at the `Client` layer even under `--debug`. Enforced by `test_status_quiet_by_default_suppresses_verbose_stderr` and independently re-verified via real subprocess in 05-VERIFICATION.md. | closed |
| T-05-05 | Denial of Service (log-noise obscuring errors) | quiet-mode stderr channel | low | mitigate | Quiet mode re-adds a `sys.stderr` sink at level `WARNING` (`cli.py:52`) so genuine warnings/errors still surface; only INFO/DEBUG spam is suppressed. | closed |
| T-05-SC | Tampering | pip/uv package installs | low | accept | No new third-party packages added across 05-01/05-02 — `argparse` and `loguru` are already dependencies; `uv pip install -e .` installs only the local editable project. No package-legitimacy audit triggered. | closed |

*Status: open · closed · open — below {block_on} threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-05-01 | T-05-03 | Single synchronous live login+list call per `status` invocation; no user-controlled volume or loop — DoS surface is negligible at CLI scope. | Plan 05-01 threat model | 2026-07-06 |
| AR-05-02 | T-05-SC | No new third-party dependencies introduced in Phase 5 (`argparse` stdlib, `loguru` pre-existing). | Plan 05-01/05-02 threat models | 2026-07-06 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-06 | 6 | 6 | 0 | gsd-secure-phase (L1 grep-depth, register authored at plan time — short-circuit path, no auditor spawn needed) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-07-06
