"""Offline tests for `auraframes.reconcile` (Phase 11 Plan 03, Task 1) --
the pure placeholder predicate (`find_placeholders`) and the age guard.

Unmarked (no @pytest.mark.live) -- pure model-construction + pure-function
tests, zero network access and no credentials required. `find_placeholders`
is exercised with plain `Asset` model instances only; no `offline_aura`
transport is ever constructed in this module, which is itself the proof
that classification performs no network call.
"""
import json
from datetime import datetime, timedelta

import pytest
from loguru import logger

from auraframes.models.asset import Asset
from auraframes.reconcile import ReconcileResult, find_placeholders
from auraframes.utils.dt import format_dt_to_aura
from tests.offline import FIXTURES_DIR

RECENT_TOKEN = '__RECENT_CREATED_AT_TOKEN__'
# Fixed reference instant for every test below -- far enough in the future
# of the fixture's hardcoded old dates (2020/2023) that those rows are
# unambiguously "old" without depending on wall-clock time at test-run time.
NOW = datetime(2030, 6, 15, 12, 0, 0)
# Default fill for the recently-created row's token when a test doesn't care
# about that row -- old enough (relative to NOW) that it can never
# accidentally land in `recently_created` and pollute an unrelated
# assertion.
_OLD_FILL = '2020-01-01T00:00:00.000Z'


@pytest.fixture(autouse=True)
def _reset_loguru():
    # loguru's `logger` is a process-global singleton; reset around each
    # test so no sink from a prior test/module can fire unexpectedly here.
    logger.remove()
    yield
    logger.remove()


def _load_placeholder_assets(recent_created_at: str = _OLD_FILL) -> list[Asset]:
    """Load tests/fixtures/assets_placeholders.json, substituting the
    recently-created row's placeholder token for `recent_created_at`, and
    hydrate every entry through the real `Asset` model (proving the fixture
    is real-shaped, not just a JSON blob)."""
    data = json.loads((FIXTURES_DIR / 'assets_placeholders.json').read_text())
    for entry in data['assets']:
        if entry.get('created_at') == RECENT_TOKEN:
            entry['created_at'] = recent_created_at
    return [Asset(**a) for a in data['assets']]


def _ids(assets) -> set:
    return {a.id for a in assets}


# ---------------------------------------------------------------------------
# Test 1: a stuck placeholder (older than the threshold) lands in `stuck`.
# ---------------------------------------------------------------------------

def test_stuck_placeholder_older_than_threshold_lands_in_stuck():
    assets = _load_placeholder_assets()

    result = find_placeholders(assets, now=NOW)

    assert {'asset-fake-stuck-001', 'asset-fake-stuck-002'} <= _ids(result.stuck)
    assert result.total_scanned == len(assets)


# ---------------------------------------------------------------------------
# Test 2: a video-shaped asset (md5_hash None, file_name/uploaded_at
# populated) lands in neither `stuck` nor `recently_created` -- the strict
# conjunction excludes it. It must not appear in `unknown_age` either.
# ---------------------------------------------------------------------------

def test_video_shaped_asset_excluded_from_every_bucket():
    assets = _load_placeholder_assets()

    result = find_placeholders(assets, now=NOW)

    every_bucket = _ids(result.stuck) | _ids(result.recently_created) | _ids(result.unknown_age)
    assert 'asset-fake-video-001' not in every_bucket


# ---------------------------------------------------------------------------
# Test 3: a partially-hydrated asset (only md5_hash None, or only file_name
# None) is likewise excluded from every bucket.
# ---------------------------------------------------------------------------

def test_partially_hydrated_assets_excluded_from_every_bucket():
    only_md5_null = Asset.model_construct(
        id='partial-only-md5-null', uploaded_at='2020-01-01T00:00:00.000Z',
        file_name='x.jpg', md5_hash=None, created_at='2020-01-01T00:00:00.000Z',
    )
    only_file_name_null = Asset.model_construct(
        id='partial-only-file-name-null', uploaded_at='2020-01-01T00:00:00.000Z',
        file_name=None, md5_hash='abc123', created_at='2020-01-01T00:00:00.000Z',
    )

    result = find_placeholders([only_md5_null, only_file_name_null], now=NOW)

    assert result.stuck == []
    assert result.recently_created == []
    assert result.unknown_age == []
    assert result.total_scanned == 2


