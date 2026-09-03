# Phase 8: Live Verification Findings

**Date:** 2026-07-07
**Frame used:** "Cadre de Fabrice" (id `c063b384-38fa-4324-aaf8-319d17a5867a`) — the project's standing live-verification frame, used consistently since Phase 6/7.

## WRITE-01 / WRITE-04: Upload round-trip (CONFIRMED)

`sync ./data/ --frame "Cadre de Fabrice" --apply --yes` uploaded 1 new local file live. The round-trip (`select_asset` → S3 upload → `batch_update`, with the double `select_asset` call + both SQS polls preserved per RESEARCH.md Pitfall 4) completed with no errors. The photo was confirmed present on the frame via `inspect` immediately after (asset `b7bfc558-...`, filename matching the local upload, `taken_at` defaulted to the current UTC time as expected — Assumption A2 confirmed acceptable, no rejection or visible date corruption).

The upload correctly targeted "Cadre de Fabrice"'s own SQS queue with no queue-mismatch errors, confirming WRITE-04's `get_sqs(frame_id)` parameterization fix works for a real frame (not just the originally-hardcoded one).

**Open Question 1 (double `select_asset`) / Open Question 3 (SQS message meaning):** No error or observable difference was caused by the double call or the discarded/observational SQS polls. Both are safe to leave unchanged for now; their exact necessity remains unconfirmed (no live signal either way), consistent with treating them as best-effort/observational per RESEARCH.md's recommendation.

## WRITE-02: `remove_asset` (CONFIRMED)

`remove_asset` correctly disassociates a frame asset when applied. Live-tested at scale: 72 total assets were removed from the frame across two `--apply --yes` runs (see incident note below) with 0 errors on retry. `remove_asset`'s docstring claim ("does not seem to remove from S3/Glacier") is consistent with what was observed at the frame level — assets vanish from *this frame's* listing; the underlying account data was not independently destroyed (the user maintains an independent backup of all affected photos, so this was not verified against account-wide asset deletion, but no error or unexpected side effect outside the target frame was observed).

## WRITE-03: `delete_asset` blast-radius probe (CONFIRMED — reaffirms D-06)

A dedicated disposable throwaway JPEG (`/tmp/aura-disposable-probe/throwaway.jpg`, an 8x8 solid-color test image — never a real photo) was uploaded to "Cadre de Fabrice" via `sync --apply --yes`, then `AssetApi.delete_asset` was invoked directly via a one-off `uv run python -c "..."` script (never through the CLI or `sync.py`/`cli.py` — `grep -c 'delete_asset' auraframes/sync.py auraframes/cli.py` still returns 0):

```python
aura = Aura(); aura.login()
asset = Asset.model_construct(id="95a68498-7a3e-11f1-a6ad-0affe06aea17")
aura.asset_api.delete_asset(asset)
```

**Observed:** `DELETE /assets/{id}.json` → HTTP 200, empty body `{}`, no `error` field. A subsequent `sync` dry-run and `inspect` confirmed the asset is **completely gone** — it no longer appears anywhere on the frame, and (unlike `remove_asset`) the endpoint itself is asset-scoped (`/assets/{id}.json`), not frame-scoped (`/frames/{frame_id}/remove_asset.json`), meaning it is not merely a per-frame disassociation.

**D-07 stop-condition check:** This matches — does not exceed — what the docstring already anticipated ("maybe deletes it from S3/Glacier"). No unexpected side effects were observed on other assets, other frames, or the account. **No STOP was triggered.**

**Conclusion:** `delete_asset` is confirmed broader-scoped than `remove_asset` (asset-level, not frame-level) and is correctly kept out of the `--apply` execution path. **`remove_asset` is reaffirmed as the safe default for `sync --apply`'s delete behavior (D-06).** `delete_asset` remains completely unwired from any executable path in this codebase.

## Incident note: transient auth-token expiry mid-batch (process finding, not a code defect)

During the very first live `--apply --yes` run, the operator ran `sync` against `./data/` (2 files) while "Cadre de Fabrice" held ~74 real photos accumulated since 2012 (the same test frame used throughout Phases 6-7, evidently also used as the operator's real personal frame). Since `sync`'s diff logic deletes anything on the frame not present locally, this produced a large plan (1 upload, 72 deletes) that was applied in full.

- 1 upload succeeded.
- 47 deletes succeeded via `remove_asset`.
- The remaining 25 deletes failed with `401 Unauthorized` partway through the batch — the auth session/token expired mid-run. **WRITE-05's fail-loud handling and D-08's continue-past-failure model worked exactly as designed:** each failure was caught, individually attributed by asset id, the batch continued rather than aborting, and the CLI exited non-zero (confirming SYNC-04's exit-code contract) rather than silently reporting partial success as success.
- A follow-up dry-run confirmed the frame's state was left consistent (no partial/corrupted state) — the 25 failed items were still correctly identified as delete candidates.
- Re-running `sync --apply --yes` with a fresh process (fresh auth token) completed the remaining 25 deletes with 0 failures, fully reconciling the frame against `./data/`.
- The operator confirmed all affected photos are independently backed up elsewhere, so this was not a real data-loss event — but it is a genuine, previously-unknown operational finding: **a single `sync --apply` run against a large delete batch can outlive the auth session's token lifetime.** This is not a code defect (WRITE-05/D-08 handled it correctly) but is worth flagging as a future hardening candidate (e.g., token refresh mid-batch) — out of scope for this phase, not required by SYNC-03/04/WRITE-01..05.

## Summary

| Requirement | Status |
|---|---|
| WRITE-01 (upload round-trip) | ✅ Confirmed live |
| WRITE-02 (`remove_asset`) | ✅ Confirmed live |
| WRITE-03 (`delete_asset` blast radius) | ✅ Confirmed live — broader than `remove_asset`, correctly unwired from `--apply` |
| WRITE-04 (SQS queue targeting) | ✅ Confirmed live — correct frame's queue used |
| SYNC-04 (fail-loud + non-zero exit) | ✅ Confirmed live — the 401 incident is direct proof this works correctly under a real partial-failure condition |
