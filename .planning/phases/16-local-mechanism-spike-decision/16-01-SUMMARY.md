# Plan 16-01 Summary — Shared-link probe

Built and ran the shared-album-link probe: plain-HTTP fetch (no cookies/JS), `ds:1`
AF_initDataCallback parse, per-album item counts vs the ~500 ceiling, `=d` originals
hashed with the frame's `get_md5` convention, offline test suite on a synthetic fixture.

## What was delivered

- `probes/shared_link_probe.py` — CLI probe; `parse_af_initdata` is the D-02 parser
  that Phase 17 inherits. Tolerant ds:1 extraction (all occurrences tried, balanced-
  bracket, strict-JSON→tolerant-sanitize fallback), fail-loud on missing ds:1.
- `probes/common.py` — `redact_link()`/`redact_tokens()` (AF1Qip…<last4> shapes) and a
  fail-loud `fetch()`.
- `probes/.gitignore` — `.probe-downloads/`, `*.link` untracked (verified `git check-ignore`).
- `tests/test_probe_shared_link.py` + `tests/fixtures/probe_af_initdata_sample.html` —
  4 offline tests (fixture parse, missing-ds1 fail-loud, redaction guard, import-time
  no-network).

## Live results (Task 3, operator gates honored)

- Album C (24 photos): **24/24 ground-truth parse**, repeat-fetch identical, `=d`
  original 3,412,350 B → `DSWMyGKS2k3nxpzqIdh37g==`.
- Album B (operator-confirmed 1000+ album via its share link): **exactly 300 items**
  exposed — the suspected ~500 ceiling is in fact the page-1 batch size (measured).
- Owner-view `/album/` URLs are auth-gated (no ds:1) — real share links are a
  per-album setup cost.

## Deviations

- None material. The ceiling verdict upgraded from D-04's "bounded risk" to a full
  measurement (real 1000+ album beat the synthetic-600 contingency).

## Self-Check: PASSED

- `uv run pytest -q -m "not live"`: 286 passed (10 new).
- Verify commands from the plan: parser fixture check OK; evidence file greps clean.
