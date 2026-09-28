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

_(pending — gate approved 2026-09-28; bootstrap in progress, operator login)_

## Plan 16-03 — Byte fidelity

_(pending — after 16-01/16-02 evidence)_
