"""Shared-album-link probe (Phase 16, plan 16-01 — LGS-01/LGS-06).

Fetches a Google Photos shared-album page with plain HTTP — no cookies, no
login, no JS — parses the inline `AF_initDataCallback({key: 'ds:1', ...})`
payload into the album's item list, and optionally downloads originals via
the `{baseUrl}=d` convention, hashing them with the frame's own base64-MD5
convention (`auraframes.aws.s3client.get_md5`) for the 16-03 fidelity
comparison.

Usage:
    uv run python probes/shared_link_probe.py <share_url> [--download-n N] [--out DIR]

Privacy: every URL printed goes through `probes.common.redact_link` — the
full capability URL is never echoed to stdout and never written to any
committed file. Full links live only in untracked `probes/*.link` files or
in the shell invocation itself (D-05 privacy tiers).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import httpx

# Import path shim so `python probes/shared_link_probe.py` works from the
# repo root without installing the probes package.
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from probes.common import fetch, redact_link, redact_tokens  # noqa: E402

SUSPECTED_CEILING = 500

_DS1_RE = re.compile(r"AF_initDataCallback\(\s*\{\s*key:\s*['\"]ds:1['\"]")


class ProbeParseError(RuntimeError):
    """Raised when the share page lacks the expected ds:1 payload (fail-loud)."""


def extract_ds1_data(html: str) -> list:
    """Extract and JSON-parse the `data` argument of the ds:1 AF_initDataCallback.

    Regex-locates the `key: 'ds:1'` occurrence, then performs balanced-bracket
    extraction of the `data:[...]` argument and parses it as a JS array literal.
    Raises ProbeParseError (naming the missing key) when the page has no ds:1
    block — fail loud, never emit a partial item list silently.
    """
    matches = list(_DS1_RE.finditer(html))
    if not matches:
        raise ProbeParseError(
            "page has no AF_initDataCallback with key 'ds:1' — page shape changed "
            "or the link did not resolve to an album page; refusing to guess"
        )

    # Try every ds:1 occurrence (pages can carry several; non-payload lookalikes
    # — e.g. prose or comments naming the structure — fail their parse and the
    # walk continues to the next occurrence). First parseable payload wins.
    last_error: ProbeParseError | None = None
    for match in matches:
        try:
            return _extract_data_at(html, match)
        except ProbeParseError as exc:
            last_error = exc
            continue
    raise ProbeParseError(
        f"no parseable ds:1 data block among {len(matches)} occurrence(s): "
        f"{last_error} — refusing to guess"
    )


def _extract_data_at(html: str, match: re.Match) -> list:
    # From the match, find the `data:` argument's opening bracket.
    tail = html[match.end():]
    data_m = re.search(r"\bdata\s*:", tail)
    if not data_m:
        raise ProbeParseError(
            "ds:1 callback found but has no 'data:' argument — refusing to guess"
        )
    after = tail[data_m.end():]
    bracket_m = re.search(r"\[", after)
    if not bracket_m:
        raise ProbeParseError("data argument carries no opening '[' — refusing to guess")

    start = match.end() + data_m.end() + bracket_m.start()
    depth = 0
    end = None
    in_str = False
    esc = False
    quote = ""
    for i in range(start, len(html)):
        ch = html[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == quote:
                in_str = False
            continue
        if ch in ("'", '"'):
            in_str = True
            quote = ch
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None:
        raise ProbeParseError("unbalanced brackets in ds:1 data payload — truncated page?")

    literal = html[start:end]
    return _parse_array_literal(literal)


def _parse_array_literal(literal: str) -> list:
    """Parse a JS array literal: strict json.loads first, tolerant fallback second.

    The payload is normally plain JSON (double-quoted). When Google emits JS-isms
    (single quotes, bare keys, trailing commas), a conservative sanitizer normalizes
    only those cases — no bespoke parser beyond balanced extraction, per the plan.
    """
    import json

    try:
        parsed = json.loads(literal)
    except json.JSONDecodeError as first_error:
        sanitized = literal
        # Strip // line comments if any leaked in.
        sanitized = re.sub(r"^\s*//.*$", "", sanitized, flags=re.MULTILINE)
        # Quote bare object keys:  {foo: 1} -> {"foo": 1}
        sanitized = re.sub(r"([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*):", r'\1"\2"\3:', sanitized)
        # Trailing commas: [1,2,] -> [1,2]
        sanitized = re.sub(r",\s*([\]}])", r"\1", sanitized)
        try:
            parsed = json.loads(sanitized)
        except json.JSONDecodeError:
            raise ProbeParseError(
                f"ds:1 data is neither strict JSON nor tolerantly sanitizable "
                f"(first error: {first_error.msg} at {first_error.pos}) — refusing to guess"
            ) from first_error
        print("parse note: ds:1 payload needed tolerant sanitization (JS-isms present)",
              file=sys.stderr)
    if not isinstance(parsed, list):
        raise ProbeParseError("ds:1 data is not an array — page shape changed")
    return parsed


def _walk_items(node, items):
    """Depth-first walk collecting media items with the §1b structure:
    [mediaItemId, [baseUrl, width, height, ...], uploadTimestampMs, ...]."""
    if not isinstance(node, list):
        return
    if (len(node) >= 3 and isinstance(node[0], str)
            and node[0].startswith("AF1Qip")
            and isinstance(node[1], list) and node[1]
            and isinstance(node[1][0], str)
            and node[1][0].startswith("http")):
        base = node[1]
        items.append({
            "id": node[0],
            "base_url": base[0],
            "width": base[1] if len(base) > 1 else None,
            "height": base[2] if len(base) > 2 else None,
            "ts_ms": node[2] if isinstance(node[2], (int, float)) else None,
        })
        return
    for child in node:
        _walk_items(child, items)


def parse_af_initdata(html: str) -> list[dict]:
    """Parse a shared-album page's HTML into a deduped list of media items."""
    data = extract_ds1_data(html)
    items: list[dict] = []
    _walk_items(data, items)
    seen: set[str] = set()
    deduped = []
    for item in items:
        if item["id"] not in seen:
            seen.add(item["id"])
            deduped.append(item)
    return deduped


