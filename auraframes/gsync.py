"""Album → frame mirror engine — plan-computing half (phase 18, plan 18-02).

Pure by construction (CSE-05, the structural dry-run rule): `build_demand`,
`run_google_sync_plan` and `format_plan_report` contain no mutating call and
no I/O — everything they need (listing, manifest, staged outcome, frame
assets) is passed in. The mutating half (`run_google_sync`, plan 18-03)
composes these with v2.0's `execute_plan` behind the CLI's apply gate.

The load-bearing rule (CSE-03 / roadmap criterion 3): demand is rebuilt from
the album LISTING plus the MANIFEST — never from a directory walk of the
(pruned) cache. A manifest member whose cache file is gone still asserts its
md5_hash (the manifest MEANS the upload was confirmed, so the frame already
holds the bytes); its demand entry carries a sentinel path that must never
enter `to_upload` — if the frame disagrees, that is drift and fails loud.
"""
from __future__ import annotations

from pathlib import Path

from auraframes.google.redaction import redact_link
from auraframes.sync import compute_plan

# Suffix of the sentinel demand path for manifest members whose cache file
# was pruned: the md5 is asserted from the manifest, the path is fictional
# and must never be uploaded.
SENTINEL_SUFFIX = ".absent"


class SafeSyncError(RuntimeError):
    """Named mirror-safety abort (SAFE-01) — never a silent plan."""

    @classmethod
    def empty_listing(cls) -> "SafeSyncError":
        return cls(
            "album listing is EMPTY (SAFE-01) — an empty listing cannot be "
            "distinguished from a truncated one and must never be read as "
            "'hide everything on the frame'; refusing to plan"
        )

    @classmethod
    def truncated_listing(cls) -> "SafeSyncError":
        return cls(
            "album listing is NOT exhausted cleanly (SAFE-01) — a truncated "
            "listing would understate demand and mass-hide the difference; "
            "refusing to plan"
        )

    @classmethod
    def empty_frame_listing(cls) -> "SafeSyncError":
        return cls(
            "frame asset listing is EMPTY (SAFE-01) — indistinguishable from "
            "the live-observed get_assets drift (16-LIVE-FINDINGS); verify "
            "the frame's assets and re-run"
        )

    @classmethod
    def manifest_drift(cls) -> "SafeSyncError":
        return cls(
            "manifest claims an upload was confirmed but the frame reports "
            "no matching md5_hash (SAFE-01 drift guard) — the cache was "
            "pruned on that claim; investigate before re-running"
        )


def build_demand(listing, manifest, staged, cache_dir: Path, *,
                 metadata_item_count: int | None = None,
                 ) -> tuple[dict[str, list[Path]], list[tuple[str, str]], int | None]:
    """Rebuild the v2.0 demand map from the album listing + manifest.

    Returns `(demand, failures, videos_skipped)` where `demand` is shaped
    exactly like `scan_directory`'s output (`{md5_hash: [path]}`, one
    logical want per hash) so v2.0's `compute_plan` consumes it unchanged.

    Per listing item:
    - manifest entry exists → demand key = the manifest's md5_hash; the
      demand path is the staged cache file when present, else the sentinel
      `cache_dir/<id>.absent` (pruned — the frame already holds the bytes).
    - no manifest entry, staged → demand key = the staged md5_hash, real path.
    - otherwise (failed/missing download) → excluded from demand and
      collected in `failures` (SAFE-04: never planned from absent bytes).

    This function NEVER walks `cache_dir` — the cache is a staging area, not
    a source of truth (CSE-03).
    """
    from auraframes.google.cache import videos_skipped as _videos_skipped

    demand: dict[str, list[Path]] = {}
    failures: list[tuple[str, str]] = []
    staged_by_id = staged.staged_by_id if staged is not None else {}
    failed_by_id = dict(staged.failed) if staged is not None else {}

    for item in listing.items:
        gid = item["id"]
        entry = manifest.entry_for(gid) if manifest is not None else None
        if entry is not None:
            md5 = entry["md5_hash"]
            s = staged_by_id.get(gid)
            path = Path(s["path"]) if s else Path(cache_dir) / f"{gid}{SENTINEL_SUFFIX}"
            demand[md5] = [path]
        elif gid in staged_by_id:
            s = staged_by_id[gid]
            demand[s["md5_hash"]] = [Path(s["path"])]
        else:
            error = failed_by_id.get(gid) or (
                "item is neither manifest-backed nor staged — not downloaded"
            )
            failures.append((gid, error))

    videos = _videos_skipped(listing, metadata_item_count)
    return demand, failures, videos


def run_google_sync_plan(listing, manifest, staged, cache_dir: Path,
                         frame_assets: list, *,
                         metadata_item_count: int | None = None,
                         skipped_non_image: int = 0,
                         ) -> tuple[object, list[tuple[str, str]], int | None]:
    """The pure plan computation: SAFE-01 gates → demand → v2.0's compute_plan.

    Returns (SyncPlan, failures, videos_skipped). Raises a named
    SafeSyncError — never returns a plan — when the listing or the frame
    asset listing cannot be trusted.
    """
    if not listing.items:
        raise SafeSyncError.empty_listing()
    if getattr(listing, "exhausted_cleanly", None) is not True:
        raise SafeSyncError.truncated_listing()
    if not frame_assets:
        raise SafeSyncError.empty_frame_listing()

    demand, failures, videos = build_demand(
        listing, manifest, staged, cache_dir,
        metadata_item_count=metadata_item_count,
    )
    plan = compute_plan(demand, frame_assets, skipped_non_image=skipped_non_image)

    # Structural enforcement of the sentinel contract: a sentinel path in
    # to_upload means the manifest claimed a confirmed upload the frame
    # disputes — the cache was pruned on that claim, so downloading again is
    # the ONLY honest recovery and that decision is not the plan's to make.
    if any(p.name.endswith(SENTINEL_SUFFIX) for p in plan.to_upload):
        raise SafeSyncError.manifest_drift()

    return plan, failures, videos


def format_plan_report(plan, failures: list[tuple[str, str]],
                       videos_skipped: int | None, *,
                       staged=None) -> str:
    """Render the plan for the CLI (dry-run print and post-apply summary).

    Every Google id passes through `redact_link` — the report is print-ready
    and log-safe by construction.
    """
    lines = [
        f"Plan: {len(plan.to_upload)} to upload, {len(plan.to_reshow)} to "
        f"re-show, {plan.unchanged} unchanged, {len(plan.to_delete)} to hide, "
        f"{plan.already_hidden} already hidden",
    ]
    if videos_skipped is not None:
        lines.append(
            f"Videos skipped: {videos_skipped} (metadata delta — videos are "
            f"out of sync scope, never silently dropped)"
        )
    if failures:
        lines.append(f"Failed downloads ({len(failures)}):")
        for gid, err in failures:
            lines.append(f"  {redact_link(gid)}: {err}")

    staged_by_id = {s["google_media_id"]: s for s in staged.staged} if staged else {}
    if plan.to_upload:
        lines.append("Upload candidates (index | id shape | bytes):")
        for i, p in enumerate(plan.to_upload, 1):
            gid = p.name.removesuffix(SENTINEL_SUFFIX)
            size = staged_by_id.get(gid, {}).get("size_bytes")
            size_s = f"{size:,}" if size is not None else "?"
            lines.append(f"  {i:4d} | {redact_link(gid)} | {size_s}")
    return "\n".join(lines)
