"""Offline tests for `aura-cli sync --apply` (auraframes.cli.run_sync's
apply/confirm/execute branch, Phase 8 Plan 03). Calls run_sync() directly
(never main()) so load_dotenv() is not invoked and a filesystem .env cannot
interfere.

`execute_plan`/`S3Client`/`SQSClient` are all monkeypatched on the
`auraframes.cli` namespace -- these tests never touch the network or AWS,
matching tests/test_cli_sync.py's offline-only convention.
"""
import copy
import json
from pathlib import Path

import httpx
import pytest
from loguru import logger

import auraframes.cli as cli
from auraframes.aws.s3client import get_md5
from auraframes.client import RateLimitError
from auraframes.sync import ConsecutiveWriteFailureError, ExecutionResult
from tests.offline import offline_aura

FIXTURES_DIR = Path(__file__).parent / 'fixtures'


def _frame_asset(**overrides):
    """A frame-side Asset payload (from assets_page1.json) with overridable
    fields -- used to seed a delete candidate (an asset whose md5 has no local
    match) so `push`'s no-delete guarantee can be proven."""
    data = json.loads((FIXTURES_DIR / 'assets_page1.json').read_text())
    asset = copy.deepcopy(data['assets'][0])
    asset.update(overrides)
    return asset

FRAME_ID = 'frame-fake-0001'
FRAME_NAME = 'Fake Frame'
ASSETS_PATH = f'/v5/frames/{FRAME_ID}/assets.json'


@pytest.fixture(autouse=True)
def _reset_loguru(tmp_path_factory, monkeypatch):
    # Mirrors tests/test_cli_sync.py's fixture: chdir into a dedicated
    # scratch dir (not the test's own tmp_path, which several tests pass
    # directly as dir_arg) so _configure_cli_logging's logs/ side effect
    # can't pollute scan_directory's traversal or the real working tree.
    monkeypatch.chdir(tmp_path_factory.mktemp('cli-apply-logging-cwd'))
    logger.remove()
    yield
    logger.remove()


def _env(monkeypatch):
    monkeypatch.setenv('AURA_EMAIL', 'you@example.invalid')
    monkeypatch.setenv('AURA_PASSWORD', 'super-secret-pw')


def _assets_response(*assets):
    return httpx.Response(200, json={'assets': list(assets), 'next_page_cursor': None})


class _FakeS3Client:
    """Trivial stand-in for auraframes.aws.s3client.S3Client -- constructed
    but never used since execute_plan itself is monkeypatched below; its
    only job is to prove no real Cognito auth fires."""

    def __init__(self, *args, **kwargs):
        pass


class _FakeSQSClient:
    """Trivial stand-in for auraframes.aws.sqsclient.SQSClient (see
    _FakeS3Client)."""

    def __init__(self, *args, **kwargs):
        pass


def _patch_aws_clients(monkeypatch):
    monkeypatch.setattr(cli, 'S3Client', _FakeS3Client)
    monkeypatch.setattr(cli, 'SQSClient', _FakeSQSClient)


def _patch_execute_plan(monkeypatch, result=None):
    """Monkeypatch auraframes.cli.execute_plan with a fake that records each
    call's arguments and returns a controllable ExecutionResult (clean by
    default). Returns the list of recorded calls for assertions."""
    calls = []

    def fake_execute_plan(plan, aura, frame_id, *, s3_client, sqs_client, progress=None, on_wait=None,
                          batch_size=None, chunk_delay_seconds=None, **kwargs):
        # **kwargs absorbs Phase 09's budget/geo_check/wait_on_budget/
        # max_wait_seconds -- run_sync forwards these by default now
        # (ANTI-06), but this pre-existing fake's callers don't assert on
        # them, so they're accepted-and-ignored rather than tracked.
        calls.append({
            'plan': plan,
            'aura': aura,
            'frame_id': frame_id,
            's3_client': s3_client,
            'sqs_client': sqs_client,
            'batch_size': batch_size,
            'chunk_delay_seconds': chunk_delay_seconds,
        })
        return result if result is not None else ExecutionResult()

    monkeypatch.setattr(cli, 'execute_plan', fake_execute_plan)
    return calls


