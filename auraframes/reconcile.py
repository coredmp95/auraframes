"""Data hygiene for stuck placeholder rows on an existing frame -- deliberately
NOT part of the sync loop (`auraframes/sync.py`).

`select_asset` calls whose upload never completed leave rows with no
`uploaded_at`, no `file_name` and no `md5_hash`. Neither existing removal
primitive clears them (`AssetApi.delete_asset` returns 200 and removes
nothing; `FrameApi.remove_asset` 404s). This module accounts for them: it
reports how many exist (unconditionally, whether or not any removal
mechanism works) and, only when explicitly asked, attempts a bounded,
gated removal.

Following `auraframes/sync.py`'s own pure-diff/mutating-execute split:
`find_placeholders` is this module's pure classifying function -- no I/O,
no network, no mutation of its input. `apply_reconciliation` is this
module's ONLY mutating function -- the sole place that calls a removal
primitive against a live frame, reachable only when the caller explicitly
asks for it.

This module imports nothing Google-side, and `auraframes/sync.py` never
imports from or calls into this module -- the two are structurally
independent (mirroring D-06's `sync.py`/hard-delete isolation convention).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from auraframes.utils.dt import get_utc_now, parse_aura_dt

# How long a row matching the placeholder predicate (D-14) must sit before it
# is even a candidate for removal (D-15). A row created seconds ago by a
# legitimate in-progress upload matches the predicate exactly -- the server
# processes an upload asynchronously, so a freshly-registered asset is
# indistinguishable from a genuinely stuck one until enough time has passed
# for normal processing to have finished (`tests/test_cli_inspect.py::
# test_inspect_tolerates_unprocessed_placeholder_asset` already covers a
# mid-processing asset with the exact same null shape). 24 hours is generous
# relative to how quickly the app's own uploads are observed to process
# (minutes, not hours) -- the cost of waiting an extra day before a genuinely
# stuck row is reported as removable is far lower than the cost of proposing
# to remove a photo that was still mid-upload. Overridable via
# `find_placeholders`'/`apply_reconciliation`'s `age_threshold_seconds`
# (the CLI's `--max-age-hours`).
RECONCILE_AGE_THRESHOLD_SECONDS = 86400


@dataclass
class ReconcileResult:
    """Classification of a frame's assets against the placeholder predicate
    (D-14) and the age guard (D-15). Mirrors `auraframes/sync.py`'s
    `ExecutionResult`/`SyncPlan` plain-dataclass shape.

    `stuck`/`recently_created`/`unknown_age` are populated by
    `find_placeholders` (pure); `removed`/`failed` are populated by
    `apply_reconciliation` (mutating) acting on `stuck` only -- a row in
    `recently_created` or `unknown_age` is structurally never passed to a
    removal mechanism (D-15).
    """
    stuck: list = field(default_factory=list)
    recently_created: list = field(default_factory=list)
    unknown_age: list = field(default_factory=list)
    removed: list = field(default_factory=list)
    failed: list = field(default_factory=list)
    total_scanned: int = 0

    @property
    def placeholder_count(self) -> int:
        """The single number both `inspect` and `reconcile` print -- computed
        from one place so the two can never disagree (D-13)."""
        return len(self.stuck) + len(self.recently_created) + len(self.unknown_age)


def _creation_instant(asset):
    """Resolve `asset.created_at` to a parsed datetime, or `None` when the
    value is absent, empty, or unparseable. Never raises -- an asset from an
    undocumented, drifting API must never crash this module's pure
    classifier; an unresolvable creation time is handled by the caller as
    `unknown_age` (D-15's "fails toward not deleting" rule), not as an
    exception.
    """
    raw = getattr(asset, 'created_at', None)
    if not raw:
        return None
    try:
        return parse_aura_dt(raw)
    except (ValueError, TypeError):
        return None


def find_placeholders(assets, *, now=None,
                       age_threshold_seconds: float = RECONCILE_AGE_THRESHOLD_SECONDS) -> ReconcileResult:
    """Classify `assets` into stuck / recently-created / unknown-age
    placeholders (D-13/D-14/D-15). Pure -- no I/O, no network, no mutation
    of `assets` or any element of it.

    D-14: a row is a placeholder candidate only under the STRICT three-way
    conjunction `uploaded_at is None and file_name is None and md5_hash is
    None`. This is deliberately narrower than the diff engine's own
    hashless-asset bucket in `auraframes/sync.py`'s `compute_plan`, which
    counts every hashless asset including every video on the frame -- a
    video is hashless by design but does carry `file_name` and
    `uploaded_at`, so it trips at most one of the three conditions here and
    is excluded. A partially-hydrated asset (e.g. only `md5_hash` null,
    mid-server-side processing) likewise trips at most one condition and is
    excluded.

    D-15: a matching row's creation time decides which bucket it lands in.
    An unresolvable creation time (`_creation_instant` returns `None`) is
    treated EXACTLY like a too-young row -- `unknown_age`, never `stuck` --
    because being wrong here means proposing to remove a real photo, and the
    failure direction must be toward not deleting.

    :param assets: The frame's assets (e.g. from `Aura.get_all_assets`).
    :param now: The current instant, injected (mirrors `execute_plan`'s
        `clock` seam) so tests can control time deterministically. Defaults
        to `get_utc_now()` when `None`.
    :param age_threshold_seconds: Minimum age (in seconds) for a matching
        row to be reported as `stuck` rather than `recently_created`. See
        `RECONCILE_AGE_THRESHOLD_SECONDS`.
    :return: A `ReconcileResult` with `stuck`/`recently_created`/
        `unknown_age` populated and `removed`/`failed` left empty (this
        function never mutates anything).
    """
    if now is None:
        now = get_utc_now()

    result = ReconcileResult(total_scanned=len(assets))

    for asset in assets:
        if not (asset.uploaded_at is None and asset.file_name is None and asset.md5_hash is None):
            # Not a placeholder candidate at all -- a video (hashless but
            # named and uploaded) or a partially-hydrated asset each trip at
            # most one of the three conditions and are skipped entirely.
            continue

        instant = _creation_instant(asset)
        if instant is None:
            result.unknown_age.append(asset)
            continue

        age_seconds = (now - instant).total_seconds()
        if age_seconds < age_threshold_seconds:
            result.recently_created.append(asset)
        else:
            result.stuck.append(asset)

    return result
