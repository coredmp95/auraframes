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