def test_apply_false_no_prompt_no_execution(tmp_path, monkeypatch, capsys):
    _env(monkeypatch)
    _patch_aws_clients(monkeypatch)
    calls = _patch_execute_plan(monkeypatch)

    (tmp_path / 'new.jpg').write_bytes(b'new-photo-bytes')
    aura = offline_aura(overrides={ASSETS_PATH: _assets_response()})

    rc = cli.run_sync(str(tmp_path), 'Fake', aura=aura)

    assert rc == 0
    assert calls == []
    out = capsys.readouterr().out
    assert 'To upload: 1' in out
    assert 'Proceed?' not in out
    assert 'Uploads:' not in out


def test_apply_yes_executes_without_prompt(tmp_path, monkeypatch, capsys):
    _env(monkeypatch)
    _patch_aws_clients(monkeypatch)
    calls = _patch_execute_plan(monkeypatch, result=ExecutionResult(upload_succeeded=1, delete_succeeded=0))

    (tmp_path / 'new.jpg').write_bytes(b'new-photo-bytes')
    aura = offline_aura(overrides={ASSETS_PATH: _assets_response()})

    rc = cli.run_sync(str(tmp_path), 'Fake', apply=True, yes=True, aura=aura)

    assert rc == 0
    assert len(calls) == 1
    assert calls[0]['frame_id'] == FRAME_ID
    out = capsys.readouterr().out
    assert 'Proceed?' not in out
    assert 'Uploads: 1 succeeded, 0 failed' in out
    assert 'Deletes: 0 succeeded, 0 failed' in out


def test_apply_non_tty_without_yes_fails_closed(tmp_path, monkeypatch, capsys):
    _env(monkeypatch)
    _patch_aws_clients(monkeypatch)
    calls = _patch_execute_plan(monkeypatch)
    monkeypatch.setattr(cli.sys.stdin, 'isatty', lambda: False)

    aura = offline_aura(overrides={ASSETS_PATH: _assets_response()})

    rc = cli.run_sync(str(tmp_path), 'Fake', apply=True, yes=False, aura=aura)

    assert rc == 1
    assert calls == []
    out = capsys.readouterr().out
    assert '--apply requires --yes when running non-interactively' in out


def test_apply_interactive_abort_on_non_y_answer(tmp_path, monkeypatch, capsys):
    _env(monkeypatch)
    _patch_aws_clients(monkeypatch)
    calls = _patch_execute_plan(monkeypatch)
    monkeypatch.setattr(cli.sys.stdin, 'isatty', lambda: True)
    monkeypatch.setattr('builtins.input', lambda prompt='': 'n')

    aura = offline_aura(overrides={ASSETS_PATH: _assets_response()})

    rc = cli.run_sync(str(tmp_path), 'Fake', apply=True, yes=False, aura=aura)

    assert rc == 0
    assert calls == []
    out = capsys.readouterr().out
    assert 'Aborted.' in out


def test_apply_interactive_confirm_echoes_frame_name_and_id(tmp_path, monkeypatch, capsys):
    _env(monkeypatch)
    _patch_aws_clients(monkeypatch)
    calls = _patch_execute_plan(monkeypatch, result=ExecutionResult(upload_succeeded=1))
    monkeypatch.setattr(cli.sys.stdin, 'isatty', lambda: True)
    seen_prompt = {}

    def fake_input(prompt=''):
        seen_prompt['prompt'] = prompt
        return 'y'

    monkeypatch.setattr('builtins.input', fake_input)

    (tmp_path / 'new.jpg').write_bytes(b'new-photo-bytes')
    aura = offline_aura(overrides={ASSETS_PATH: _assets_response()})

    rc = cli.run_sync(str(tmp_path), 'Fake', apply=True, yes=False, aura=aura)

    assert rc == 0
    assert len(calls) == 1
    assert FRAME_NAME in seen_prompt['prompt']
    assert FRAME_ID in seen_prompt['prompt']


