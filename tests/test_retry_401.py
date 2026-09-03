"""Offline tests for `execute_plan`'s HTTP-401 verify-then-retry path
(Phase 11 Plan 01, Tasks 1-3 -- REL-01/REL-02/REL-03/REL-04, MOD-03).

Follows `tests/test_execute_plan.py`'s header-docstring, `_reset_loguru`
autouse fixture, `_FakeS3Client`/`_FakeSQSClient` and `_write_jpeg`
conventions. Drives `execute_plan` through `offline_aura(overrides=...)`
with STATEFUL callable overrides on the write endpoints (`tests/offline.py`'s
callable-override extension) so a single MockTransport route can answer
differently across successive calls (401 then 200), and drives the verify
probe via the injected `asset_probe=` keyword rather than routing
`/v5/assets/asset_for_local_identifier.json`, so landed/absent/inconclusive
are controlled directly rather than depending on a second live-shaped fixture.

Zero network access, zero AWS credentials -- no real S3Client/SQSClient/
Client transport is ever constructed here.
"""
import json

import httpx
import pytest
from loguru import logger
from PIL import Image

from auraframes.client import AuthenticationError
from auraframes.sync import SyncPlan, execute_plan
from tests.offline import offline_aura

FRAME_ID = 'frame-fake-0001'
SELECT_ASSET_PATH = f'/v5/frames/{FRAME_ID}/select_asset.json'
EXCLUDE_ASSET_PATH = f'/v5/frames/{FRAME_ID}/exclude_asset'
REMOVE_ASSET_PATH = f'/v5/frames/{FRAME_ID}/remove_asset.json'
BATCH_UPDATE_PATH = '/v5/assets/batch_update.json'
LOGIN_PATH = '/v5/login.json'


@pytest.fixture(autouse=True)
def _reset_loguru():
    # loguru's `logger` is a process-global singleton; execute_plan's
    # trailing debug log could otherwise fire against a sink torn down by a
    # prior test (see tests/test_execute_plan.py's identical rationale).
    logger.remove()
    yield
    logger.remove()


def _write_jpeg(path, color=(255, 0, 0)):
    Image.new('RGB', (4, 4), color).save(path, format='JPEG')


class _FakeS3Client:
    def __init__(self):
        self.upload_calls = []

    def upload_file(self, data: bytes, extension: str):
        self.upload_calls.append((data, extension))
        return f'uploaded-{len(self.upload_calls)}{extension}', 'fake-md5-hash'


class _FakeSQSClient:
    def __init__(self):
        self.queue_url_requests = []

    def get_queue_url(self, frame_id: str):
        self.queue_url_requests.append(frame_id)
        return f'https://sqs.fake/{frame_id}'

    def receive_message(self, queue_url, wait_time_seconds=5):
        return {}


def _sequenced_responses(*responses):
    """A MockTransport-callable override returning each `httpx.Response` in
    `responses` in order, repeating the LAST one once exhausted -- how these
    tests drive an endpoint that 401s on its first call and succeeds after."""
    state = {'i': 0}

    def handler(request: httpx.Request) -> httpx.Response:
        i = min(state['i'], len(responses) - 1)
        state['i'] += 1
        return responses[i]

    return handler


def _batch_update_recorder(*, fail_first: bool = False, always_fail: bool = False):
    """A MockTransport-callable override for `/v5/assets/batch_update.json`
    that records each call's sent `assets` list (for payload-shape
    assertions) and acknowledges every local_identifier it was sent --
    unless `fail_first` (401 on call 1 only) or `always_fail` (401 on every
    call) is set."""
    payloads: list = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        payloads.append(body['assets'])
        if always_fail or (fail_first and len(payloads) == 1):
            return httpx.Response(401, json={'error': 'unauthorized'})
        sent_ids = [a['local_identifier'] for a in body['assets']]
        return httpx.Response(200, json={
            'ids': sent_ids,
            'successes': [{'id': f'new-{lid}', 'local_identifier': lid} for lid in sent_ids],
        })

    return handler, payloads


