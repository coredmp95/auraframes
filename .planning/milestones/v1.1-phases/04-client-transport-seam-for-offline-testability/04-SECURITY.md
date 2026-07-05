---
phase: 04
slug: client-transport-seam-for-offline-testability
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: 2026-07-05
---

# Phase 04 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| test/library caller → httpx transport | The new `transport` param lets a caller choose the network I/O layer. Only reachable from code that constructs `Client`/`Aura` (library callers and tests), not from remote input. | None — transport selection only |
| fixture author → committed test data | Hand-authored JSON fixtures become part of git history permanently; any real secret committed here cannot be fully un-leaked by a later revert. | Synthetic auth tokens, emails, asset metadata |
| test code → `httpx.MockTransport` router | The router is entirely test-authored and test-controlled; it never receives real network input. | Fixture JSON only |
| offline test suite → production `Client`/`Aura`/`*Api` code | The offline tests exercise real production logic (redaction, raise_for_status, cursor loop, model hydration) against fake responses — the intended trust boundary being tested, not a new attack surface. | Fake HTTP responses |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-04-01 | Tampering | `Client.__init__` transport param | low | accept | Param defaults to `None`; real `HTTPTransport` built exactly as before when unset. No remote/untrusted caller can reach the constructor — injection is compile-time/library-level only. Additive-only, no new production attack surface. | closed |
| T-04-02 | Elevation of Privilege | `Aura.__init__` client param | low | accept | Injected `Client` carries no elevated capability beyond what `Aura()` already builds itself; auth/login mechanism untouched. | closed |
| T-04-03 | Information Disclosure | `tests/fixtures/*.json` | high | mitigate | All fixture values are synthetic/hand-authored fakes. Verified directly: `login.json` uses `fake-user@example.invalid` / `fake-auth-token-0001`; grep across all 5 fixture files for `hunter2`, real email domains (`@gmail`/`@yahoo`/`@hotmail`/`@outlook`), and `location`/GPS fields returned zero matches. `tests/test_fixtures_validity.py` structurally guards fixture shape. | closed |
| T-04-04 | Tampering | `tests/test_fixtures_validity.py` | low | accept | Test-only code, not shipped in the package; cannot be reached by any production code path. | closed |
| T-04-05 | Tampering | `tests/offline.py` router | low | accept | Router is test-only code, never shipped, never reachable from any production entry point (`main.py`, `Aura()` with no args). The `overrides` mechanism only affects the in-process test's own mocked responses. | closed |
| T-04-06 | Information Disclosure | `tests/test_offline_read_path.py` login test | low | accept | Uses only fake credentials `fake@example.invalid`/`fake-pw` and the fake `auth_token` already sanitized into `tests/fixtures/login.json` — no real credential referenced or logged. | closed |
| T-04-07 | Denial of Service (self) | Router default/fallback branch | low | accept | Unmatched paths return a deterministic 404 with the `error_envelope.json` fixture rather than raising an unhandled exception inside the mock, keeping test failures legible. | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on (high) count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-04-01 | T-04-01 | Additive-only DI param, default-`None`, no remote reachability — accepted at plan time. | Plan 04-01 threat model | 2026-07-04 |
| AR-04-02 | T-04-02 | Injected client carries no elevated capability beyond `Aura()`'s own default construction. | Plan 04-01 threat model | 2026-07-04 |
| AR-04-04 | T-04-04 | Test-only code, unreachable from any production path. | Plan 04-02 threat model | 2026-07-04 |
| AR-04-05 | T-04-05 | Test-only mock router, unreachable from production entry points. | Plan 04-03 threat model | 2026-07-04 |
| AR-04-06 | T-04-06 | Test uses only synthetic fake credentials already sanitized in fixtures. | Plan 04-03 threat model | 2026-07-04 |
| AR-04-07 | T-04-07 | Self-DoS risk bounded to deterministic fallback fixture, not an unhandled exception. | Plan 04-03 threat model | 2026-07-04 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-05 | 7 | 7 | 0 | Claude (secure-phase, L1 grep-depth short-circuit) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-07-05
