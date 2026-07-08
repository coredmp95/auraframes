---
status: resolved
trigger: "Live sync --apply against 'Cadre de Fabrice' gets HTTP 401 Unauthorized on every select_asset call (all 120/120 uploads failed), even though the same process's login() and get_assets() (dry-run diff) succeeded moments earlier in the same session. This is the first write command run today — not a long-running batch, so 'token expires over time' doesn't fully explain it. User suspects this could be account-level blacklisting/flagging of write endpoints rather than simple rate-limiting, possibly triggered by yesterday's Phase 8 live-verification burst (uploads, ~72 remove_asset deletes, and a direct delete_asset probe against a disposable asset, all within a short window against this same frame/account)."
created: "2026-07-08T06:00:00Z"
updated: "2026-07-08T08:40:00Z"
---

## Symptoms

**Expected behavior:** `sync ./data/ --frame "Cadre de Fabrice" --apply` uploads new local files successfully via `select_asset` → S3 → `batch_update`, as it did (at least partially — 47/72 succeeded before a separate mid-batch 401 yesterday) during Phase 8's live verification.

**Actual behavior:** Every one of 120 `select_asset` POST calls in this run returned `401 Unauthorized` from the very first item. `Uploads: 0 succeeded, 120 failed`. The failure is immediate — item #1 fails identically to item #120, no partial-success pattern like yesterday's run.

**Error messages:**
```
Client error '401 Unauthorized' for url 'https://api.pushd.com/v5/frames/c063b384-38fa-4324-aaf8-319d17a5867a/select_asset.json'
```
(repeated for all 120 items, each individually caught and reported per WRITE-05/D-08 — the fail-loud/continue-past-failure design itself is working correctly)

**Timeline:** First write command of today (2026-07-08). Follows yesterday's (2026-07-07/08) Phase 8 live-verification session against the same frame/account: a live upload, ~72 total `remove_asset` deletes across two runs (25 of which hit a mid-batch 401 on the first attempt, succeeded on retry), and a standalone `delete_asset` probe against a disposable asset. All of that write activity happened within roughly an hour, then this new run — the first of a new day — immediately fails on every write call.

**Reproduction:**
1. `aura-cli sync ./data/ --frame "Cadre de Fabrice" --apply`
2. Dry-run diff prints correctly (120 to upload, 0 to delete, 2 unchanged) — this requires a successful `login()` + `get_assets()` in the same process.
3. Confirm `y` at the prompt.
4. Every subsequent `select_asset` call in `execute_plan()`'s upload loop fails with 401, immediately, no successes.
5. Immediately after, in a **separate** process, `aura-cli status` succeeds (login + `get_frames()`, a GET call) — so a fresh login/session works fine for reads.

## Key open questions (from user)

- Is this transient (retry later, e.g. a cooldown) or a persistent state on the account/frame?
- Does this API apply different/stricter auth to POST (write) endpoints vs GET (read) endpoints, independent of any rate-limiting?
- Is there a way to distinguish rate-limiting vs. account/endpoint-level blacklisting vs. a plain bug in our own token-handling from the response (status code alone is 401 — check for any distinguishing headers/body in the raw response)?
- Could yesterday's burst of live destructive-endpoint traffic (first time in this codebase's ~3 year history that select_asset/remove_asset/delete_asset were exercised live) have triggered anti-abuse flagging specifically on write endpoints for this account?

## Current Focus

hypothesis: CONFIRMED (a) — Server-side anti-abuse throttling/flagging on the Aura/Pushd account, triggered by an abnormally high volume of write/destructive API calls (yesterday's ~72 remove_asset + delete_asset probe + uploads, then today's 120 rapid-fire select_asset burst). It first manifested as 401 on all write (POST) endpoints while reads (GET) still worked, and has since ESCALATED to reject even login with a custom HTTP 475 ("The email or password was incorrect.") despite the credentials being valid. Not a client code defect: the write-path code is byte-identical to yesterday's successful single-file writes. CHECKPOINT RESOLVED: human confirms the official Aura phone app is working fine against this account/frame right now — consistent with (a), since human-paced app traffic never looks like a burst and never trips the anti-abuse layer; rules out a persistent full-account ban, supports a burst-triggered throttle instead.
test: (done, read-only) Live login diagnostic to inspect token validity + capture the raw failing-response signature. Result: login now returns HTTP 475 with body {"error":true,"message":"The email or password was incorrect."} using the SAME .env credentials that produced a 200 login at 07:49 today.
expecting: (met) A server-side signal that distinguishes rate-limit/flagging from a client bug. The custom 475 code + credentials-valid-13-min-ago proves a server-side account state change.
next_action: DONE. Preventive fix part (2) applied and offline-verified (pytest -m "not live" → 92 passed). Client now classifies 429/475 into RateLimitError; execute_plan paces every write and aborts the batch on a rate-limit instead of emitting N per-item 401s; CLI prints one clear back-off message. Live end-to-end write verification remains DEFERRED (needs a recovered account + explicit human approval for a minimal live burst). See Resolution.verification.

