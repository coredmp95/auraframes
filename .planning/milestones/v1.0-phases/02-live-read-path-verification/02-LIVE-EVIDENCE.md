---
phase: 02-live-read-path-verification
type: live-evidence
captured: 2026-06-29
account: «redacted»
result: read-path PROVEN end-to-end against api.pushd.com/v5
---

# Phase 2 — Live Read-Path Evidence

The live read-path tests were run with real credentials (loaded from a local
`.env` via python-dotenv). All four READ requirements pass against the live
Aura API. This is the human-check evidence the plans deferred — captured here
because the credentials were provided during execution.

## Command

```
uv run pytest -m live -s
# 4 passed, 9 deselected
```

## Results

| Req | Test | Result | Evidence |
|-----|------|--------|----------|
| READ-01 | `test_read_01_login` | PASS | Login injected `x-token-auth` + `x-user-id` onto the shared session |
| READ-02 | `test_read_02_list_frames` | PASS | Listed frame **"«frame-name-redacted»"** (`«uuid-redacted»`) |
| READ-03 | `test_read_03_pagination` | PASS | `get_all_assets(limit=38)` drained **77 assets across multiple pages**, `len(assets) == total == 77` |
| READ-04 | `test_read_04_download_exif` | PASS | Downloaded asset `«uuid-redacted»` via `image+location_name` branch; `DateTimeOriginal` read back from disk; **GPS IFD readable for location "«location-redacted»"** |

## Security gate (D-07) — verified against real logs

After a live login, the on-disk log (`logs/file_*.log`) was grepped:

- Plaintext password value: **0 occurrences**
- Unredacted `auth_token` / `x-token-auth` lines: **0**
- Confirmed redaction marker present: `auth_token': '***REDACTED***'`

The HIGH-severity secret-logging item is closed against live traffic, not just
unit assertions.

## Live API drift discovered & repaired (in-scope, read-path only)

Live verification surfaced four schema drifts vs the 2023-era models. All were
fixed pragmatically (commit `93409f5`) under the milestone's "change only what's
needed to prove the read path" constraint:

1. **`User` Optional fields** — the Phase 1 "add `= None`" fix was applied to
   `Frame`/`Asset` but missed `user.py`; the live API now omits `has_frame`,
   which a required-but-nullable field rejected. Added `= None` to all seven
   Optional `User` fields.
2. **`Feature` enum outgrown** — live API returned
   `text_to_frame_four_hour_reminders`, absent from the closed enum. `Feature`
   now maps unknown values to `UNKNOWN` via `_missing_` so a newly-added flag
   can't break hydration.
3. **`Asset.unglacierable`** — live API returns `null`; changed to
   `Optional[bool] = None`.
4. **Asset count moved** — `total_asset_count` is gone from the top level of
   `/frames/{id}.json`; it now lives at `frame.num_assets`. `get_frame` reads
   the new location with a fallback to the legacy key.

## Drift recorded but NOT fixed (deferred, per plan)

- **GPS lat/long swap** in `exif.build_gps_ifd` (T-02-09, accepted): GPS is
  still *readable* so READ-04 passes, but the written coordinates are
  transposed. Deferred to a later milestone.

## Tooling change

- Added `python-dotenv` (dev extra) + `load_dotenv()` in `tests/conftest.py`
  so live tests pick up `AURA_EMAIL`/`AURA_PASSWORD` from `.env`. Shell vars
  still win; a missing `.env` is a no-op, so the credential-less skip (D-02)
  is preserved. `.env.sample` committed as the template; `.env` stays
  gitignored.
