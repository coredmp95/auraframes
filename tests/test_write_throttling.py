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
from auraframes.sync import SyncPlan, WRITE_THROTTLE_SECONDS, execute_plan
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
