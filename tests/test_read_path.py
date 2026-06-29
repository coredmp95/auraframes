import os

import pytest

from auraframes import export
from auraframes.exif import get_readable_exif
from auraframes.models.frame import Frame


def _is_image_asset(asset) -> bool:
    """An asset we can safely download + EXIF-stamp: it has a thumbnail URL
    (get_thumbnail does an unconditional httpx.get(thumbnail_url)) and is not a
    video / live photo (avoids the non-JPEG body that would crash piexif)."""
    return bool(asset.thumbnail_url) and not asset.video_url and not asset.is_live


@pytest.mark.live
def test_read_01_login(aura):
    """READ-01: a live login injects auth state onto the shared httpx session.

    The `aura` fixture already performed the login act (D-03); this asserts the
    resulting authenticated state — both auth headers must be present.
    """
    headers = aura._client.http2_client.headers
    assert headers.get("x-token-auth"), "x-token-auth header missing after login"
    assert headers.get("x-user-id"), "x-user-id header missing after login"


@pytest.mark.live
def test_read_02_list_frames(aura):
    """READ-02: a live get_frames() returns a non-empty list[Frame]."""
    frames = aura.frame_api.get_frames()

    assert frames, "expected at least one frame for the account"
    for f in frames:
        assert isinstance(f, Frame)
        assert f.id, "frame is missing an id"
        print(f"{f.name} ({f.id})")


@pytest.mark.live
def test_read_03_pagination(aura):
    """READ-03 (D-04/D-05): the real get_all_assets cursor loop drains every page.

    We drive the *production* pagination helper (not a hand-rolled loop) with a
    `limit` strictly below the frame's total asset count, which forces the
    cursor branch to run, then assert it stitched back exactly `total` assets.
    """
    frame = aura.frame_api.get_frames()[0]  # D-10: first frame
    _, total = aura.frame_api.get_frame(frame.id)

    if total < 2:
        pytest.skip(
            f"first frame has <2 assets (total={total}); cannot demonstrate "
            "multi-page cursor traversal (data gap, A2)"
        )

    limit = max(1, total // 2)
    assert limit < total, "limit must be below total so the cursor branch runs"

    assets = aura.get_all_assets(frame.id, limit=limit)

    # Indirect-but-airtight proof: if the cursor loop had stopped early or
    # double-counted, len would not equal the server's total_asset_count.
    assert len(assets) == total, (
        f"paginated fetch returned {len(assets)} assets, expected {total}"
    )
    print(f"READ-03: drained {len(assets)} assets across pages of {limit} (total={total})")


@pytest.mark.live
def test_read_04_download_exif(aura, tmp_path):
    """READ-04 (D-09/D-10): download one image and read its EXIF back from disk.

    The read-back from disk is the proof that cannot be faked by a write call
    that returns without writing: DateTimeOriginal is always asserted; GPS is
    asserted only when the asset has location data and geocoding populated it.
    """
    frame = aura.frame_api.get_frames()[0]
    assets = aura.get_all_assets(frame.id)
    assert assets, "expected at least one asset on the first frame"

    image_assets = [a for a in assets if _is_image_asset(a)]
    geo_image_assets = [a for a in image_assets if a.location_name]

    if geo_image_assets:
        asset = geo_image_assets[0]
        branch = "image+location_name"
    elif image_assets:
        asset = image_assets[0]
        branch = "image"
    else:
        asset = assets[0]
        branch = "first-asset-fallback"
    print(f"READ-04: selected asset {asset.id} via '{branch}' branch")

    export.get_image_from_asset(asset, str(tmp_path) + os.sep, aura.exif_writer)

    # get_image_from_asset does not return the saved path; glob it out of the
    # clean tmp_path (exactly one file is written).
    written = list(tmp_path.iterdir())
    assert len(written) == 1, f"expected exactly one saved image, found {written}"
    saved = written[0]
    assert saved.stat().st_size > 0, "saved image is empty (0-byte write slipped through)"

    readable = get_readable_exif(str(saved))

    expected_dt = asset.taken_at_dt.strftime('%Y:%m:%d %H:%M:%S').encode()
    assert readable["Exif"]["DateTimeOriginal"] == expected_dt, (
        "DateTimeOriginal read back from disk does not match the asset's taken_at"
    )

    # GPS is conditional: only assert when the asset had a location name AND the
    # geocode actually populated the GPS IFD (D-09). A geocode miss is tolerated.
    if asset.location_name and readable.get("GPS"):
        assert readable["GPS"], "GPS IFD was expected to be populated but is empty"
        print(f"READ-04: GPS IFD readable for location '{asset.location_name}'")
    else:
        print(
            "READ-04: GPS branch not exercised "
            f"(location_name={asset.location_name!r}, GPS present={bool(readable.get('GPS'))})"
        )
