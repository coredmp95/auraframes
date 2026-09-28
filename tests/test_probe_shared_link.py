"""Offline tests for the shared-link probe parser and redaction (plan 16-01 T2).

Zero network: the fixture is fully synthetic (authored, not recorded), and the
import-time test monkeypatches httpx.get to prove importing the probe modules
performs no I/O.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

import probes.common as common  # noqa: E402
from probes.common import redact_tokens  # noqa: E402
from probes.shared_link_probe import ProbeParseError, parse_af_initdata, redact_link  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "probe_af_initdata_sample.html"

# Fully synthetic share URL for redaction tests — shape-valid, never real.
FAKE_FULL_URL = (
    "https://photos.google.com/share/"
    "AF1QipSYNTHsynthSYNTHsynthSYNTHsynthSYNTHsynth0123"
)

EXPECTED_IDS = [
    "AF1QipFAKEitem0000000000000000000000000000001",
    "AF1QipFAKEitem0000000000000000000000000000002",
    "AF1QipFAKEitem0000000000000000000000000000003",
    "AF1QipFAKEitem0000000000000000000000000000004",
]


def test_parse_fixture_returns_all_items():
    html = FIXTURE.read_text()
    items = parse_af_initdata(html)
    assert len(items) == 4, f"expected 4 items, got {len(items)}"
    assert [i["id"] for i in items] == EXPECTED_IDS
    assert all(i["base_url"].startswith("https://lh3.googleusercontent.com/pw/FAKE")
               for i in items)
    assert items[0]["width"] == 4898 and items[0]["height"] == 3265
    assert items[0]["ts_ms"] == 1532210429477


def test_parse_handles_missing_ds1():
    with pytest.raises(ProbeParseError) as exc:
        parse_af_initdata("<html><body>no data here</body></html>")
    assert "ds:1" in str(exc.value), "error must name the missing key (fail-loud)"


def test_redact_link_never_emits_full_url():
    redacted = redact_link(FAKE_FULL_URL)
    # Shape convention: domain path kept, token collapsed to AF1Qip…<last4>.
    assert redacted == "photos.google.com/share/AF1Qip…0123"
    assert len(redacted) <= len("photos.google.com/share/AF1Qip…0123")
    # The full token must be absent from the output.
    assert "AF1QipSYNTHsynth" not in redacted
    # Defensive: even raw token text gets collapsed.
    token_only = FAKE_FULL_URL.rsplit("/", 1)[1]
    assert redact_tokens(token_only) == "AF1Qip…0123"


def test_probe_module_imports_offline(monkeypatch):
    """Importing the probe modules must perform no network I/O at import time."""
    def _boom(*args, **kwargs):
        raise AssertionError("network I/O attempted at import time")

    monkeypatch.setattr(httpx, "get", _boom)
    monkeypatch.setattr(httpx.Client, "request", _boom)
    # Force a fresh import of both modules under the patched transport.
    import importlib
    import probes.shared_link_probe as probe_mod
    importlib.reload(probe_mod)
    importlib.reload(common)
    # And the parser itself stays offline-pure on the fixture.
    items = parse_af_initdata(FIXTURE.read_text())
    assert len(items) == 4
