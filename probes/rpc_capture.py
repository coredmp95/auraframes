"""RPC shape capture (plan 16-02 continuation — read-only).

Opens the album page in the dedicated logged-in Chrome profile (same profile
as the bootstrap), auto-scrolls a bounded number of times, and records every
batchexecute POST the Google Photos frontend itself emits (rpcid + f.req
payload). This is the one-time shape capture the plain-httpx continuation
then replicates — exactly how the public reference implementation learned
the RPC shapes.

Read-only: no clicks, no writes, no UI interaction beyond scrolling.
Output: /tmp/gsd-rpc-capture.json (untracked) + a redacted stdout summary.
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from probes.common import redact_link  # noqa: E402

OUT = Path("/tmp/gsd-rpc-capture.json")
SCROLLS = int(sys.argv[2]) if len(sys.argv) > 2 else 25
PAUSE_S = 1.2


def main() -> int:
    url = sys.argv[1]
    from playwright.sync_api import sync_playwright  # lazy, in-function ONLY

    captured: list[dict] = []

    def on_request(request):
        if "batchexecute" not in request.url:
            return
        rpcid_m = re.search(r"rpcids=([^&]+)", request.url)
        body = request.post_data or ""
        captured.append({
            "url_query": request.url.split("?")[-1][:300],
            "rpcid": rpcid_m.group(1) if rpcid_m else None,
            "freq_head": body[:1200],
        })

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(_profile()), headless=False, channel="chrome",
            args=["--disable-blink-features=AutomationControlled"])
        page = context.pages[0] if context.pages else context.new_page()
        page.on("request", on_request)
        print(f"opening {redact_link(url)}")
        page.goto(url, wait_until="domcontentloaded")
        time.sleep(3)
        for i in range(SCROLLS):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(PAUSE_S)
            if i % 5 == 0:
                print(f"  scroll {i}/{SCROLLS}, captured {len(captured)} batchexecute calls")
        time.sleep(2)
        context.close()

    OUT.write_text(json.dumps(captured, indent=2))
    print(f"\ncaptured {len(captured)} batchexecute calls -> {OUT}")
    for c in captured[:12]:
        print(f"  rpcid={c['rpcid']}  freq[:120]={c['freq_head'][:120]!r}")
    return 0


def _profile() -> Path:
    import os
    profile = os.environ.get("AURA_PROBE_CHROME_PROFILE", "").strip()
    if not profile:
        raise SystemExit("AURA_PROBE_CHROME_PROFILE unset")
    return Path(profile).expanduser().resolve()


if __name__ == "__main__":
    raise SystemExit(main())
