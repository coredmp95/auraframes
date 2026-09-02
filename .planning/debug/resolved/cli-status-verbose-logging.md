---
status: resolved
trigger: "UAT gap diagnosis for phase 05-cli-skeleton-status, Test 1: `aura-cli status` prints verbose loguru request/response logging (headers, cookies, full bodies) interleaved with the intended concise output. User: 'well .. realy to verbose, maybe add a --debug to get all the answer ..'"
created: 2026-07-06T13:00:11Z
updated: 2026-09-02T00:00:00Z
---

## Current Focus

hypothesis: CONFIRMED - see Resolution
test: reproduced via offline harness (tests/offline.py:offline_aura) + direct stderr capture
expecting: n/a - root cause confirmed
next_action: n/a - goal is find_root_cause_only, handing off to plan-phase --gaps

## Symptoms

expected: `aura-cli status` prints only `AURA_EMAIL: set`, `AURA_PASSWORD: set`, `Logged in as <email>`, `N frames:`, and one `  - <name> (id: <id>)` line per frame.
actual: Two config lines print correctly, then a large block of loguru INFO+DEBUG log lines (full request/response bodies, headers, cookies for /login.json and /frames.json) appear before the final login/frame-listing lines. Functional data is correct; only the noise is wrong.
errors: None - not a crash.
reproduction: Test 1 in .planning/phases/05-cli-skeleton-status/05-UAT.md - run `aura-cli status` with real (or offline-fixture) credentials.
started: Present since Aura._init_logger() was written (pre-existing in auraframes/aura.py, unchanged per D-04); surfaced now because phase 05 is the first CLI entry point that instantiates a real `Aura()` and puts stdout output next to it in an interactive terminal.

## Eliminated

(none - hypothesis confirmed on first test)

## Evidence

- timestamp: 2026-07-06T13:05:00Z
  checked: auraframes/aura.py:136-145 (`Aura._init_logger`)
  found: |
    def _init_logger(self):
        os.makedirs('logs/', exist_ok=True)
        # logger.remove()  # remove / set this to debug if needed
        logger.add(sys.stderr, level="INFO", format="...Context: {extra}")
        logger.add('logs/file_{time}.log')
    The `logger.remove()` call that would clear loguru's auto-registered
    default handler (id 0, sys.stderr, unrestricted level) is present in
    source but commented out.
  implication: Every `Aura()` instantiation ADDS a second stderr sink on top
    of loguru's default one, rather than replacing it. Both sinks write to
    sys.stderr for the lifetime of the process.

- timestamp: 2026-07-06T13:06:00Z
  checked: auraframes/client.py - Client.get/post/put/delete
  found: Every HTTP call does `logger.info(f'{METHOD} request to {url}', query_params=..., headers=..., data=_redact(data))` followed by `logger.debug(f'Response ({status}), body: {_redact(response.json())}')`. `login()` triggers one POST, `get_frames()` triggers one GET - both call sites hit this.
  implication: Two log calls per HTTP request (one INFO, one DEBUG) x2 requests (login, get_frames) = 4 log events, each written to BOTH stderr sinks - explaining the "large block" the user saw.

