"""Offline tests for `aura-cli google-album` (plan 17-02 T2).

Zero network: resolution runs against AlbumSummary fakes (pure function);
the full command runs with a real GoogleSession over a MockTransport
replaying the protocol (home page -> share page -> snAcKc pages -> =d
sizes). Redaction is proven by grepping stdout for full AF1Qip tokens.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from auraframes.cli import (  # noqa: E402
    AlbumResolution,
    resolve_album,
    run_google_album,
)
from auraframes.google.client import GoogleSession  # noqa: E402
from auraframes.google.parsers import AlbumSummary  # noqa: E402

ALBUM_ID_1 = "AF1QipFAKEalbumONE" + "0" * 28 + "1"
ALBUM_ID_2 = "AF1QipFAKEalbumTWO" + "0" * 28 + "2"
ALBUM_ID_3 = "AF1QipFAKEalbumTHR" + "0" * 28 + "3"
ALBUMS = [
    AlbumSummary(album_id=ALBUM_ID_1, title="Vacances Corse",
                 share_url=f"https://photos.google.com/share/{ALBUM_ID_1}"),
    AlbumSummary(album_id=ALBUM_ID_2, title="Vacances Bretagne",
                 share_url=f"https://photos.google.com/share/{ALBUM_ID_2}"),
    AlbumSummary(album_id=ALBUM_ID_3, title="Famille 2024",
                 share_url=f"https://photos.google.com/share/{ALBUM_ID_3}"),
]


def test_resolve_album_by_unique_substring():
    r = resolve_album("corse", ALBUMS)
    assert isinstance(r, AlbumResolution)
    assert r.status == "resolved" and r.album.album_id == ALBUM_ID_1


def test_resolve_album_ambiguous_lists_candidates():
    r = resolve_album("vacances", ALBUMS)
    assert r.status == "ambiguous" and len(r.candidates) == 2


def test_resolve_album_not_found_carries_all_albums():
    r = resolve_album("alpes", ALBUMS)
    assert r.status == "not_found" and len(r.candidates) == 3


def test_resolve_album_direct_link_bypasses_names():
    r = resolve_album(f"https://photos.google.com/share/{ALBUM_ID_1}?key=K1", ALBUMS)
    assert r.status == "resolved" and r.album.album_id == ALBUM_ID_1


def test_resolve_album_direct_id_bypasses_names():
    r = resolve_album(ALBUM_ID_3, ALBUMS)
    assert r.status == "resolved"


# --- Full command over a stateful MockTransport ------------------------------

HOME_TOKEN = "AH_" + "H" * 40 + "0001"
SHARE_TOKEN = "AH_" + "S" * 40 + "0001"


def _home_html() -> str:
    rows = "".join(
        f'["{a.album_id}", "{a.title}", null], ' for a in ALBUMS)
    data_literal = '[[' + rows[:-2] + ']]'
    return (
        '<html><body><script>window.WIZ_global_data = '
        '{"SNlM0e": "SYNTH-AT", "FdrFJe": "123", "cfb2h": "boq_bl", '
        '"oPEP7c": "someone@example.com"};</script>'
        "<script>AF_initDataCallback({key: 'ds:0', hash: '1', data:"
        + data_literal + '});</script>'
        '</body></html>'
    )


def _share_html(album_id: str) -> str:
    return (
        "<html><body>"
        "<script>AF_initDataCallback({key: 'ds:1', hash: '2', "
        "data:[[\"album-header\", null]]});</script>"
        f"<script>window._continuation = \"{SHARE_TOKEN}\";</script>"
        "</body></html>"
    )


def _rpc_items(page: int, count: int) -> list:
    # Real Google media ids run ~48 chars after the AF1Qip prefix; keep the
    # synthetic ids above redact_link's 40-char threshold so the redaction
    # assertions below exercise the real shape, not a threshold edge.
    return [[f"AF1QipRPC{page:02d}{i:06d}" + "0" * 32,
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


def _router():
    state = {"posted": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "GET" and path == "/":
            return httpx.Response(200, text=_home_html())
        if request.method == "GET" and "/share/" in path:
            return httpx.Response(200, text=_share_html(ALBUM_ID_1))
        if request.method == "GET" and path.endswith("=d"):
            num = int(path.removesuffix("=d").rsplit("i", 1)[-1])
            return httpx.Response(206, text="x",
                                  headers={"Content-Range": f"bytes 0-0/{num * 10 + 3}"})
        if request.method == "POST":
            state["posted"] += 1
            page = state["posted"]
            has_next = page < 2
            tok = ("AH_" + "N" * 40 + f"{page + 1:04d}") if has_next else None
            return httpx.Response(200, text=_rpc_response(_rpc_items(page, 5), tok))
        return httpx.Response(404)

    return handler


def _session() -> GoogleSession:
    return GoogleSession([{"name": "SID", "value": "x", "domain": ".google.com",
                           "path": "/"}],
                         transport=httpx.MockTransport(_router()))


def test_google_album_by_name_full_enumeration_and_disk_weight(capsys):
    rc = run_google_album("corse", session=_session())
    assert rc == 0
    out = capsys.readouterr().out
    # Resolution echo (redacted id shape), enumeration totals, disk weight.
    assert "Album: Vacances Corse" in out
    assert "Items: 10" in out          # 5 + 5 across 2 snAcKc pages
    assert "exhausted: cleanly" in out
    assert "Disk weight:" in out and "MiB" in out
    # Per-item table with redacted id shapes only.
    assert "Per-item" in out
    assert ALBUM_ID_1 not in out       # full tokens never print
    assert "AF1QipRPC01" + "0" * 32 not in out
    assert "AF1Qip…" in out            # the redacted shape does print


def test_google_album_ambiguous_prints_numbered_and_exits_2(capsys):
    rc = run_google_album("vacances", session=_session())
    assert rc == 2
    out = capsys.readouterr().out
    assert "more than one album" in out
    assert "1. Vacances Corse" in out
    assert "2. Vacances Bretagne" in out


def test_google_album_not_found_prints_albums_and_exits_2(capsys):
    rc = run_google_album("alpes", session=_session())
    assert rc == 2
    out = capsys.readouterr().out
    assert "No album matches" in out
    assert "Famille 2024" in out


def test_google_album_by_direct_link_enumerates(capsys):
    rc = run_google_album(f"https://photos.google.com/share/{ALBUM_ID_1}?key=K1",
                          session=_session())
    assert rc == 0
    out = capsys.readouterr().out
    assert "Items: 10" in out


def test_google_album_list_flag_prints_numbered_albums(capsys):
    rc = run_google_album(None, session=_session(), list_all=True)
    assert rc == 0
    out = capsys.readouterr().out
    assert "3 shared albums:" in out
    assert "1. Vacances Corse" in out
    assert "3. Famille 2024" in out
    assert ALBUM_ID_1 not in out       # redaction holds on the listing too


def test_google_album_requires_target_without_list(capsys):
    rc = run_google_album(None, session=_session())
    assert rc == 2
    assert "--list" in capsys.readouterr().out


def test_google_album_without_vault_fails_cleanly(monkeypatch, capsys):
    """No vault (and no injected session) -> clean failure, exit 1, and no
    network reach whatsoever (the vault paths are pointed at nothing)."""
    monkeypatch.setattr("auraframes.google.vault.DEFAULT_VAULT_PATH",
                        Path("/nonexistent/prod-vault.json"))
    monkeypatch.setattr("auraframes.google.vault.LEGACY_VAULT_PATH",
                        Path("/nonexistent/legacy-vault.json"))
    rc = run_google_album("anything")  # no session injected; vault absent
    assert rc == 1
    assert "google-album failed" in capsys.readouterr().out
