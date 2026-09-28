---
status: testing
phase: 18-album-frame-mirror-sync-single-pair
source: [18-VERIFICATION.md]
started: 2026-09-28T21:30:00Z
updated: 2026-09-28T21:30:00Z
---

## Current Test

number: 1
name: Two-run live UAT on the real pair (criterion 4)
expected: |
  Run 1: `uv run aura-cli google-sync "Cadre" --frame "Cadre de Fabrice"` prints
  the plan (dry-run), then `--apply` uploads the album photos not yet on the
  frame and reports the confirmed uploads. Remove one photo from the Google
  album "Cadre"; re-run with `--apply`: the plan shows it as a HIDE and the
  frame reports it hidden (asset still on the frame, excluded). Re-add the
  photo to the album; re-run with `--apply`: the plan shows it as a RE-SHOW
  with zero bytes re-uploaded (the manifest md5 matches — no S3 upload).
awaiting: user response

## Tests

### 1. Two-run live UAT on the real pair (criterion 4)
expected: |
  remove → HIDE (reversible), re-add → RE-SHOW without re-uploading a byte;
  steady-state runs download nothing and upload nothing; every live write step
  is operator-gated (16-03 precedent).
result: [pending]

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
