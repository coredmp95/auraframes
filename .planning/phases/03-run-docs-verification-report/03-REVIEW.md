---
phase: 03-run-docs-verification-report
reviewed: 2026-06-29T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - main.py
  - README.md
  - VERIFICATION-REPORT.md
findings:
  critical: 1
  warning: 3
  info: 1
  total: 5
status: issues_found
---

# Phase 3: Code Review Report

**Reviewed:** 2026-06-29
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Reviewed the read-path demo (`main.py`) and two documentation artifacts (`README.md`,
`VERIFICATION-REPORT.md`). All three files are tracked in git (`git ls-files` confirms),
and the diff base `e9c650c^..HEAD` covers exactly these three files.

`main.py`'s API surface was cross-checked against the code it drives (`Aura.login`,
`FrameApi.get_frames`/`get_assets`, `Aura.get_all_assets`, `export.get_image_from_asset`,
and the `Asset`/`Frame` models). Every attribute and method it touches exists with the
expected shape — no broken calls. The README's documented `uv` commands and pytest
`live` marker match `pyproject.toml` (dev extra = pytest + python-dotenv; `live` marker
registered), `.env.sample`, `.python-version` (`3.14`), and `uv.lock`, all of which exist.

The dominant problem is a hard security-requirement violation: `VERIFICATION-REPORT.md`,
which is committed to the repository, embeds the **real account email** (the literal
`AURA_EMAIL` credential) plus other real personal data (account holder's name in a frame
title, a derived GPS location, and live asset/frame UUIDs). CLAUDE.md states "secrets
must stay out of version control," and this phase's mandate explicitly forbids leaked
credentials/PII in the docs. Two lower-severity correctness issues exist in `main.py`'s
end-of-run reporting and its unguarded list-indexing.

## Critical Issues

### CR-01: Real account credential (AURA_EMAIL) committed in verification report

**File:** `VERIFICATION-REPORT.md:4`
**Issue:** The committed report records the live account email in plaintext:
`**Account:** «redacted» (email only — ...)`. `AURA_EMAIL` is one of the two
**required credentials** (README "Required:" section; CLAUDE.md "Required vars:
`AURA_EMAIL`, `AURA_PASSWORD`"). Committing it to version control directly violates the
project constraint "secrets must stay out of version control" and this phase's hard
requirement of no leaked credentials. The parenthetical "email only — password / auth
tokens never recorded" rationalizes the leak as safe, but the email is the account
*username* half of the credential pair and an identifier tying the public repo to a real
person. `git ls-files VERIFICATION-REPORT.md` confirms the file is tracked, and
`git grep` finds the email in the committed tree.
**Fix:** Redact the account identifier in the committed artifact, e.g.:
```markdown
**Account:** <redacted — set via AURA_EMAIL> (credentials never recorded in this report).
```
If the email already landed in pushed history, also scrub it from history (e.g.
`git filter-repo`) and treat the account as exposed.

## Warnings

### WR-01: Real personal data (name, GPS location, account UUIDs) in committed report

**File:** `VERIFICATION-REPORT.md:27,29-30,46,48`
**Issue:** Beyond the email, the committed report embeds live personal data harvested from
the account: the frame title **"«frame-name-redacted»"** (a real person's given name) with its
frame UUID `«uuid-redacted»`, a live asset UUID
`«uuid-redacted»`, and a reverse-geocoded **location "«location-redacted»"**
revealing where the account holder's photos were taken. This is PII committed to version
control. The same evidence appears twice (raw block lines 27/29/30 and the status table
lines 46/48), so redaction must cover both.
**Fix:** Replace identifying values with non-identifying placeholders while preserving the
evidentiary shape, e.g. `Listed frame "<frame-name>" (<frame-uuid-prefix>…)`,
`selected asset <asset-uuid>…`, and `GPS IFD readable for location "<redacted>"`. The
counts (77 assets, pages of 38) carry the verification signal and are safe to keep.

### WR-02: End-of-run "Saved image(s)" can report a different file than the selected asset

**File:** `main.py:45,52`
**Issue:** `saved = sorted(os.path.join(out_dir, f) for f in os.listdir(out_dir))` lists
**every** file in `asset_images/`, then `saved[-1]` is printed as the saved image. The
output directory is persistent across runs (gitignored, not cleaned), and filenames are
prefixed with the asset's `taken_at` datetime (`export.get_image_from_asset` →
`{_get_path_safe_datetime(asset.taken_at_dt)}-{asset.file_name}`). After a sort, `saved[-1]`
is the lexicographically-greatest *taken_at* prefix among all accumulated files — which is
not necessarily the asset just selected/downloaded this run. The summary therefore can
print a "Selected asset" (line 51) and a "Saved image(s)" (line 52) that refer to
different images, silently misreporting the demo result. `export.get_image_from_asset`
does not return the path, but the path is deterministically reconstructable from the asset.
**Fix:** Derive the exact saved path from the selected asset instead of globbing:
```python
from auraframes.export import _get_path_safe_datetime
saved_path = os.path.join(out_dir, f'{_get_path_safe_datetime(asset.taken_at_dt)}-{asset.file_name}')
...
print(f'  Saved image:    {saved_path if os.path.isfile(saved_path) else "(none)"}')
```
(Or have `export.get_image_from_asset` return `new_filename` and use that.)

### WR-03: Unhandled IndexError on accounts with no frames or an empty frame

**File:** `main.py:29,37`
**Issue:** `frame = aura.frame_api.get_frames()[0]` crashes with `IndexError` if the
account owns/collaborates on zero frames, and `asset = (geo_image_assets or image_assets
or assets)[0]` crashes with `IndexError` if the selected frame has no assets at all. The
file deliberately handles the missing-credentials case with a clean message and
`sys.exit(0)` (lines 18-23), so an unguarded traceback on these equally-foreseeable empty
states is an inconsistent, confusing failure mode for the read-path demo.
**Fix:** Guard both before indexing, e.g.:
```python
frames = aura.frame_api.get_frames()
if not frames:
    print('No frames on this account — nothing to demo.'); sys.exit(0)
frame = frames[0]
...
candidates = geo_image_assets or image_assets or assets
if not candidates:
    print(f'Frame {frame.id} has no assets — nothing to download.'); sys.exit(0)
asset = candidates[0]
```

## Info

### IN-01: README upload_image source link anchors one line above the definition

**File:** `README.md:74`
**Issue:** `[Aura.upload_image](auraframes/aura.py#L101)` points at line 101, but
`def upload_image` is at `auraframes/aura.py:102` (line 101 is the blank line above it).
Cosmetic, but the anchor lands on the wrong line.
**Fix:** Update the anchor to `auraframes/aura.py#L102`.

---

_Reviewed: 2026-06-29_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
