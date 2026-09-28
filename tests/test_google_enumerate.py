"""Offline tests for the snAcKc enumerator and disk-weight measurer
(plan 17-01 T2).

Zero network: a stateful MockTransport router replays the live-proven
protocol — share page batch-1, triple-nested f.req envelope, AH_ token
swap, clean exhaustion — over synthetic pages of 300+300+194 = 794 items
(the live-confirmed album B shape, LGS-05).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from auraframes.google.client import GoogleSession  # noqa: E402
from auraframes.google.enumerate import (  # noqa: E402
    EnumerateError,
    enumerate_album,
    measure_disk_weight,
)

ALBUM_ID = "AF1QipFAKEalbum0000000000000000000000001"
PAGE_KEY = "FAKEPAGEKEY0001"
SHARE_URL = f"https://photos.google.com/share/{ALBUM_ID}?key={PAGE_KEY}"

SHARE_TOKEN = "AH_" + "T" * 40 + "0001"
SHARE_HTML = (
    "<html><body>"
    "<script>AF_initDataCallback({key: 'ds:1', hash: '2', "
    "data:[[\"album-header\", null]]});</script>"
    f"<script>window._continuation = \"{SHARE_TOKEN}\";</script>"
    "</body></html>"
)
SHARE_HTML_NO_TOKEN = SHARE_HTML.replace(SHARE_TOKEN, "no-cursor-here")
HOME_HTML = (
    "<html><body><script>window.WIZ_global_data = "
    '{"SNlM0e": "SYNTH-AT", "FdrFJe": "12345", "cfb2h": "boq_test_bl", '
    '"oPEP7c": "someone@example.com"};</script></body></html>'
)

COOKIES = [{"name": "SID", "value": "fake-sid", "domain": ".google.com", "path": "/"}]


def _next_token(n: int) -> str:
    return "AH_" + "N" * 40 + f"{n:04d}"


def _rpc_items(page: int, count: int) -> list:
    return [[f"AF1QipRPC{page:02d}{i:06d}",
             [f"https://lh3.googleusercontent.com/pw/FAKEp{page:02d}i{i:06d}",
              100 + i, 200 + i],
             1700000000000 + i]
            for i in range(1, count + 1)]


def _rpc_response(items: list, next_token: str | None) -> str:
    payload = [items]
    if next_token:
        payload.append([next_token])
    inner = json.dumps(payload, separators=(",", ":"))
    line = json.dumps([["wrb.fr", "snAcKc", inner, None, "generic"]],
                      separators=(",", ":"))
    return ")]}'\n\n" + line + "\n"


class _GoogleRouter:
    """Stateful MockTransport replaying the live-proven protocol: it
    VALIDATES the client's side (triple-nested envelope, token chain,
    Range headers) and fails the request when the client deviates."""

    def __init__(self, pages: list[int], *, share_token_attempts: int = 0,
                 rpc_status: int = 200, rpc_body: str | None = None) -> None:
        self.pages = pages
        self.share_token_attempts = share_token_attempts
        self.rpc_status = rpc_status
        self.rpc_body = rpc_body
        self.share_gets = 0
        self.post_count = 0
        self.size_requests: list[tuple[str, str]] = []
        self.last_freq: str | None = None
        self._expected_token: str | None = SHARE_TOKEN

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "GET" and path == "/":
            return httpx.Response(200, text=HOME_HTML)
        if request.method == "GET" and "/share/" in path:
            self.share_gets += 1
            if self.share_gets <= self.share_token_attempts:
                return httpx.Response(200, text=SHARE_HTML_NO_TOKEN)
            return httpx.Response(200, text=SHARE_HTML)
        if request.method == "GET" and path.endswith("=d"):
            num = int(re.search(r"(\d+)$", path.removesuffix("=d")).group(1))
            self.size_requests.append((path, request.headers.get("range", "")))
            return httpx.Response(206, text="x",
                                  headers={"Content-Range": f"bytes 0-0/{num * 1000 + 7}"})
        if request.method == "POST" and "batchexecute" in path:
            self.post_count += 1
            if self.rpc_status != 200:
                return httpx.Response(self.rpc_status, text="server exploded")
            if self.rpc_body is not None:
                return httpx.Response(200, text=self.rpc_body)
            parts = dict(p.split("=", 1) for p in request.content.decode().split("&")
                         if "=" in p)
            self.last_freq = unquote(parts["f.req"])
            arr = json.loads(self.last_freq)
            # TRIPLE nesting is the live-proven envelope (double = HTTP 400).
            if not (isinstance(arr, list) and len(arr) == 1
                    and isinstance(arr[0], list) and len(arr[0]) == 1
                    and isinstance(arr[0][0], list) and arr[0][0][0] == "snAcKc"):
                return httpx.Response(400, text="bad envelope")
            inner = json.loads(arr[0][0][1])
            token = inner[1]
            if token != self._expected_token:
                return httpx.Response(400, text="stale continuation token")
            page_idx = self.post_count - 1
            if page_idx >= len(self.pages):
                return httpx.Response(400, text="too many pages requested")
            has_next = page_idx + 1 < len(self.pages)
            next_token = _next_token(page_idx + 2) if has_next else None
            self._expected_token = next_token
            return httpx.Response(200, text=_rpc_response(
                _rpc_items(page_idx + 1, self.pages[page_idx]), next_token))
        return httpx.Response(404)


def _session(router: _GoogleRouter) -> GoogleSession:
    return GoogleSession(COOKIES, transport=httpx.MockTransport(router.handler))


def test_enumerate_album_794_items_clean_exhaustion():
    """The live-confirmed shape: 3 snAcKc pages of 300+300+194 = 794 items,
    exhausted cleanly, no live network (LGS-05, TEST-02)."""
    router = _GoogleRouter([300, 300, 194])
    listing = enumerate_album(_session(router), SHARE_URL)
    assert len(listing.items) == 794
    assert len({i["id"] for i in listing.items}) == 794  # all unique
    assert listing.exhausted_cleanly is True
    assert listing.page_count == 4  # batch-1 share page + 3 RPC pages
    assert listing.album_id == ALBUM_ID
    assert router.post_count == 3
    assert router.last_freq is not None
    # The envelope the client actually sent is triple-nested compact JSON.
    assert json.loads(router.last_freq)[0][0][0] == "snAcKc"


def test_enumerate_token_swap_chain_validated_by_router():
    """The router rejects stale tokens (400) — a passing enumeration proves
    the client swapped AH_ cursors correctly on every page."""
    router = _GoogleRouter([300, 194])
    listing = enumerate_album(_session(router), SHARE_URL)
    assert len(listing.items) == 494
    assert router.post_count == 2


def test_enumerate_splits_share_url_page_key():
    """page_key (the ?key= param) is the snAcKc 4th argument (live-proven);
    the album id is the share URL's final path segment."""
    router = _GoogleRouter([300])
    enumerate_album(_session(router), SHARE_URL)
    inner = json.loads(json.loads(router.last_freq)[0][0][1])
    assert inner[0] == ALBUM_ID
    assert inner[3] == PAGE_KEY