def test_apply_execution_failures_return_1_and_name_failed_items(tmp_path, monkeypatch, capsys):
    _env(monkeypatch)
    _patch_aws_clients(monkeypatch)
    failing_result = ExecutionResult(
        upload_succeeded=0,
        delete_succeeded=1,
        upload_failures=[(tmp_path / 'bad.jpg', 'boom')],
        delete_failures=[],
    )
    calls = _patch_execute_plan(monkeypatch, result=failing_result)

    (tmp_path / 'bad.jpg').write_bytes(b'bad-bytes')
    aura = offline_aura(overrides={ASSETS_PATH: _assets_response()})

    rc = cli.run_sync(str(tmp_path), 'Fake', apply=True, yes=True, aura=aura)

    assert rc == 1
    assert len(calls) == 1
    out = capsys.readouterr().out
    assert 'Uploads: 0 succeeded, 1 failed' in out
    assert 'bad.jpg' in out
    assert 'boom' in out


def test_apply_rate_limited_batch_aborts_with_single_backoff_message(tmp_path, monkeypatch, capsys):
    # execute_plan raising RateLimitError mid-apply must produce ONE clear
    # back-off message and rc 1 -- not N per-item lines (the confusing
    # 120x-401 symptom that motivated this fix).
    _env(monkeypatch)
    _patch_aws_clients(monkeypatch)

    def rate_limited_execute_plan(plan, aura, frame_id, *, s3_client, sqs_client, progress=None, on_wait=None, **kwargs):
        raise RateLimitError(429, retry_after=60, server_message='too many')

    monkeypatch.setattr(cli, 'execute_plan', rate_limited_execute_plan)

    (tmp_path / 'new.jpg').write_bytes(b'new-photo-bytes')
    aura = offline_aura(overrides={ASSETS_PATH: _assets_response()})

    rc = cli.run_sync(str(tmp_path), 'Fake', apply=True, yes=True, aura=aura)

    assert rc == 1
    out = capsys.readouterr().out
    assert 'Aborted:' in out
    assert 'HTTP 429' in out
    assert '60s' in out
    # Not a per-item upload summary -- the batch never produced one.
    assert 'Uploads:' not in out


def test_apply_consecutive_failures_aborts_with_distinct_message(tmp_path, monkeypatch, capsys):
    # execute_plan raising ConsecutiveWriteFailureError (the plain-401 run that
    # RateLimitError could not classify) must produce a DISTINCT back-off
    # message -- different wording from the RateLimitError "Aborted:" path --
    # plus the partial progress, and rc 1.
    _env(monkeypatch)
    _patch_aws_clients(monkeypatch)

    def failing_execute_plan(plan, aura, frame_id, *, s3_client, sqs_client, progress=None, on_wait=None, **kwargs):
        raise ConsecutiveWriteFailureError(
            5,
            "Client error '401 Unauthorized' for url '.../select_asset.json'",
            ExecutionResult(upload_succeeded=7),
        )

    monkeypatch.setattr(cli, 'execute_plan', failing_execute_plan)

    (tmp_path / 'new.jpg').write_bytes(b'new-photo-bytes')
    aura = offline_aura(overrides={ASSETS_PATH: _assets_response()})

    rc = cli.run_sync(str(tmp_path), 'Fake', apply=True, yes=True, aura=aura)

    assert rc == 1
    out = capsys.readouterr().out
    # Distinct wording from the RateLimitError path (which prints "Aborted:").
    assert 'consecutive write failures' in out
    assert 'lockout' in out.lower()
    # Partial progress surfaced.
    assert '7 uploads' in out
    # Not the throttle-specific "Aborted:" lead-in.
    assert 'Aborted:' not in out


def test_login_rate_limited_reports_clear_message(tmp_path, monkeypatch, capsys):
    # The 475 login lockout escalation must surface as a back-off message,
    # not a generic "Login failed".
    _env(monkeypatch)

    class _LockedOutAura:
        def login(self):
            raise RateLimitError(475, server_message='The email or password was incorrect.')

    rc = cli.run_sync(str(tmp_path), 'Fake', apply=True, yes=True, aura=_LockedOutAura())

    assert rc == 1
    out = capsys.readouterr().out
    assert 'Rate limited / locked out at login' in out
    assert 'HTTP 475' in out


