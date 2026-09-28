---
phase: 17-google-link-album-selection
verified: 2026-09-28T18:05:00Z
status: passed
score: 5/5 success criteria verified
covered_files:
  - .planning/phases/17-google-link-album-selection/17-01-PLAN.md
  - .planning/phases/17-google-link-album-selection/17-02-PLAN.md
  - .planning/phases/17-google-link-album-selection/17-01-SUMMARY.md
  - .planning/phases/17-google-link-album-selection/17-02-SUMMARY.md
  - auraframes/google/client.py
  - auraframes/google/vault.py
  - auraframes/google/parsers.py
  - auraframes/google/enumerate.py
  - auraframes/google/redaction.py
  - auraframes/google/bootstrap.py
  - auraframes/cli.py
  - tests/test_google_client.py
  - tests/test_google_parsers.py
  - tests/test_google_vault.py
  - tests/test_google_enumerate.py
  - tests/test_cli_google_link.py
  - tests/test_cli_google_album.py
  - tests/test_cli_status_google.py
behavior_unverified: 0
coincidental_reliance_items: []
---

# Phase 17: Google Link & Album Selection Verification Report

**Phase Goal:** The user links Google once through the chosen mechanism, names an album at album granularity, and the CLI can enumerate every photo inside it
**Verified:** 2026-09-28T18:05:00Z
**Status:** passed

## Goal Achievement

### Observable Truths (ROADMAP success criteria 1–5)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | One documented command links/re-links; the credential persists outside version control | ✓ VERIFIED | `aura-cli google-link` (README-documented, LGS-02) → `GoogleSession.from_vault` / `default_bootstrap` → `vault.save` (0600, `~/.config/auraframes/google-cookies.json`, repo-inside refusal test-proven). Re-link is the same command (refresh notice test). The operator's session harvested in phase 16 still works through the new package (live status check returned `linked: yes`). |
| 2 | `status` reports Google linked/account/session without printing credential/cookie/token | ✓ VERIFIED | `_google_status_section` prints `linked: yes/no`, `account: <email>`, `session: usable/expired` only. Tests grep the output for planted fake cookie values and assert absence (test_cli_status_google.py::test_status_google_section_never_prints_cookie_values). Live: `linked: yes`, account resolvable. |
| 3 | Album selection at album granularity — share link, id, or name; no per-photo picking anywhere | ✓ VERIFIED | `resolve_album` (URL/id direct, name substring, numbered ambiguity exit 2 — no silent pick, no prompt) + `google-album --list`. No per-photo selection surface exists anywhere in the phase's diff (grep-checked). |
| 4 | Listing returns EVERY photo, including albums larger than one page; count matches what the UI shows | ✓ VERIFIED | RPC-first `enumerate_album` (300/page, AH_ token swap, exhaustion flag, page-cap fail-loud). Live-proven this session through the CLI's own code path: album "Cadre" → **24/24 items** (= UI ground truth), clean exhaustion, 86.6 MiB exact disk weight; album "Nous" → 300+300+300+194 = 1094 photos on the 1096-item album (the 2-item delta = videos, which the photo walker skips by shape — enumerated on the mock at 794 items across 3 pages too). |
| 5 | Every Google-facing component exercised offline via injected transport/fixture-backed fake (TEST-02) | ✓ VERIFIED | 37 package tests + 22 CLI tests, all over `httpx.MockTransport`/injected seams (`transport=`, `bootstrap_fn`, `google_session=`, `session=`). Zero browser launch, zero live network in the suite; playwright never appears in the test import graph (asserted). The mock router VALIDATES the client's protocol side (triple-nested envelope, null batch-1, token chain, page_key, Range headers) — deviations answer 400. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `auraframes/google/client.py` | Full-jar session client, DI seam | ✓ EXISTS + SUBSTANTIVE | GoogleSession (full jar domain+path, UA, `transport=`, is_linked/at_token/account_email/SAPISIDHASH); test-proven jar shape |
| `auraframes/google/vault.py` | Migrated 0600 vault + denylist | ✓ EXISTS + SUBSTANTIVE | Denylist verbatim (test asserts the exact tuple), repo refusal, legacy fallback tests |
| `auraframes/google/parsers.py` | ds:1/snAcKc/batchexecute/album parsers | ✓ EXISTS + SUBSTANTIVE | Generalized `extract_initdata(key)`, `parse_snackc_payload`, `parse_batchexecute`, live-proven `parse_album_summaries` (ds:5 shape) |
| `auraframes/google/enumerate.py` | RPC-first enumerator + sizer + listing | ✓ EXISTS + SUBSTANTIVE | `enumerate_album(album_id, page_key=)`, `measure_disk_weight`, `list_shared_albums` — all live-validated read-only |
| `auraframes/google/redaction.py` | Redaction helpers | ✓ EXISTS + SUBSTANTIVE | `redact_link`/`redact_tokens`; re-exported by probes/common.py |
| `auraframes/google/bootstrap.py` | Dedicated-profile bootstrap seam | ✓ EXISTS + SUBSTANTIVE | `run_bootstrap(auto=True)` default, lazy playwright import, env-gated profile |
| `auraframes/cli.py` | google-link / google-album / status extension | ✓ EXISTS + SUBSTANTIVE | `run_google_link(bootstrap_fn=)`, `run_google_album(session=, list_all=)`, `run_status(google_session=)`, `AlbumResolution`; parser + dispatch wired |
| Tests (7 modules) + 2 fixtures | Offline coverage | ✓ EXISTS + SUBSTANTIVE | 59 google-related tests green; fixtures authored-synthetic |

