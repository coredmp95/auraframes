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
