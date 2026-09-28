# Plan 16-02 Summary — Browser bootstrap + internal RPC

Built and ran the browser-automation probe: one-time cookie harvest from a dedicated
Chrome profile into the untracked 0600 vault (structural sync/apply denylist), then a
plain-httpx `batchexecute` listing with no browser alive — including the pagination
continuation the research declared unpublished.

## What was delivered

- `probes/cookie_vault.py` — 0600 vault outside the repo (repo-inside refused at save),
  caller-frame denylist refusing `auraframes.sync|reconcile|cli` structurally (D-06).
- `probes/browser_bootstrap.py` — `bootstrap` (Playwright persistent context, lazy
  import, system-Chrome channel, `--auto` login detection) + `list` (plain-httpx,
  full-jar session, `snAcKc` continuation loop).
- `probes/rpc_capture.py` — read-only scroll capture of Google's own frontend
  `batchexecute` calls; the source of the `snAcKc` shape (committed instrument).
- `tests/test_probe_browser.py` — 6 offline tests (round-trip, 0600, repo-inside
  refusal, denylist refusal, missing-vault error, no-playwright-in-test-graph).

## Live results (Task 3, D-07 gate 1 approved "go")

- Bootstrap: first attempt blocked by Google's "browser not secure" (bundled Chromium);
  the single D-03-allowed documented retry (system Chrome + automation flags masked)
  **succeeded**; 45 cookies harvested, vault 0600 verified, untracked.
- Plain-httpx session requires the **full cookie jar** (domain+path) — a flattened dict
  is treated as anonymous (recorded in code + findings).
- **Pagination proven: `snAcKc(share_token, continuation_token, null, key)`, 300/page;
  300+300+194 = 794/794 unique items on the real 1000+ album, clean token exhaustion.**
  The "300 ceiling" was page-1 size, not a mechanism limit. Reproduced via the
  committed `list` subcommand.

## Deviations

- `--auto` wait mode added (operator runs bootstrap from a non-interactive shell; same
  consent scope, profile, and vault).
- `rpc_capture.py` added beyond the plan's file list — it is the documented method for
  re-learning RPC shapes when Google redeploys (the mechanism's known failure mode).

## Self-Check: PASSED

- `uv run pytest -q -m "not live"`: 286 passed (6 new).
- AST verify: playwright absent from module-level imports (lazy in-function only).
- Evidence: "Plan 16-02" section with explicit verdicts; no full capability URLs.
