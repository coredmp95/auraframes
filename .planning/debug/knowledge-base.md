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

