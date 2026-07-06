import argparse
import os
import sys

from dotenv import load_dotenv
from loguru import logger

from auraframes.aura import Aura


def build_parser() -> argparse.ArgumentParser:
    """Construct the root `aura-cli` parser. Subparsers are structured so
    `inspect`/`sync` siblings can be added in later phases (D-02)."""
    parser = argparse.ArgumentParser(prog='aura-cli')
    subparsers = parser.add_subparsers(dest='command', required=True)
    status_parser = subparsers.add_parser('status', help='Check config/auth health and list account frames')
    status_parser.add_argument(
        '--debug',
        action='store_true',
        default=False,
        help='Show verbose loguru request/response logging on stderr',
    )
    return parser


def _configure_cli_logging(debug: bool) -> None:
    """Neutralize (or leave alone) loguru's stderr handlers for the CLI.

    `Aura.__init__` -> `Aura._init_logger()` (frozen per D-04) adds a
    level=INFO stderr sink on every construction but never removes loguru's
    auto-registered default stderr handler (its `logger.remove()` is
    commented out), so two stderr handlers fire on every HTTP call. Because
    `aura.py` cannot be edited, this CLI-side helper re-initializes loguru's
    sinks *after* `Aura()` construction to compensate for the frozen file's
    missing cleanup.

    - debug=True: no-op — every sink `_init_logger()` registered stays
      active, reproducing today's full verbose output (opt-in per the
      user's UAT suggestion).
    - debug=False (default): drop every accumulated handler, then restore
      on-disk logging (the same `logs/file_{time}.log` sink target
      `_init_logger()` uses) plus a stricter `sys.stderr` sink at level
      WARNING so genuine warnings/errors still surface without the
      INFO/DEBUG request/response spam.
    """
    if debug:
        return

    logger.remove()
    os.makedirs('logs/', exist_ok=True)
    logger.add('logs/file_{time}.log')
    logger.add(sys.stderr, level='WARNING')


def run_status(aura=None, debug: bool = False) -> int:
    """Status command handler. Returns a process exit code (0 success, 1
    failure) — never calls sys.exit directly. Accepts an optional injected
    `Aura` (dependency-injection seam) so this is testable offline."""
    # Config health check (D-07) — must run first; never print the password
    # value, only the literal set/NOT SET.
    email_set = bool(os.getenv('AURA_EMAIL'))
    password_set = bool(os.getenv('AURA_PASSWORD'))
    print(f"AURA_EMAIL: {'set' if email_set else 'NOT SET'}")
    print(f"AURA_PASSWORD: {'set' if password_set else 'NOT SET'}")

    if not (email_set and password_set):
        # D-09: stop immediately after the config check — no Aura, no
        # network call, when either credential is missing.
        return 1

    aura = aura or Aura()
    # Must run after Aura() construction (which registers the noisy sinks)
    # and before login/get_frames (the HTTP calls that trigger them).
    _configure_cli_logging(debug)

    try:
        aura.login()
    except Exception as e:
        # D-08: bad credentials, network error, or API drift all surface
        # here — a broad catch at the CLI boundary is correct.
        print(f'Login failed: {e}')
        return 1

    frames = aura.frame_api.get_frames()
    print(f'Logged in as {os.getenv("AURA_EMAIL")}')
    print(f'{len(frames)} frames:')
    for frame in frames:
        print(f'  - {frame.name} (id: {frame.id})')

    return 0


def main(argv=None) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)

    if args.command == 'status':
        return run_status(debug=args.debug)


if __name__ == '__main__':
    sys.exit(main())