def resolve_share_url(url: str) -> tuple[str, httpx.Response]:
    """Follow app.goo.gl 302s to the final photos.google.com/share/... URL."""
    resp = fetch(url)  # follow_redirects=True in common.fetch
    return str(resp.url), resp


def download_original(base_url: str, dest: Path) -> tuple[int, str]:
    """Download the `{baseUrl}=d` original, return (byte_length, base64_md5).

    Hash comes from the repo's own convention — auraframes.aws.s3client.get_md5 —
    the exact function the frame's md5_hash provenance rests on (Phase 7).
    Bytes are hashed raw; no re-encoding, no Pillow round-trip.
    """
    from auraframes.aws.s3client import get_md5

    url = f"{base_url}=d"
    resp = httpx.get(url, timeout=60.0, follow_redirects=True)
    if resp.status_code != 200:
        raise RuntimeError(
            f"=d download failed: HTTP {resp.status_code} for a media baseUrl "
            f"(sha-prefix {base_url[-6:]}) — failing loud"
        )
    data = resp.content
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return len(data), get_md5(data)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("share_url", help="photos.google.com/share/... or app.goo.gl link")
    parser.add_argument("--download-n", type=int, default=0,
                        help="download the first N originals via =d (default 0: listing only)")
    parser.add_argument("--out", type=Path, default=Path("probes/.probe-downloads"),
                        help="download directory (gitignored)")
    args = parser.parse_args(argv)

    final_url, resp = resolve_share_url(args.share_url)
    print(f"final URL: {redact_link(final_url)}")
    print(f"HTTP status: {resp.status_code}, page bytes: {len(resp.content)}")

    items = parse_af_initdata(resp.text)
    print(f"item count: {len(items)}")
    for i, item in enumerate(items, 1):
        w = item["width"] if item["width"] is not None else "?"
        h = item["height"] if item["height"] is not None else "?"
        print(f"  {i:3d}. {item['id'][:14]}…  {w}x{h}  ts={item['ts_ms']}")

    if len(items) >= SUSPECTED_CEILING:
        verdict = (f"AT/ABOVE the suspected ~{SUSPECTED_CEILING} ceiling — ceiling "
                   f"MEASURED at {len(items)} items returned by one fetch")
    else:
        verdict = (f"below the suspected ~{SUSPECTED_CEILING} ceiling "
                   f"(lower bound so far: {len(items)})")
    print(f"ceiling verdict: {verdict}")

    if args.download_n > 0:
        for item in items[: args.download_n]:
            dest = args.out / f"{item['id']}.bin"
            length, digest = download_original(item["base_url"], dest)
            print(f"downloaded: {dest.name}  bytes={length}  base64_md5={digest}")

    # Safety net: nothing printed above may contain a full capability token.
    # (redact_link is applied at the print sites; this guards regressions.)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
