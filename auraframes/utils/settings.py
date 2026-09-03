import os
from pathlib import Path

LOCALE = os.getenv('AURA_LOCALE', 'en-US')
AURA_APP_IDENTIFIER = os.getenv('AURA_APP_IDENTIFIER', 'com.pushd.client')
# TODO: Load device identifier through config
DEVICE_IDENTIFIER = os.getenv('AURA_DEVICE_IDENTIFIER', '0000000000000000')
IMAGE_PROXY_BASE_URL = 'https://imgproxy.pushd.com'


def _bool_env(name: str, default: bool) -> bool:
    """Defensive boolean env-var parser (Phase 09, ANTI-05) -- Python's
    built-in `bool("false")` is `True`, so every non-empty string env var
    needs this membership test instead. Missing var -> `default`; present
    -> case-insensitive membership in `('1', 'true', 'yes', 'on')`."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ('1', 'true', 'yes', 'on')


# Proactive write-rate-budget + geo pre-flight guard config (Phase 09,
# ANTI-05) -- the first non-string env vars in this codebase, hence the
# `_bool_env` helper above and bare `float(...)` for the numeric ones.
AURA_WRITE_BUDGET_CAPACITY = float(os.getenv('AURA_WRITE_BUDGET_CAPACITY', '30'))
AURA_WRITE_BUDGET_REFILL_PER_MIN = float(os.getenv('AURA_WRITE_BUDGET_REFILL_PER_MIN', '0.75'))
AURA_WRITE_BUDGET_WAIT = _bool_env('AURA_WRITE_BUDGET_WAIT', True)
AURA_WRITE_BUDGET_MAX_WAIT = float(os.getenv('AURA_WRITE_BUDGET_MAX_WAIT', '3600'))
# None -> geo pre-flight check skipped entirely, per check_geo's falsy contract.
AURA_COUNTRY = os.getenv('AURA_COUNTRY')
AURA_GEO_FAIL_OPEN = _bool_env('AURA_GEO_FAIL_OPEN', True)
AURA_STATE_DIR = Path(os.getenv('AURA_STATE_DIR', '~/.config/auraframes')).expanduser()
