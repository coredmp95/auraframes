"""Offline tests for the write-call throttling and rate-limit batch-abort
behavior in `auraframes.sync.execute_plan` (select-asset-401-unauthorized
preventive fix, parts 1 & 3).

Proves:
  * every write network call (both select_asset calls + batch_update per
    upload, and each remove_asset per delete) is paced by a `sleep(seconds)`
    call, so a bulk apply is throttled rather than fired as a burst;
  * `throttle_seconds=0` disables pacing entirely;
  * a `RateLimitError` from any write aborts the WHOLE batch (propagates,
    is not recorded as one of N per-item failures, and stops further items)
    -- the anti-abuse back-off behavior.

All through `tests/offline.py`'s MockTransport harness + duck-typed S3/SQS
fakes: zero network, no AWS credentials, and an injected fake `sleep` so no
real time passes.
"""
import httpx
import pytest
from loguru import logger
from PIL import Image

from auraframes.client import RateLimitError
from auraframes.models.asset import Asset
from auraframes.sync import (
    ConsecutiveWriteFailureError,
    MAX_CONSECUTIVE_WRITE_FAILURES,
    SyncPlan,
    WRITE_THROTTLE_SECONDS,
    execute_plan,
)
from tests.offline import offline_aura

FRAME_ID = 'frame-fake-0001'
SELECT_ASSET_PATH = f'/v5/frames/{FRAME_ID}/select_asset.json'
REMOVE_ASSET_PATH = f'/v5/frames/{FRAME_ID}/remove_asset.json'
BATCH_UPDATE_PATH = '/v5/assets/batch_update.json'


@pytest.fixture(autouse=True)
def _reset_loguru():
    logger.remove()
    yield
    logger.remove()


def _write_jpeg(path, color=(255, 0, 0)):
    Image.new('RGB', (4, 4), color).save(path, format='JPEG')


def _asset(id_):
    return Asset.model_construct(id=id_, md5_hash='deadbeef', taken_at='2024-03-11T12:00:00.000Z')


def _ok_overrides():
    return {
        SELECT_ASSET_PATH: httpx.Response(200, json={'number_failed': 0}),
        REMOVE_ASSET_PATH: httpx.Response(200, json={'number_failed': 0}),
        BATCH_UPDATE_PATH: httpx.Response(200, json={
            'ids': ['local-id'],
            'successes': [{'id': 'new-asset-id', 'local_identifier': 'local-id'}],
        }),
    }


class _FakeS3Client:
    def __init__(self):
        self.upload_calls = []

    def upload_file(self, data: bytes, extension: str):
        self.upload_calls.append((data, extension))
        return f'uploaded-{len(self.upload_calls)}{extension}', 'fake-md5-hash'


class _FakeSQSClient:
    def get_queue_url(self, frame_id: str):
        return f'https://sqs.fake/{frame_id}'

    def receive_message(self, queue_url, wait_time_seconds=5):
        return {}


class _SleepRecorder:
    def __init__(self):
        self.calls = []

    def __call__(self, seconds):
        self.calls.append(seconds)


# ---------------------------------------------------------------------------
# Throttling (part 1)
# ---------------------------------------------------------------------------

def test_each_write_call_is_throttled_for_an_upload(tmp_path):
    path_a = tmp_path / 'a.jpg'
    _write_jpeg(path_a)
    plan = SyncPlan(to_upload=[path_a], to_delete=[])
    sleep = _SleepRecorder()

    execute_plan(
        plan, offline_aura(overrides=_ok_overrides()), FRAME_ID,
        s3_client=_FakeS3Client(), sqs_client=_FakeSQSClient(), sleep=sleep,
    )

    # One upload issues 3 write network calls (select_asset x2 + batch_update),
    # each paced by a sleep at the default interval.
    assert sleep.calls == [WRITE_THROTTLE_SECONDS] * 3


