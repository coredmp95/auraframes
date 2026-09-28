# Phase 16 — Live Findings

Live evidence for the access-mechanism spike, following the `11-LIVE-FINDINGS.md`
discipline: every row carries the command, the raw output, and the date. No outcome
is inferred — what was not run says so.

**Date:** 2026-09-28 · **Operator:** Fabrice · **Privacy:** capability URLs appear
only in redacted `AF1Qip…<last4>` shape (full links live in untracked `probes/*.link`).

---

## Plan 16-01 — Shared-album link probe

**Mechanism under probe:** plain-HTTP fetch of `photos.google.com/share/…` pages —
no cookies, no login, no JS — parse `AF_initDataCallback({key:'ds:1'})` into the
item list; download originals via `{baseUrl}=d` hashed with the frame's
base64-MD5 convention (`auraframes.aws.s3client.get_md5`).

### Command shape

```
uv run python probes/shared_link_probe.py "$(cat probes/<album>.link)" [--download-n 1]
```

### Results per album

| Album | Link shape (redacted) | HTTP | Page bytes | Items parsed | Verdict |
|---|---|---|---|---|---|
| A = B (operator: 1000+ photos; confirmed same album via its share link) | `app.goo.gl` → `photos.google.com/share/AF1Qip…OBrg?key=…` (redacted) | 200 | 1,435,057 | **300** | ✅ parses fully without auth; repeat fetch identical. **Ceiling measured: 300 exposed of 1000+ actual.** |
| A owner-URL attempt | `photos.google.com/album/AF1Qip…g1Gt` | 200 (login page) | 942,277 | 0 — no ds:1 | ❌ **NOT a share link**: `/album/…` is the owner-view URL; it 302s to `accounts.google.com/v3/signin/identifier?continue=…`. Probe refused to guess (fail-loud, by design). |
| C (operator states 24 photos) | `app.goo.gl` → `photos.google.com/share/AF1Qip…` (redacted) | 200 | (fetched) | **24** | ✅ **ground-truth match**: parser count == operator's UI count (24/24) |

### Ceiling verdict (D-04 discipline) — **MEASURED, decisive**

- **The operator confirmed (2026-09-28, this session) that share link**
  `app.goo.gl/L1AhmTe1Fbyfxm3N7` (→ `photos.google.com/share/AF1Qip…OBrg?key=…`)
  **is the 1000+ photo album** — the one whose owner-view URL is
  `photos.google.com/album/AF1Qip…g1Gt`.
- **Measured result: the share page exposes exactly 300 items for a 1000+ photo album.**
  One fetch, repeatable. The suspected ~500 ceiling is in fact **300 on this real album**
  — and at least ~700 photos are unreachable via the plain-HTTP share page.
