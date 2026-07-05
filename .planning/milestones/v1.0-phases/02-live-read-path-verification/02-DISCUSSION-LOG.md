# Phase 2: Live Read-Path Verification - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-29
**Phase:** 2-Live Read-Path Verification
**Areas discussed:** Verification harness & evidence, Pagination rigor, Error & drift surfacing, EXIF/GPS strictness & asset selection

---

## Verification harness & evidence

### How the read path is run and proven

| Option | Description | Selected |
|--------|-------------|----------|
| pytest integration test | Live test via `uv run pytest`, reuses Phase 1 harness, pass/fail per step, feeds Phase 3 report | ✓ |
| Runnable script / main.py | Flesh out main.py to log in/list/fetch/download and print | |
| Both | pytest + runnable example | |

**User's choice:** pytest integration test

### Gating live tests vs credential-less runs

| Option | Description | Selected |
|--------|-------------|----------|
| Skip when creds absent | `@pytest.mark.live` auto-skip when AURA_EMAIL/AURA_PASSWORD unset; default pytest stays green | ✓ |
| Separate opt-in command | Keep live tests out of default run, invoke explicitly | |
| You decide | Pick idiomatic gating | |

**User's choice:** Skip when creds absent

### Test granularity

| Option | Description | Selected |
|--------|-------------|----------|
| One test per READ req | Separate tests for READ-01..04 sharing a login fixture | ✓ |
| Single end-to-end test | One chained test asserting at each step | |
| You decide | Cleanest mapping to READ-01..04 | |

**User's choice:** One test per READ req

**Notes:** Output of the live pytest run becomes the evidence consumed by the Phase 3 verification report.

---

## Pagination rigor

### How to genuinely prove cursor pagination

| Option | Description | Selected |
|--------|-------------|----------|
| Force small limit | Tiny limit so even a small account yields multiple pages; assert cursor traversal | ✓ |
| Accept account size | Use real limit, assert all assets returned (cursor branch may never run) | |
| Conditional / hybrid | Small limit only if needed, else document the gap | |

**User's choice:** Force small limit

### Target + bound (helper hardcodes limit=1000 and sleeps 1s/page)

| Option | Description | Selected |
|--------|-------------|----------|
| Parametrize get_all_assets | Add optional `limit`, verify real helper; drop/shorten the 1s sleep | ✓ |
| Test-local pagination loop | Drive frame_api.get_assets in the test's own loop | |
| Prove cursor, don't drain | Assert cursor advances ≥2 pages rather than draining a large frame | |

**User's choice:** Parametrize get_all_assets

**Notes:** Planner should pick a sensible small limit and reasonable target frame — goal is proving the cursor mechanism, not stress-testing a large frame.

---

## Error & drift surfacing

### How much error surfacing to add for trustworthy verification

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal surfacing | `raise_for_status()` in Client + raise/log on silent `error`-key spots; no exception hierarchy | ✓ |
| Assert in tests only | Leave production code, tests assert on status/shape | |
| Observe via logs | Change nothing, inspect loguru output + history deque | |

**User's choice:** Minimal surfacing

### Plaintext credential logging during live run

| Option | Description | Selected |
|--------|-------------|----------|
| Redact secrets in logs | Scrub password/auth_token/x-token-auth from request+response logging | ✓ |
| Ensure logs gitignored only | Don't touch logging, just confirm logs/ gitignored | |
| Leave as-is | Defer as a security item | |

**User's choice:** Redact secrets in logs

**Notes:** Also flagged the must-fix that `logs/` is never created at startup → `FileNotFoundError` on first live run; planner must ensure `logs/` exists + is gitignored.

---

## EXIF/GPS strictness & asset selection

### Strictness of the datetime + GPS pass bar

| Option | Description | Selected |
|--------|-------------|----------|
| Datetime required, GPS conditional | Always assert datetime; require GPS only when asset has location; document gap otherwise | ✓ |
| Both strictly required | Must download an asset yielding both, else fail | |
| Datetime only, GPS best-effort | Assert datetime, log whether GPS written | |

**User's choice:** Datetime required, GPS conditional

### Frame + asset selection

| Option | Description | Selected |
|--------|-------------|----------|
| Auto: first frame, first geo asset | First frame; first asset with non-null location_name, fallback first asset | ✓ |
| Configurable frame/asset | Optional env var/param to target a known-good frame | |
| You decide | Best strategy without manual setup | |

**User's choice:** Auto: first frame, first geo asset

### Silent download/EXIF failures + Nominatim user-agent

| Option | Description | Selected |
|--------|-------------|----------|
| Tighten + fix UA | Surface EXIF-write failure; set a proper Nominatim user-agent | ✓ |
| Read-back catches it | Leave bare excepts, rely on read-back; fix only UA | |
| Leave as-is | Don't touch exif.py, defer | |

**User's choice:** Tighten + fix UA

**Notes:** READ-04 is verified by reading EXIF back from the saved file (reuse `get_readable_exif`), not by trusting the write returned.

---

## Claude's Discretion

- Exact pytest mechanics: fixture scoping, `live` marker registration, the chosen small `limit` value, how the login fixture exposes the session to the 4 tests.
- Whether to opportunistically close Phase 1's deferred `.dict()` → `.model_dump()` migration (NOT on the read path, so optional here).
- Exact secret-redaction mechanism (log filter vs. sanitizing the payload dict).
- Defaulting READ-04 to an image asset when video assets are encountered.

## Deferred Ideas

- `.env` loader for credentials (kept plain shell env vars per constraint; Phase 3 docs cover them).
- Video / non-image asset handling.
- Full typed exception hierarchy (MOD-03), AWS pool-ID config (MOD-02), async migration (MOD-01), upload round-trip (UP-01).
- Retry/backoff on transient network/429 errors — note flakiness for the Phase 3 report rather than building retry now.