def test_each_write_call_is_throttled_for_a_delete():
    plan = SyncPlan(to_upload=[], to_delete=[_asset('x1'), _asset('x2')])
    sleep = _SleepRecorder()

    execute_plan(
        plan, offline_aura(overrides=_ok_overrides()), FRAME_ID,
        s3_client=_FakeS3Client(), sqs_client=_FakeSQSClient(), sleep=sleep,
    )

    # One remove_asset per delete, each paced.
    assert sleep.calls == [WRITE_THROTTLE_SECONDS] * 2


def test_throttle_uses_supplied_interval(tmp_path):
    path_a = tmp_path / 'a.jpg'
    _write_jpeg(path_a)
    plan = SyncPlan(to_upload=[path_a], to_delete=[])
    sleep = _SleepRecorder()

    execute_plan(
        plan, offline_aura(overrides=_ok_overrides()), FRAME_ID,
        s3_client=_FakeS3Client(), sqs_client=_FakeSQSClient(),
        throttle_seconds=2.5, sleep=sleep,
    )

    assert sleep.calls == [2.5, 2.5, 2.5]


def test_throttle_seconds_zero_disables_sleeping(tmp_path):
    path_a = tmp_path / 'a.jpg'
    _write_jpeg(path_a)
    plan = SyncPlan(to_upload=[path_a], to_delete=[_asset('x1')])
    sleep = _SleepRecorder()

    execute_plan(
        plan, offline_aura(overrides=_ok_overrides()), FRAME_ID,
        s3_client=_FakeS3Client(), sqs_client=_FakeSQSClient(),
        throttle_seconds=0, sleep=sleep,
    )

    assert sleep.calls == []


# ---------------------------------------------------------------------------
# Rate-limit batch abort (part 3)
# ---------------------------------------------------------------------------

def test_rate_limited_upload_aborts_whole_batch(tmp_path):
    # 475 on select_asset must abort the entire apply, NOT be recorded as one
    # of N per-item upload failures (that was the confusing 120x-401 symptom).
    path_a = tmp_path / 'a.jpg'
    path_b = tmp_path / 'b.jpg'
    _write_jpeg(path_a)
    _write_jpeg(path_b)
    plan = SyncPlan(to_upload=[path_a, path_b], to_delete=[_asset('x1')])

    overrides = _ok_overrides()
    overrides[SELECT_ASSET_PATH] = httpx.Response(475, json={'message': 'locked out'})
    s3 = _FakeS3Client()

    with pytest.raises(RateLimitError):
        execute_plan(
            plan, offline_aura(overrides=overrides), FRAME_ID,
            s3_client=s3, sqs_client=_FakeSQSClient(),
            throttle_seconds=0, sleep=lambda *_: None,
        )

    # Aborted at the very first write -- no S3 upload, no second item attempted.
    assert s3.upload_calls == []


def test_rate_limited_delete_aborts_and_does_not_record_per_item(monkeypatch):
    plan = SyncPlan(to_upload=[], to_delete=[_asset('x1'), _asset('x2')])

    overrides = _ok_overrides()
    overrides[REMOVE_ASSET_PATH] = httpx.Response(429, headers={'Retry-After': '60'},
                                                  json={'message': 'too many'})

    with pytest.raises(RateLimitError) as exc_info:
        execute_plan(
            plan, offline_aura(overrides=overrides), FRAME_ID,
            s3_client=_FakeS3Client(), sqs_client=_FakeSQSClient(),
            throttle_seconds=0, sleep=lambda *_: None,
        )

    assert exc_info.value.status_code == 429
    assert exc_info.value.retry_after == 60


