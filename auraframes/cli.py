import argparse
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger
from tqdm import tqdm

from auraframes.aura import Aura
from auraframes.aws.s3client import S3Client
from auraframes.aws.sqsclient import SQSClient
from auraframes.client import RateLimitError
from auraframes.models.frame import Frame
from auraframes.sync import scan_directory, compute_plan, execute_plan, ConsecutiveWriteFailureError

# First-N photos printed by default before truncating with a "+K more"
# summary line (D-06). Claude's discretion per 06-CONTEXT.md; real frames
# can hold 77+ assets (Phase 2 finding) so dumping everything by default
# isn't useful in a terminal.
INSPECT_PHOTO_LIMIT = 10


def build_parser() -> argparse.ArgumentParser:
    """Construct the root `aura-cli` parser. Subparsers are structured so
    `inspect`/`sync` siblings can be added in later phases (D-02).

    `--debug` lives on the root parser (folded todo, promoted from the
    `status`-only subparser) so it is parsed once regardless of which
    subcommand runs, and every future subcommand inherits the same
    quiet-by-default logging convention for free.
    """
    parser = argparse.ArgumentParser(prog='aura-cli')
    parser.add_argument(
        '--debug',
        action='store_true',
        default=False,
        help='Show verbose loguru request/response logging on stderr',
    )
    subparsers = parser.add_subparsers(dest='command', required=True)
    subparsers.add_parser('status', help='Check config/auth health and list account frames')
    inspect_parser = subparsers.add_parser('inspect', help="Inspect a frame's photos and metadata")
    inspect_parser.add_argument('--frame', required=True, help='Frame name (substring) or id')
    sync_parser = subparsers.add_parser('sync', help='Dry-run diff a local directory against a frame')
    sync_parser.add_argument('dir', help='Local directory to scan for photos')
    sync_parser.add_argument('--frame', required=True, help='Frame name (substring) or id')
    sync_parser.add_argument('--apply', action='store_true', default=False, help='Execute the plan (upload + delete) instead of only printing it')
    sync_parser.add_argument('--yes', action='store_true', default=False, help='Skip the confirmation prompt (required for --apply when running non-interactively)')
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


@dataclass
class FrameResolution:
    """Result of resolving a `--frame` CLI argument against the account's
    frame list (CLI-04). `status` is a discriminator — 'resolved',
    'ambiguous', or 'not_found' — deliberately not a raised exception
    (MOD-03 typed exceptions stays deferred; see 06-CONTEXT.md)."""
    frame: Frame | None
    status: str
    candidates: list[Frame] = field(default_factory=list)


def resolve_frame(target: str, frames: list[Frame]) -> FrameResolution:
    """Resolve a `--frame` value to a single Frame (CLI-04, D-01..D-04).

    Pure function — no I/O, no side effects. Resolution order:
    1. Case-insensitive substring match on `Frame.name` (D-01).
       - Exactly one match -> resolved (D-02).
       - More than one match -> ambiguous; the id fallback is NOT
         attempted (D-03).
    2. Zero name matches -> fall back to an exact (case-sensitive)
       match on `Frame.id`.
       - Exactly one match -> resolved (D-02).
       - Otherwise -> not_found, candidates is every frame on the
         account so the caller can list available names (D-04).
    """
    target_lower = target.lower()
    name_matches = [f for f in frames if target_lower in f.name.lower()]

    if len(name_matches) == 1:
        return FrameResolution(frame=name_matches[0], status='resolved', candidates=[])
    if len(name_matches) > 1:
        return FrameResolution(frame=None, status='ambiguous', candidates=name_matches)

    id_matches = [f for f in frames if f.id == target]
    if len(id_matches) == 1:
        return FrameResolution(frame=id_matches[0], status='resolved', candidates=[])

    return FrameResolution(frame=None, status='not_found', candidates=frames)


