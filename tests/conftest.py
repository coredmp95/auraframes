import os

import pytest


@pytest.fixture(scope="session")
def aura():
    """Authenticated Aura session shared by all live read-path tests.

    Reads AURA_EMAIL/AURA_PASSWORD from the environment and skips the whole
    live suite cleanly when either is unset (D-02), so a credential-less
    checkout stays green. When credentials are present it instantiates Aura()
    and performs the login (READ-01's act, D-03), returning the authenticated
    instance so all live tests reuse one session.
    """
    email = os.getenv("AURA_EMAIL")
    password = os.getenv("AURA_PASSWORD")
    if not email or not password:
        pytest.skip("AURA_EMAIL/AURA_PASSWORD not set; skipping live Aura API tests")

    from auraframes.aura import Aura

    instance = Aura()
    instance.login()
    return instance
