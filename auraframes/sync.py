"""Sync engine: pure dry-run core (Phase 7) plus the single mutating
execute path (Phase 8).

Contains a recursive local-directory scanner + content hasher
(`scan_directory`) and a pure diff function (`compute_plan`) that classifies
a frame's assets into upload / delete / unchanged against local hashes --
both remain pure, no I/O beyond reading local file bytes, no mutation.

`execute_plan()` is this module's ONLY mutating function -- the sole place
that calls select_asset/S3 upload/batch_update (for `to_upload`) and
remove_asset (for `to_delete`). It never references the hard-delete
primitive (the other, non-frame-scoped Asset removal call on `AssetApi`);
the delete loop calls `remove_asset` exclusively (D-06 structural
isolation, grep-verified absent from this module including comments).
Uploads are attempted before any delete (D-09), and a single item's
failure is caught, recorded with its identity, and the loop continues
rather than aborting (D-08), with results reported back as a separated
`ExecutionResult` (D-10).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image
from loguru import logger

from auraframes.aws.s3client import get_md5
from auraframes.models.asset import AssetPartial, AssetPartialId
from auraframes.utils.dt import format_dt_to_aura, get_utc_now

# Only these extensions are eligible for content-hash diffing (D-02). Phase 6
# confirmed md5_hash is populated for photo assets but null for video assets,
# so videos/non-images are excluded here rather than diffed unsafely.
ELIGIBLE_EXTENSIONS = frozenset({'.jpg', '.jpeg', '.png', '.heic'})

# Maps a local file's suffix to the Apple UTI the API expects in
# `data_uti`. Deliberately narrower than ELIGIBLE_EXTENSIONS: '.heic'
# has no registered Pillow decoder in this environment (no pillow-heif
# installed) so `Image.open()` on a `.heic` path always raises before a
# UTI would even be used, and '.png' has no verified-correct UTI value
# yet -- both are left unmapped so `_execute_upload` fails closed with a
# named reason instead of mislabeling the upload server-side.
_DATA_UTI_BY_SUFFIX = {'.jpg': 'public.jpeg', '.jpeg': 'public.jpeg'}


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
    recurse into symlinked directories, and symlinks are excluded
    explicitly below (in addition to the `is_file()` check) -- bounding
    traversal to real files under the user's own directory (T-07-01,
    WR-01: a symlink to a file directly inside the scanned root would
    otherwise still be matched by `rglob('*')` and `is_file()` follows the
    symlink, silently reading and hashing content from outside `root`).

    Raises `NotADirectoryError` if `root` does not exist or is not a
    directory (CR-01): `Path.rglob` silently yields nothing for a missing
    or non-directory path, which would otherwise be indistinguishable from
    a genuinely empty directory and produce a misleading "delete everything"
    plan downstream.
    """
    if not root.is_dir():
        raise NotADirectoryError(f'{root} is not an existing directory')

    local_hashes: dict[str, list[Path]] = {}
    skipped_non_image = 0

    for p in root.rglob('*'):
        if p.is_symlink() or not p.is_file():
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


@dataclass
class ExecutionResult:
    upload_succeeded: int = 0
    delete_succeeded: int = 0
    upload_failures: list = field(default_factory=list)  # list[tuple[Path, str]]
    delete_failures: list = field(default_factory=list)  # list[tuple[str, str]]


def _execute_upload(aura, frame_id: str, path: Path, s3_client, sqs_client, queue_url) -> None:
    """Perform the real upload round-trip for a single new local file.

    Preserves the double `select_asset` call + discarded first SQS poll
    from the original `Aura.upload_image()` for the first live attempt
    (RESEARCH.md Pitfall 4) -- deliberately NOT collapsed into a single
    call. Both SQS polls are best-effort/observational only (Pitfall 3):
    their results are never used to gate success or failure.
    """
    data_uti = _DATA_UTI_BY_SUFFIX.get(path.suffix.lower())
    if data_uti is None:
        raise ValueError(f'Unsupported upload extension: {path.suffix}')

    local_identifier = str(uuid.uuid4())
    with Image.open(path) as image:
        width, height = image.size

    aura.frame_api.select_asset(frame_id, AssetPartialId(local_identifier=local_identifier))
    sqs_client.receive_message(queue_url, wait_time_seconds=5)
    aura.frame_api.select_asset(frame_id, AssetPartialId(local_identifier=local_identifier))

    filename, md5 = s3_client.upload_file(path.read_bytes(), path.suffix)

    pending = AssetPartial(
        local_identifier=local_identifier,
        file_name=filename,
        md5_hash=md5,
        height=height,
        width=width,
        taken_at=format_dt_to_aura(get_utc_now()),
        data_uti=data_uti,
        selected=True,
        upload_priority=0,
    )
    aura.asset_api.batch_update(pending)

    message = sqs_client.receive_message(queue_url, wait_time_seconds=5)
    logger.debug(f'Trailing SQS poll after upload of {path}: {message}')


def execute_plan(plan: SyncPlan, aura, frame_id: str, *, s3_client, sqs_client) -> ExecutionResult:
    """Execute a `SyncPlan` against a live frame -- the module's only
    mutating entry point (D-06/D-08/D-09/D-10).

    For each path in `plan.to_upload`, performs the real upload round-trip
    (select_asset -> S3 upload -> batch_update); for each asset in
    `plan.to_delete`, calls `remove_asset` to disassociate it from the
    frame. All uploads are attempted before any delete is attempted (D-09)
    -- on interruption mid-run this leaves the safer partial state (content
    added, nothing removed). A single item's failure (upload or delete) is
    caught, recorded with its identity, and the loop continues rather than
    aborting (D-08); the aggregate outcome is returned as a separated
    `ExecutionResult` with named per-item failures (D-10). The delete loop
    calls `remove_asset` exclusively -- the module's grep-verified absence
    of any reference to the other, hard Asset-removal primitive is what
    enforces D-06's structural isolation.

    `s3_client`/`sqs_client` are injected by the caller (never constructed
    in this module) so this function is offline-testable with fakes --
    no AWS client construction call appears here at all.

    :param plan: The `SyncPlan` (from `compute_plan`) to execute.
    :param aura: An authenticated `Aura` instance.
    :param frame_id: The frame to upload to / delete from.
    :param s3_client: An object providing `upload_file(data, extension) -> (filename, md5)`.
    :param sqs_client: An object providing `get_queue_url(frame_id)` and `receive_message(...)`.
    :return: An `ExecutionResult` with separated upload/delete success counts and named failures.
    """
    result = ExecutionResult()

    queue_url = sqs_client.get_queue_url(frame_id) if plan.to_upload else None

    for path in sorted(plan.to_upload):
        try:
            _execute_upload(aura, frame_id, path, s3_client, sqs_client, queue_url)
            result.upload_succeeded += 1
        except Exception as e:
            result.upload_failures.append((path, str(e)))

    for asset in plan.to_delete:
        try:
            aura.frame_api.remove_asset(frame_id, AssetPartialId(id=asset.id))
            result.delete_succeeded += 1
        except Exception as e:
            result.delete_failures.append((asset.id, str(e)))

    return result
