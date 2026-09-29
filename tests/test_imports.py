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


def test_aws_literals_stay_out_of_aws_modules():
    # MOD-02 (Phase 19) regression gate: the bucket name and the two Cognito
    # pool IDs live in auraframes/utils/settings.py now. If any AWS module
    # re-creates the old literal-bearing constants, this fails.
    from auraframes.aws import s3client, sqsclient
    from auraframes.utils import settings

    assert settings.AWS_S3_BUCKET == 'images.senseapp.co'  # the shipped default
    for module, attr in (
        (s3client, 'AWS_UPLOAD_PART_SIZE'),  # untouched non-debt constant still present
    ):
        assert hasattr(module, attr), f'{module.__name__} lost {attr}'
    # The env-config values are ONLY sourced from settings: the AWS modules
    # must not carry a same-named attribute that could drift from settings.
    assert s3client.BUCKET_KEY is settings.AWS_S3_BUCKET
    assert s3client.UPLOAD_IDENTITY_POOL_ID is settings.AWS_UPLOAD_IDENTITY_POOL_ID
    assert sqsclient.SQS_IDENTITY_POOL_ID is settings.AWS_SQS_IDENTITY_POOL_ID
