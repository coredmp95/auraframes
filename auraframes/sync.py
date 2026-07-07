"""Pure, offline-testable core of the dry-run sync engine (Phase 7).

Contains a recursive local-directory scanner + content hasher
(`scan_directory`) and a pure diff function (`compute_plan`) that classifies
a frame's assets into upload / delete / unchanged against local hashes.

There is deliberately NO execute/mutating counterpart in this module (no
upload, no delete, no S3/SQS call) -- the dry-run guarantee is structural.
The future `execute_plan()` lands in Phase 8.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from auraframes.aws.s3client import get_md5

# Only these extensions are eligible for content-hash diffing (D-02). Phase 6
# confirmed md5_hash is populated for photo assets but null for video assets,
# so videos/non-images are excluded here rather than diffed unsafely.
ELIGIBLE_EXTENSIONS = frozenset({'.jpg', '.jpeg', '.png', '.heic'})


@dataclass
class ScanResult:
    local_hashes: dict[str, list[Path]]
    skipped_non_image: int


def scan_directory(root: Path) -> ScanResult:
    """Recursively walk `root` (D-01) and content-hash every eligible image
    file, grouping local paths by base64-MD5 hash (D-05: byte-identical
    files collapse to one hash key/logical want).

    Non-eligible files (videos, dotfiles, arbitrary junk) are counted in
    `skipped_non_image` and never error (D-02, D-03). `Path.rglob` does not
    follow directory symlinks, and only regular files (`is_file()`) are
    considered -- bounding traversal to real files under the user's own
    directory (T-07-01).
    """
    local_hashes: dict[str, list[Path]] = {}
    skipped_non_image = 0

    for p in root.rglob('*'):
        if not p.is_file():
            continue

        if p.suffix.lower() not in ELIGIBLE_EXTENSIONS:
            skipped_non_image += 1
            continue

        data = p.read_bytes()
        h = get_md5(data)
        local_hashes.setdefault(h, []).append(p)

    return ScanResult(local_hashes, skipped_non_image)


@dataclass
class SyncPlan:
    to_upload: list[Path] = field(default_factory=list)
    to_delete: list = field(default_factory=list)
    unchanged: int = 0
    skipped_non_image: int = 0
    frame_no_hash: int = 0


def compute_plan(local_hashes: dict[str, list[Path]], frame_assets: list, skipped_non_image: int = 0) -> SyncPlan:
    """Diff local content hashes against a frame's assets (SYNC-01).

    Pure function -- no I/O, no network, no mutation of its inputs --
    mirroring `resolve_frame`'s pure dataclass-result shape. There is
    deliberately no execute/mutating counterpart here; the dry-run
    guarantee is structural.

    Local duplicates (per `scan_directory`'s dedup) already collapse to one
    logical want per hash (D-05), so each unique hash demands exactly one
    frame copy. Frame-side assets are matched count-for-count against that
    demand (D-06 multiset asymmetry): surplus frame copies beyond local
    demand become delete candidates, they are NOT deduped as a group.
    Hashless frame assets (e.g. videos) are excluded from both unchanged
    and delete, and counted separately in `frame_no_hash`.
    """
    demand = {h: 1 for h in local_hashes}
    to_delete: list = []
    unchanged = 0
    frame_no_hash = 0

    for asset in frame_assets:
        if not asset.md5_hash:
            frame_no_hash += 1
            continue

        if demand.get(asset.md5_hash, 0) > 0:
            demand[asset.md5_hash] -= 1
            unchanged += 1
        else:
            to_delete.append(asset)

    to_upload = [local_hashes[h][0] for h, remaining in demand.items() if remaining > 0]

    return SyncPlan(
        to_upload=to_upload,
        to_delete=to_delete,
        unchanged=unchanged,
        skipped_non_image=skipped_non_image,
        frame_no_hash=frame_no_hash,
    )
