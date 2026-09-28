"""Browser-automation probe (Phase 16, plan 16-02 — LGS-01).

Two subcommands:

  bootstrap — open Chromium (Playwright persistent context) on the DEDICATED
  profile directory ($AURA_PROBE_CHROME_PROFILE, required), let the operator
  log into Google interactively once, harvest the session cookies into the
  untracked 0600 vault, and print only a redacted identity signal. The
  daily-driver profile is structurally unreachable: unset/empty env fails
  loud before any browser exists (T-16-06).

  list — with NO browser at all: load vaulted cookies into a plain httpx
  client and issue ONE internal batchexecute album listing against a
  throwaway album (URL from an untracked *.link file or --url), reusing the
  shared-link probe's ds:1 parser. Prints batch-1 count and the follow-up
  continuation attempt, redacted (xob0t/Google-Photos-Toolkit is the RPC-shape
  reference; the exact continuation rpcid is part of what this probe measures).

Playwright is imported lazily INSIDE the bootstrap function only — importing
this module never requires playwright (isolation rule, BROWSER-AUTOMATION §4.2).

Usage:
    uv run python probes/browser_bootstrap.py bootstrap
    uv run python probes/browser_bootstrap.py list --url <throwaway-album-link>
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import probes.cookie_vault as cookie_vault  # noqa: E402
from probes.common import redact_link, redact_tokens  # noqa: E402
from probes.shared_link_probe import parse_af_initdata  # noqa: E402

PHOTOS_HOME = "https://photos.google.com/"
# batchexecute endpoint for the Photos web frontend (authuser keeps the call
# bound to the logged-in account the vault came from).
_BATCHEXECUTE_URL = "https://photos.google.com/_/PhotosUi/data/batchexecute"


def _require_dedicated_profile() -> Path:
    profile = os.environ.get("AURA_PROBE_CHROME_PROFILE", "").strip()
    if not profile:
        raise SystemExit(
            "PROBE FAILED: AURA_PROBE_CHROME_PROFILE is unset — the daily-driver "
            "profile is structurally unreachable; point the env var at a dedicated "
            "profile directory (T-16-06)"
        )
    path = Path(profile).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _bootstrap(*, auto: bool = False) -> int:
    """Interactive one-time cookie harvest from the dedicated profile.

    auto=True polls the context for completed Google auth (SAPISID-family
    cookies) instead of waiting for an Enter in the terminal — for runs
    launched from a non-interactive shell. Same consent scope, same profile,
    same vault.
    """
    profile_dir = _require_dedicated_profile()
    from playwright.sync_api import sync_playwright  # lazy, in-function import ONLY

    print(f"dedicated profile: {profile_dir}")
    print("opening Chromium — log into Google in the window.")
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(str(profile_dir), headless=False)
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(PHOTOS_HOME, wait_until="domcontentloaded")
        if auto:
            import time

            _AUTH_MARKERS = {"SAPISID", "__Secure-1PAPISID", "__Secure-3PAPISID"}
            print("waiting for login to complete (auto-detect, 10 min timeout)…")
            deadline = time.monotonic() + 600
            auth_names: set[str] = set()
            while time.monotonic() < deadline:
                cookies = context.cookies()
                auth_names = {c["name"] for c in cookies if c["name"] in _AUTH_MARKERS}
                if auth_names:
                    break
                time.sleep(2)
            if not auth_names:
                context.close()
                print("PROBE FAILED: no auth cookies detected within 10 minutes — "
                      "was the login completed in the opened window?", file=sys.stderr)
                return 1
            print(f"login detected via {sorted(auth_names)} — harvesting")
            cookies = context.cookies()
            context.close()
        else:
            input("…press Enter here AFTER logging in on the opened window> ")
            cookies = context.cookies()
            context.close()

    if not any(c["name"] in ("SID", "SAPISID", "__Secure-1PSID") for c in cookies):
        print("PROBE FAILED: no Google session cookies found after login — "
              "was the login completed in the opened window?", file=sys.stderr)
        return 1

    vault = cookie_vault.save(cookies)
    # Identity signal only — never cookie values (T-16-07).
    markers = sorted({c["name"] for c in cookies
                      if c["name"] in ("SID", "SAPISID", "__Secure-1PSID",
                                       "__Secure-3PSID", "LSID", "__Secure-1PAPISID",
                                       "__Secure-3PAPISID")})
    print(f"vault saved: {vault} (0600, untracked)")
    print(f"session cookies present: {len(cookies)} total; auth markers: {markers}")
    return 0


def _extract_sapisid() -> str | None:
    """SAPISID (or its __Secure- variants) is needed for the Authorization
    header some batchexecute calls expect. Returns None when absent; the
    listing still attempts cookie-only auth first."""
    try:
        for c in cookie_vault.load():
            if c.get("name") in ("SAPISID", "__Secure-1PAPISID", "__Secure-3PAPISID"):
                return c["value"]
    except cookie_vault.CookieVaultError as exc:
        raise SystemExit(f"PROBE FAILED: {exc}")
    return None


def _batchexecute(http: httpx.Client, rpcid: str, payload: list, origin: str) -> httpx.Response:
    """Issue ONE batchexecute POST replicating the public envelope shape:
    f.req carries [[ [rpcid, json(payload), None, 'generic'] ]], with the
    standard at/bt boilerplate; SAPISID-derived Authorization attached when
    available (xob0t/Google-Photos-Toolkit reference shapes)."""
    import hashlib
    import time

    inner = json_dumps([rpcid, json_dumps(payload), None, "generic"])
    freq = json_dumps([[json_dumps([inner])]])
    headers = {
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        "Origin": origin,
        "Referer": f"{origin}/",
    }
    sapisid = _extract_sapisid()
    if sapisid:
        now_ms = int(time.time() * 1000)
        auth_hash = hashlib.sha1(f"{now_ms} {sapisid} {origin}".encode()).hexdigest()
        headers["Authorization"] = f"SAPISIDHASH {now_ms}_{auth_hash}"
    body = f"f.req={freq}&at={query_escape(_extract_at())}&"
    resp = http.post(_BATCHEXECUTE_URL, headers=headers, content=body.encode())
    return resp


_AT_TOKEN = ""


def _extract_at() -> str:
    """The WIZ_global_data 'SNlM0e' anti-CSRF token from the album page —
    fetched fresh by the caller's page GET; the list flow caches it."""
    return _AT_TOKEN