def test_ordinary_per_item_failure_still_recorded_not_aborted(tmp_path):
    # A non-rate-limit failure (nonzero number_failed) must still be caught
    # per-item and the loop continue -- the D-08 fail-loud-but-continue
    # behavior is preserved for genuine per-item errors.
    path_a = tmp_path / 'a.jpg'
    path_b = tmp_path / 'b.jpg'
    _write_jpeg(path_a)
    _write_jpeg(path_b)
    plan = SyncPlan(to_upload=[path_a, path_b], to_delete=[])

    overrides = _ok_overrides()
    overrides[SELECT_ASSET_PATH] = httpx.Response(200, json={'number_failed': 1})

    result = execute_plan(
        plan, offline_aura(overrides=overrides), FRAME_ID,
        s3_client=_FakeS3Client(), sqs_client=_FakeSQSClient(),
        throttle_seconds=0, sleep=lambda *_: None,
    )

    # Both items failed per-item (not aborted), each recorded by name.
    assert result.upload_succeeded == 0
    assert len(result.upload_failures) == 2


# ---------------------------------------------------------------------------
# Consecutive-failure-run backstop (REOPENED-gap fix)
#
# The anti-abuse trip did NOT always announce itself with the 429/475 that
# RateLimitError catches -- the live regression saw a plain HTTP 401 on every
# write after the 7th succeeded, so execute_plan caught each of the 103
# post-trip failures per-item and kept hammering. These prove a RUN of N
# consecutive write failures (status-code agnostic) aborts the batch, while an
# isolated failure (surrounded by successes) never does.
# ---------------------------------------------------------------------------

def _write_jpegs(tmp_path, n):
    paths = []
    for i in range(n):
        p = tmp_path / f'{i:02d}.jpg'
        _write_jpeg(p)
        paths.append(p)
    return paths


def test_run_of_plain_401_write_failures_aborts_batch(tmp_path):
    # The exact live regression: plain HTTP 401 (NOT 429/475, NOT a
    # RateLimitError) on every select_asset. A run of them must abort the whole
    # batch after MAX_CONSECUTIVE_WRITE_FAILURES rather than dutifully failing
    # all N items one by one.
    paths = _write_jpegs(tmp_path, 7)
    plan = SyncPlan(to_upload=paths, to_delete=[])

    overrides = _ok_overrides()
    overrides[SELECT_ASSET_PATH] = httpx.Response(401, json={'error': 'unauthorized'})
    s3 = _FakeS3Client()

    with pytest.raises(ConsecutiveWriteFailureError) as exc_info:
        execute_plan(
            plan, offline_aura(overrides=overrides), FRAME_ID,
            s3_client=s3, sqs_client=_FakeSQSClient(),
            throttle_seconds=0, sleep=lambda *_: None,
        )

    err = exc_info.value
    assert err.count == MAX_CONSECUTIVE_WRITE_FAILURES
    # Aborted after exactly N attempts -- the remaining 2 items were never
    # attempted (did not hammer all 7).
    assert len(err.result.upload_failures) == MAX_CONSECUTIVE_WRITE_FAILURES
    # select_asset fails before any S3 upload, so nothing was uploaded.
    assert s3.upload_calls == []
    # The distinct message, not the RateLimitError "Retry after" wording.
    assert 'consecutive write failures' in str(err)


def test_interspersed_failures_do_not_trip_the_backstop(tmp_path, monkeypatch):
    # Failures scattered among successes (max run of 1) must NEVER abort -- an
    # isolated bad/expired asset ref or a one-off permissions edge is not a
    # lockout. 8 uploads, every other one fails at batch_update.
    paths = _write_jpegs(tmp_path, 8)
    plan = SyncPlan(to_upload=paths, to_delete=[])
    aura = offline_aura(overrides=_ok_overrides())

    original_batch_update = aura.asset_api.batch_update

    def _flaky_batch_update(asset_partial):
        # s3 fake names files 'uploaded-N.jpg'; N increments per processed
        # upload. Fail odd N so failures never run 2-in-a-row.
        n = int(asset_partial.file_name.split('-')[1].split('.')[0])
        if n % 2 == 1:
            raise RuntimeError('isolated per-item failure')
        return original_batch_update(asset_partial)

    monkeypatch.setattr(aura.asset_api, 'batch_update', _flaky_batch_update)

    result = execute_plan(
        plan, aura, FRAME_ID,
        s3_client=_FakeS3Client(), sqs_client=_FakeSQSClient(),
        throttle_seconds=0, sleep=lambda *_: None,
    )

    # No abort: all 8 attempted, 4 succeeded, 4 recorded per-item (D-08 intact).
    assert result.upload_succeeded == 4
    assert len(result.upload_failures) == 4


