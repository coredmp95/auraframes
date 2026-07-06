import argparse
import os
import sys

from dotenv import load_dotenv

from auraframes.aura import Aura


def build_parser() -> argparse.ArgumentParser:
    """Construct the root `aura-cli` parser. Subparsers are structured so
    `inspect`/`sync` siblings can be added in later phases (D-02)."""
    parser = argparse.ArgumentParser(prog='aura-cli')
    subparsers = parser.add_subparsers(dest='command', required=True)
    subparsers.add_parser('status', help='Check config/auth health and list account frames')
    return parser


def run_status(aura=None) -> int:
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
        return run_status()


if __name__ == '__main__':
    sys.exit(main())
