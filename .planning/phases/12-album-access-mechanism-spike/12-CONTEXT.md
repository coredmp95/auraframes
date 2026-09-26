# Phase 12: Album-Access Mechanism Spike - Context

**Gathered:** 2026-09-26
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase is **decision-producing, not feature-producing**. It delivers ONE artifact of
substance: a written decision record (SPK-05) that selects the single album-access
mechanism v3.0 builds on, backed by live evidence from three probes:

1. **SPK-01 — Pushd/Ambient:** does the Pushd API expose the endpoints behind Aura's own
   June-2026 Google Photos sync? If yes, the frame pulls from Google server-side and this
   client never touches Google's APIs.
2. **SPK-02 — Shared album link:** does `photos.google.com/share/...` enumeration hold up
   against the user's real target albums, including the suspected ~500-item lazy-load
   ceiling?
3. **SPK-03 — Browser automation:** can a one-time cookie bootstrap from a real logged-in
   Chrome profile plus one internal `batchexecute` album listing actually work — with its
   permanent local-only, never-CI-able cost stated plainly?

Plus the load-bearing **SPK-04 — byte fidelity**: is what the chosen mechanism downloads
byte-identical to what the frame's `md5_hash` convention expects (base64-MD5, proven
byte-identical to `S3Client.get_md5` in Phase 7)? If not, every sync run re-uploads
everything forever.

No production feature code ships here. Probes may be throwaway scripts and evidence
files; the milestone builds on whichever mechanism SPK-05 selects.

Closed dead ends, never re-opened (locked from REQUIREMENTS.md Out of Scope): Picker API
per-photo selection (user-rejected), app-created albums, Takeout as the mechanism,
Data Portability API, restricted-scope allowlist application.
</domain>

<decisions>
## Implementation Decisions

### Pushd probe method (SPK-01)

- **D-01:** The Pushd probe is **passive + GET-only**: mine existing authenticated GET
  payloads (frames, assets, activities — sources/album/config-shaped fields) for evidence
  of the Ambient/Google-link feature, then probe candidate read endpoints. No mutating
  call reaches Pushd during the spike; POST-shaped hypotheses are recorded in the evidence
  file and gated for later rather than fired blind at the live account.
- **D-02:** **Escalation ladder — capture only if blind fails.** Blind probing (from what
  the client already knows: payload shapes, educated endpoint guesses) runs first; a
  mitmproxy/Charles traffic capture of the Aura mobile app's Google-link flow happens only
  if the blind verdict is inconclusive. The user runs the capture and hands over a
  sanitized log — the same method that originally reversed this API.
- **D-03:** The SPK-01 verdict bar is **drivable end-to-end**: the spike must show this
  client can authenticate and successfully call the discovered mechanism itself — not
  merely find evidence that it exists. Reconciliation with D-01's GET-only rule: if full
  driving requires a POST (e.g. a linking/config call), that single call is surfaced as an
  explicit mid-spike gate for the user's approval before it runs — an agent never fires it
  unilaterally (Phase 11's consent precedent).

### Shared-album test data (SPK-02)

- **D-04:** The probe targets the **user's real target albums** (SPK-02 requires their
  actual item counts recorded), with this refinement: the real albums are expected to be
  100–500 photos, so **if every real album falls short of measuring the suspected
  ~500-item lazy-load ceiling, one synthetic 600+ photo album is built** to measure the
  ceiling directly — better to settle it here than discover it in Phase 14.
- **D-05:** **Share links are redacted in committed docs.** The repo is public on GitHub
  and `.planning/` is committed (`commit_docs: true`); a share link is a capability URL —
  anyone holding it sees the album. Committed evidence records the truncated link shape
  (e.g. `AF1Qip…VAw`) plus item counts; **full links live in an untracked local file** so
  the probe stays reproducible. — **Reversibility:** one-way — a committed capability URL
  cannot be un-published; once a full link enters git history, deleting the file does not
  remove the album's exposure.
- **D-06:** **The user creates share links via the Google Photos UI/app at probe time.**
  There is no programmatic way to create a share link for an arbitrary album without
  Google auth — which is the very thing being spiked around — so this is a one-time human
  step, the same kind as the OAuth consent Phase 13 will need.

### Browser bootstrap (SPK-03)

- **D-07:** The cookie bootstrap uses a **dedicated Chrome profile**, not the daily-driver
  profile. The profile contains only a lightweight Google session for this project and
  doubles as the permanent local credential store (refreshed by re-running the bootstrap
  when cookies expire) — this is the posture carried into Phase 13 if SPK-05 selects this
  path.
- **D-08:** **Harvested cookies are untracked + structurally denylisted:** stored 0600 in
  an untracked local file, with a config-keyed denylist so that `sync`/`--apply` code
  paths can never load them. The denylist makes the write-path boundary structural rather
  than a convention future code must remember.
- **D-09:** The browser-automation probe runs against a **throwaway/secondary album**,
  not the real target albums — the mechanism is what's being proven, not these albums,
  and real content gets zero exposure to the automation.
