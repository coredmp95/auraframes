# GSD Debug Knowledge Base

Resolved debug sessions. Used by `gsd-debugger` to surface known-pattern hypotheses at the start of new investigations.

---

## inspect-asset-null-fields — Asset model rejects mid-processing placeholder assets from the live API
- **Date:** 2026-07-08
- **Error patterns:** pydantic ValidationError, data_uti, file_name, taken_at, uploaded_at, height, width, upload_priority, good_resolution, field required, input should be a valid string, input should be a valid integer, Asset model, inspect crash, mid-processing, placeholder asset, unprocessed upload
- **Root cause:** The live Aura/Pushd API returns freshly-uploaded assets that are still mid-server-side-processing as placeholder records — source_id/local_identifier/user/selected populated, but processed content metadata (data_uti, file_name, dimensions, dates, upload_priority) null and good_resolution omitted entirely. The Asset pydantic model declared those 8 fields as required, so hydrating such an asset raised 8 ValidationErrors and crashed `aura-cli inspect`.
- **Fix:** Made the 8 affected fields (data_uti, file_name, good_resolution, height, width, upload_priority, taken_at, uploaded_at) Optional[...] = None on the Asset model; guarded the taken_at_dt property to return None instead of crashing on parse_aura_dt(None).
- **Files changed:** auraframes/models/asset.py, tests/fixtures/asset_unprocessed.json, tests/test_asset_unprocessed.py, tests/test_cli_inspect.py
---

## select-asset-401-unauthorized — Aura/Pushd anti-abuse trip on write bursts, escalating to login-475; plain-401 trips evade status-code-based detection
- **Date:** 2026-07-08
- **Error patterns:** 401 Unauthorized, select_asset, remove_asset, HTTP 475, "The email or password was incorrect", RateLimitError, Retry-After, consecutive write failures, account lockout, anti-abuse throttle, execute_plan, write burst, rate limit, 429
- **Root cause:** The Aura/Pushd API's anti-abuse layer trips on abnormal write/destructive request volume (first-ever live burst of select_asset/remove_asset/delete_asset in this codebase's history). It responds in stages: (1) 401 on all write (POST) endpoints while reads (GET) keep working, (2) escalates to reject even login with a non-standard HTTP 475 ("The email or password was incorrect.") despite valid credentials. Critically, the trip does NOT reliably announce itself with a distinguishable status code — a later live regression showed it as a run of plain HTTP 401s (indistinguishable from a genuine isolated per-item auth failure) rather than 429/475.
- **Fix:** Two-layer defense in `execute_plan`/`Client`. (1) Pace every write call (`WRITE_THROTTLE_SECONDS`, default 0.5s, injectable/disable-via-0) so bursts don't trip the layer. (2) Classify HTTP 429 and the custom 475 into a typed `RateLimitError` (parsed Retry-After, server message) that aborts the whole batch immediately with one clear message instead of N per-item failures. (3) BACKSTOP for trips that don't surface as 429/475: a status-code-agnostic consecutive-failure-run counter in `execute_plan` (`MAX_CONSECUTIVE_WRITE_FAILURES`, default 5, injectable/disable-via-0) spanning both the upload and delete loops, incrementing on ANY caught per-item write failure and resetting on any success — reaching the threshold raises a distinct `ConsecutiveWriteFailureError` and aborts, while a single isolated failure (surrounded by successes) never trips it.
- **Key lesson:** Do not rely on HTTP status code alone to detect a rate-limit/lockout condition — the same underlying anti-abuse trip can manifest as different status codes across attempts. A consecutive-failure-run heuristic (reset on success) is a useful status-agnostic backstop that composes cleanly below a status-code-based fast path.
- **Files changed:** auraframes/client.py, auraframes/sync.py, auraframes/cli.py, tests/test_client_rate_limit.py, tests/test_write_throttling.py, tests/test_cli_apply.py, tests/test_execute_plan.py
---