def _ordered_probe(fates: list):
    """A fake `asset_probe` callable driving `_probe_landed`'s three-way
    classification directly, keyed by CALL ORDER (which matches `prepped`'s
    sorted-path order, since `_probe_landed` is fed `list(by_lid)` and
    `by_lid` is built from `prepped` in order) rather than by the real
    (uuid-generated, unpredictable) local_identifier values.

    Each entry in `fates` is `'landed'`, `'absent'`, or an int HTTP status
    code to raise as an inconclusive probe (any non-404 status)."""
    state = {'i': 0}

    def probe(local_identifier: str):
        fate = fates[state['i']]
        state['i'] += 1
        if fate == 'landed':
            return None
        status_code = 404 if fate == 'absent' else fate
        request = httpx.Request('GET', 'https://api.pushd.com/v5/assets/asset_for_local_identifier.json')
        response = httpx.Response(status_code, request=request)
        raise httpx.HTTPStatusError(f'probe returned {status_code}', request=request, response=response)

    return probe


def _unreachable_probe(local_identifier: str):
    raise AssertionError(f'probe should not have been called for {local_identifier}')


# ---------------------------------------------------------------------------
# Task 1: end-to-end 401 verify-then-retry for one upload chunk
# ---------------------------------------------------------------------------

def test_401_on_select_asset_recovers_after_relogin_and_resend(tmp_path):
    path = tmp_path / 'a.jpg'
    _write_jpeg(path)
    plan = SyncPlan(to_upload=[path], to_delete=[])

    select_asset_handler = _sequenced_responses(
        httpx.Response(401, json={'error': 'unauthorized'}),
        httpx.Response(200, json={'number_failed': 0}),
    )
    batch_update_handler, batch_payloads = _batch_update_recorder()
    aura = offline_aura(overrides={
        SELECT_ASSET_PATH: select_asset_handler,
        BATCH_UPDATE_PATH: batch_update_handler,
    })

    result = execute_plan(
        plan, aura, FRAME_ID, s3_client=_FakeS3Client(), sqs_client=_FakeSQSClient(),
        sleep=lambda *_: None, throttle_seconds=0, chunk_delay_seconds=0,
        asset_probe=_ordered_probe(['absent']),
    )

    assert result.upload_succeeded == 1
    assert result.upload_failures == []
    login_requests = [r for r in aura._client.history if r.request.url.path == LOGIN_PATH]
    assert len(login_requests) == 1
    assert len(batch_payloads) == 1  # only the retry's resend reaches batch_update


def test_two_item_chunk_401_resends_only_the_genuinely_absent_item(tmp_path):
    path_a = tmp_path / 'a.jpg'
    path_b = tmp_path / 'b.jpg'
    _write_jpeg(path_a)
    _write_jpeg(path_b)
    plan = SyncPlan(to_upload=[path_a, path_b], to_delete=[])

    batch_update_handler, batch_payloads = _batch_update_recorder(fail_first=True)
    aura = offline_aura(overrides={
        SELECT_ASSET_PATH: httpx.Response(200, json={'number_failed': 0}),
        BATCH_UPDATE_PATH: batch_update_handler,
    })

    # sorted(to_upload) => a.jpg, b.jpg -- probe call order matches: A
    # (a.jpg) already landed, B (b.jpg) genuinely absent.
    result = execute_plan(
        plan, aura, FRAME_ID, s3_client=_FakeS3Client(), sqs_client=_FakeSQSClient(),
        sleep=lambda *_: None, throttle_seconds=0, chunk_delay_seconds=0,
        asset_probe=_ordered_probe(['landed', 'absent']),
    )

    assert result.items_already_landed == 1
    assert result.upload_succeeded == 2
    assert result.upload_failures == []
    # First batch_update payload carried BOTH prepped items and 401'd; the
    # SECOND (the retry's resend) carries strictly fewer -- only item B.
    assert len(batch_payloads) == 2
    assert len(batch_payloads[0]) == 2
    assert len(batch_payloads[1]) == 1
    assert len(batch_payloads[1]) < len(batch_payloads[0])


