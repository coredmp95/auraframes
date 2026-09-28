# Phase 16 — Decision Record: Album-Access Mechanism for v4.0

**Status:** DECIDED · **Date:** 2026-09-28 · **Gate:** this record gates Phases 17-19
(LGS-01's written selection; undoing it mid-milestone means replanning 17-19).

**Evidence anchors:** `16-LIVE-FINDINGS.md` — "Plan 16-01" (shared-link probe),
"Plan 16-02" (browser bootstrap + RPC), "Plan 16-03 — Byte fidelity". Privacy
discipline held: capability URLs appear only in redacted shape throughout.

---

## Verdict table

| Mechanism | Verdict | One-line live evidence | Evidence |
|---|---|---|---|
| `browser-automation` (dedicated-profile cookie bootstrap + internal `snAcKc` RPC) | **SELECTED** | 794/794 unique items enumerated from the real 1000+ album via plain-httpx continuation; byte fidelity MATCH proven by upload round-trip | 16-02, 16-03 |
| `shared-album-link` (plain HTTP, no auth) | **rejected as the primary mechanism — retained as bootstrap stage** | 24/24 ground-truth parse, but the 1000+ album exposes exactly 300 items on the public page with no published pagination — measured, not inferred | 16-01 |
| `pushd/ambient` (Aura's server-side Google sync) | abandoned 2026-09-28 — does not work in practice (operator-observed), not evaluated | n/a — outside v4.0's scope by the replan decision | ROADMAP v4.0 scope note |

---

## Narrative per mechanism

### Browser-automation (cookie bootstrap + internal RPC) — SELECTED

**What was probed.** One-time interactive login in the dedicated Chrome profile
(`AURA_PROBE_CHROME_PROFILE`, system Chrome via `channel="chrome"` after the bundled
Chromium was refused by Google's bot detection — the D-03 documented retry). Harvest:
45 cookies into the untracked 0600 vault outside the repo (structural denylist keeps
sync/apply code from ever reading it — tested offline). Then, with no browser running:
plain-httpx `batchexecute` calls with the full cookie jar.

**What worked.**
- The Google-frontend capture (`probes/rpc_capture.py`, read-only scroll) recorded the
  real pagination shape: **`snAcKc(share_token, continuation_token, null, key)`** — the
  continuation mechanism the research pass found no prior art for (V4-ADDENDUM Q1).
- Replaying the captured body with the token swapped: **300 + 300 + 194 = 794 items,
  794 unique, clean token exhaustion** on the operator's real 1000+ album. Reproduced by
  the committed `probes/browser_bootstrap.py list`. **No ceiling observed.**
- Full-jar cookies (domain+path preserved) are required — a flattened dict is treated
  as anonymous (live finding, recorded).
- Byte fidelity: the `=d` original of album C pushed to the frame came back with the
  frame's `md5_hash` **identical** to the Google-side hash — see fidelity section.

**Costs stated plainly (all accepted at the 2026-09-28 replan):**
- **Permanently local-only, never-CI-able** — Google's bot detection blocks unattended
  login (confirmed live: bundled Chromium refused; even system Chrome needed a human).
- **Periodic re-auth** at an unpredictable cadence (weeks-to-months, per research);
  bootstrap is one documented command, re-runnable.
- **Undocumented RPC surface** — shapes change without notice (Google redeploys); when
  it breaks it breaks loudly (400 + error envelope, observed). The capture-and-replay
  method is the recovery path, and `rpc_capture.py` ships as the tool for it.
- Test upload + read consumed ~2 of the 30-token write budget; steady-state sync is
  read-dominated (upload only for new items).

### Shared-album-link — rejected as primary, retained as bootstrap stage

**What worked.** Plain HTTP (no cookies, no JS) fetches `photos.google.com/share/…`,
parses `ds:1` exactly (24/24 ground truth on the operator's 24-photo album, synthetic
fixture suite green), and `=d` serves originals (fidelity MATCH — same bytes as the RPC
path, since the URL family is the same).

**Why rejected as the primary.** The operator-confirmed 1000+ album exposes **exactly
300 items** on its public share page (repeatable). No plain-HTTP pagination has ever
been published (V4-ADDENDUM Q1: no prior art; publicalbum.org: "this is the limit").
For the milestone's own target albums this mechanism cannot enumerate past 300 — a
measured limitation, not a suspicion (D-04 was in force; the ceiling got measured
rather than bounded).

**Why not discarded.** The share page hands out, with zero auth: the share token, the
`key` parameter, the at-token context, and batch-1 (300 items) — exactly the arguments
`snAcKc` consumes. Phase 17's client opens with the public page as the bootstrap stage
and continues with the RPC. Both parsers are committed and offline-tested (D-02's
survival promise honored).

### Pushd/Ambient — out of scope

Abandoned at the v4.0 replan (2026-09-28): Aura's own server-side Google sync does not
work in practice (operator-observed) and is not a reference. During this phase's probes
the Pushd assets endpoint additionally exhibited a live drift (0 assets returned against
`num_assets: 251`, recovering minutes later) — recorded in 16-03 as corroborating
evidence that v4.0 must not depend on Pushd's Google-side plumbing.

---

## Byte fidelity (LGS-06)

- **Account quality setting: Original** (operator-confirmed, 2026-09-28).
- **Verdict: MATCH** — album C's `=d` original (3,412,350 bytes,
  base64-MD5 `DSWMyGKS2k3nxpzqIdh37g==`) uploaded to the frame; the frame's reported
  `md5_hash` for that asset is **byte-identical**. Upload-test round-trip path (D-07
  gate 3 approved); the test asset was then hidden (reversible, v2.0 hide semantics).
- **D-05 hard-reject: not triggered** — the mechanism(s) under selection can download
  diffable bytes. The mirror-sync diff engine may be built on `md5_hash` equality.
- Per-mechanism note: fidelity is a property of the `=d` URL family (identical for both
  mechanisms), independent of enumeration path — so the rejection/rejection-free
  verdict transfers to the selected mechanism as-is.

---

## Recommendation (agent's, labeled)

**Select browser-automation, with the shared-link page as the bootstrap stage.**
Grounds: only the RPC path enumerated the real 1000+ album completely (measured);
every one of its permanent costs was explicitly accepted by the operator at the
2026-09-28 replan; fidelity is proven for both.

---

## Decision (signed by the operator)

**Selected mechanism: `browser-automation` (dedicated-profile cookie bootstrap +
internal `snAcKc` RPC), with the shared-album-link page retained as the bootstrap
stage of the Phase 17 client.**

- Operator's selection, captured 2026-09-28 at the Phase 16 decision checkpoint:
  **"Navigateur + RPC (recommandé)"** — matching the agent's recommendation.
- The recommendation-vs-decision question is moot: the operator's call and the
  recommendation coincide; the operator's call is the recorded authority.
- Pause (D-05) did not apply: both mechanisms ran and produced evidence.

Signed for the record by the Phase 16 executor at the operator's explicit
checkpoint response (verbatim above).

---

*Next gate: Phase 17 (Google Link & Album Selection) plans against THIS selection.
Out of scope by REQUIREMENTS: Takeout, Data Portability API, app-created albums,
Picker per-photo flow — the closed dead ends are not re-opened by this record.*
