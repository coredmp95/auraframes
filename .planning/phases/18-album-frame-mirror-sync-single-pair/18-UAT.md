---
status: passed
phase: 18-album-frame-mirror-sync-single-pair
source: [18-VERIFICATION.md]
started: 2026-09-28T21:30:00Z
updated: 2026-09-28T22:15:00Z
---

## Tests

### 1. Two-run live UAT on the real pair (criterion 4)
expected: |
  remove → HIDE (reversible), re-add → RE-SHOW without re-uploading a byte;
  steady-state runs download nothing and upload nothing; every live write step
  is operator-gated (16-03 precedent).
result: [passed]
log: |
  Live pair: Google album « Cadre » (real session, RPC-first protocol)
    → Aura frame « Cadre de Fabrice » (c063b384…). Every write step ran only
    after explicit operator consent via checkpoint.

  STEP 1 — DRY-RUN (read-only, ~22:00Z): PASS
    Plan: 23 to upload, 1 to re-show, 0 unchanged, 0 to hide, 0 already hidden
    Videos skipped: 0 (24 metadata == 24 photos)
    Upload candidates: 23 items, 129,680 → 8,847,782 bytes (sum ≈ 87.0 MiB);
    the re-show item (3,412,350-byte phase-16 fidelity-probe photo) correctly
    NOT in the upload list — matched by md5 via the manifest-drift sentinel.
    exit 0; zero frame writes, zero S3 calls.

  STEP 2 — APPLY #1 (uploads; operator consent): PASS
    24 uploads confirmed (23 new + fidelity-probe path exercised).
    Manifest written: 24 entries, perms 0o600.
    Cache pruned: google-cache/ empty after run.
    Pushd side: 24 assets created via batch_update (S3 + confirmations).

  STEP 2b — APPLY #2 (re-show leg of criterion 4; operator consent): PASS
    Plan before: 0 to upload, 23 unchanged, 1 to re-show → zero downloads,
    zero uploads, cache empty (steady-state proof on real data).
    Evidence (logs/file_2026-09-28_22-02-32_245356.log):
      GET /frames.json, GET /frames/{id}/assets.json,
      POST /frames/{id}/select_asset.json  ← exactly 1 re-show call
      0 POST /assets/* (no upload), 0 batch_update, 0 exclude_asset
    Server truth: asset 01a0e737-d637-735f-a6fe-820a4b48809d
      updated_selected_at: 2026-09-28T20:02:38.911Z, selected: true.

  STEP 3 — remove from Google album → apply #3 (hide leg; operator consent): PASS
    Operator removed one photo from the album (24 → 23 items).
    google-album ground truth after removal: 23 items, 78.1 MiB.
    Plan: 0 to upload, 23 unchanged, 1 to hide (SAFE-02 gate: 1/24 ≈ 4 %
    ≤ 20 % threshold; hide-only, no delete path).
    Evidence (logs/file_2026-09-28_22-05-23_036478.log):
      GET /frames.json, GET /frames/{id}/assets.json,
      POST /frames/{id}/exclude_asset  ← exactly 1 hide call
      0 POST /assets/* (no upload), 0 batch_update, 0 select_asset, 0 DELETE
    Server truth: asset 01a0e999-f52b-771e-be69-1a132239981a
      updated_selected_at: 2026-09-28T20:05:29.623Z, selected: false.
    Reversibility proof: the asset REMAINS on the frame (24 assets total)
    — hidden, not deleted; manifest keeps its entry (24 entries).

  STEP 4 — STEADY-STATE dry-run (post-hide): PASS
    Plan: 0 to upload, 0 to re-show, 23 unchanged, 0 to hide, 1 already hidden
    exit 0; zero writes. The system converged: hidden frame asset is
    correctly classified (not re-demanded, not re-hidden), album and frame
    agree at 23 visible photos.

  Frame end-state: 24 assets (23 visible, 1 hidden = the album-removed photo).

## Summary

total: 1
passed: 1
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

- Optional (not required by criterion 4): re-add the removed photo in Google
  Photos and re-run --apply to watch the SAME photo re-showed with zero
  uploads. Both halves of criterion 4 (re-show w/o re-upload, remove→hide)
  are already individually proven live; this would only chain them on the
  same item.
