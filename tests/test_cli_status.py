"""Offline tests for `aura-cli status` (auraframes.cli.run_status). Calls
run_status() directly (never main()) so load_dotenv() is not invoked and a
filesystem .env cannot interfere.

Unmarked (no @pytest.mark.live) — this is the default pytest suite, runs
with zero network access and no real credentials.
"""
import httpx
import pytest

from auraframes.cli import run_status
from tests.offline import offline_aura


def test_status_missing_creds_exits_nonzero_no_network(monkeypatch, capsys):
    monkeypatch.delenv('AURA_EMAIL', raising=False)
    monkeypatch.delenv('AURA_PASSWORD', raising=False)

    rc = run_status()

    assert rc == 1
    out = capsys.readouterr().out
    assert 'AURA_EMAIL: NOT SET' in out
    assert 'AURA_PASSWORD: NOT SET' in out


def test_status_success_lists_frames_and_never_prints_password(monkeypatch, capsys):
    monkeypatch.setenv('AURA_EMAIL', 'you@example.invalid')
    monkeypatch.setenv('AURA_PASSWORD', 'super-secret-pw')

    rc = run_status(aura=offline_aura())

    assert rc == 0
    out = capsys.readouterr().out
    assert 'AURA_EMAIL: set' in out
    assert 'AURA_PASSWORD: set' in out
    assert 'Logged in as you@example.invalid' in out
    assert '1 frames:' in out
    assert 'Fake Frame' in out
    assert 'frame-fake-0001' in out
    assert 'super-secret-pw' not in out


def test_status_login_failure_exits_nonzero(monkeypatch, capsys):
    monkeypatch.setenv('AURA_EMAIL', 'you@example.invalid')
    monkeypatch.setenv('AURA_PASSWORD', 'super-secret-pw')
    aura = offline_aura(overrides={
        '/v5/login.json': httpx.Response(200, json={'error': 'invalid_credentials', 'message': 'Bad login'})
    })

    rc = run_status(aura=aura)

    assert rc == 1
    out = capsys.readouterr().out
    assert 'Login failed' in out
