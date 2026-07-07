"""Offline tests for `auraframes.sync.execute_plan` (Phase 8 Plan 02, Task 2).

`execute_plan` is exercised against the REST layer mocked via
`offline_aura()` (`httpx.MockTransport`), while S3/SQS are duck-typed fakes
injected as `s3_client=`/`sqs_client=` (RESEARCH.md Don't-Hand-Roll: inject
fakes, not a botocore Stubber). Zero network access, zero AWS credentials --
no real `S3Client`/`SQSClient` is ever constructed here.
"""
import httpx
import pytest
from loguru import logger
from PIL import Image

from auraframes.models.asset import Asset
from auraframes.sync import SyncPlan, execute_plan
from tests.offline import offline_aura

FRAME_ID = 'frame-fake-0001'
SELECT_ASSET_PATH = f'/v5/frames/{FRAME_ID}/select_asset.json'
REMOVE_ASSET_PATH = f'/v5/frames/{FRAME_ID}/remove_asset.json'
BATCH_UPDATE_PATH = '/v5/assets/batch_update.json'


@pytest.fixture(autouse=True)
def _reset_loguru():
    # loguru's `logger` is a process-global singleton; execute_plan's
    # trailing debug log could otherwise fire against a sink torn down by a
    # prior test (see tests/test_cli_sync.py's identical rationale).
    logger.remove()
    yield
    logger.remove()


def _write_jpeg(path, color=(255, 0, 0)):
    Image.new('RGB', (4, 4), color).save(path, format='JPEG')


def _asset(id_):
    return Asset.model_construct(id=id_, md5_hash='deadbeef', taken_at='2024-03-11T12:00:00.000Z')


def _default_overrides():
    """Canned success responses for every write endpoint execute_plan can
    reach -- select_asset/remove_asset report zero failures, batch_update
    returns a successes envelope. MockTransport routes purely on path, so
    the same response serves every upload/delete in a test."""
    return {
        SELECT_ASSET_PATH: httpx.Response(200, json={'number_failed': 0}),
        REMOVE_ASSET_PATH: httpx.Response(200, json={'number_failed': 0}),
        BATCH_UPDATE_PATH: httpx.Response(200, json={
            'ids': ['local-id'],
            'successes': [{'id': 'new-asset-id', 'local_identifier': 'local-id'}],
        }),
    }


class _FakeS3Client:
    """Duck-typed S3 fake -- records every upload_file call (and, if given a
    shared list, appends to it for cross-fake ordering proof)."""

    def __init__(self, call_order=None):
        self.upload_calls = []
        self.call_order = call_order if call_order is not None else []

    def upload_file(self, data: bytes, extension: str):
        self.upload_calls.append((data, extension))
        self.call_order.append('upload')
        return f'uploaded-{len(self.upload_calls)}{extension}', 'fake-md5-hash'


class _FakeSQSClient:
    """Duck-typed SQS fake -- get_queue_url records the frame_id it was
    queried with; receive_message is a no-op (execute_plan treats both
    polls as best-effort/observational only, per Pitfall 3)."""

    def __init__(self):
        self.queue_url_requests = []

    def get_queue_url(self, frame_id: str):
        self.queue_url_requests.append(frame_id)
        return f'https://sqs.fake/{frame_id}'

    def receive_message(self, queue_url, wait_time_seconds=5):
        return {}


def test_execute_plan_happy_path_uploads_and_deletes(tmp_path):
    path_a = tmp_path / 'a.jpg'
    path_b = tmp_path / 'b.jpg'
    _write_jpeg(path_a)
    _write_jpeg(path_b)
    plan = SyncPlan(to_upload=[path_a, path_b], to_delete=[_asset('asset-to-delete')])

    aura = offline_aura(overrides=_default_overrides())
    s3 = _FakeS3Client()
    sqs = _FakeSQSClient()

    result = execute_plan(plan, aura, FRAME_ID, s3_client=s3, sqs_client=sqs)

    assert result.upload_succeeded == 2
    assert result.delete_succeeded == 1
    assert result.upload_failures == []
    assert result.delete_failures == []
    assert len(s3.upload_calls) == 2
    assert sqs.queue_url_requests == [FRAME_ID]


def test_execute_plan_upload_partial_failure_continues_and_records(tmp_path, monkeypatch):
    path_a = tmp_path / 'a.jpg'
    path_b = tmp_path / 'b.jpg'
    _write_jpeg(path_a)
    _write_jpeg(path_b)
    plan = SyncPlan(to_upload=[path_a, path_b], to_delete=[])

    aura = offline_aura(overrides=_default_overrides())
    s3 = _FakeS3Client()
    sqs = _FakeSQSClient()

    original_batch_update = aura.asset_api.batch_update

    def _flaky_batch_update(asset_partial):
        # sorted(plan.to_upload) processes a.jpg first, so the first S3
        # upload call (whose fabricated filename starts with 'uploaded-1')
        # corresponds to path_a -- fail only that one.
        if asset_partial.file_name and asset_partial.file_name.startswith('uploaded-1'):
            raise RuntimeError('simulated batch_update failure')
        return original_batch_update(asset_partial)

    monkeypatch.setattr(aura.asset_api, 'batch_update', _flaky_batch_update)

    result = execute_plan(plan, aura, FRAME_ID, s3_client=s3, sqs_client=sqs)

    assert result.upload_succeeded == 1
    assert len(result.upload_failures) == 1
    failed_path, message = result.upload_failures[0]
    assert failed_path == path_a
    assert 'simulated batch_update failure' in message
    # The other upload still ran to completion -- loop did not abort (D-08).
    assert len(s3.upload_calls) == 2


def test_execute_plan_delete_partial_failure_continues_and_records(monkeypatch):
    plan = SyncPlan(to_upload=[], to_delete=[_asset('asset-good'), _asset('asset-bad')])

    aura = offline_aura(overrides=_default_overrides())
    s3 = _FakeS3Client()
    sqs = _FakeSQSClient()

    original_remove_asset = aura.frame_api.remove_asset

    def _flaky_remove_asset(frame_id, asset_partial_id):
        if asset_partial_id.id == 'asset-bad':
            raise RuntimeError('simulated remove_asset failure')
        return original_remove_asset(frame_id, asset_partial_id)

    monkeypatch.setattr(aura.frame_api, 'remove_asset', _flaky_remove_asset)

    result = execute_plan(plan, aura, FRAME_ID, s3_client=s3, sqs_client=sqs)

    assert result.delete_succeeded == 1
    assert result.delete_failures == [('asset-bad', 'simulated remove_asset failure')]


def test_execute_plan_all_uploads_precede_all_deletes(tmp_path, monkeypatch):
    path_a = tmp_path / 'a.jpg'
    _write_jpeg(path_a)
    plan = SyncPlan(to_upload=[path_a], to_delete=[_asset('asset-1'), _asset('asset-2')])

    aura = offline_aura(overrides=_default_overrides())
    call_order: list = []
    s3 = _FakeS3Client(call_order=call_order)
    sqs = _FakeSQSClient()

    original_remove_asset = aura.frame_api.remove_asset

    def _recording_remove_asset(frame_id, asset_partial_id):
        call_order.append('delete')
        return original_remove_asset(frame_id, asset_partial_id)

    monkeypatch.setattr(aura.frame_api, 'remove_asset', _recording_remove_asset)

    result = execute_plan(plan, aura, FRAME_ID, s3_client=s3, sqs_client=sqs)

    assert result.upload_succeeded == 1
    assert result.delete_succeeded == 2
    assert call_order == ['upload', 'delete', 'delete']