# ---------------------------------------------------------------------------
# Test 4: a matching asset whose creation time is 1 hour old lands in
# `recently_created`, not `stuck`, at the 24h default threshold.
# ---------------------------------------------------------------------------

def test_recently_created_placeholder_at_default_threshold():
    one_hour_ago = format_dt_to_aura(NOW - timedelta(hours=1))
    assets = _load_placeholder_assets(recent_created_at=one_hour_ago)

    result = find_placeholders(assets, now=NOW)

    assert 'asset-fake-recent-001' in _ids(result.recently_created)
    assert 'asset-fake-recent-001' not in _ids(result.stuck)


# ---------------------------------------------------------------------------
# Test 5: the same asset with age_threshold_seconds=1800 (30 min) lands in
# `stuck` -- the threshold is genuinely overridable.
# ---------------------------------------------------------------------------

def test_overridden_age_threshold_reclassifies_the_same_row_as_stuck():
    one_hour_ago = format_dt_to_aura(NOW - timedelta(hours=1))
    assets = _load_placeholder_assets(recent_created_at=one_hour_ago)

    result = find_placeholders(assets, now=NOW, age_threshold_seconds=1800)

    assert 'asset-fake-recent-001' in _ids(result.stuck)
    assert 'asset-fake-recent-001' not in _ids(result.recently_created)


# ---------------------------------------------------------------------------
# Test 6: an asset matching the predicate with no resolvable creation time
# lands in `unknown_age`, never in `stuck`.
# ---------------------------------------------------------------------------

def test_unresolvable_creation_time_lands_in_unknown_age_never_stuck():
    assets = _load_placeholder_assets()

    result = find_placeholders(assets, now=NOW)

    assert 'asset-fake-unknown-age-001' in _ids(result.unknown_age)
    assert 'asset-fake-unknown-age-001' not in _ids(result.stuck)


def test_unresolvable_creation_time_still_excludes_unparseable_string():
    # _creation_instant must never raise on a garbage created_at value --
    # the same "fails toward not deleting" rule as an absent value.
    garbage = Asset.model_construct(
        id='garbage-created-at', uploaded_at=None, file_name=None, md5_hash=None,
        created_at='not-a-real-timestamp',
    )

    result = find_placeholders([garbage], now=NOW)

    assert 'garbage-created-at' in _ids(result.unknown_age)
    assert result.stuck == []


# ---------------------------------------------------------------------------
# Test 7: find_placeholders([]) returns a well-defined, non-crashing result.
# ---------------------------------------------------------------------------

def test_find_placeholders_empty_list_returns_well_defined_empty_result():
    result = find_placeholders([])

    assert isinstance(result, ReconcileResult)
    assert result.stuck == []
    assert result.recently_created == []
    assert result.unknown_age == []
    assert result.removed == []
    assert result.failed == []
    assert result.total_scanned == 0
    assert result.placeholder_count == 0


# ---------------------------------------------------------------------------
# find_placeholders performs no network call: exercised here with plain
# Asset model objects and no offline_aura transport anywhere in this module.
# ---------------------------------------------------------------------------

def test_find_placeholders_performs_no_network_call():
    assets = _load_placeholder_assets()

    result = find_placeholders(assets, now=NOW)

    assert result.total_scanned == len(assets)


def test_placeholder_count_sums_all_three_buckets():
    assets = _load_placeholder_assets()

    result = find_placeholders(assets, now=NOW)

    assert result.placeholder_count == (
        len(result.stuck) + len(result.recently_created) + len(result.unknown_age)
    )
    # Default load uses _OLD_FILL for the recent-created row's token, so it
    # classifies as stuck too: 3 stuck (stuck-001, stuck-002, recent-001) + 0
    # recently_created + 1 unknown_age (unknown-age-001) = 4.
    assert result.placeholder_count == 4