## Reasoning Checkpoint (2026-07-08, applying preventive fix)

reasoning_checkpoint:
  hypothesis: "The Aura/Pushd anti-abuse layer trips on burst write volume; unpaced writes (each upload = 2x select_asset + 1x batch_update fired ~300ms apart, x120) look like abuse. Once tripped it returns 429/custom-475, but the client currently keeps hammering per-item and emits N confusing 401s instead of backing off. CONFIRMED upstream in this session."
  confirming_evidence:
    - "Yesterday's low-volume single-file writes returned 200 with byte-identical code; today's 120-item burst returned 401 on every call (Evidence log-analysis entry)."
    - "Login returned custom HTTP 475 with valid creds ~13 min after a 200 login — a server-side account state change, not a client bug (Evidence LIVE read-only diagnostic)."
    - "Official phone app (human-paced traffic) works fine right now against the same account (human checkpoint response) — pacing is the differentiator."
  falsification_test: "If, after pacing every write network call and aborting cleanly on 429/475, a paced low-volume run still 401s on the first item while the phone app works, then burst-volume is NOT the trigger and the hypothesis is wrong. (Live confirmation DEFERRED per scope.)"
  fix_rationale: "Throttling paces the write burst so it never trips anti-abuse (addresses the ROOT cause — abnormal request rate — not the 401 symptom). Rate-limit classification + batch abort converts an already-tripped state into one clear back-off message instead of N misleading per-item 401s, and respects Retry-After so callers wait the right amount. This is the prevention the confirmed root cause calls for."
  blind_spots: "Cannot live-verify that (a) the chosen throttle interval is actually below the anti-abuse threshold, nor (b) that a single select_asset per upload suffices — both need a recovered account + live burst, explicitly out of scope. Offline tests prove pacing happens on every write and that 429/475 abort cleanly; they cannot prove the server's exact threshold."

## Double select_asset reconsideration (fix part 2, item 2)

Kept the double `select_asset`-per-upload rather than collapsing to one. Rationale: it is a deliberate, RESEARCH.md-Pitfall-4-backed reproduction of the original `Aura.upload_image()` handshake, and whether one call suffices can only be confirmed against the live API (out of scope this session — no forced live burst-testing). Removing it blind risks breaking uploads for an unverified ~2x volume win. Instead, throttling now paces BOTH select_asset calls plus batch_update, so the per-upload write burst is eliminated regardless of call count — the volume concern is addressed without the unverifiable behavioural change. Revisit collapsing to one call when a recovered account allows a live A/B.

## Human Response (2026-07-08, continuing session)

DATA_START
"everithing is working fine from the app on my phone. I think you have to add throteling"
DATA_END

Interpreted: (1) the official Aura mobile app currently works fine against this account/frame — informational evidence the account is not generally/persistently locked, only the burst-triggered anti-abuse response seen earlier; (2) explicit approval to implement the preventive throttling fix proposed in Resolution.fix part (2). Goal shifts from find_root_cause_only to find_and_fix for this continuation.

## Evidence

- timestamp: 2026-07-08 (investigation)
  checked: Whether the --apply write path uses the same authenticated client/session as the reads (cli.run_sync + sync.execute_plan).
  found: A single `aura` instance is created once in run_sync, `aura.login()` runs once, and the SAME instance is passed to execute_plan. The x-token-auth/x-user-id are default headers on the shared http2_client, applied identically to GET and POST. No separate/unauthenticated client for writes.
  implication: Rules out "writes use a client that never logged in." The token is present on the POST calls; the reads-work/writes-fail split is NOT a missing-auth-on-execute bug.

- timestamp: 2026-07-08 (investigation)
  checked: git history of client.py / frameApi.py / aura.py / sync.py since yesterday's successful live runs.
  found: No code changes today. Latest commits are all Phase 8 work from before yesterday's successful writes. The write path is byte-identical between yesterday's 200s and today's 401s.
  implication: Rules out a code regression. The behavior change is server-side, not client-side.