def test_failed_relogin_raises_authentication_error_and_makes_no_further_write_calls(tmp_path):
    path = tmp_path / 'a.jpg'
    _write_jpeg(path)
    plan = SyncPlan(to_upload=[path], to_delete=[])

    select_calls: list = []

    def _select_asset_401(request: httpx.Request) -> httpx.Response:
        select_calls.append(request)
        return httpx.Response(401, json={'error': 'unauthorized'})

    batch_calls: list = []

    def _batch_update_recorder_only(request: httpx.Request) -> httpx.Response:
        batch_calls.append(request)
        return httpx.Response(200, json={'ids': [], 'successes': []})

    aura = offline_aura(overrides={
        SELECT_ASSET_PATH: _select_asset_401,
        BATCH_UPDATE_PATH: _batch_update_recorder_only,
    })

    def _failing_relogin():
        raise RuntimeError('bad credentials')

    with pytest.raises(AuthenticationError):
        execute_plan(
            plan, aura, FRAME_ID, s3_client=_FakeS3Client(), sqs_client=_FakeSQSClient(),
            sleep=lambda *_: None, throttle_seconds=0, chunk_delay_seconds=0,
            relogin=_failing_relogin, asset_probe=_unreachable_probe,
        )

    assert len(select_calls) == 1  # only the original, failing call
    assert batch_calls == []


def test_second_401_after_relogin_attributes_all_and_makes_no_third_attempt(tmp_path):
    path_a = tmp_path / 'a.jpg'
    path_b = tmp_path / 'b.jpg'
    _write_jpeg(path_a)
    _write_jpeg(path_b)
    plan = SyncPlan(to_upload=[path_a, path_b], to_delete=[])

    batch_update_handler, batch_payloads = _batch_update_recorder(always_fail=True)
    aura = offline_aura(overrides={
        SELECT_ASSET_PATH: httpx.Response(200, json={'number_failed': 0}),
        BATCH_UPDATE_PATH: batch_update_handler,
    })

    result = execute_plan(
        plan, aura, FRAME_ID, s3_client=_FakeS3Client(), sqs_client=_FakeSQSClient(),
        sleep=lambda *_: None, throttle_seconds=0, chunk_delay_seconds=0,
        relogin=lambda: None, asset_probe=_ordered_probe(['absent', 'absent']),
    )

    assert len(result.upload_failures) == 2
    assert {p for p, _ in result.upload_failures} == {path_a, path_b}
    # First attempt's batch_update + the ONE retry's resend -- no third.
    assert len(batch_payloads) == 2


def test_inconclusive_probe_is_never_resent_and_is_attributed_as_failure(tmp_path):
    path = tmp_path / 'a.jpg'
    _write_jpeg(path)
    plan = SyncPlan(to_upload=[path], to_delete=[])

    select_asset_handler = _sequenced_responses(
        httpx.Response(401, json={'error': 'unauthorized'}),
        httpx.Response(200, json={'number_failed': 0}),
    )
    batch_calls: list = []

    def _batch_update_recorder_only(request: httpx.Request) -> httpx.Response:
        batch_calls.append(request)
        return httpx.Response(200, json={'ids': [], 'successes': []})

    aura = offline_aura(overrides={
        SELECT_ASSET_PATH: select_asset_handler,
        BATCH_UPDATE_PATH: _batch_update_recorder_only,
    })

    result = execute_plan(
        plan, aura, FRAME_ID, s3_client=_FakeS3Client(), sqs_client=_FakeSQSClient(),
        sleep=lambda *_: None, throttle_seconds=0, chunk_delay_seconds=0,
        relogin=lambda: None, asset_probe=_ordered_probe([500]),
    )

    assert result.upload_succeeded == 0
    assert len(result.upload_failures) == 1
    failed_path, reason = result.upload_failures[0]
    assert failed_path == path
    assert 'inconclusive' in reason
    assert batch_calls == []  # never resent -- an ambiguous probe must not re-send


def test_chunk_where_every_file_fails_prep_issues_no_select_asset_call(tmp_path):
    # '.png' has no data_uti mapping yet (D-11/D-12 land in a later plan),
    # so _prep_upload fails closed on it without ever needing the file to
    # exist -- the whole point of this test is that the chunk never reaches
    # a network call at all.
    bad_path = tmp_path / 'photo.png'
    plan = SyncPlan(to_upload=[bad_path], to_delete=[])

    select_calls: list = []

    def _select_asset_recorder(request: httpx.Request) -> httpx.Response:
        select_calls.append(request)
        return httpx.Response(200, json={'number_failed': 0})

    aura = offline_aura(overrides={SELECT_ASSET_PATH: _select_asset_recorder})

    result = execute_plan(
        plan, aura, FRAME_ID, s3_client=_FakeS3Client(), sqs_client=_FakeSQSClient(),
        sleep=lambda *_: None, throttle_seconds=0, chunk_delay_seconds=0,
    )

    assert len(result.upload_failures) == 1
    assert select_calls == []
    assert result.chunks_retried == 0
