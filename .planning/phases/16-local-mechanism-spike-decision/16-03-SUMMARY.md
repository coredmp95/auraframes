# Plan 16-03 Summary — Byte fidelity + decision record

Settled LGS-06 and compiled LGS-01's gate document.

## Task 1 — Byte fidelity (live, gates honored)

- Quality setting: **Original** (operator-confirmed).
- Planned standing-asset comparison was impossible this session: `get_assets` returned
  0 assets across all parameter variants while `num_assets: 251` (Pushd server drift,
  recorded verbatim — itself evidence for v4.0's independence from Pushd plumbing).
- Executed the approved **upload-test round-trip** instead (D-07 gate 3 "go"): album C's
  `=d` original (3,412,350 B, `DSWMyGKS2k3nxpzqIdh37g==`) pushed to the frame; the
  frame's `md5_hash` for the new asset **equals the Google-side hash byte-for-byte —
  MATCH**. Test asset hidden afterward (reversible hide; re-read confirmed
  `hidden: true, selected: false`). The frame's slideshow is unchanged.

## Task 2 — Decision record (checkpoint:decision, operator's call)

- `16-DECISION-RECORD.md` compiled: verdict table (browser SELECTED; shared-link
  rejected as primary, retained as bootstrap stage; pushd/ambient out of scope),
  narratives with costs stated plainly, fidelity section with D-05 not triggered,
  agent recommendation, and the operator's **signed selection: "Navigateur + RPC
  (recommandé)"** — matching the recommendation.
- Verify greps pass: verdict table present, SELECTED line present, zero full
  capability URLs in record or findings.

## Deviations

- Standing-asset → upload-test path substitution (documented in findings with the
  get_assets drift evidence).

## Self-Check: PASSED

- Fidelity evidence greps: complete (setting + MATCH rows + verdict).
- `uv run pytest -q -m "not live"`: 286 passed — full suite green.