def run_inspect(frame_arg: str, aura=None, debug: bool = False) -> int:
    """Inspect command handler. Returns a process exit code (0 success, 1
    failure) — never calls sys.exit directly. Accepts an optional injected
    `Aura` (dependency-injection seam) so this is testable offline.

    `frame_arg` is argparse-required, not an env var, so (unlike
    `run_status`) there's no config-precheck step before constructing
    `Aura()`.
    """
    aura = aura or Aura()
    # Must run after Aura() construction (which registers the noisy sinks)
    # and before login/get_frames (the HTTP calls that trigger them).
    _configure_cli_logging(debug)

    try:
        aura.login()
    except Exception as e:
        # D-05: bad credentials, network error, or API drift all surface
        # here — a broad catch at the CLI boundary is correct.
        print(f'Login failed: {e}')
        return 1

    try:
        frames = aura.frame_api.get_frames()
        resolved = resolve_frame(frame_arg, frames)

        if resolved.status == 'ambiguous':
            print(f"'{frame_arg}' matches more than one frame name — re-run with --frame <id>:")
            for candidate in resolved.candidates:
                print(f'  - {candidate.name} (id: {candidate.id})')
            return 1

        if resolved.status == 'not_found':
            print(f"No frame matches name or id '{frame_arg}'. Available frames:")
            for candidate in resolved.candidates:
                print(f'  - {candidate.name} (id: {candidate.id})')
            return 1

        frame, total_asset_count = aura.frame_api.get_frame(resolved.frame.id)
        contributors = frame.contributors or []

        print(f'Frame: {frame.name} (id: {frame.id})')
        print(f'Owner: {frame.user.name} <{frame.user.email}>')
        print(f'Contributors ({len(contributors)}):')
        for contributor in contributors:
            print(f'  - {contributor.name} <{contributor.email}>')
        print(f'Assets: {total_asset_count}')

        assets = aura.get_all_assets(resolved.frame.id)
        shown = assets[:INSPECT_PHOTO_LIMIT]
        print(f'Photos (showing {len(shown)} of {len(assets)}, API order):')
        for asset in shown:
            print(f'  - {asset.id} | {asset.file_name} | {asset.taken_at_dt}')
        remaining = len(assets) - len(shown)
        if remaining > 0:
            print(f'  ... +{remaining} more')
    except Exception as e:
        # WR-01 fail-loud (D-05): surface post-login API drift instead of a
        # raw traceback.
        print(f'Failed to inspect frame: {e}')
        return 1

    return 0