- timestamp: 2026-07-08 (log analysis)
  checked: Actual select_asset outcomes in today's failing run log (file_2026-07-08_07-49-18_836147.log) vs yesterday's successful runs (19-38-43, 22-00-56), by pairing each select_asset POST with its following Response line.
  found: Yesterday each successful run made exactly 2 select_asset calls (a single-file upload's double-call) and BOTH returned 200. Today's run made 120 select_asset calls in a rapid burst (~300ms apart) and ZERO returned 200 — every one raised (401). Login (200), GET frames (200), GET assets (200) all succeeded in today's run before the writes.
  implication: The exact same code+auth returns 200 for low-volume writes (yesterday) and 401 for a high-volume burst (today). Reads succeed in the same session. Strong signature of server-side write-endpoint anti-abuse throttling, not a client defect.

- timestamp: 2026-07-08 (log analysis)
  checked: The rotating _pushd_web_session cookie and the manual _set_cookies() re-setting it on every response (redundant with httpx's own cookie jar).
  found: Server rotates _pushd_web_session on every response; _set_cookies re-sets it via cookies.set(name, value) (empty domain). Potential cookie duplication, but this affects GET and POST equally and reads work fine.
  implication: Not the cause of the read/write split (it would break reads too). Noted as latent cleanup, not root cause.

- timestamp: 2026-07-08 (LIVE read-only diagnostic — login only, no writes)
  checked: Ran a read-only login to inspect auth_token validity and capture the raw failing-response signature (the debug file's original next_action). Made 2 login attempts total, then stopped.
  found: Login now returns **HTTP 475** (custom Pushd status, non-standard) with headers {content-type: json, x-powered-by: Phusion Passenger, server: Apache, status: 475, x-request-id present, NO Retry-After header} and body **{"error":true,"message":"The email or password was incorrect."}** — using the SAME .env credentials (same load_dotenv path) that produced a successful 200 login at 07:49 today and successful logins yesterday.
  implication: SMOKING GUN. Credentials valid ~13 minutes earlier are now rejected with a custom code. This is a server-side account state change (escalating anti-abuse response), NOT a wrong-password error and NOT a code bug. The absence of a Retry-After header means the cooldown window is unknown. The original write-401 was the first stage; login-475 is the escalation.

## Eliminated

- hypothesis: Writes fail because the --apply path uses a client that wasn't logged in (missing x-token-auth on POST).
  evidence: run_sync/execute_plan share one authenticated aura instance; x-token-auth is a default header applied to GET and POST alike.
  timestamp: 2026-07-08

- hypothesis: A code regression in the write path broke select_asset.
  evidence: git shows no changes to client.py/frameApi.py/aura.py/sync.py today; identical code returned 200 for single-file writes yesterday.
  timestamp: 2026-07-08

- hypothesis: Client sends a null/stale x-token-auth so writes 401 while reads use the cookie.
  evidence: Could not be confirmed via logs (redaction masks value), but the live diagnostic showed the failure is now at LOGIN (475) with valid creds — the account state changed server-side rather than the header being malformed. Superseded by the confirmed anti-abuse hypothesis.
  timestamp: 2026-07-08

- hypothesis: Cookie duplication from manual _set_cookies breaks write auth.
  evidence: Would break reads too; reads succeed. Latent cleanup only.
  timestamp: 2026-07-08

## Resolution

root_cause: |
  Server-side anti-abuse throttling / account flagging by the Aura/Pushd API — NOT a client code defect.

  Mechanism: The API normally sees gentle, human-paced mobile-app traffic. Over ~24h this account issued the first-ever live burst of write/destructive calls in the codebase's 3-year history: yesterday's uploads + ~72 remove_asset deletes + a delete_asset probe, then today a 120-file rapid-fire select_asset burst (~300ms apart, plus the double-select_asset-per-upload doubling the write count). The backend's anti-abuse layer responded in stages:
    1. Blocked all write (POST) endpoints for the account with 401 while still serving reads (GET) — the originally reported symptom (120/120 select_asset 401).
    2. Escalated to reject even login with a custom HTTP 475 "The email or password was incorrect." despite valid credentials (observed live during this investigation, ~13 min after a successful 200 login).

  Proof it is server-side state, not code: (a) the write path is byte-identical to yesterday's runs that returned 200 for single-file writes; (b) reads and writes share one authenticated client, so auth is structurally identical for both; (c) the same .env credentials logged in successfully at 07:49 and are now rejected with a non-standard 475 code.

fix: |
  TWO parts.

  (1) OPERATIONAL (required first — code cannot undo a server-side lock):
      - STOP all API calls immediately; every attempt may extend the throttle window.
      - Wait for a cooldown (no Retry-After header was returned, so window is unknown — suggest 30–60+ min), then attempt exactly ONE login.
        * If login recovers → it was transient rate-limiting; resume ONLY with low-volume, paced usage.
        * If login stays 475 → likely a persistent account lock / forced-reset; user must reset the Aura password in the official app and/or contact Aura support.

  (2) PREVENTIVE CODE FIX (proposed, needs approval + a recovered account to verify):
      - Throttle write calls in execute_plan (e.g. a small sleep/token-bucket between select_asset/batch_update/remove_asset) so bursts don't trip anti-abuse.
      - Reconsider the double select_asset-per-upload (halves write volume if one call suffices).
      - Detect and classify rate-limit/lockout responses (HTTP 429 and the custom 475) in Client, surfacing a clear "you are being rate-limited/locked — back off" message and aborting the batch instead of emitting 120 confusing per-item 401s. Respect Retry-After when present.

verification: |
  OFFLINE-VERIFIED (live end-to-end DEFERRED by explicit human decision — mirrors the
  login-475-null-creds session, which was resolved with non-network verification and left the
  live login to the user). Preventive fix part (2) applied and proven via `pytest -m "not live"`
  → 92 passed, 4 live deselected, in 1.22s (fast runtime itself confirms the injected fake sleep
  fires — no real pacing delay leaked into the suite).

  What the offline tests prove:
    1. THROTTLING (fix items 1 & 2): `execute_plan` now paces EVERY write network call via an
       injected `sleep(throttle_seconds)` — 3 sleeps per upload (both select_asset calls +
       batch_update, so the retained double select_asset is paced rather than removed) and 1 per
       delete (remove_asset). `throttle_seconds=0` disables pacing. Default is 0.5s
       (`WRITE_THROTTLE_SECONDS`). Tests: tests/test_write_throttling.py.
    2. RATE-LIMIT CLASSIFICATION (fix item 3): `Client` converts HTTP 429 and the custom 475 into
       a typed `RateLimitError` (carrying status_code, parsed Retry-After — int seconds or raw
       HTTP-date, and the server body message) on ALL request methods, BEFORE the generic
       raise_for_status. Ordinary 4xx (404, a plain 401) still raise httpx.HTTPStatusError — only
       the two throttle codes are reclassified, so genuine auth failures are not masked. A
       non-JSON rate-limit body still raises cleanly. Tests: tests/test_client_rate_limit.py.
    3. BATCH ABORT (fix item 3): a `RateLimitError` from any write propagates out of `execute_plan`
       (NOT recorded as one of N per-item failures) — aborting the whole apply at the first write
       instead of hammering the throttling server with 120 confusing per-item errors. Ordinary
       per-item failures (e.g. nonzero number_failed) are still caught-and-continued (D-08
       preserved). The CLI surfaces one clear back-off message ("Aborted: ... HTTP 429 ... Retry
       after 60s") for the batch and a distinct "Rate limited / locked out at login — ... HTTP 475"
       for the login-lockout escalation. Tests: tests/test_cli_apply.py.

  DEFERRED (out of scope, needs a recovered account + explicit human approval for a minimal live
  burst): (a) confirming the chosen 0.5s interval is actually below the server's anti-abuse
  threshold; (b) confirming a single select_asset per upload suffices (the double call was kept —
  see the reconsideration note above). Neither is offline-observable.

files_changed:
  - auraframes/client.py            # RateLimitError + _parse_retry_after + _raise_if_rate_limited on all 4 request methods (429/475 classification)
  - auraframes/sync.py              # execute_plan write throttling (throttle_seconds/sleep injection) + RateLimitError batch-abort (re-raise, not per-item)
  - auraframes/cli.py               # clear back-off messages: batch "Aborted:" and login "Rate limited / locked out at login"
  - tests/test_client_rate_limit.py # NEW — Client 429/475 classification, Retry-After parsing, non-rate-limit 4xx untouched
  - tests/test_write_throttling.py  # NEW — per-write pacing, throttle_seconds=0 disable, RateLimitError batch abort
  - tests/test_cli_apply.py         # rate-limit CLI messaging (batch abort + login lockout)
  - tests/test_execute_plan.py      # inject no-op sleep into existing calls so the default 0.5s pacing does not slow the suite
