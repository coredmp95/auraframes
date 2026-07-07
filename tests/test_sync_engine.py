"""Offline unit tests for auraframes.sync (the dry-run diff engine's pure
core). Zero network access, zero credentials -- scan_directory only reads
local bytes under tmp_path, and compute_plan is a pure function.
"""
from auraframes.aws.s3client import get_md5
from auraframes.sync import scan_directory


def _write(path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def test_scan_directory_recurses_into_nested_subdirectories(tmp_path):
    _write(tmp_path / "top.jpg", b"top-bytes")
    _write(tmp_path / "2024" / "vacation" / "nested.jpg", b"nested-bytes")

    result = scan_directory(tmp_path)

    all_paths = [p for paths in result.local_hashes.values() for p in paths]
    assert tmp_path / "top.jpg" in all_paths
    assert tmp_path / "2024" / "vacation" / "nested.jpg" in all_paths


def test_scan_directory_hashes_each_eligible_extension_case_insensitively(tmp_path):
    _write(tmp_path / "a.jpg", b"jpg-bytes")
    _write(tmp_path / "b.JPEG", b"jpeg-bytes")
    _write(tmp_path / "c.png", b"png-bytes")
    _write(tmp_path / "d.HEIC", b"heic-bytes")

    result = scan_directory(tmp_path)

    all_paths = {p.name: h for h, paths in result.local_hashes.items() for p in paths}
    assert all_paths["a.jpg"] == get_md5(b"jpg-bytes")
    assert all_paths["b.JPEG"] == get_md5(b"jpeg-bytes")
    assert all_paths["c.png"] == get_md5(b"png-bytes")
    assert all_paths["d.HEIC"] == get_md5(b"heic-bytes")
    assert result.skipped_non_image == 0


def test_scan_directory_skips_non_image_files_without_erroring(tmp_path):
    _write(tmp_path / "clip.mp4", b"video-bytes")
    _write(tmp_path / ".DS_Store", b"ds-store-bytes")
    _write(tmp_path / "notes.txt", b"text-bytes")
    _write(tmp_path / "photo.jpg", b"photo-bytes")

    result = scan_directory(tmp_path)

    assert result.skipped_non_image == 3
    all_paths = [p for paths in result.local_hashes.values() for p in paths]
    assert tmp_path / "photo.jpg" in all_paths
    assert len(all_paths) == 1


def test_scan_directory_collapses_byte_identical_files_to_one_hash_key(tmp_path):
    _write(tmp_path / "folder_a" / "photo.jpg", b"identical-bytes")
    _write(tmp_path / "folder_b" / "copy.jpg", b"identical-bytes")

    result = scan_directory(tmp_path)

    assert len(result.local_hashes) == 1
    expected_hash = get_md5(b"identical-bytes")
    paths = result.local_hashes[expected_hash]
    assert len(paths) == 2
    assert tmp_path / "folder_a" / "photo.jpg" in paths
    assert tmp_path / "folder_b" / "copy.jpg" in paths


def test_scan_directory_empty_directory_yields_empty_result(tmp_path):
    result = scan_directory(tmp_path)

    assert result.local_hashes == {}
    assert result.skipped_non_image == 0