def run_sync(dir_arg: str, frame_arg: str, apply: bool = False, yes: bool = False, aura=None, debug: bool = False) -> int:
    """Sync command handler (SYNC-01/SYNC-03/SYNC-04). Resolves the target
    frame, scans `dir_arg` locally, computes the upload/delete/unchanged plan
    via `auraframes.sync`, and prints a full (untruncated) report.

    Dry-run remains the default (`apply=False`): nothing is executed and this
    function returns after printing the plan, exactly as before Phase 8.

    When `apply=True`, after the plan is printed a confirmation gate runs
    (D-01/D-02/D-03/D-04) before `execute_plan()` (Phase 8 Plan 02) is called
    with real `S3Client()`/`SQSClient()` instances — the only place in this
    module that constructs them. A non-interactive invocation without `--yes`
    fails closed (D-03) rather than hanging on `input()`. On confirmation,
    `execute_plan()`'s result is printed as a separated upload/delete
    success/failure summary (D-10) and the exit code reflects any failure
    (SYNC-04).

    Returns a process exit code (0 success, 1 failure) — never calls
    sys.exit directly. Accepts an optional injected `Aura` (dependency-
    injection seam) so this is testable offline, mirroring `run_inspect`.
    """
    aura = aura or Aura()
    # Must run after Aura() construction (which registers the noisy sinks)
    # and before login/get_frames (the HTTP calls that trigger them).
    _configure_cli_logging(debug)

    try:
        aura.login()
    except RateLimitError as e:
        # Anti-abuse throttle/lockout escalated to reject login (the HTTP 475
        # seen in the select-asset-401-unauthorized session). Surface the
        # back-off message explicitly rather than as a generic login failure.
        print(f'Rate limited / locked out at login — {e}')
        return 1
    except Exception as e:
        # Fail-loud (D-05 convention): bad credentials, network error, or API
        # drift all surface here — a broad catch at the CLI boundary is correct.
        print(f'Login failed: {e}')
        return 1

    try:
        frames = aura.frame_api.get_frames()
        resolved = resolve_frame(frame_arg, frames)

        if resolved.status == 'ambiguous':
            print(f"'{frame_arg}' matches more than one frame name — re-run with --frame <id>:")
            for candidate in resolved.candidates:
                print(f'  - {candidate.name} (id: {candidate.id})')
            return 1

        if resolved.status == 'not_found':
            print(f"No frame matches name or id '{frame_arg}'. Available frames:")
            for candidate in resolved.candidates:
                print(f'  - {candidate.name} (id: {candidate.id})')
            return 1

        frame = resolved.frame
        assets = aura.get_all_assets(frame.id)

        # WR-02: scanned separately from the surrounding API calls so a
        # local filesystem error (missing/invalid `dir_arg`, permission
        # error reading a file) is reported distinctly from a remote
        # API/auth failure instead of being collapsed into the same
        # generic "Failed to sync frame" message below.
        try:
            scan = scan_directory(Path(dir_arg))
        except OSError as e:
            print(f'Failed to scan {dir_arg}: {e}')
            return 1

        plan = compute_plan(scan.local_hashes, assets, scan.skipped_non_image)

        print(f'Sync plan for {frame.name} (id: {frame.id}) — DRY RUN, nothing will be changed')
        print(f'To upload: {len(plan.to_upload)}')
        print(f'To delete: {len(plan.to_delete)}')
        print(f'Unchanged: {plan.unchanged}')

        # WR-03: local_hashes (and to_upload built from it) is populated in
        # filesystem-traversal order, which is OS/filesystem dependent and
        # not sorted -- sort here so dry-run output is reproducible across
        # runs/machines (e.g. diffable, stable for bug reports).
        for path in sorted(plan.to_upload):
            print(f'  + {path}')

        for asset in plan.to_delete:
            print(f'  - {asset.id} (taken {asset.taken_at_dt})')

        if plan.skipped_non_image > 0:
            print(f'{plan.skipped_non_image} non-photo files skipped')

        if plan.frame_no_hash > 0:
            print(f'{plan.frame_no_hash} frame assets without a content hash (e.g. videos) left untouched')

        if not apply:
            return 0

        # D-03: fail closed on a non-interactive invocation missing --yes --
        # never block on input() forever, never silently proceed.
        if not yes and not sys.stdin.isatty():
            print('--apply requires --yes when running non-interactively')
            return 1

        # D-01/D-02/D-04: a single confirmation gate covers the whole plan
        # (uploads + deletes together), echoing the resolved frame's name and
        # id so a substring --frame match can't silently apply to the wrong
        # frame.
        if not yes:
            answer = input(f'About to apply this plan to "{frame.name}" (id: {frame.id}). Proceed? [y/N] ')
            if answer.strip().lower() not in ('y', 'yes'):
                print('Aborted.')
                return 0

        # Real AWS clients are constructed here only, on confirmed apply --
        # execute_plan() itself never constructs them (offline-testable seam
        # from Phase 8 Plan 02).
        s3_client = S3Client()
        sqs_client = SQSClient()

        total = len(plan.to_upload) + len(plan.to_delete)
        # tqdm writes to stderr, so stdout-based test assertions (D-10's
        # summary, printed after the bar closes below) are unaffected.
        with tqdm(total=total, desc='Applying', unit='item') as bar:
            def _report_progress(kind, identifier, ok):
                bar.update(1)
                status = 'ok' if ok else 'FAIL'
                bar.set_postfix_str(f'{kind} {status} {identifier}')

            def _report_wait(remaining):
                # Inter-chunk cooldown -- the bar doesn't advance, so surface
                # the countdown in the postfix rather than looking frozen.
                bar.set_postfix_str(f'cooldown {remaining:.0f}s before next batch')

            result = execute_plan(
                plan, aura, frame.id, s3_client=s3_client, sqs_client=sqs_client,
                progress=_report_progress, on_wait=_report_wait,
            )

        # D-10: separated success/failure summary, each failed item named.
        print(f'Uploads: {result.upload_succeeded} succeeded, {len(result.upload_failures)} failed')
        for path, err in result.upload_failures:
            print(f'  ! {path}: {err}')
        print(f'Deletes: {result.delete_succeeded} succeeded, {len(result.delete_failures)} failed')
        for asset_id, err in result.delete_failures:
            print(f'  ! {asset_id}: {err}')

        return 1 if (result.upload_failures or result.delete_failures) else 0
    except RateLimitError as e:
        # The API is throttling/locking out this account mid-apply (HTTP
        # 429/475). execute_plan aborted the batch rather than emitting N
        # confusing per-item 401s -- surface the single back-off message.
        print(f'Aborted: {e}')
        return 1
    except ConsecutiveWriteFailureError as e:
        # A RUN of consecutive write failures with no 429/475 signal -- the
        # plain-HTTP-401 form of the anti-abuse trip (or another systemic
        # cut-off). execute_plan aborted after the run rather than emitting N
        # confusing per-item errors. Report what succeeded first, then the
        # distinct back-off message (deliberately worded differently from the
        # RateLimitError "Aborted:" path above so the two are distinguishable).
        print(f'{e.result.upload_succeeded} uploads and {e.result.delete_succeeded} '
              f'deletes succeeded before the run of failures.')
        print(str(e))
        return 1
    except Exception as e:
        # WR-01 fail-loud (D-05): surface post-login API drift instead of a
        # raw traceback.
        print(f'Failed to sync frame: {e}')
        return 1


def main(argv=None) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)

    if args.command == 'status':
        return run_status(debug=args.debug)
    if args.command == 'inspect':
        return run_inspect(args.frame, debug=args.debug)
    if args.command == 'sync':
        return run_sync(args.dir, args.frame, apply=args.apply, yes=args.yes, debug=args.debug)
    raise ValueError(f'Unhandled command: {args.command}')


if __name__ == '__main__':
    sys.exit(main())
