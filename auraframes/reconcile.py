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

This module imports nothing Google-side, so it is decoupled from wherever
the Google side of this milestone eventually lands. It DOES reuse
`auraframes/sync.py`'s existing pacing primitives (`_chunked`,
`WRITE_THROTTLE_SECONDS`, `WRITE_BATCH_SIZE`) rather than duplicating them --
that is a one-way dependency only: `auraframes/sync.py` never imports from
or calls into this module (grep-verified absent, mirroring D-06's
structural-isolation convention in `sync.py` itself).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from auraframes.client import RateLimitError
from auraframes.models.asset import AssetPartialId
from auraframes.sync import WRITE_BATCH_SIZE, WRITE_THROTTLE_SECONDS, _chunked
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


# D-16: no removal mechanism is yet confirmed to work on these rows
# (`delete_asset` returns 200 and removes nothing; `remove_asset` 404s), so
# the first LIVE use of `apply_reconciliation` is a time-boxed probe, not a
# bulk operation. A cap keeps a mechanism that silently does nothing from
# burning the whole write budget before the operator notices, and keeps a
# mechanism that turns out to be destructive from acting on all 58+ known
# rows at once. `apply_reconciliation` raises when `len(result.stuck)`
# exceeds this unless the caller explicitly passes a higher
# `candidate_limit`.
RECONCILE_PROBE_CANDIDATE_LIMIT = 25


def _complete_placeholder(aura, frame_id, chunk):
    """Placeholder for the 'complete' mechanism (D-16): treating a stuck row
    as an incomplete upload to FINISH -- batch_update-ing it with real
    file_name/md5_hash/uploaded_at so it becomes an ordinary asset the
    existing hide/remove paths already handle -- rather than a bad row to
    delete. Not yet implemented, and STILL UNTESTED as of plan 11-05
    (2026-09-03) -- not because it was tried and failed, but because
    plan 11-05's live run found ZERO eligible `stuck`-bucket candidates on
    the live account to test any mechanism against: `/frames/{id}/assets.json`
    never sends a `created_at` key at all (confirmed via the raw JSON
    payload, not just the parsed model), so `_creation_instant` resolves
    every placeholder row to `unknown_age`, never `stuck`, regardless of
    `age_threshold_seconds`. All 53 placeholder rows observed that day
    landed in `unknown_age`. Widening what counts as eligible (e.g. an
    opt-in unknown-age policy) was explicitly considered and deferred to a
    follow-up plan rather than decided inside 11-05 -- see
    11-LIVE-FINDINGS.md for the full reasoning. This remains a genuinely
    open question, not a probed dead end."""
    raise NotImplementedError(
        "The 'complete' mechanism is not yet implemented, and was not live-probed by "
        "plan 11-05 (2026-09-03): the live account had zero eligible 'stuck'-bucket "
        "candidates to test it against (see the docstring above and 11-LIVE-FINDINGS.md)."
    )


# Dispatch table mirroring `auraframes/sync.py`'s `_REMOVAL_PRIMITIVE` shape.
# 'remove' and 'hard-delete' were both KNOWN, from PRIOR (Phase 10 UAT / debug
# session) live probing, NOT to clear these rows -- they are wired here
# anyway so `apply_reconciliation` can prove (or, more likely given what's
# already known, disprove) that on a small bounded batch, with the honest
# outcome recorded either way. Plan 11-05 (2026-09-03) did NOT get to
# re-probe 'remove'/'hard-delete' live either: the live account had zero
# eligible 'stuck'-bucket candidates that day (see `_complete_placeholder`'s
# docstring and 11-LIVE-FINDINGS.md) -- the prior findings stand as
# historical evidence, not freshly reconfirmed.
# 'complete' is the untried third option (D-16); it raises until a future
# plan builds it out.
_RECONCILE_PRIMITIVE = {
    'remove': lambda aura, frame_id, chunk: aura.frame_api.remove_asset(
        frame_id, [AssetPartialId(id=asset.id) for asset in chunk]),
    'hard-delete': lambda aura, frame_id, chunk: [
        aura.asset_api.delete_asset(asset) for asset in chunk],
    'complete': _complete_placeholder,
}

# Requests a removal chunk actually costs, per mechanism -- 'remove' is a
# batch endpoint (one call regardless of chunk size, mirroring
# auraframes/sync.py's _REMOVAL_REQUEST_COST['delete']); 'hard-delete' has
# no batch form and is charged per asset for the same reason
# auraframes/sync.py charges hard_delete per asset (a chunk-level charge of
# 1 would let it run the budget dry unnoticed). 'complete' is provisionally
# charged like 'hard-delete' (a per-asset batch_update call) pending 11-05.
_RECONCILE_REQUEST_COST = {
    'remove': lambda chunk: 1,
    'hard-delete': lambda chunk: len(chunk),
    'complete': lambda chunk: len(chunk),
}


