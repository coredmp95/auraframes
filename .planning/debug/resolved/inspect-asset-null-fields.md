---
status: resolved
trigger: "aura-cli inspect --frame \"Cadre de Fabrice\" prints the frame/owner header correctly, then crashes with 8 pydantic validation errors while constructing an `Asset` from the frame's asset list (88 assets total): data_uti, file_name, taken_at, uploaded_at are None where a string is required; height, width, upload_priority are None where an int is required; good_resolution is missing entirely (input dict has no such key). The failing asset's id starts with 3d372d12-7a98-11f..."
created: "2026-07-08T09:00:00Z"
updated: "2026-07-08T09:00:00Z"
---

## Symptoms

expected: `aura-cli inspect --frame "Cadre de Fabrice"` prints frame/owner info, contributor count, and successfully lists/summarizes all 88 assets.
actual: Frame/owner/contributor info prints correctly. Then it crashes while parsing the asset list with a pydantic ValidationError (8 errors) for one `Asset` — 4 fields got `None` where a `str` was required (data_uti, file_name, taken_at, uploaded_at), 3 fields got `None` where an `int` was required (height, width, upload_priority), and 1 required field (good_resolution) was missing from the API response dict entirely.
errors: |
  8 validation errors for Asset
  data_uti / file_name / taken_at / uploaded_at: Input should be a valid string [type=string_type, input_value=None]
  height / width / upload_priority: Input should be a valid integer [type=int_type, input_value=None]
  good_resolution: Field required [type=missing, input_value={'id': '3d372d12-7a98-11f...analytics_optout': False}}]
started: User reports `inspect` "worked before, broke now" — something changed between a prior successful run and this one. User hasn't tried other frames (Cadre de Fabrice is likely their only/primary frame). This frame received a large batch of live writes recently (Phase 8 verification + the just-fixed throttling work: ~120-item sync, ~72 deletes, and a delete_asset probe) — worth checking whether the failing asset is one of those recent uploads and whether the API returns partially-processed assets (server-side processing not yet complete: dimensions/thumbnail/data_uti not yet populated) rather than fully-formed ones.
reproduction: "`aura-cli inspect --frame \"Cadre de Fabrice\"` against the live API with real credentials."

## Current Focus

hypothesis: CONFIRMED (a) — the live API returns assets mid-server-side-processing (an unprocessed placeholder), which the `Asset` model rejects because 8 content fields aren't `Optional`.
test: Extracted the raw failing-asset dict from the last live-run log; verified it is a near-empty placeholder and that the exactly-8 null/missing fields match the 8 pydantic errors.
expecting: n/a — confirmed.
next_action: Apply scoped model fix (8 fields → Optional[...] = None) + guard `taken_at_dt` against None, then verify with an offline fixture built from the real placeholder shape.

reasoning_checkpoint:
  hypothesis: "The Aura/Pushd API can return an asset that is still mid-server-side-processing — a placeholder with source_id/local_identifier/user populated but no processed content metadata yet (dimensions, filenames, dates, urls, md5 all null; good_resolution not yet emitted). The current `Asset` model declares data_uti/file_name/taken_at/uploaded_at as required str, height/width/upload_priority as required int, and good_resolution as required bool, so it raises 8 ValidationErrors on such an asset."
  confirming_evidence:
    - "Raw failing-asset dict (id 3d372d12-7a98-11f1-b9b5-0affe06aea17) pulled from log file_2026-07-08_08-42-55_684861.log: data_uti/file_name/taken_at/uploaded_at/height/width/upload_priority are all None and 'good_resolution' key is absent — exactly the 8 reported errors, no more no less."
    - "The asset is a near-empty shell: 60+ fields None (all *_url, all *_rect, md5_hash, location, duration, orientation, thumbnail_url) while source_id, local_identifier, selected=True, user, user_id ARE populated — the shape of a queued-but-not-yet-processed upload, not a video/screenshot (a video would still carry dimensions/file_name)."
    - "It carries new server fields the model doesn't declare (is_classified, attachments, is_b2, is_video_b2) — pydantic v2 ignores extras by default, so they are harmless and not the cause."
  falsification_test: "If, after making the 8 fields Optional and building a fixture Asset from this exact raw shape, Asset(**data) still raised — or if a fully-processed asset (assets_page1/2 fixtures) stopped hydrating — the fix would be wrong. Both are checked by the offline suite."
  fix_rationale: "Making the 8 fields Optional[...] = None makes Asset tolerate whatever the live API actually returns for an unprocessed asset (root cause: the model assumed every asset is fully processed). Guarding taken_at_dt to return None when taken_at is None is required because the very next line the CLI runs after the model fix (cli.py:211 prints asset.taken_at_dt) would otherwise crash in parse_aura_dt(None). This is the minimal change per the modernization-scope constraint — no broad model refactor, extras still ignored, required fields that were never null (id, user, source_id, selected, ...) stay required."
  blind_spots: "The export/exif write-back path (exif.py:61 does asset.taken_at_dt.strftime(...)) would NoneType-crash if such a placeholder were selected for download — but that path is not exercised by `inspect` and these unprocessed placeholders have no thumbnail_url so _is_image_asset filters them out of download anyway. Not fixing it here keeps scope tight; noted for the export path. Cannot re-confirm live (account was throttled/475 in the sibling session) — verification is offline against the captured real shape, which is the exact JSON that crashed."

