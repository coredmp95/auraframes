# Plan 17-01 Summary — auraframes/google/ package migration

Migrated the phase-16-proven Google mechanics from the `probes/` instruments into
the production package `auraframes/google/` — session client, parsers, snAcKc
enumerator, disk-weight measurer, cookie vault — every component offline-tested
through injected transports (TEST-02), with the cookie-vault security boundary
carried over verbatim.

## What was delivered

- `auraframes/google/vault.py` — the 0600 vault with the D-06 denylist carried over
  byte-for-byte (`auraframes.sync|reconcile|cli`, enforced via frame inspection in
  `load()`), the repo-inside save refusal, and a production default path
  (`~/.config/auraframes/google-cookies.json`) with a legacy-path fallback
  (`~/.config/auraframes/probes/google-cookies.json`) so the operator's existing
  session survives the soft migration (17-CONTEXT discretion). The denylist now
  also routes the CLI through the package: `GoogleSession.from_vault` is the
  sanctioned read path, direct `auraframes.cli` imports are refused.
- `auraframes/google/parsers.py` — migrated `parse_af_initdata`/`extract_ds1_data`
  (balanced-bracket ds:1 extraction, tolerant-sanitize fallback), the §1b item
  walker, plus new `parse_snackc_payload` (wire payload → items + LAST AH_ token =
  cursor, none = exhaustion) and `parse_batchexecute` (envelope splitter, zero
  parseable lines = fail-loud). `ProbeParseError` names the missing structure.
- `auraframes/google/client.py` — `GoogleSession`: full-cookie-jar httpx (domain+path
  preserved — the live-proven requirement; a flattened dict reads as anonymous),
  harvesting-browser UA, `transport=` DI seam mirroring `Client`'s, `is_linked()`
  (SNlM0e vs anonymous redirect), `at_token()`, `account_email()` (email only,
  D-02), SAPISIDHASH Authorization builder.
- `auraframes/google/enumerate.py` — `enumerate_album()` replaying the proven flow
  (share-page batch-1 with the intermittent AH_-token retry budget, 300/page snAcKc
  continuation with token swap, clean-exhaustion flag, page-cap fail-loud
  INCOMPLETE) and `measure_disk_weight()` (1-byte Range GETs → Content-Range
  totals, 0 on absence).
- `auraframes/google/redaction.py` — `redact_link`/`redact_tokens` (AF1Qip…<last4>),
  re-exported by `probes/common.py`.
- Fixtures fully synthetic: `google_share_page_sample.html` (4 items + SNlM0e/
  FdrFJe/cfb2h/oPEP7c markers + AH_ cursor), `google_rpc_snackc_page.json`.
- Tests: `tests/test_google_{client,parsers,vault,enumerate}.py` — 37 new offline
  tests (MockTransport DI; zero live network; zero playwright).
- Task 3: probes import the package (cookie_vault.py is a shim; shared_link_probe
  re-exports the package parsers; browser_bootstrap builds its client via
  `GoogleSession.from_vault`) — CLI surfaces unchanged.

## Key discovery encoded (16-LIVE-FINDINGS addendum)

The phase-16 "HTTP 400 / payload deviné" failure was an ENVELOPE-NESTING bug, not
a payload bug: f.req must be TRIPLE-nested
(`[[["snAcKc", <inner_json>, null, "generic"]]]`, compact separators). Both the
package enumerator and the probe's `_batchexecute` now build that shape, and the
test router rejects any deviating envelope with HTTP 400 — the protocol contract
is enforced on both sides of the mock. `page_key` (snAcKc's 4th argument) is the
share URL's `?key=` parameter; the album id is the URL's final `/share/<id>`
segment.

## Deviations

- None material. Two micro-deviations inside the plan's own discretion margins:
  `redaction.py` is its own module (plan offered "redaction.py or parsers"), and
  enumerate tests live in `tests/test_google_enumerate.py` (plan offered "extend
  client tests or add a module").
- The plan's threat T-17-03 (redaction at every print site) is enforced by the
  helpers' migration plus the probe print sites unchanged; `enumerate.py` redacts
  URLs and RPC body heads in its error messages.

## Self-Check: PASSED

- Verify T1/T2/T3 commands from the plan: all green (`27 passed` → `10 passed` →
  full suite).
- `uv run pytest tests/ -q -m "not live"`: **323 passed** (286 before phase 17;
  37 new google/probe tests), 6 deselected (live).
- Probes smoke: `probes/shared_link_probe.py --help` OK;
  `import probes.browser_bootstrap, probes.shared_link_probe` against the package OK.