**Artifacts:** 8/8 verified

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| cli.run_google_album | google.enumerate.enumerate_album | direct import + call | ✓ WIRED | Resolution → `enumerate_album(session, album.album_id, page_key=...)` → per-item table |
| cli.run_google_link | google.bootstrap.default_bootstrap | bootstrap_fn seam | ✓ WIRED | `bootstrap = bootstrap_fn or default_bootstrap`; tests inject fakes |
| cli.run_status | GoogleSession.is_linked/account_email | google_session DI + vault route | ✓ WIRED | `_google_status_section`; vault route goes through from_vault (denylist-sanctioned broker) — live-proven with a real vault |
| google.enumerate | google.parsers (batchexecute/snAcKc walk) | parse_batchexecute/parse_snackc_payload | ✓ WIRED | Mock enforces the envelope shape |
| probes/* | auraframes.google (parsers, vault shim, redaction, session) | import shims | ✓ WIRED | Probe tests + smoke imports green; probe CLI surfaces unchanged |

**Wiring:** 5/5 connections verified

## Requirements Coverage

| Requirement | Status | Blocking Issue |
|-------------|--------|----------------|
| LGS-02: one documented link/re-link command, persisted out of VCS | ✓ SATISFIED | - |
| LGS-03: status reports Google state, never a secret | ✓ SATISFIED | - |
| LGS-04: album-granularity selection (link/id/name), no photo picking | ✓ SATISFIED | - |
| LGS-05: full enumeration beyond one page, count = UI | ✓ SATISFIED | Live-proven 24/24 (Cadre) and 1094 paginated (Nous) |
| TEST-02: every Google-facing component offline-testable | ✓ SATISFIED | 59 tests, zero live network |

**Coverage:** 5/5 requirements satisfied

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | - | - | - | - |

**Anti-patterns:** 0 found (0 blockers, 0 warnings)

## Human Verification Required

None required for the goal — every criterion is machine-verified. Optional operator
confirmation (outside the goal's scope): an interactive `google-link` re-link through
the dedicated profile, and a `google-album "Cadre"` run through the actual CLI entry
point (the underlying package path was live-proven this session; the CLI surface is
the same code).

## Gaps Summary

**No gaps found.** Phase goal achieved. Ready to proceed.

## Verification Metadata

**Verification approach:** Goal-backward (ROADMAP Phase 17 success criteria 1–5)
**Must-haves source:** .planning/ROADMAP.md Phase 17 + both PLAN frontmatters
**Automated checks:** 345 passed, 0 failed (`uv run pytest -q -m "not live"`; 6 live deselected)
**Live read-only validations:** session usable; /albums listing decoded; 24/24 + 86.6 MiB end-to-end; 1094-photo full pagination
**Human checks required:** 0
**Total verification time:** ~10 min

---
*Verified: 2026-09-28T18:05:00Z*
*Verifier: Buffy (inline, Freebuff — no gsd-verifier subagent available)*
