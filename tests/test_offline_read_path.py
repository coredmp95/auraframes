"""Offline mirror of tests/test_read_path.py — exercises the same
Aura/*Api/Client stack assertions (login header-set, frame hydration,
pagination drain, both error-raise mechanisms) entirely through
`tests/offline.py`'s `httpx.MockTransport`-backed harness, with zero
network access and no credentials required.

Unmarked (no @pytest.mark.live) — this is the default pytest suite.
tests/test_read_path.py and tests/conftest.py are untouched.
"""
import httpx
import pytest

from auraframes.client import Client
from auraframes.models.frame import Frame
from tests.offline import offline_aura


def test_offline_login_sets_auth_headers():
    """Mirrors test_read_01_login: a login through the mocked transport sets
    both auth headers on the shared httpx session."""
    aura = offline_aura()
    aura.login(email='fake@example.invalid', password='fake-pw')

    headers = aura._client.http2_client.headers
    assert headers.get("x-token-auth"), "x-token-auth header missing after login"
    assert headers.get("x-user-id"), "x-user-id header missing after login"


def test_offline_get_frames_hydrates_frame():
    """Mirrors test_read_02_list_frames: get_frames() returns a non-empty
    list[Frame] hydrated from the frames.json fixture."""
    aura = offline_aura()
    frames = aura.frame_api.get_frames()

    assert frames, "expected at least one frame from the fixture"
    for f in frames:
        assert isinstance(f, Frame)
        assert f.id, "frame is missing an id"


def test_offline_get_all_assets_drains_pagination():
    """Mirrors test_read_03_pagination: get_all_assets with a limit that
    forces the cursor branch drains both fixture pages (2 distinct assets)."""
    aura = offline_aura()
    frame = aura.frame_api.get_frames()[0]

    assets = aura.get_all_assets(frame.id, limit=1)

    assert len(assets) == 2, f"expected 2 stitched assets, got {len(assets)}"
    ids = {a.id for a in assets}
    assert len(ids) == 2, "expected two distinct asset ids across pages"


def test_offline_get_assets_raises_on_error_envelope():
    """Exercises the soft '200 + {error: ...} body' business-rule raise in
    FrameApi.get_assets (RESEARCH.md Pattern 3, mechanism 1)."""
    overrides = {
        "/v5/frames/frame-fake-0001/assets.json": httpx.Response(
            200, json={"error": "not_found", "message": "Resource not found"}
        )
    }
    aura = offline_aura(overrides=overrides)

    with pytest.raises(RuntimeError):
        aura.frame_api.get_assets("frame-fake-0001")


def test_offline_http_status_error_raises():
    """Exercises Client's unconditional raise_for_status() path (RESEARCH.md
    Pattern 3, mechanism 2) — distinct from the business-rule RuntimeError
    above."""
    transport = httpx.MockTransport(
        lambda request: httpx.Response(404, json={"error": "not_found"})
    )
    client = Client(transport=transport)

    with pytest.raises(httpx.HTTPStatusError):
        client.get("/missing.json")