def apply_reconciliation(result: ReconcileResult, aura, frame_id: str, *, mechanism: str = 'remove',
                          budget=None, wait_on_budget: bool = True, max_wait_seconds: float = 3600.0,
                          clock=get_utc_now, sleep=time.sleep, throttle_seconds: float = WRITE_THROTTLE_SECONDS,
                          batch_size: int = WRITE_BATCH_SIZE,
                          candidate_limit: int = RECONCILE_PROBE_CANDIDATE_LIMIT,
                          progress=lambda *args: None) -> ReconcileResult:
    """This module's ONLY mutating function (D-16) -- the sole place that
    calls a removal primitive against a live frame.

    Operates on `result.stuck` and NOTHING else -- every other classification
    bucket `find_placeholders` can populate is structurally unreachable from
    this function's body, which is the enforcement of D-15's "never a
    removal candidate" rule: a young or unresolvable-age row simply cannot
    reach a removal primitive through this code path, independent of any
    caller discipline.

    Raises a `ValueError` (D-16) when `len(result.stuck)` exceeds
    `candidate_limit` -- no removal mechanism is confirmed to work on these
    rows yet, so the first live use of this path is a bounded, time-boxed
    probe, not a bulk operation. Pass a higher `candidate_limit` to
    override.

    :param result: A `ReconcileResult` from `find_placeholders`. Only
        `result.stuck` is read; `result.removed`/`result.failed` are
        populated in place and the same object is returned.
    :param aura: An authenticated `Aura` instance.
    :param frame_id: The frame `result.stuck`'s rows belong to.
    :param mechanism: Which primitive to attempt -- `'remove'`
        (`FrameApi.remove_asset`, batch), `'hard-delete'`
        (`AssetApi.delete_asset`, per-asset, irreversible and account-wide),
        or `'complete'` (not yet implemented, see `_complete_placeholder`).
    :param budget: Optional `auraframes.ratelimit.WriteBudget` gating each
        chunk exactly like `execute_plan` -- the account-wide budget,
        shared with `sync`/`push`. `None` (the default) skips every
        budget-related touch point, a true byte-for-byte no-op.
    :param throttle_seconds: Seconds to pause before each write network
        call, mirroring `execute_plan`'s `throttle_seconds`. 0 disables.
    :param batch_size: Maximum number of candidates per removal-primitive
        call, mirroring `execute_plan`'s `batch_size`.
    :param candidate_limit: See `RECONCILE_PROBE_CANDIDATE_LIMIT`.
    :param progress: Optional reporter called once per resolved candidate as
        `progress('reconcile', asset_id, ok)`. Defaults to a no-op.
    :return: The same `ReconcileResult`, with `removed`/`failed` populated.

    Raises `RateLimitError` (from the client layer) WITHOUT catching it,
    mirroring `execute_plan`'s removal loop: a 429/475 throttle or lockout
    aborts the whole batch immediately rather than being recorded as one of
    N per-item failures.
    """
    candidates = result.stuck
    if len(candidates) > candidate_limit:
        raise ValueError(
            f'{len(candidates)} stuck placeholder row(s) exceeds RECONCILE_PROBE_CANDIDATE_LIMIT '
            f'({candidate_limit}) -- no removal mechanism is yet confirmed to work on these rows '
            f'(D-16), so this refuses to act on a large batch at once. Pass a higher '
            f'candidate_limit to override.'
        )

    def throttle() -> None:
        if throttle_seconds > 0:
            sleep(throttle_seconds)

    for chunk in _chunked(candidates, batch_size):
        if budget is not None:
            budget.acquire(_RECONCILE_REQUEST_COST[mechanism](chunk), wait=wait_on_budget,
                            max_wait=max_wait_seconds, now=clock(), sleep=sleep)
        try:
            throttle()
            _RECONCILE_PRIMITIVE[mechanism](aura, frame_id, chunk)
            for asset in chunk:
                result.removed.append(asset.id)
                progress('reconcile', asset.id, True)
        except RateLimitError:
            if budget is not None:
                budget.reconcile_tripped(clock())
                budget.save()
            raise
        except Exception as e:
            # remove_asset/delete_asset raising attributes the WHOLE chunk
            # as failed -- there is no per-item signal to fall back on
            # (remove_asset returns only a count; a mid-loop delete_asset
            # failure aborts the remaining per-asset calls in this chunk).
            for asset in chunk:
                result.failed.append((asset.id, str(e)))
                progress('reconcile', asset.id, False)

        if budget is not None:
            budget.save()

    return result
