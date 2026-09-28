# Targeted Research — v4.0 Open Questions (2026-09-28)

**Scope:** The three questions left open by v3.0's research that this milestone's
mechanism decision still depends on. This file is **additive** to
`ALBUM-ACCESS.md` (whose §1 shared-link findings and dead-ends list remain valid) —
it does not re-litigate anything already settled. The Pushd/Ambient section (§5) of
ALBUM-ACCESS.md is **obsolete**: Aura's server-side sync does not work in practice
(user-observed, 2026-09-28) and is not a reference for anything in v4.0.

**Researched:** 2026-09-28, targeted web search (marked per claim).

---

## Q1: Shared-link pagination — is the ~500-item ceiling still the state of the art?

**VERIFIED, convergent:** no plain-HTTP pagination mechanism for shared-album pages has
been published. The search pass (2026-09-28) surfaced:

- **Stack Overflow (59675348, "Fetching complete Google Photos album webpage"):** the
  known problem — the album page returns only the initial batch; fetching the complete
  item list requires the undocumented scroll-triggered RPC. No answer replicates it
  without a browser.
- **Google support thread (232249048, "shared albums not showing more than 500 photos"):**
  user reports of shared albums capping around ~500 items in the web UI itself —
  consistent with the publicalbum.org admission already recorded in ALBUM-ACCESS §1e.
- **No tool has appeared since:** the scraper landscape in ALBUM-ACCESS §1f is unchanged
  (`austenstone/google-photos-scraper` still surfaces as the reference tool; still no
  pagination handling anywhere).

**Marking `metadatafixer.com`'s "Download all" note:** the manual 500-selection cap it
describes is a UI batch limit, not the scraper ceiling — the relevant, independent
confirmation is that the ~500 practical ceiling keeps being reported from different
surfaces.

**Consequence for v4.0 (INFERRED, high confidence):** the shared-link mechanism without
a browser is expected to cap out in the low hundreds of items per fetch. The milestone's
own live spike (probing the user's real 100–500-photo albums against the true count,
plus a 600+ synthetic album if needed) remains the decisive measurement — nothing found
here changes that plan, it only reinforces that no prior art exists to copy.

**One genuinely new lead (VERIFIED, found 2026-09-28):** `xob0t/Google-Photos-Toolkit`
— an actively maintained open-source userscript that operates Google Photos' **internal
`batchexecute` RPC surface from inside the logged-in web UI**, including on shared
albums. It is the strongest public evidence that the internal-RPC mechanism SPK-03 was
going to probe actually works at scale, and a reference implementation to learn the RPC
shapes from (not a dependency — its transport is the browser page itself). It upgrades
the browser-automation path's risk profile from "undocumented, nobody has done it" to
"undocumented, but publicly reverse-engineered and working".

## Q2: Cookie/session longevity for the browser-automation path

**NOT SETTLED by this pass** — no authoritative source on Google Photos web-session
cookie lifetime was found in this targeted search. What is known:

- Sessions are long-lived in practice (weeks+ of idle browser sessions persist), but
  Google can and does invalidate sessions on risk signals (new device, IP change,
  suspicious automation patterns).
- The user has already accepted **periodic re-authentication** as non-blocking, which
  converts this unknown from a design risk into an operational cost: the mechanism
  must make re-running the bootstrap a single documented command (this is now a
  requirement, LGS-02), and `aura-cli status` must surface session state (LGS-03).
- `xob0t/Google-Photos-Toolkit`'s continued operation (inside a live browser session)
  confirms session-bound RPC calls work; it does not bound their lifetime.

**Consequence for v4.0:** cookie-expiry handling is a first-class requirement, not an
implementation detail. The planner should schedule a session-expiry probe early in the
mechanism spike so the re-auth cadence is known before Phase 17 builds on it.

## Q3: `=d` byte fidelity — anything new?

**No change.** This pass found nothing that alters ALBUM-ACCESS §1c's live-verified
finding (`{baseUrl}=d` returns the original file bytes with EXIF, dimensions matching
the inline metadata) or PITFALLS.md's framing: fidelity is primarily an **account
setting** question (Original vs Storage Saver), settled once in the spike, not per
mechanism. The v3.0 requirement text carries over (LGS-06): a standing asset's
downloaded bytes must base64-MD5-match the frame's reported `md5_hash`.

---

## Bottom line for the mechanism spike

| Question | Answer | Effect on v4.0 |
|---|---|---|
| Prior art for shared-link pagination? | None (confirmed again 2026-09-28) | Spike measures the ceiling live; shared-link alone likely caps <~500 |
| Browser-automation credibility? | Strengthened — `xob0t/Google-Photos-Toolkit` proves internal batchexecute works on shared albums from a session | SPK-03-style probe is lower-risk; RPC shapes have a public reference |
| Cookie re-auth cost? | Unknown lifetime, but user accepts periodic re-auth; tooling makes bootstrap re-runnable | LGS-02/LGS-03 requirements; spike measures cadence |
| Byte fidelity? | Unchanged — account-setting question + `=d` original bytes | LGS-06 carries over verbatim |

---
*Targeted research: 2026-09-28 — additive to ALBUM-ACCESS.md; §5 (Pushd/Ambient) obsolete.*