## Eliminated

- hypothesis: (b) The failing asset is a distinct asset "kind" (video/screenshot/other-source) that structurally never carries these fields.
  evidence: The raw dict shows EVERY content field null (dimensions, all urls, all rects, md5_hash, thumbnail_url, duration, data_uti) — a video/screenshot would still carry file_name, height, width, data_uti and a url. This is an unprocessed placeholder, not a differently-shaped-but-complete asset. burst_id/represents_burst/video_* are all null too.
  timestamp: 2026-07-08

## Evidence

- timestamp: 2026-07-08 (log extraction, offline)
  checked: Pulled the raw failing-asset dict (id starting 3d372d12-7a98-11f) out of the most recent live-run log (logs/file_2026-07-08_08-42-55_684861.log) by parsing the DEBUG "Response (200), body: {...}" line for the assets.json call and locating the asset by id.
  found: 72-key dict where source_id, local_identifier, user, user_id, selected(True), exif_orientation(1), rotation_cw(0), is_subscription(False), glaciered_at('4001-01-01T00:00:00.000Z' sentinel) are populated, but data_uti/file_name/taken_at/uploaded_at=None, height/width/upload_priority=None, and NO 'good_resolution' key at all. Also present: new fields is_classified(False), attachments([]), is_b2(None), is_video_b2(None) not declared on the model.
  implication: This is a freshly-uploaded asset the server has not finished processing (thumbnail/dimension/EXIF/data_uti extraction pending) — a real, legitimate API state. The 8 null/missing fields correspond 1:1 to the 8 ValidationErrors. Fix = make those 8 fields Optional so the read path tolerates unprocessed assets; do NOT special-case the id. New extra fields need no action (pydantic v2 ignores extras).

## Resolution

root_cause: |
  The `Asset` pydantic model assumed every asset returned by GET
  frames/{id}/assets.json is a fully-processed photo. In reality the Aura/Pushd
  API returns freshly-uploaded assets that are still mid-server-side-processing
  (thumbnail/dimension/EXIF/data_uti extraction not yet complete) as placeholder
  records: source_id, local_identifier, user, selected are populated but the
  processed content metadata is null and `good_resolution` is omitted entirely.
  The model declared data_uti/file_name/taken_at/uploaded_at as required `str`,
  height/width/upload_priority as required `int`, and good_resolution as required
  `bool`, so building such an asset raised 8 ValidationErrors and crashed
  `aura-cli inspect` inside get_all_assets. This was newly triggered because the
  Phase 8 write burst uploaded ~120 assets to this frame; the id-3d372d12 asset
  is one still in the processing queue at read time.

fix: |
  Scoped model change (no broad refactor, per the modernization constraint):
  made the 8 offending fields Optional with a None default in
  auraframes/models/asset.py — data_uti, file_name, good_resolution, height,
  width, upload_priority, taken_at, uploaded_at. Also guarded the `taken_at_dt`
  property to return None when taken_at is None (parse_aura_dt(None) would raise,
  and cli.py inspect/sync read this property for every listed asset). Newer
  server fields observed on the placeholder (is_classified, attachments, is_b2,
  is_video_b2) need no action — pydantic v2 ignores undeclared extras. Required
  fields that were never null (id, user, source_id, selected, glaciered_at,
  exif_orientation, rotation_cw, is_subscription, local_identifier, user_id)
  stay required.

verification: |
  LIVE end-to-end (the account recovered from the sibling session's throttle):
  ran the user's exact reproduction `python -m auraframes.cli inspect --frame
  "Cadre de Fabrice"` -> exit 0, prints frame/owner/contributors/Assets: 88,
  then lists photos with the placeholder asset rendered as
  "3d372d12-7a98-11f1-b9b5-0affe06aea17 | None | None" (no crash) alongside 13
  fully-processed assets that hydrate normally. Previously this crashed with 8
  ValidationErrors.

  OFFLINE (default CI suite, `pytest -m "not live"` -> 96 passed, 4 deselected):
    - tests/test_asset_unprocessed.py (NEW): the exact captured placeholder
      shape (redacted fixture tests/fixtures/asset_unprocessed.json) now
      hydrates; the 8 fields are None; taken_at_dt returns None not a crash;
      newer extra fields are ignored.
    - tests/test_cli_inspect.py (NEW test): run_inspect over the offline harness
      with the placeholder in the asset list returns rc=0, prints the id, no
      "Failed to inspect frame".
    - Existing tests/test_fixtures_validity.py (fully-processed page1/page2
      fixtures) still hydrate — the fix did not loosen a real regression.

  Out of scope / noted, not fixed: (1) the export/exif write-back path
  (exif.py:61 asset.taken_at_dt.strftime) would NoneType-crash on a placeholder,
  but placeholders have no thumbnail_url so _is_image_asset excludes them from
  download; (2) frame reports num_assets=88 while get_all_assets returns 14 — a
  pre-existing count/pagination discrepancy unrelated to this crash.

files_changed:
  - auraframes/models/asset.py            # 8 fields -> Optional[...] = None; taken_at_dt None-guard
  - tests/fixtures/asset_unprocessed.json # NEW — redacted real placeholder shape
  - tests/test_asset_unprocessed.py       # NEW — model hydration + taken_at_dt + extras-ignored
  - tests/test_cli_inspect.py             # NEW test — inspect tolerates placeholder end-to-end