- **D-10:** **Consent for the harvest was granted explicitly by the user in this
  discussion.** Verbatim answer to the consent gate ("do you approve harvesting session
  cookies from your Chrome profile for this probe?"): *"Yes, proceed (Recommended)"*. This
  consent is recorded here as data; it covers the read-only harvest + probe described
  above, not unlimited future actions — significant live actions still get their own gate
  (Phase 11 precedent).

### Claude's Discretion

Areas the user did not select for discussion; the agent decides during planning/execution
within the constraints above:

- **Evidence file layout** — probe evidence records follow the `11-LIVE-FINDINGS.md`
  precedent (raw HTTP evidence, mechanism tables, re-read confirmation rather than
  status-code-only claims).
- **SPK-04 byte-fidelity scope** — test the leading candidate mechanism first (per the
  SPK-01 probe's direction); extend to the other surviving mechanisms only if cheap. The
  comparison yardstick is fixed regardless: a photo already on the frame, downloaded back
  through the candidate mechanism, base64-MD5 compared directly against the frame's
  reported `md5_hash`. The account's Original-quality vs Storage-Saver setting is checked
  once — it is account-level, mechanism-independent.
- **SPK-05 decision-authority flow** — the agent compiles the decision record with a
  recommendation grounded in probe evidence; the user makes the final selection call.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone gating research (the reason this phase exists)
- `.planning/research/ALBUM-ACCESS.md` — the mechanism ranking, the VERIFIED live
  shared-link fetch (§1: `AF_initDataCallback` structure, `=d` full-res convention, no
  EU consent wall from a Paris IP), the Pushd/Ambient analysis (§5 — the single
  highest-value unknown), and the dead-ends list (§ end — do not re-litigate)
- `.planning/research/BROWSER-AUTOMATION.md` — the cookie-bootstrap + `batchexecute`
  approach SPK-03 probes, including the browser-dependency isolation rule
- `.planning/research/PITFALLS.md` — SPK-02 (pagination ceiling) and SPK-04 (byte
  fidelity, incl. the Original-vs-Storage-Saver account-setting angle) risk assignments
- `.planning/research/STACK.md` — the March-2025 scope-cull facts treated as closed

### Requirements & success criteria
- `.planning/REQUIREMENTS.md` — SPK-01..05 verbatim; Out of Scope table (the closed dead
  ends this phase must not re-open)
- `.planning/ROADMAP.md` (Phase 12 section) — the five success criteria this phase is
  verified against; Notes on SPK-04 being load-bearing and the three-times-vindicated
  live-spike precedent

### Prior live-evidence precedent
- `.planning/phases/11-write-path-reliability-format-support/11-LIVE-FINDINGS.md` — the
  evidence-recording format precedent: full command, raw HTTP evidence, mechanism table,
  re-read confirmation

### Project conventions
- `.planning/PROJECT.md` — Key Decisions table ("Trust live probes over model
  assumptions" — this phase is that decision's fourth instance), Constraints (secrets out
  of version control; unofficial-API posture)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `auraframes/client.py` (`Client`) — the authenticated httpx (HTTP/2) session with
  token headers; SPK-01's blind GET probes run through it exactly like any other verb
- `auraframes/api/frameApi.py` (`FrameApi.get_assets`) — the source of the frame's
  per-asset `md5_hash`, SPK-04's comparison target
- `auraframes/aws/s3client.py` (`S3Client.get_md5`) — the local base64-MD5 convention,
  proven byte-identical to the frame's reported hash (Phase 7 D-09); the exact function
  SPK-04's comparison reuses
- `auraframes/aura.py` (`Aura` facade + `login()`) — credential resolution pattern for
  any probe script that needs an authenticated Pushd session

### Established Patterns
- **Raw httpx, no heavy SDK** — any Google-side probing follows the same convention;
  no Google client library gets adopted for a spike
- **DI transport seam** (`Client(transport=...)`) — offline-testability is a standing
  convention (TEST-02 later makes it explicit); probe code that survives into Phase 13
  must be structured so its HTTP surface is injectable
- **Fail-loud** — silent `pass` on API `error` fields is a known anti-pattern; probe
  scripts surface errors rather than swallow them
- **Cheap live spikes redirect designs before they cost rewrites** — Phase 6
  (`md5_hash` nullability), Phase 7 (hash byte format), Phase 10 (visibility flag) all
  did; Phase 12 is the deliberate, whole-phase instance
- **Browser dependency isolation** (ROADMAP Phase 13 note) — if the browser path wins,
  it must sit behind a leaf module that never appears in a test-suite import graph

### Integration Points
- `auraframes/api/frameApi.py` + `auraframes/client.py` — where SPK-01 probe calls attach
- The eventual Google-side source module (Phase 13/14) — created only after SPK-05's
  decision record exists; SPK-05 is the written gate for every GP requirement
- Note: the `.planning/codebase/*.md` maps date to 2026-06-29 (pre-CLI, pre-v2.0) and are
  stale on stack details — trust the source over the maps for anything load-bearing

</code_context>

<specifics>
## Specific Ideas

- **Privacy tiers established during discussion:** harvested cookies = use for the probe,
  never committed (untracked + 0600 + denylist); share links = capability URLs, redacted
  in committed docs with full links untracked locally; item counts and link *shapes* =
  fine to commit.
- The user's real albums are expected at 100–500 photos — close enough to the suspected
  ceiling that the real-album probe is informative, with the synthetic 600+ album as the
  ceiling measurement fallback.
- SPK-01's verdict must be earned by *this client driving the mechanism*, not by
  documentation or captured traffic alone — "we found the endpoint" is a start, not a
  verdict.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. (The synthetic 600+ photo album is within
SPK-02's scope as the ceiling-measurement fallback, not a deferred idea.)

</deferred>

---

*Phase: 12-Album-Access Mechanism Spike*
*Context gathered: 2026-09-26*
