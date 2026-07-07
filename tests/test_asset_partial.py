"""Offline tests for `AssetPartial` (auraframes.models.asset), the
all-Optional variant of `Asset` used to send new-upload metadata through
`AssetApi.batch_update` before every field of a real `Asset` is known
(Phase 8 Plan 01, Task 1).

Unmarked (no @pytest.mark.live) — pure model-construction tests, zero
network access and no credentials required.
"""
from auraframes.models.asset import Asset, AssetPartial

# The exact allowlist AssetApi.batch_update uses for its `.dict(include=...)`
# call (auraframes/api/assetApi.py:19-38) -- AssetPartial must serialize to
# precisely this shape.
BATCH_UPDATE_ALLOWLIST = {
    'data_uti': True,
    'favorite': True,
    'file_name': True,
    'height': True,
    'local_identifier': True,
    'location': True,
    'md5_hash': True,
    'modified_at': True,
    'orientation': True,
    'selected': True,
    'taken_at': True,
    'upload_priority': True,
    'width': True,
}


def test_asset_partial_constructs_with_id_unset():
    """AssetPartial(local_identifier='x') constructs with no ValidationError,
    unlike Asset(id=None, ...) which raises because `id` is a required str."""
    partial = AssetPartial(local_identifier='x')

    assert partial.local_identifier == 'x'
    assert partial.id is None


def test_asset_partial_serializes_to_batch_update_payload_shape():
    """.dict(include=...) over batch_update's allowlist returns exactly
    those keys, regardless of which fields were actually set."""
    partial = AssetPartial(
        local_identifier='local-id-1',
        file_name='photo.jpg',
        md5_hash='deadbeef==',
        height=100,
        width=200,
        taken_at='2026-07-07T00:00:00Z',
        data_uti='public.jpeg',
        selected=True,
        upload_priority=1,
    )

    payload = partial.dict(include=BATCH_UPDATE_ALLOWLIST)

    assert set(payload.keys()) == set(BATCH_UPDATE_ALLOWLIST.keys())
    assert payload['local_identifier'] == 'local-id-1'
    assert payload['file_name'] == 'photo.jpg'
    assert payload['md5_hash'] == 'deadbeef=='
    assert payload['height'] == 100
    assert payload['width'] == 200
    assert payload['taken_at'] == '2026-07-07T00:00:00Z'
    assert payload['data_uti'] == 'public.jpeg'
    assert payload['selected'] is True
    assert payload['upload_priority'] == 1


def test_asset_partial_is_subclass_of_asset():
    """make_partial uses __base__=model, so isinstance(p, Asset) is True."""
    partial = AssetPartial(local_identifier='x')

    assert isinstance(partial, Asset)