- timestamp: 2026-07-06T13:08:00Z
  checked: Direct repro - constructed `tests.offline.offline_aura()` (the same `Aura(client=Client(transport=MockTransport(...)))` composition phase-05 tests use) and called `auraframes.cli.run_status(aura=...)` in a fresh subprocess, capturing stdout and stderr to separate files.
  found: |
    stdout.txt (5 lines, exactly as expected):
      AURA_EMAIL: set
      AURA_PASSWORD: set
      Logged in as you@example.invalid
      1 frames:
        - Fake Frame (id: frame-fake-0001)
    stderr.txt (7 lines) included, among others:
      INFO | auraframes.client:post:69 - POST request to /login.json                    <- default loguru sink (id 0), default format
      INFO | auraframes.client:post:69 | POST request to /login.json Context: {'data': {'user': {'email': ..., 'password': '***REDACTED***'}, ...}, 'headers': None}   <- custom sink added by _init_logger (level=INFO, custom format w/ Context)
      DEBUG | auraframes.client:post:74 - Response (200), body: {'result': {'current_user': {... 'auth_token': '***REDACTED***'}}}   <- ONLY appears via the default sink (custom sink is level=INFO, would filter DEBUG out)
      INFO | auraframes.client:get:57 - GET request to /frames.json
      INFO | auraframes.client:get:57 | GET request to /frames.json Context: {...}
      DEBUG | auraframes.client:get:62 - Response (200), body: {full frames.json payload}
  implication: CONFIRMED - two independent stderr handlers are active
    simultaneously: (1) loguru's library-default handler, auto-registered at
    import time with no level ceiling (passes DEBUG), plain `LEVEL | name:func:line - message` format - this is what leaks full response bodies (including nested `user` dicts) to the terminal; (2) the custom
    handler `_init_logger()` explicitly adds at level=INFO with a
    `Context: {extra}` format - this duplicates the request-line log a
    second time and also surfaces headers/query_params/redacted-data via
    the `{extra}` context, even though secrets themselves are redacted.
    Every request produces up to 3 visible stderr lines (2x INFO
    duplicate + 1x DEBUG body dump), all interleaved with the CLI's stdout
    prints because both streams render to the same terminal.

- timestamp: 2026-07-06T13:09:00Z
  checked: tests/test_cli_status.py assertions
  found: All three tests call `capsys.readouterr().out` only - `.err` (stderr) is never inspected or asserted on.
  implication: This is exactly why "the format already covered by tests/test_cli_status.py" never caught the noise - the test suite is stdout-only by design (per its own docstring: "Offline tests... calls run_status() directly"), so the stderr leak from `_init_logger()`'s always-on logging sinks passes silently through CI even though it fires on every single test run identical to the live CLI path.

## Resolution

root_cause: |
  `Aura._init_logger()` (auraframes/aura.py:136-145, unchanged per D-04) adds
  a formatted stderr sink at level=INFO on every `Aura()` construction but
  never removes loguru's own auto-registered default stderr handler (the
  `logger.remove()` call needed to do so is present in source but commented
  out on line 140). This leaves TWO active stderr handlers for the lifetime
  of the CLI process:
    1. loguru's library-default handler (unrestricted level, passes DEBUG) -
       leaks full request/response bodies (via `Client.*`'s
       `logger.debug(f'Response ..., body: {...}')` calls in
       auraframes/client.py) to the terminal.
    2. The `_init_logger()`-added handler (level=INFO, custom
       `Context: {extra}` format) - duplicates every request-level log line
       and surfaces headers/query_params/data via `{extra}`.
  Because `aura-cli status` (auraframes/cli.py:run_status) constructs a real
  `Aura()` and performs a login + one frame-listing call, both handlers fire
  for every HTTP call made during `status`, producing the verbose block the
  user saw between the CLI's own `print()` lines - stdout and stderr are
  separate streams but render interleaved in an interactive terminal.
  tests/test_cli_status.py doesn't catch this because it only asserts
  against `capsys.readouterr().out`, never `.err`.
fix: |
  Delivered by plan 05-02 (gap closure), not by this session (goal was
  find_root_cause_only). `_configure_cli_logging(debug)` in auraframes/cli.py
  drops every accumulated loguru handler by default and restores a single
  WARNING-level stderr sink; `--debug` on the root parser is a no-op that
  leaves `_init_logger()`'s sinks in place. Wired into run_status, run_inspect
  and run_sync. auraframes/aura.py:_init_logger() left unchanged per D-04.
verification: |
  tests/test_cli_status.py::test_status_quiet_by_default_suppresses_verbose_stderr
  asserts 'request to' is absent from captured stderr (the RED assertion pre-fix).
  Verified present in the tree at milestone v2.0 close.
files_changed:
  - auraframes/cli.py
  - tests/test_cli_status.py
