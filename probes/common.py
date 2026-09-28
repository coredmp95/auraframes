"""Shared utilities for the Phase 16 access-mechanism probes.

Everything a probe prints that could carry a capability URL goes through
`redact_link()` first (D-05: committed docs and terminal scrollback carry the
truncated shape only — `AF1Qip…<last4>`). `fetch()` is a fail-loud raw HTTP
wrapper: a non-200 is an exception, never a silent pass, matching the repo's
convention of honest failures over optimistic defaults.
"""
from __future__ import annotations

import re
import sys

import httpx

# A full share-link token: AF1Qip followed by the ~48-char id portion.
_FULL_TOKEN_RE = re.compile(r"AF1Qip[A-Za-z0-9_-]{40,}")


def redact_link(url: str | None) -> str:
    """Return the truncated capability-URL shape for any URL string.

    `https://photos.google.com/share/AF1QipXXXXXXXX...YYYY` becomes
    `photos.google.com/share/AF1Qip…YYYY` — enough to correlate two links
    as different, never enough to resolve either. Idempotent: a string with
    no full token passes through with the scheme stripped.
    """
    if not url:
        return "(none)"
    text = _FULL_TOKEN_RE.sub(lambda m: f"AF1Qip…{m.group(0)[-4:]}", url)
    return text.replace("https://", "")


def redact_tokens(text: str) -> str:
    """Redact every full capability token embedded in arbitrary text (e.g. a
    raw error body we are about to record in evidence)."""
    return _FULL_TOKEN_RE.sub(lambda m: f"AF1Qip…{m.group(0)[-4:]}", text)


def fetch(url: str, *, timeout: float = 30.0) -> httpx.Response:
    """GET a URL fail-loudly: raise on non-200, never return a silent pass.

    Plain HTTP/2-capable httpx, no cookies, no browser. 30s timeout; no
    retry loop (T-16-04: single-album low-frequency fetches must not look
    like bulk scraping).
    """
    resp = httpx.get(url, timeout=timeout, follow_redirects=True)
    if resp.status_code != 200:
        raise RuntimeError(
            f"probe fetch failed: HTTP {resp.status_code} for {redact_link(url)} "
            f"({len(resp.content)} bytes) — failing loud per probe convention"
        )
    return resp


def fail_loud(message: str) -> None:
    """Print a failure and exit non-zero — probes never exit 0 on a bad run."""
    print(f"PROBE FAILED: {message}", file=sys.stderr)
    raise SystemExit(1)
