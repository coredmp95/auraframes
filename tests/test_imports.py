import importlib

import pytest

MODEL_MODULES = [
    "auraframes",
    "auraframes.models.user",
    "auraframes.models.person",
    "auraframes.models.activity",
    "auraframes.models.asset",
    "auraframes.models.frame",
    "auraframes.models.meta",
    "auraframes.utils.io",
]


@pytest.mark.parametrize("mod", MODEL_MODULES)
def test_imports_clean(mod):
    importlib.import_module(mod)


def test_framepartial_all_optional():
    from auraframes.models.frame import FramePartial

    # Every field optional (D-07); is_required() is the verified pydantic v2 idiom.
    assert all(not f.is_required() for f in FramePartial.model_fields.values())


def test_login_defaults_are_none_sentinels():
    from auraframes.aura import Aura

    # Regression: login() must NOT bind os.getenv(...) as default arg values —
    # those evaluate once at import time (before main.py's load_dotenv()), baking
    # creds to None and POSTing null login -> HTTP 475. Defaults stay None and the
    # body resolves the env at call time instead.
    assert Aura.login.__defaults__ == (None, None)
