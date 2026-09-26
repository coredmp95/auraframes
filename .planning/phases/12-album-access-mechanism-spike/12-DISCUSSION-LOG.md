# Phase 12: Album-Access Mechanism Spike - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-26
**Phase:** 12-Album-Access Mechanism Spike
**Areas discussed:** Pushd probe method (SPK-01), Shared-album test data (SPK-02), Browser bootstrap (SPK-03)

---

## Pushd probe method (SPK-01)

### Q1: How aggressive should the Pushd/Ambient probe be against the live API?

| Option | Description | Selected |
|--------|-------------|----------|
| Passive + GET-only | Mine existing authenticated GET payloads for album/source fields, then probe candidate read endpoints. No mutating call reaches Pushd during the spike. | ✓ |
| Full active probing | GETs plus live POST attempts at candidate linking endpoints in the same session — undocumented POSTs can mutate frame state. | |
| Passive only | Existing response payloads and research docs only; weakest verdict. | |

**User's choice:** Passive + GET-only (Recommended)
**Notes:** —

### Q2: Should the probe use Aura-app traffic capture as the endpoint-discovery source, or probe the API blind?

| Option | Description | Selected |
|--------|-------------|----------|
| Blind probe only | Work from payload shapes and educated endpoint guesses. No phone setup needed. | |
| I'll capture app traffic | One mitmproxy/Charles session on a phone running the Aura app's Google-link flow reveals the exact endpoints. | |
| Capture if blind fails | Try blind probing first; escalate to traffic capture only if the verdict is inconclusive. | ✓ |

**User's choice:** Capture if blind fails
**Notes:** The user runs any capture themselves and hands over a sanitized log.

### Q3: What evidence is enough to declare SPK-01's verdict?

| Option | Description | Selected |
|--------|-------------|----------|
| Discovery + one read | Endpoint evidence plus one authenticated read confirming the linked state; full driving is Phase 13's job. | |
| Must be drivable end-to-end | The spike must show aura-cli can authenticate and successfully call the linking mechanism itself. | ✓ |
| Discovery only | Traffic capture alone settles it. | |

**User's choice:** Must be drivable end-to-end
**Notes:** Orchestrator reconciliation recorded in CONTEXT.md (D-03): combined with Q1's GET-only rule, any POST-shaped driving step becomes an explicit mid-spike consent gate for the user — never fired unilaterally by an agent (Phase 11 precedent).

### Continuation check

**User's choice:** Next area (Remaining: Shared-album test data, Browser bootstrap)

---

## Shared-album test data (SPK-02)

### Q1: Which albums should the shared-album-link probe target?

| Option | Description | Selected |
|--------|-------------|----------|
| Real albums; extend if small | Probe real target albums; if all fall well under ~500 photos, additionally build one large (600+) test album to measure the suspected lazy-load ceiling. | ✓ |
| Real target albums only | Satisfies SPK-02 as written; the ~500-item ceiling stays unmeasured if albums are small. | |
| Synthetic test album only | Cleanest privacy-wise, but doesn't satisfy SPK-02's "user's own real target albums" requirement. | |

**User's choice:** Real albums; extend if small (Recommended)

### Q2: Roughly how large are the real albums you want to sync?

| Option | Description | Selected |
|--------|-------------|----------|
| Over 500 photos | The ceiling question gets answered by the real albums themselves. | |
| 100–500 photos | Close enough to the suspected ceiling that the real probe is informative. | ✓ |
| Under 100 photos | Real albums won't touch the ceiling. | |

**User's choice:** 100–500 photos
**Notes:** Combined with Q1: the synthetic 600+ album is built only if the real albums fall short of measuring the ceiling.

### Q3: How should share links (capability URLs) be recorded given the repo is public on GitHub and .planning/ is committed?

| Option | Description | Selected |
|--------|-------------|----------|
| Redact in committed docs | Committed evidence records truncated link shape plus item counts; full links live in an untracked local file. | ✓ |
| Full links in gitignored file | Evidence file gitignored with links in full; committed docs reference it by path. | |
| Full links committed | Simplest audit trail, but publishes your albums to anyone who reads the repo. | |

**User's choice:** Redact in committed docs (Recommended)
**Notes:** Rated one-way reversibility in CONTEXT.md (D-05): a committed capability URL cannot be un-published.

### Q4: Who creates the share links?

| Option | Description | Selected |
|--------|-------------|----------|
| I'll create them | User creates share links via the Google Photos UI/app at probe time — a one-time human step. | ✓ |
| Some already exist | Reuse already-shared links; create missing ones yourself. | |

**User's choice:** I'll create them (Recommended)
**Notes:** No programmatic way to create a share link for an arbitrary album without Google auth — the very thing being spiked around.

---

## Browser bootstrap (SPK-03)

### Q1: Where do the bootstrap cookies come from?

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated Chrome profile | A dedicated profile containing only a lightweight Google session for this project; doubles as the permanent local credential store. | ✓ |
| Daily-driver profile | Harvest from the daily-driver Chrome profile's real logged-in session — high-value secret next to personal browsing. | |
| Login inside automation | Skip the harvest; log in inside the automation's own browser, accept periodic re-logins. | |

**User's choice:** Dedicated Chrome profile (Recommended)

### Q2: Where do harvested cookies live, and what stops them reaching the write path?

| Option | Description | Selected |
|--------|-------------|----------|
| Untracked + structural denylist | Cookies 0600 in an untracked local file, config-keyed denylist so sync/--apply paths can never load them — structural, not convention. | ✓ |
| Untracked, convention only | Untracked 0600 file; boundary is a convention future code must respect. | |
| Never persisted | In-memory for the probe only; fine for the spike, unworkable as the Phase 13 mechanism. | |

**User's choice:** Untracked + structural denylist (Recommended)

### Q3: What should the browser-automation probe touch?

| Option | Description | Selected |
|--------|-------------|----------|
| Probe on throwaway | Throwaway/secondary album, not the real targets — zero exposure of real content. | ✓ |
| Real albums, listing only | Directly on real target albums, listing only (read-only either way). | |

**User's choice:** Probe on throwaway (Recommended)

### Q4: Consent gate — do you approve harvesting session cookies from your Chrome profile for this probe?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, proceed | Read-only automation against Google surfaces you already use, once the cookie-handling posture is in place. | ✓ |
| Don't touch my Chrome | Record SPK-03's verdict as not-probed; SPK-05 decides without that evidence. | |

**User's choice:** Yes, proceed (Recommended)
**Notes:** This is the explicit operator consent for a sensitive live action, selected directly by the user (not agent-relayed) — recorded verbatim in CONTEXT.md D-10. Consent covers the read-only harvest + probe described above, not unlimited future actions.

---

## Claude's Discretion

Areas presented but not selected for discussion; agent decides within CONTEXT.md constraints:

- **Evidence file layout** — follows the `11-LIVE-FINDINGS.md` precedent (raw HTTP evidence, mechanism tables, re-read confirmation)
- **SPK-04 byte-fidelity scope** — leading candidate mechanism first; comparison yardstick fixed (frame's `md5_hash` vs base64-MD5 of downloaded bytes); account quality setting checked once
- **SPK-05 decision-authority flow** — agent compiles the record with a recommendation; user makes the final selection call

## Deferred Ideas

None — discussion stayed within phase scope.
