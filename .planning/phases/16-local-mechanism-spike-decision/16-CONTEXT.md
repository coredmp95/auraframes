# Phase 16: Local Mechanism Spike & Decision - Context

**Gathered:** 2026-09-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Decision-producing, not feature-producing. This phase delivers ONE artifact of substance:
a written decision record (`16-DECISION-RECORD.md`) selecting the single album-access
mechanism v4.0 builds on, backed by live evidence from two probes plus the byte-fidelity
settlement:

1. **Shared-album link** — `photos.google.com/share/...` enumeration without any auth:
   probed against the user's real target albums, actual item counts recorded against the
   suspected ~500-item ceiling.
2. **Browser automation** — one-time cookie bootstrap from a dedicated Chrome profile
   plus one internal `batchexecute` album listing: probed end-to-end once, its permanent
   local-only, never-CI-able cost stated plainly.

Plus **LGS-06 — byte fidelity**: the account's Original-quality vs Storage-Saver setting
checked once, and a photo already on the frame downloaded back through the candidate
mechanism compared base64-MD5 against the frame's reported `md5_hash` (proven
byte-identical to `S3Client.get_md5` in Phase 7).

No production feature code ships here. Probe scripts are committed (see D-01) but live
under a clearly separated location; the milestone builds on whichever mechanism the
decision record selects.

Closed dead ends, never re-opened: Aura/Pushd server-side sync (abandoned 2026-09-28 —
does not work in practice, not a reference for anything), Picker API per-photo selection
(user-rejected), app-created albums, Takeout, Data Portability API, restricted-scope
allowlist.

Carried context from the v3.0-era discussions (still locked): share links are capability
URLs — redacted in committed docs, full links untracked locally, created by the user via
the Google Photos UI; real target albums (100–500 photos) are the probe targets; the
browser path uses a dedicated Chrome profile, untracked 0600 cookies, a structural
sync-path denylist, and a throwaway album for the automation probe.
</domain>

<decisions>
## Implementation Decisions

### Probe scripts — disposition

- **D-01:** Probe scripts are **committed to the repo** (e.g. `probes/` or `tools/`),
  clearly separated from production code — reusable, auditable, and Phase 17 starts from
  the validated probe code rather than from zero.
- **D-02:** If the shared-link ~500 ceiling is confirmed, the shared-link probe code is
  **still committed and reusable**: the `AF_initDataCallback` parser and the `=d`
  download path survive into Phase 17 even though the pagination remains unresolved —
  the verdict documents the measured ceiling honestly rather than discarding working
  code.

### Stop conditions & verdicts

- **D-03:** A probe that cannot run is **not a positive verdict**: if the browser cookie
  bootstrap fails (chromedriver blocked, RPC unreachable), the browser mechanism is
  **rejected** in the decision record with the reason "bootstrap not reproducible" —
  never selected by optimism.
- **D-04:** If the shared-link ceiling cannot be measured precisely (all real albums
  under 500 and no 600+ album available), the ceiling becomes a **bounded, documented
  risk** (lower bound = largest album actually measured) and the decision is taken
  anyway — the milestone does not block on a perfect measurement.
- **D-05:** If BOTH mechanisms fail their probes, the milestone **pauses with a
  documented decision record** — no choosing the least-bad option. Byte fidelity
  (LGS-06) and complete enumeration (LGS-05) are non-negotiable; the pause triggers
  re-evaluation (fresh research, alternative mechanisms) before any selection.

### Consent & probe execution

- **D-06:** **Cookie-harvest consent is re-confirmed for v4.0** (the 26-09 consent,
  re-affirmed 2026-09-28): dedicated Chrome profile only (never the daily driver),
  cookies stored untracked 0600 with a structural denylist keeping them out of all
  sync/apply code paths, probe runs against a throwaway album. This consent covers the
  read-only harvest + probe described; significant live actions still get their own gate
  (Phase 11 precedent).
- **D-07:** The **agent executes the probes**, with explicit confirmation gates before
  the sensitive steps: (1) the cookie harvest, (2) any call that writes to the frame,
  (3) any upload of a test asset. The user only has to say "go" at those moments.
- **D-08:** The browser automation engine is **Playwright + Chromium** loading the
  dedicated Chrome profile — Python API maturity, managed browser download, and the
  recommendation of `research/BROWSER-AUTOMATION.md`.

### Claude's Discretion

Areas not selected for discussion; the agent decides during planning/execution within
the constraints above:

- **Evidence file layout** — probe evidence follows the `11-LIVE-FINDINGS.md` precedent
  (full command, raw HTTP evidence, mechanism table, re-read confirmation).
- **SPK-04→LGS-06 comparison specifics** — which standing asset(s) to use, sample size,
  and the order of mechanism-vs-fidelity testing (leading candidate first, extend only
  if cheap).
- **Probe script structure** — exact `probes/` layout, CLI shape, and how much of the
  shared-link parser is generalized vs spike-shaped.
- **Decision-record compilation** — the agent compiles the record with a recommendation
  grounded in probe evidence; the user makes the final selection call (carried from the
  v3.0-era discussion, D-10 there).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Mechanism research (the reason this phase exists)
- `.planning/research/ALBUM-ACCESS.md` — §1 shared-link findings (VERIFIED live fetch:
  `AF_initDataCallback` structure, `=d` full-res convention, no EU consent wall from a
  Paris IP, ~500 ceiling admission), §2/§3 browser automation + app-created dead end,
  dead-ends list; **§5 (Pushd/Ambient) is OBSOLETE — abandoned 2026-09-28**
- `.planning/research/BROWSER-AUTOMATION.md` — cookie-bootstrap + `batchexecute`
  approach, browser-dependency isolation rule
- `.planning/research/ALBUM-ACCESS-V4-ADDENDUM.md` — targeted 2026-09-28 research: no
  published pagination prior art (re-confirmed), `xob0t/Google-Photos-Toolkit` as public
  proof the internal RPC works from a session, session-longevity unknown → LGS-02,
  byte-fidelity unchanged
- `.planning/research/PITFALLS.md` — byte-fidelity framing (account-setting question),
  ceiling risk, empty-listing mass-hide

### Requirements & success criteria
- `.planning/REQUIREMENTS.md` — LGS-01, LGS-06 verbatim (Phase 16); the v4.0 scope-change
  header; Out of Scope table
- `.planning/ROADMAP.md` (Phase 16 section) — the four success criteria this phase is
  verified against

### Prior live-evidence precedent
- `.planning/milestones/v3.0-phases/11-write-path-reliability-format-support/11-LIVE-FINDINGS.md` —
  the evidence-recording format precedent (archived with v3.0)

### Project conventions
- `.planning/PROJECT.md` — Key Decisions ("Trust live probes over model assumptions"),
  Constraints (secrets out of VCS; unofficial-API posture)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `auraframes/client.py` (`Client`) — authenticated httpx session; not needed for the
  no-auth shared-link probe but is the transport for any frame-side reads (LGS-06
  comparison target via `FrameApi.get_assets`' `md5_hash`)
- `auraframes/aws/s3client.py` (`S3Client.get_md5`) — the local base64-MD5 convention,
  proven byte-identical to the frame's reported hash (Phase 7); the exact function the
  fidelity comparison reuses
- `auraframes/api/frameApi.py` (`FrameApi.get_assets`) — source of the frame's
  per-asset `md5_hash` for LGS-06
- Tests' offline harness (`tests/offline.py`, `httpx.MockTransport`-backed) — the
  pattern committed probe code should follow so Phase 17 inherits injectable HTTP

### Established Patterns
- **Raw httpx, no heavy SDK** — probe scripts use the same stack as the client
- **Playwright is new to the repo** — D-08 introduces it; it must stay behind the
  browser-isolation rule (leaf module, never in the test-suite import graph) from day one
- **Fail-loud** — probe scripts surface errors, never swallow them
- **Consent gates on sensitive live actions** — Phase 11 precedent, made explicit in D-07

### Integration Points
- `probes/` (new) — committed probe scripts land here
- The eventual Google-side source module (Phase 17) — created only after
  `16-DECISION-RECORD.md` exists; LGS-01's record is the written gate for the rest of
  the milestone

</code_context>

<specifics>
## Specific Ideas

- Privacy tiers (carried + re-confirmed): harvested cookies = untracked 0600 +
  denylist, never committed; share links = redacted in committed docs, full links
  untracked locally; item counts, link shapes, and probe code = fine to commit.
- The decision record must state each mechanism's verdict, the live evidence, and the
  rejected alternative's reason — with the user's final call recorded as a signed
  decision line (carried from the v3.0-era discussion).
- The real albums are expected at 100–500 photos — close enough to the suspected
  ceiling that the real-album probe is informative; the synthetic 600+ album is the
  fallback measurement (D-04 bounds the risk if even that is not built).

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 16-Local Mechanism Spike & Decision*
*Context gathered: 2026-09-28*