def test_enumerate_share_page_token_retry():
    """The AH_ token's intermittent appearance (~3/4 live) is encoded: the
    enumerator retries token-less share pages within budget."""
    router = _GoogleRouter([300], share_token_attempts=2)
    listing = enumerate_album(_session(router), SHARE_URL)
    assert len(listing.items) == 300
    assert router.share_gets == 3


def test_enumerate_fails_loud_on_http_400():
    router = _GoogleRouter([300], rpc_status=400)
    with pytest.raises(EnumerateError, match="HTTP 400"):
        enumerate_album(_session(router), SHARE_URL)


def test_enumerate_fails_loud_on_malformed_envelope():
    router = _GoogleRouter([300], rpc_body=")]}'\nnot json at all\n")
    with pytest.raises(RuntimeError):
        enumerate_album(_session(router), SHARE_URL)


def test_enumerate_rejects_non_share_url():
    router = _GoogleRouter([])
    with pytest.raises(EnumerateError, match="share link"):
        enumerate_album(_session(router), "https://example.com/not/a/share")


def test_enumerate_page_cap_fails_loud_incomplete():
    router = _GoogleRouter([300] * 5)
    with pytest.raises(EnumerateError, match="INCOMPLETE"):
        enumerate_album(_session(router), SHARE_URL, max_pages=2)


def test_measure_disk_weight_content_range():
    """1-octet Range GETs → exact Content-Range totals (live-proven sizing)."""
    router = _GoogleRouter([])
    session = _session(router)
    base_urls = [f"https://lh3.googleusercontent.com/pw/FAKEi{i:06d}"
                 for i in (1, 2, 3)]
    sizes = measure_disk_weight(session, base_urls)
    assert sizes == [1007, 2007, 3007]
    for _path, range_header in router.size_requests:
        assert range_header == "bytes=0-0"


def test_measure_disk_weight_zero_when_no_size_headers():
    session = GoogleSession(COOKIES, transport=httpx.MockTransport(
        lambda request: httpx.Response(200)))
    assert measure_disk_weight(session, ["https://lh3.example/pw/FAKEnoheader"]) == [0]