def _list_album(url: str) -> int:
    """Plain-httpx internal RPC listing against a throwaway album."""
    global _AT_TOKEN
    http = httpx.Client(
        cookies=cookie_vault.cookies_for_httpx(),
        timeout=30.0,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                               "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"},
    )

    # Step 1: fetch the album page WITH session cookies — extracts the album's
    # internal id, the at-token, and batch-1 of items via the ds:1 parser.
    page = http.get(url)
    if page.status_code != 200:
        print(f"PROBE FAILED: album page returned HTTP {page.status_code} "
              f"(session cookies attached) — {redact_link(url)}", file=sys.stderr)
        return 1
    _AT_TOKEN_m = re.search(r'"SNlM0e":"([^"]+)"', page.text)
    _AT_TOKEN = _AT_TOKEN_m.group(1) if _AT_TOKEN_m else ""
    items = parse_af_initdata(page.text)
    print(f"album page (with session): HTTP {page.status_code}, "
          f"batch-1 count: {len(items)} — {redact_link(url)}")

    # Step 2: ONE follow-up batchexecute POST — the continuation attempt.
    # The continuation rpcid is undocumented; we probe with the observable
    # envelope. A failure mode here IS the finding (D-03 honesty): it tells
    # us whether session-cookie RPC needs more reverse-engineering, not
    # whether the mechanism is dead (the userscript reference proves it works
    # from inside a session).
    album_id_m = re.search(r"(AF1Qip[A-Za-z0-9_-]{20,})", page.text)
    album_id = album_id_m.group(1) if album_id_m else None
    if _AT_TOKEN and album_id:
        payload = [album_id, None, None, None, 1, None, None, 100]
        try:
            resp = _batchexecute(http, "EW6Kmf", payload, "https://photos.google.com")
            body = redact_tokens(resp.text[:2000])
            continuation_ok = resp.status_code == 200 and ")]}'" in resp.text
            print(f"follow-up RPC: HTTP {resp.status_code} "
                  f"(envelope {'present' if continuation_ok else 'ABSENT'})")
            print(f"follow-up body (first 2000 chars, redacted): {body}")
        except Exception as exc:  # noqa: BLE001 — the failure mode IS the evidence
            print(f"follow-up RPC failed: {redact_tokens(str(exc))}")
    else:
        print("follow-up RPC: skipped (missing at-token or album id on the page)")

    print("note: the browser mechanism is permanently local-only and never-CI-able; "
          "cookie expiry cadence is an accepted operational cost (2026-09-28 decision).")
    return 0


def json_dumps(obj) -> str:
    import json
    return json.dumps(obj, separators=(",", ":"))


def query_escape(s: str) -> str:
    from urllib.parse import quote
    return quote(s, safe="")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("bootstrap", help="interactive login + cookie harvest into the vault")
    sub.choices["bootstrap"].add_argument("--auto", action="store_true",
                                          help="auto-detect login completion instead of "
                                               "waiting for Enter (for non-interactive runs)")
    p_list = sub.add_parser("list", help="plain-httpx batchexecute album listing via vaulted cookies")
    p_list.add_argument("--url", required=False, default=None,
                        help="throwaway album share/URL (or put a full link in probes/*.link)")
    args = parser.parse_args(argv)

    if args.command == "bootstrap":
        return _bootstrap(auto=getattr(args, "auto", False))
    url = args.url
    if not url:
        links = sorted(Path(__file__).parent.glob("*.link"))
        if links:
            url = links[0].read_text().strip()
    if not url:
        raise SystemExit("PROBE FAILED: no album URL — pass --url or drop a full "
                         "link into an untracked probes/*.link file")
    return _list_album(url)


if __name__ == "__main__":
    raise SystemExit(main())
