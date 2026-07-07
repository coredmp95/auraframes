---
phase: 06
slug: inspect-frame-resolution
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: 2026-07-07
---

# Phase 06 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| user CLI arg -> resolve_frame | `--frame <value>` is untrusted free-form input; used only for in-memory string comparison against `Frame.name` / `Frame.id` | free-text frame name/id |
| CLI -> Aura/pushd API | authenticated GET responses (`get_frames`/`get_frame`/`get_assets`) cross into the process; undocumented, drift-prone API | frame/asset metadata (JSON) |
| process -> stdout/stderr | rendered metadata, photo lines, and error messages leave the trust boundary to the terminal | frame metadata, photo listing |
| live credentials -> Aura API | real `AURA_EMAIL`/`AURA_PASSWORD` authenticate the live `md5_hash` spike session | account credentials |
| `--debug` logs -> disk/stderr | verbose response bodies (asset JSON) are written to `logs/` and stderr during the live pass | asset ids, filenames, md5_hash values |
| STATE.md / PROJECT.md commit | the confirmed md5_hash finding is written into version-controlled docs | yes/no finding + drift notes only |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-06-01 | Information Disclosure | `run_inspect()` error/output paths | medium | mitigate | Ambiguous/not-found/error branches print only `Frame.name`/`Frame.id` (no secrets); `test_cli_inspect.py:56` asserts the injected password value is absent from stdout | closed |
| T-06-02 | Denial of Service (availability) | post-login `get_frame`/`get_all_assets` on drifted API | low | mitigate | Broad `try/except` around post-login data fetches (`cli.py:163-185`) prints the error and returns exit code 1 instead of a raw traceback | closed |
| T-06-03 | Tampering | `--frame` value used in string ops only | low | accept | Value is never interpolated into a shell command, SQL query, or filesystem path — pure in-memory comparison, no injection sink exists | closed |
| T-06-SC | Tampering | package installs | low | accept | This phase adds zero new packages — no install task exists, legitimacy gate not applicable | closed |
| T-06-04 | Information Disclosure | `--debug` logs to `logs/file_*.log` during the live spike | medium | mitigate | Live pass logs asset metadata (ids, filenames, md5_hash), not credentials; `logs/` is gitignored (`.gitignore:92`) and was not committed | closed |
| T-06-05 | Information Disclosure | STATE.md / PROJECT.md commit | low | mitigate | Only the yes/no md5_hash finding and drift notes are written to version-controlled docs — confirmed no secrets/tokens/account-identifying URLs present in `STATE.md:83` or `PROJECT.md:132-140` | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on (high) count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-06-01 | T-06-03 | `--frame` value is pure in-memory string comparison against `Frame.name`/`Frame.id` — no shell/SQL/filesystem sink exists for it to reach | plan author (06-01-PLAN.md) | 2026-07-06 |
| AR-06-02 | T-06-SC | Phase adds zero new package dependencies; supply-chain legitimacy gate does not trigger | plan author (06-01-PLAN.md) | 2026-07-06 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-07 | 6 | 6 | 0 | orchestrator (grep-depth verification, ASVS L1) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-07-07