def test_a_success_resets_the_consecutive_run(tmp_path, monkeypatch):
    # A run of 4 failures, then ONE success, then 4 more failures must NOT
    # abort even though 8 total failures occur -- only an unbroken run of N
    # trips it, so the counter must reset on success.
    paths = _write_jpegs(tmp_path, 9)
    plan = SyncPlan(to_upload=paths, to_delete=[])
    aura = offline_aura(overrides=_ok_overrides())

    original_batch_update = aura.asset_api.batch_update

    def _flaky_batch_update(asset_partial):
        n = int(asset_partial.file_name.split('-')[1].split('.')[0])
        # Uploads 1-4 fail, upload 5 succeeds (reset), uploads 6-9 fail.
        if n != 5:
            raise RuntimeError('per-item failure')
        return original_batch_update(asset_partial)

    monkeypatch.setattr(aura.asset_api, 'batch_update', _flaky_batch_update)

    result = execute_plan(
        plan, aura, FRAME_ID,
        s3_client=_FakeS3Client(), sqs_client=_FakeSQSClient(),
        throttle_seconds=0, sleep=lambda *_: None,
    )

    assert result.upload_succeeded == 1
    assert len(result.upload_failures) == 8


def test_max_consecutive_failures_zero_disables_the_backstop(tmp_path):
    # 0 restores the pure unbounded per-item D-08 behaviour: every item is
    # attempted and recorded, no ConsecutiveWriteFailureError.
    paths = _write_jpegs(tmp_path, 6)
    plan = SyncPlan(to_upload=paths, to_delete=[])

    overrides = _ok_overrides()
    overrides[SELECT_ASSET_PATH] = httpx.Response(401, json={'error': 'unauthorized'})

    result = execute_plan(
        plan, offline_aura(overrides=overrides), FRAME_ID,
        s3_client=_FakeS3Client(), sqs_client=_FakeSQSClient(),
        throttle_seconds=0, sleep=lambda *_: None,
        max_consecutive_failures=0,
    )

    assert result.upload_succeeded == 0
    assert len(result.upload_failures) == 6


def test_consecutive_run_spans_upload_and_delete_phases(tmp_path):
    # The run counter carries across the upload->delete boundary (reset only on
    # a success): 3 upload failures (below threshold) then delete failures push
    # the run to N and abort in the delete loop.
    paths = _write_jpegs(tmp_path, 3)
    plan = SyncPlan(to_upload=paths, to_delete=[_asset('d1'), _asset('d2'), _asset('d3')])

    overrides = _ok_overrides()
    overrides[SELECT_ASSET_PATH] = httpx.Response(401, json={'error': 'unauthorized'})
    overrides[REMOVE_ASSET_PATH] = httpx.Response(401, json={'error': 'unauthorized'})

    with pytest.raises(ConsecutiveWriteFailureError) as exc_info:
        execute_plan(
            plan, offline_aura(overrides=overrides), FRAME_ID,
            s3_client=_FakeS3Client(), sqs_client=_FakeSQSClient(),
            throttle_seconds=0, sleep=lambda *_: None,
        )

    err = exc_info.value
    assert err.count == MAX_CONSECUTIVE_WRITE_FAILURES
    # 3 uploads failed (run 1-3), then 2 deletes failed (run 4-5 -> abort);
    # the 3rd delete is never attempted.
    assert len(err.result.upload_failures) == 3
    assert len(err.result.delete_failures) == 2
