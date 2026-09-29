# Plan 17-02 Summary — CLI wiring: google-link, google-album, Google-aware status

Wired the migrated `auraframes/google/` machinery into the CLI: `google-link` (one
command for link AND re-link), `google-album` (name/link/id selection with the full
enumeration + exact disk weight), and the Google section in `status` — every path
offline-tested through injected seams (TEST-02), zero browser, zero live network.

## What was delivered

- `auraframes/cli.py`:
  - `run_google_link(*, debug, bootstrap_fn=None)` — dedicated-profile env
    (`AURA_PROBE_CHROME_PROFILE`) enforced before anything runs (T-16-06 carried;
    unset → loud failure, exit 1); the `bootstrap_fn` seam defaults to the package's
    `default_bootstrap`; a present-but-expired session gets the one-line "refreshing"
    notice (LGS-02 re-link-is-same-command); output is vault path + 0600 + marker
    NAMES, never values (T-16-07/T-17-05, tests grep for planted fake values).
  - `run_google_album(target, *, debug, session=None, list_all=False)` — resolution
    mirrors `resolve_frame`'s contract as `AlbumResolution` (D-05): share URL /
    app.goo.gl / AF1Qip id resolve directly (the album id extracted from the URL);
    otherwise case-insensitive title substring — one match resolves, several print a
    NUMBERED list and exit 2 (no silent pick, T-17-06), none prints the available
    albums and exits 2. On resolution: full `enumerate_album` walk + exact
    `measure_disk_weight` sizing, printed as count / pages / exhausted flag /
    byte-MiB-min-max-avg plus a per-item table (index | id shape | WxH | bytes).
    `--list` prints the account's shared albums (numbered, redacted ids).
  - `status` extension — `_google_status_section(google_session=None)`: `linked:` /
    `account:` / `session:` lines from `GoogleSession.is_linked()` + `account_email()`
    (LGS-03/D-02: email + state only, never a cookie value; a missing vault prints
    `linked: no` with zero network calls; a failing check degrades to an honest
    `unreachable`).
  - Package support this task needed: `parsers.extract_initdata(html, key)` (any ds:N
    block) + `parse_album_summaries`/`AlbumSummary` (ds:0 walk), `enumerate.
    list_shared_albums()` (titles from ds:0, share URLs constructed in the proven
    /share/<id> shape, no guessed counts), and `auraframes/google/bootstrap.py`
    (dedicated-profile resolution + `run_bootstrap` with lazy playwright import —
    the phase-16-proven harvest, migrated).
- Tests: `tests/test_cli_google_link.py` (9), `tests/test_cli_status_google.py` (6),
  `tests/test_cli_google_album.py` (12) — 22 new offline tests. The album tests run
  the full command against a stateful MockTransport (home → share → snAcKc pages →
  =d sizes) and prove redaction by grepping stdout for full AF1Qip tokens; the
  synthetics were widened past the 40-char redaction threshold after the first run
  caught that short ids leak through un-redacted (the test caught a real threshold
  edge).
- `README.md` — the six-command table, the Google section (dedicated-profile
  prerequisite, re-link-is-one-command, enumeration/disk-weight output shape, the
  two-sentence privacy posture).

## Deviations

- None material. Two in-discretion choices: `AlbumSummary` carries no guessed item
  counts (D-06: the authoritative count is enumerate_album's), and `google-album`
  without `target`/`--list` prints the usage hint and exits 2 instead of erroring.
- `resolve_album`'s direct-URL branch extracts the album id from the URL (the plan's
  "use it directly" reads on the resolved album, and the enumeration needs the id).

## Self-Check: PASSED

- Verify T1/T2/T3 commands from the plan: all green, including
  `uv run aura-cli google-album --help` and `run_google_link` importability.
- `uv run pytest -q -m "not live"`: **345 passed** (286 pre-phase; 37 package/probe +
  22 CLI), 6 deselected (live).
- `aura-cli google-link --help` / `google-album --help` / `status --help` all exit 0.
- No test launches a browser or hits live Google (TEST-02).

## Post-execution addendum — live-decoded album listing surface

The plan's assumed album-listing surface ("the ds:0-driven album list from the
logged-in home") was wrong: the home page's ds:5 is the photo feed. The real
surface, live-decoded this session, is **photos.google.com/albums' ds:5** —
row shape `[cover_id AF1Qip…, [cover_url…], null, null, {<int-key>:
[4, title, [dates], item_count, 1, page_key_b64, …, share_token AF1Qip…, …]}]`.
`list_shared_albums()` reads that page and yields titles + metadata counts +
constructed share URLs (the b64-decoded page_key verified byte-for-byte). Name
resolution, `--list` and the enumeration then run RPC-first (see the 17-01
summary addendum). End-to-end live proof through the CLI's own code path:
`google-album "Cadre"` machinery → 24/24 items, exhausted cleanly, 86.6 MiB exact.
