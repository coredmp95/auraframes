"""Album enumeration and disk-weight measurement over photos.google.com.

Migrated from probes/browser_bootstrap.py `_list_album` + probes/
shared_link_probe.py `measure_sizes` (phase 16, live-proven: 794/794
UI-confirmed across 3 snAcKc pages, album C 86.6 MiB exact).

The snAcKc recipe below is the live-proven one (16-LIVE-FINDINGS addendum,
re-proven this session):

- The f.req envelope is TRIPLE-nested:
  `[[["snAcKc", <inner_json>, null, "generic"]]]` (compact separators). A
  double-nested envelope answers HTTP 400 — the phase-16 "payload guess"
  failure was a nesting bug, not a payload bug.
- `page_key` (the snAcKc 4th argument) is the `?key=` query parameter of the
  share URL (`/share/<album_id>?key=<page_key>`). The album id is the share
  URL's final path segment.
- batch-1 inputs: the FIRST `AH_[A-Za-z0-9_-]{40,}` token on the share page
  itself (intermittent ~3/4 fetches — retry); at-token (SNlM0e), f.sid
  (FdrFJe) and bl (cfb2h) come from photos.google.com/ home.
- POST
  `https://photos.google.com/_/PhotosUi/data/batchexecute?rpcids=snAcKc&source-path=%2Fshare%2F{album_id}&f.sid={fsid}&bl={bl_quoted}&hl=fr&soc-app=165&soc-platform=1&soc-device=1`
  with body `f.req={freq url-encoded}&at={at url-encoded}&`, form-urlencoded
  Content-Type, Origin/Referer photos.google.com, and the SAPISIDHASH
  Authorization header.
- Response: `)]}'`-prefixed lines, `["wrb.fr","snAcKc",<payload>,...]`
  entries; items walk with the §1b shape (same as the share page); the
  NEXT token is the LAST `AH_` in the payload; NO token = exhausted.

Fail-loud discipline (T-17-02): HTTP != 200, a malformed envelope or an
unparseable share page raises — never a silent partial listing.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from urllib.parse import quote

import httpx

from auraframes.google.parsers import (
    ProbeParseError,
    _walk_items,
    parse_af_initdata,
    parse_batchexecute,
    parse_snackc_payload,
)
from auraframes.google.redaction import redact_link, redact_tokens

BATCHEXECUTE_URL = "https://photos.google.com/_/PhotosUi/data/batchexecute"
PHOTOS_HOME = "https://photos.google.com/"

MAX_PAGES = 60  # 60 x 300 = 18000, far beyond any real album (T-17-04 cap)
PAGE_SIZE = 300  # live-proven page size

# The share URL's album id: the final path segment of /share/<album_id>.
_ALBUM_ID_RE = re.compile(r"/share/([A-Za-z0-9_-]+)")
# A share URL carrying an explicit ?key= parameter (page_key pre-known).
_KEY_RE = re.compile(r"[?&]key=([A-Za-z0-9_-]+)")
# batch-1 input: the first AH_ token anywhere on the share page.
_AH_TOKEN_RE = re.compile(r"AH_[A-Za-z0-9_-]{40,}")
# WIZ_global_data scalars on the home page.
_FSID_RE = re.compile(r'"FdrFJe"\s*:\s*"([^"]+)"')
_BL_RE = re.compile(r'"cfb2h"\s*:\s*"([^"]+)"')
_AT_RE = re.compile(r'"SNlM0e"\s*:\s*"([^"]+)"')

# The intermittent share-page token: retry budget before failing loud.
_SHARE_PAGE_ATTEMPTS = 4


class EnumerateError(RuntimeError):
    """Album enumeration failed — fail loud, never a silent partial listing."""


@dataclass
class AlbumListing:
    """The complete, exhausted album listing (D-06: every item, disk weight
    via measure_disk_weight, count must equal what the Google UI shows)."""

    items: list[dict] = field(default_factory=list)
    page_count: int = 0
    exhausted_cleanly: bool = False
    album_id: str | None = None

    @property
    def total_bytes(self) -> int:
        return sum(i.get("bytes", 0) for i in self.items)


@dataclass
class _SessionScalars:
    at: str
    fsid: str
    bl: str


def _session_scalars(session) -> _SessionScalars:
    """Extract at-token / f.sid / bl from the logged-in photos home page."""
    text = session.home_text()
    at_m = _AT_RE.search(text)
    fsid_m = _FSID_RE.search(text)
    bl_m = _BL_RE.search(text)
    if not (at_m and fsid_m and bl_m):
        missing = [n for n, m in (("SNlM0e", at_m), ("FdrFJe", fsid_m),
                                  ("cfb2h", bl_m)) if not m]
        raise EnumerateError(
            f"photos.google.com home lacks required batchexecute scalars: "
            f"{missing} — session dead or page shape changed; failing loud"
        )
    return _SessionScalars(at=at_m.group(1), fsid=fsid_m.group(1), bl=bl_m.group(1))


def _split_share_url(share_url: str) -> tuple[str, str | None]:
    """Split a share URL into (album_id, page_key-or-None).

    `page_key` is the URL's `?key=` parameter when present (the snAcKc 4th
    argument, live-proven); the album id is the final /share/<id> segment.
    """
    album_m = _ALBUM_ID_RE.search(share_url)
    if not album_m:
        raise EnumerateError(
            f"URL is not a photos.google.com share link ({redact_link(share_url)}) "
            f"— expected /share/<album_id>[?key=<page_key>]; refusing to guess"
        )
    key_m = _KEY_RE.search(share_url)
    return album_m.group(1), (key_m.group(1) if key_m else None)


def _fetch_share_page(session, share_url: str) -> httpx.Response:
    """GET the share page with the session, retrying the intermittent
    AH_-token appearance (live: ~3/4 fetches carry it), then fail loud."""
    last: Exception | None = None
    for attempt in range(1, _SHARE_PAGE_ATTEMPTS + 1):
        resp = session.http.get(share_url)
        if resp.status_code != 200:
            raise EnumerateError(
                f"share page returned HTTP {resp.status_code} "
                f"({redact_link(share_url)}) — failing loud"
            )
        if _AH_TOKEN_RE.search(resp.text):
            return resp
        last = EnumerateError(
            f"share page carries no AH_ token (attempt {attempt}/{_SHARE_PAGE_ATTEMPTS}, "
            f"intermittent live behavior) — {redact_link(share_url)}"
        )
    raise last  # type: ignore[misc]


def _freq_envelope(rpcid: str, args: list) -> str:
    """The TRIPLE-nested compact f.req envelope (live-proven: double nesting
    answers HTTP 400). Shape: [[ [rpcid, <stringified args>, null, "generic"] ]] —
    the 4-element entry sits at the third nesting level, its 2nd member being
    the JSON-encoded args STRING."""
    entry = [rpcid, json.dumps(args, separators=(",", ":")), None, "generic"]
    return json.dumps([[entry]], separators=(",", ":"))


def _rpc_headers(session) -> dict[str, str]:
    headers = {
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        "Origin": PHOTOS_HOME.rstrip("/"),
        "Referer": PHOTOS_HOME,
    }
    auth = session.authorization_header()
    if auth:
        headers["Authorization"] = auth
    return headers


def _snackc_page(session, scalars: _SessionScalars, album_id: str,
                 page_key: str | None, continuation_token: str | None) -> tuple[list[dict], str | None]:
    """Issue ONE snAcKc batchexecute call; return (items, next_token_or_None)."""
    args = [album_id, continuation_token, None, page_key]
    freq = _freq_envelope("snAcKc", args)
    url = (
        f"{BATCHEXECUTE_URL}?rpcids=snAcKc"
        f"&source-path={quote('/share/' + album_id, safe='')}"
        f"&f.sid={quote(scalars.fsid, safe='')}"
        f"&bl={quote(scalars.bl, safe='')}"
        f"&hl=fr&soc-app=165&soc-platform=1&soc-device=1"
    )
    body = f"f.req={quote(freq, safe='')}&at={quote(scalars.at, safe='')}&"
    resp = session.http.post(url, content=body.encode("utf-8"),
                             headers=_rpc_headers(session))
    if resp.status_code != 200:
        raise EnumerateError(
            f"snAcKc batchexecute returned HTTP {resp.status_code} "
            f"(album {album_id[:12]}…, page {continuation_token is not None}) — "
            f"failing loud; body head: {redact_tokens(resp.text[:200])}"
        )
    entries = [e for e in parse_batchexecute(resp.text) if e.rpcid == "snAcKc"]
    if not entries:
        raise EnumerateError(
            "snAcKc batchexecute answer carries no wrb.fr/snAcKc entry — "
            "malformed envelope; refusing to guess"
        )
    page = parse_snackc_payload(entries[0].payload)
    return page.items, page.continuation_token


def enumerate_album(session, share_url: str, *, max_pages: int = MAX_PAGES) -> AlbumListing:
    """Enumerate EVERY item of a shared album (D-06) via the proven flow:

    share page (batch-1 + inputs) → snAcKc continuation loop (300/page, AH_
    token swap) until no token or a 0-item page. Fail-loud on HTTP != 200 or
    a malformed envelope (never a silent partial listing).
    """
    album_id, page_key = _split_share_url(share_url)
    scalars = _session_scalars(session)

    # Batch-1: the share page itself.
    resp = _fetch_share_page(session, share_url)
    try:
        items = parse_af_initdata(resp.text)
    except ProbeParseError as exc:
        raise EnumerateError(f"share page unparseable: {exc}") from exc

    listing = AlbumListing(album_id=album_id)
    listing.items = items
    listing.page_count = 1

    if not _AH_TOKEN_RE.search(resp.text):
        # No cursor on the page and none needed: album fits in batch-1.
        # Live: the share page itself carries an AH_ even for small albums —
        # a small album's page simply exhausts on the first RPC call below.
        listing.exhausted_cleanly = True
        return listing

    # Continuation loop.
    token: str | None = _AH_TOKEN_RE.search(resp.text).group(0)  # type: ignore[union-attr]
    while listing.page_count < max_pages:
        page_items, next_token = _snackc_page(session, scalars, album_id,
                                              page_key, token)
        listing.page_count += 1
        known = {i["id"] for i in listing.items}
        fresh = [i for i in page_items if i["id"] not in known]
        listing.items.extend(fresh)
        if next_token is None or not page_items:
            listing.exhausted_cleanly = True
            return listing
        token = next_token

    raise EnumerateError(
        f"album enumeration hit the {max_pages}-page cap (T-17-04) with "
        f"{len(listing.items)} items and a live continuation token — "
        f"listing is INCOMPLETE; raise max_pages or investigate"
    )


def list_shared_albums(session) -> list:
    """The account's shared albums, from the logged-in home page's ds:0 block.

    The discovery aid behind `google-album --list` and the name resolution:
    titles come from the ds:0 rows, share URLs are CONSTRUCTED in the proven
    /share/<album_id> shape. Item counts are NOT carried (the authoritative
    count is enumerate_album's) — the summary never guesses one.
    """
    from auraframes.google.parsers import AlbumSummary, extract_initdata, parse_album_summaries

    text = session.home_text()
    try:
        ds0 = extract_initdata(text, "ds:0")
    except ProbeParseError:
        # A logged-in home without a ds:0 album block: an account with no
        # shared albums is a legitimate empty listing, not a parse failure.
        return []
    summaries: list[AlbumSummary] = parse_album_summaries(ds0)
    for s in summaries:
        if s.album_id:
            s.share_url = f"{PHOTOS_HOME.rstrip('/')}/share/{s.album_id}"
    return summaries


def measure_disk_weight(session, base_urls: list[str]) -> list[int]:
    """Exact per-item byte sizes via 1-octet Range GETs on `{baseUrl}=d`.

    Google answers `Content-Range: bytes 0-0/TOTAL` — the album's total disk
    weight is measurable without downloading any photo (live-proven: album C,
    24 items → 86.6 MiB exact). Items whose answer carries neither
    Content-Range nor Content-Length report 0 (defensive; live never seen).
    """
    sizes: list[int] = []
    for base in base_urls:
        r = session.http.get(f"{base}=d", headers={"Range": "bytes=0-0"})
        cr = r.headers.get("content-range", "")
        size = int(cr.rsplit("/", 1)[-1]) if "/" in cr else None
        if size is None:
            cl = r.headers.get("content-length")
            size = int(cl) if cl else 0
        sizes.append(size)
    return sizes
