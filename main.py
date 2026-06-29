import os
import sys

from auraframes.aura import Aura
from auraframes import export


def _is_image_asset(asset) -> bool:
    """An asset we can safely download + EXIF-stamp: it has a thumbnail URL and
    is not a video / live photo (mirrors tests/test_read_path.py:10-14)."""
    return bool(asset.thumbnail_url) and not asset.video_url and not asset.is_live


def main():
    # Credential guard (D-07): mirror the Phase 2 test skip philosophy, but exit
    # cleanly instead of skipping. Aura.login() already defaults its args to these
    # same env vars (aura.py:36), so we only need to detect-and-message here.
    if not os.getenv('AURA_EMAIL') or not os.getenv('AURA_PASSWORD'):
        print(
            'AURA_EMAIL / AURA_PASSWORD not set — export them (or add a local .env '
            'used by the test path) to run the read-path demo.'
        )
        sys.exit(0)

    # Read path via existing Aura facade methods only (D-07 — no new client logic).
    aura = Aura()
    aura.login()                                    # READ-01

    frame = aura.frame_api.get_frames()[0]          # READ-02 (first frame)
    assets = aura.get_all_assets(frame.id)          # READ-03 (cursor loop)

    # Asset selection fallback chain (test_read_path.py:79-94): first downloadable
    # image asset with a location (exercises GPS) → else first image asset → else
    # first asset.
    image_assets = [a for a in assets if _is_image_asset(a)]
    geo_image_assets = [a for a in image_assets if a.location_name]
    asset = (geo_image_assets or image_assets or assets)[0]

    out_dir = 'asset_images/'
    os.makedirs(out_dir, exist_ok=True)             # gitignored output dir
    export.get_image_from_asset(asset, out_dir, aura.exif_writer)  # READ-04

    # get_image_from_asset does not return the saved path; glob it out of the
    # output dir (test_read_path.py:99-104).
    saved = sorted(os.path.join(out_dir, f) for f in os.listdir(out_dir))

    # Concise summary — non-secret values only (never the password or auth token).
    print('Read-path demo complete:')
    print(f'  Frame:          {frame.name} ({frame.id})')
    print(f'  Total assets:   {len(assets)}')
    print(f'  Selected asset: {asset.id}')
    print(f'  Saved image(s): {saved[-1] if saved else "(none)"}')


if __name__ == '__main__':
    main()