# ---------------------------------------------------------------------------
# `push` (additive upload) + probe flags (--limit / --batch-size / --chunk-delay)
# ---------------------------------------------------------------------------

def test_push_never_deletes_even_with_delete_candidates(tmp_path, monkeypatch, capsys):
    # SECURITY-CRITICAL: `push` (no_delete=True) must NEVER remove existing
    # frame photos, even when the diff would classify them as delete
    # candidates -- the guarantee that lets you push from a "buffet" supply
    # directory without wiping the frame. The plan handed to execute_plan
    # must carry ZERO deletes.
    _env(monkeypatch)
    _patch_aws_clients(monkeypatch)
    calls = _patch_execute_plan(monkeypatch)

    (tmp_path / 'new.jpg').write_bytes(b'brand-new-photo-bytes')
    # A frame asset with no local match -> a delete candidate under plain sync.
    frame_asset = _frame_asset(id='asset-on-frame', md5_hash=get_md5(b'not-in-local-dir'))
    aura = offline_aura(overrides={ASSETS_PATH: _assets_response(frame_asset)})

    rc = cli.run_sync(str(tmp_path), 'Fake', apply=True, yes=True, aura=aura,
                      no_delete=True, verb='push')

    assert rc == 0
    assert len(calls) == 1
    assert calls[0]['plan'].to_delete == []          # nothing to delete, ever
    assert len(calls[0]['plan'].to_upload) == 1       # the new photo still uploads
    out = capsys.readouterr().out
    assert 'additive' in out.lower()
    assert 'asset-on-frame' not in out                # the delete candidate is not even listed


def test_push_limit_caps_uploads(tmp_path, monkeypatch, capsys):
    # --limit N attempts at most N uploads this run (controlled budget probing).
    _env(monkeypatch)
    _patch_aws_clients(monkeypatch)
    calls = _patch_execute_plan(monkeypatch)

    for i in range(5):
        (tmp_path / f'{i:02d}.jpg').write_bytes(f'photo-{i}'.encode())
    aura = offline_aura(overrides={ASSETS_PATH: _assets_response()})

    rc = cli.run_sync(str(tmp_path), 'Fake', apply=True, yes=True, aura=aura,
                      no_delete=True, limit=2, verb='push')

    assert rc == 0
    assert len(calls[0]['plan'].to_upload) == 2
    assert 'To upload: 2' in capsys.readouterr().out


def test_push_forwards_batch_size_and_chunk_delay(tmp_path, monkeypatch):
    # --batch-size / --chunk-delay are forwarded to execute_plan when supplied.
    _env(monkeypatch)
    _patch_aws_clients(monkeypatch)
    calls = _patch_execute_plan(monkeypatch)

    (tmp_path / 'a.jpg').write_bytes(b'photo')
    aura = offline_aura(overrides={ASSETS_PATH: _assets_response()})

    cli.run_sync(str(tmp_path), 'Fake', apply=True, yes=True, aura=aura,
                 no_delete=True, batch_size=7, chunk_delay=3.0, verb='push')

    assert calls[0]['batch_size'] == 7
    assert calls[0]['chunk_delay_seconds'] == 3.0


def test_sync_defaults_do_not_override_execute_plan_defaults(tmp_path, monkeypatch):
    # Backward compat: a classic sync --apply (no new flags) forwards NEITHER
    # batch_size nor chunk_delay, so execute_plan keeps its own defaults.
    _env(monkeypatch)
    _patch_aws_clients(monkeypatch)
    calls = _patch_execute_plan(monkeypatch)

    (tmp_path / 'a.jpg').write_bytes(b'photo')
    aura = offline_aura(overrides={ASSETS_PATH: _assets_response()})

    cli.run_sync(str(tmp_path), 'Fake', apply=True, yes=True, aura=aura)

    assert calls[0]['batch_size'] is None
    assert calls[0]['chunk_delay_seconds'] is None
