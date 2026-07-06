---
created: 2026-07-06T13:46:01.671Z
title: Promote --debug flag to a global CLI convention
area: cli
files:
  - auraframes/cli.py
---

## Problem

Phase 05-02 added a `--debug` flag to the `status` subcommand only (quiet-by-default
loguru logging, `--debug` restores full verbose stderr output). The user flagged that
this pattern should apply to *all* future CLI functionality, not just `status` — Phase 6
(`inspect`), Phase 7 (`sync`), and Phase 8 (`upload`) will each add new subcommands, and
each one will hit the same verbose-loguru-noise problem `_configure_cli_logging()` in
`auraframes/cli.py` was built to solve.

If each future subcommand reinvents its own `--debug` flag (as 05-02 did, since `aura.py`
is frozen per D-04 and the fix lives entirely in the CLI layer), the flag will need to be
threaded through argparse and wired to `_configure_cli_logging()` again and again.

## Solution

TBD — when Phase 6's CLI surface (`inspect`) is designed, consider promoting `--debug`
from a per-subcommand flag to a global `aura-cli` flag parsed before the subcommand
(e.g. `aura-cli --debug inspect ...`), so `_configure_cli_logging()` is invoked once in
`main()` regardless of which subcommand runs, instead of being duplicated per-subparser.
