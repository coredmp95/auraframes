import pytest

from auraframes.models.frame import Frame


@pytest.mark.live
def test_read_01_login(aura):
    """READ-01: a live login injects auth state onto the shared httpx session.

    The `aura` fixture already performed the login act (D-03); this asserts the
    resulting authenticated state — both auth headers must be present.
    """
    headers = aura._client.http2_client.headers
    assert headers.get("x-token-auth"), "x-token-auth header missing after login"
    assert headers.get("x-user-id"), "x-user-id header missing after login"


@pytest.mark.live
def test_read_02_list_frames(aura):
    """READ-02: a live get_frames() returns a non-empty list[Frame]."""
    frames = aura.frame_api.get_frames()

    assert frames, "expected at least one frame for the account"
    for f in frames:
        assert isinstance(f, Frame)
        assert f.id, "frame is missing an id"
        print(f"{f.name} ({f.id})")
