"""Cookie vault — MOVED to auraframes/google/vault.py (phase 17, plan 17-01
T3: D-03's single-source intent). This shim keeps the probes importing
`probes.cookie_vault` working unchanged; the boundary itself (denylist,
0600, repo refusal, production path + legacy fallback) lives in the package
and is carried over verbatim.
"""
from __future__ import annotations

from auraframes.google.vault import (  # noqa: F401
    DEFAULT_VAULT_PATH,
    CookieVaultError,
    cookies_for_httpx,
    load,
    save,
)