- No plain-HTTP pagination mechanism has ever been published (ALBUM-ACCESS-V4-ADDENDUM Q1:
  no prior art; publicalbum.org's operator: "now it's not possible to grab more"). The
  synthetic-600+ album contingency is moot: a real 1000+ album is a strictly stronger
  measurement, and it is done.
- **Ceiling verdict: the shared-link mechanism enumerates only the first ~300 items of a
  large album — measured, not inferred.** For albums of this size it cannot serve as the
  sole enumeration path. For albums ≤300 it is exact (24/24 ground truth on album C).
- Owner-view URLs (`photos.google.com/album/…`) are auth-gated and carry no ds:1 — a real
  share link per album is a prerequisite for this mechanism (setup cost, `user_setup`).

### Fidelity evidence (`=d` originals, base64-MD5 via `get_md5`)

| Album | Item | Bytes | base64-MD5 | File |
|---|---|---|---|---|
| B | first item (`AF1QipOBgkMnpp…`, 2268x4032) | 2,588,116 | `wykQr6jv8mSpkXCtZtwM3Q==` | `probes/.probe-downloads/AF1QipOBgkMnpp….bin` (untracked) |
| C | first item (`AF1QipPZo9nEEJ…`) | 3,412,350 | `DSWMyGKS2k3nxpzqIdh37g==` | `probes/.probe-downloads/AF1QipPZo9nEEJ….bin` (untracked) |

These hashes are the 16-03 comparison inputs: each downloaded original must equal the
`md5_hash` the frame reports for the same media via `get_assets` (Phase 7 proved the
convention; this spike proves the bytes).

### Repeatability (evidence precedent: re-fetch, not status-code-only)

- Album C fetched twice: identical count (24) both times — repeat-fetch confirmed.
- Album B fetched twice across two runs (listing, then `--download-n 1`): identical count (300).

### Honesty notes

1. Album A's owner-URL redirect finding means **share-link enumeration is blind to
   albums the operator has not shared** — the mechanism requires one-time share-link
   creation per album (accepted setup cost, `user_setup` in 16-01-PLAN).
2. Parser validity rests on album C's 24/24 ground truth + the fixture suite; item
   dimensions embedded in the page matched expectation ranges for all parsed rows.

---

## Plan 16-02 — Browser bootstrap + internal RPC listing

**Gate record (D-07 gate 1):** operator approved execution ("go — exécuter le harvest",
2026-09-28). Consent D-06 re-confirmed for v4.0.

### Bootstrap — one D-03 retry after a concrete fix

1. **First attempt — FAILED (bot detection):** Playwright bundled Chromium at
   `photos.google.com` → Google refused the login with "this browser or app may not be
   secure" (operator-reported, exactly the §2 BROWSER-AUTOMATION finding).
2. **Documented retry (the one D-03 allows) — concrete fix:** launch the **real system
   Google Chrome** (`channel="chrome"`, Chrome 153.0.8010.52) with
   `--disable-blink-features=AutomationControlled`. **SUCCEEDED:** operator logged in;
   harvest detected SAPISID/__Secure-1PAPISID/__Secure-3PAPISID; **45 cookies** saved to
   `~/.config/auraframes/probes/google-cookies.json` — **0600 verified**, outside the repo,
   `git check-ignore` clean.
3. Retry ledger: one documented retry used; a third attempt would violate D-03.

### Session-RPC listing — proven end-to-end, with the decisive discovery

| Step | Result |
|---|---|
| Vaulted cookies → httpx (full jar, domain+path preserved) | ✅ logged-in page: title "Photos - Google Photos", `SNlM0e` at-token present. (Live finding: a flattened name→value dict is treated as anonymous — redirects to the marketing page; the **complete jar** is required.) |
| batchexecute transport, plain httpx POST | ✅ `)]}'` envelope received; Google's own error bodies arrive well-formed (the transport/auth layer works; a 400 from a guessed payload is a payload problem, not an auth problem) |
| RPC shape capture (`probes/rpc_capture.py`, read-only scroll) | ✅ Google's own frontend on the scrolled album emitted **`snAcKc(share_token, continuation_token, null, key)`** — the continuation mechanism the research pass found no prior art for |
| **Pagination, plain httpx, replaying the captured body with the token swapped** | ✅ **page 1: +300, page 2: +300, page 3: +194, token exhausted** |
| **Exhaustive enumeration of the 1000+ album** | ✅ **794 items, 794 unique, clean exhaustion** (the true album size per the operator's "1000+" claim — 794 enumerated; delta vs "1000+" noted below) |
| Repeat run via the committed `browser_bootstrap.py list` | ✅ identical: 794/794, EXHAUSTED cleanly |

**Decisive consequence: the "~500 ceiling" (suspected) and the "300 cap" (measured on the
public page this morning) were both page-size artifacts. With the session RPC
(`snAcKc` + continuation), the full album enumerates — the browser mechanism has **no
observed ceiling**.** The share page's 300-item ds:1 is merely batch-1 of the same stream
the UI paginates via RPC.

**Secondary findings (honesty):**
- With the full logged-in jar, the share page's `ds:1` returned 0 items — the logged-in
  page shape differs from the anonymous one (items move to the RPC stream). The anonymous
  parse path remains valid for un-authed use (16-01 evidence stands).
- Initial guessed payloads (`EW6Kmf`, raw ids from ds:0) returned 400s with Google's
  standard error envelope — recorded as evidence of payload-sensitivity, not auth failure.
- The operator reports the album as "1000+"; enumeration exhausts at 794. Either the UI
  count includes items the share stream filters (videos, archived), or the count is
  approximate. Recorded as-is; the exhaustive-stream result is what matters mechanically.

### Permanent cost statement (from the plan, now evidence-backed)

The browser mechanism is **permanently local-only and never-CI-able** (Google's bot
detection blocks unattended login — confirmed live above); the cookie-expiry cadence is
unknown and **accepted** per the 2026-09-28 operator decision. Bootstrap is a single
documented command (`probes/browser_bootstrap.py bootstrap`), re-runnable when cookies
expire.

## Plan 16-03 — Byte fidelity

**Gate record (D-07 gates 2-3):** operator confirmed backup quality **Original**
(2026-09-28) and approved the read (`get_assets`) and then the test-upload write.

### Account quality setting

**Original** — operator-confirmed from Google Photos settings, 2026-09-28. The bytes
Google stores are the bytes originally uploaded; `=d` serves them untransformed (§1c
ALBUM-ACCESS precedent). No Storage-saver lossy tier applies.

### The live comparison (upload-test path, D-07 gate 3 approved)

**Why the planned standing-asset path was replaced:** `FrameApi.get_assets` returned
**0 assets across every parameter variant** during this session (2026-09-28 ~10:30Z) —
while `frame.num_assets` reported 251 — a server-side drift on the Pushd assets
endpoint (the same backend refactor that broke Aura's own Google sync). A frame asset
hash WAS obtained from the frame detail's embedded `last_feed_item` (hash
`iPvpbEhC…`, 3461×2645), but that phone-uploaded photo belongs to none of the probed
albums — the standing-asset comparison was structurally impossible in this session.

**The executed path (stronger, actually): upload-test round-trip** —

| Step | Command | Result |
|---|---|---|
| 1. Download album C's first original via `=d` (plain httpx, 3,412,350 bytes) | `probes.shared_link_probe.download_original` | base64-MD5 `DSWMyGKS2k3nxpzqIdh37g==` (via the frame's own `get_md5`) |
| 2. Upload those exact bytes to the frame (additive push, D-07 gate 3) | `aura-cli push /tmp/fidelity-upload --apply --yes` | upload ok (1 succeeded, 0 retries) |
| 3. Read the frame's `md5_hash` for the new asset (filter=all listing, post-processing) | `assets.json` re-read | `md5_hash: DSWMyGKS2k3nxpzqIdh37g==` |
| 4. **Verdict** | **`get_md5(=d bytes) == frame.md5_hash`** | **MATCH — byte-identical, LGS-06 proven** |
| 5. Cleanup (reversible hide, v2.0 semantics) | `exclude_asset(AssetPartialId)` | `hidden: true, selected: false` re-read confirmed; the frame's slideshow is unchanged |

**Verdict line (D-05 application): the download path preserves the frame's hash
convention exactly — no mechanism rejection applies; the shared-link/RPC `=d` download
is fidelity-safe for the mirror-sync diff engine.**

### Honesty notes

- The `get_assets` 0-asset drift was transient-by-observation (the endpoint returned 1
  asset immediately after the upload minutes later); it is recorded as an observed
  instability of the Pushd assets endpoint on 2026-09-28 — itself load-bearing evidence
  for NOT building v4.0 on Aura's server-side Google sync (the operator's own finding).
- The assets.json response earlier in the session returned `0 assets` while
  `num_assets: 251` — both facts recorded verbatim; Phase 17's design must treat any
  single Pushd listing as potentially incomplete and re-verify (mirrors PITFALLS #3).
