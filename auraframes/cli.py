import argparse
import hashlib
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
from auraframes.ratelimit import WriteBudget, check_geo, _default_resolver, GeoMismatchError, BudgetExhausted
from auraframes.reconcile import apply_reconciliation, find_placeholders
from auraframes.sync import scan_directory, compute_plan, execute_plan, ConsecutiveWriteFailureError
from auraframes.utils.settings import (
    AURA_WRITE_BUDGET_CAPACITY,
    AURA_WRITE_BUDGET_REFILL_PER_MIN,
    AURA_WRITE_BUDGET_WAIT,
    AURA_WRITE_BUDGET_MAX_WAIT,
    AURA_COUNTRY,
    AURA_GEO_FAIL_OPEN,
    AURA_STATE_DIR,
)

# execute_plan's own defaults for the two budget-wait knobs (auraframes/sync.py:
# wait_on_budget=True, max_wait_seconds=3600.0). Used below to forward the
# AURA_WRITE_BUDGET_WAIT / AURA_WRITE_BUDGET_MAX_WAIT env values only when they
# would actually change execute_plan's behavior, preserving the Phase 08
# "defaults don't override execute_plan defaults" contract.
_EXECUTE_PLAN_DEFAULT_WAIT = True
_EXECUTE_PLAN_DEFAULT_MAX_WAIT = 3600.0

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
    # The three tiers of "no longer in the local directory" (D-02/D-03).
    # Hiding is the default because the frame has no photo-count limit, so a
    # mistaken sync should cost visibility, never photos. argparse enforces
    # the mutual exclusion at parse time (V5).
    removal_group = sync_parser.add_mutually_exclusive_group()
    removal_group.add_argument('--delete', action='store_true', default=False,
                               help='Remove gone-local photos from the frame instead of hiding them (frame-scoped; the photo leaves this frame)')
    removal_group.add_argument('--hard-delete', action='store_true', default=False, dest='hard_delete',
                               help='IRREVERSIBLY destroy gone-local photos instead of hiding them (account-wide; requires typing the exact count to confirm)')

    # `push` = purely additive upload from a supply ("buffet") directory. Unlike
    # `sync`, the frame is NOT diffed-to-match the directory: nothing is ever
    # deleted (structurally -- to_delete is forced empty). Photos already on the
    # frame are still skipped via the md5 diff, so only new files upload. The
    # probe flags (--limit/--batch-size/--chunk-delay) make it the safe tool for
    # empirically measuring the anti-abuse write budget without touching
    # existing frame photos.
    push_parser = subparsers.add_parser('push', help='Upload photos from a directory to a frame (additive -- never deletes)')
    push_parser.add_argument('dir', help='Local directory of photos to upload (a supply/"buffet"; the frame is NOT synced to match it)')
    push_parser.add_argument('--frame', required=True, help='Frame name (substring) or id')
    push_parser.add_argument('--apply', action='store_true', default=False, help='Execute the upload instead of only printing the plan')
    push_parser.add_argument('--yes', action='store_true', default=False, help='Skip the confirmation prompt (required for --apply when running non-interactively)')
    push_parser.add_argument('--limit', type=int, default=None, help='Upload at most N photos this run (for controlled anti-abuse budget probing)')
    push_parser.add_argument('--batch-size', type=int, default=None, dest='batch_size', help='Assets per select_asset/batch_update call (default 50)')
    push_parser.add_argument('--chunk-delay', type=float, default=None, dest='chunk_delay', help='Seconds to pause between write chunks (default 5)')
    # Proactive write-rate-budget + geo pre-flight guard overrides (Phase 09,
    # ANTI-06). `sync` deliberately does NOT expose these -- `sync --apply`
    # still gets the budget/geo guard by default (built from AURA_* env vars
    # in run_sync), just without per-run override flags this phase.
    push_parser.add_argument('--max-wait', type=float, default=None, dest='max_wait', help='Max seconds to wait for write budget before stopping (default 3600)')
    push_parser.add_argument('--no-wait', action='store_true', default=False, help='Stop immediately instead of waiting when the write budget is exhausted')
    push_parser.add_argument('--country', default=None, help='Override the expected account country for the geo pre-flight guard (default from AURA_COUNTRY)')
    push_parser.add_argument('--ignore-budget', action='store_true', default=False, dest='ignore_budget', help='Escape hatch: bypass the write budget entirely for this run')

    # `reconcile` = data hygiene on EXISTING stuck placeholder rows (REL-05,
    # D-13) -- deliberately outside the sync/push loop. Report-only by
    # default; `--remove` is required to attempt any write, mirroring
    # `--apply`'s report-vs-mutate split.
    reconcile_parser = subparsers.add_parser(
        'reconcile', help='Report (and optionally remove) stuck placeholder rows on a frame')
    reconcile_parser.add_argument('--frame', required=True, help='Frame name (substring) or id')
    reconcile_parser.add_argument(
        '--remove', action='store_true', default=False,
        help='Attempt removal of stuck placeholder rows instead of only reporting them')
    reconcile_parser.add_argument(
        '--yes', action='store_true', default=False,
        help='Skip the confirmation prompt (required for --remove when running non-interactively)')
    reconcile_parser.add_argument(
        '--mechanism', choices=['remove', 'hard-delete', 'complete'], default='remove',
        help="Which removal mechanism to attempt. 'remove' (the default) is confirmed working "
             "live as of 2026-09-03 (plan 11-06); 'hard-delete' is unconfirmed; "
             "'complete' is not yet implemented")
    reconcile_parser.add_argument(
        '--max-age-hours', type=float, default=24.0, dest='max_age_hours',
        help='Minimum age in hours for a placeholder row to be reported as stuck rather than '
             'recently created (default 24)')
    # Plan 11-06, Task 1: explicit opt-in on `find_placeholders`'
    # `unknown_age_policy` -- corrects D-15's unconditional form now that
    # plan 11-05 established live that `created_at` is never sent by this
    # API, which made the unconditional form permanently inert rather than
    # conservative (see auraframes/reconcile.py's find_placeholders
    # docstring). Bare `--remove` (this flag omitted) is BYTE-FOR-BYTE
    # unchanged: an unresolvable creation time still lands in unknown_age
    # and is never a removal candidate. Keyword-only on the Python side and
    # its own explicitly named flag here -- nothing promotes a row by
    # accident.
    reconcile_parser.add_argument(
        '--include-unknown-age', action='store_true', default=False, dest='include_unknown_age',
        help='Explicit opt-in: treat placeholder rows whose creation time this API never sends '
             '(unknown_age) as eligible for removal too, not just rows old enough per '
             '--max-age-hours. Without this flag, --remove cannot touch unknown-age rows.')
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
        # REL-05, D-13: computed via the exact same pure function
        # `run_reconcile` calls, so the two counts can never disagree.
        print(f'Placeholder rows: {find_placeholders(assets).placeholder_count} '
              f'(run `aura-cli reconcile --frame ...` for detail)')
    except Exception as e:
        # WR-01 fail-loud (D-05): surface post-login API drift instead of a
        # raw traceback.
        print(f'Failed to inspect frame: {e}')
        return 1

    return 0


def run_reconcile(frame_arg: str, *, remove: bool = False, yes: bool = False, mechanism: str = 'remove',
                   max_age_hours: float = 24.0, include_unknown_age: bool = False,
                   aura=None, debug: bool = False) -> int:
    """Reconcile command handler (REL-05, D-13) -- data hygiene on EXISTING
    stuck placeholder rows, deliberately outside the sync/push loop. Reports
    how many placeholder rows a frame carries unconditionally, whether or
    not any removal mechanism works, and (only when `remove=True`) attempts
    a bounded, gated removal. Returns a process exit code (0 success, 1
    failure) -- never calls sys.exit directly. Accepts an optional injected
    `Aura` (dependency-injection seam), mirroring `run_inspect`.

    `include_unknown_age` (plan 11-06, Task 1, CLI-side `--include-unknown-age`)
    is the explicit opt-in on `find_placeholders`' `unknown_age_policy` --
    default `False` reproduces today's behaviour exactly (an unresolvable
    creation time stays in `unknown_age`, never a removal candidate).
    """
    aura = aura or Aura()
    # Must run after Aura() construction (which registers the noisy sinks)
    # and before login/get_frames (the HTTP calls that trigger them).
    _configure_cli_logging(debug)

    try:
        aura.login()
    except Exception as e:
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

        if not assets:
            # T-11-11: an empty listing cannot be distinguished from a
            # frame with genuinely no placeholders -- refuse to report a
            # reassuring zero on no data.
            print(f'No assets returned for "{frame.name}" (id: {frame.id}) -- an empty asset '
                  f'listing cannot be distinguished from a frame with no placeholders. Refusing '
                  f'to report zero placeholders on no data.')
            return 1

        # REL-05, D-13: the exact same pure function `run_inspect` calls, so
        # the two counts can never disagree. `unknown_age_policy` defaults
        # to 'unknown_age' -- 'stuck' only when --include-unknown-age was
        # explicitly passed (plan 11-06, Task 1).
        unknown_age_policy = 'stuck' if include_unknown_age else 'unknown_age'
        result = find_placeholders(assets, age_threshold_seconds=max_age_hours * 3600,
                                    unknown_age_policy=unknown_age_policy)

        print(f'Frame: {frame.name} (id: {frame.id})')
        print(f'Assets scanned: {result.total_scanned}')
        print(f'Placeholder rows: {result.placeholder_count}')
        print(f'  stuck (older than {max_age_hours}h): {len(result.stuck)}')
        print(f'  recently created (may still be processing): {len(result.recently_created)}')
        print(f'  creation time unknown: {len(result.unknown_age)}')
        for asset in result.stuck:
            print(f'    - {asset.id}')

        if not remove:
            # D-13: reconcile without --remove performs no write of any
            # kind -- return here, before any write path is reachable.
            return 0

        # D-13/D-16: --remove continuation. Fail closed on a non-interactive
        # invocation missing --yes -- never block on input() forever, never
        # silently proceed (mirrors run_sync's identical check verbatim).
        if not yes and not sys.stdin.isatty():
            print('--remove requires --yes when running non-interactively')
            return 1

        if not yes:
            if mechanism == 'hard-delete':
                # Same escalated-friction gate as run_sync's hard_delete
                # branch: this primitive is irreversible and account-wide,
                # so a reworded y/N is too easy to answer reflexively.
                count = len(result.stuck)
                print(f'IRREVERSIBLE: {count} row(s) will be permanently destroyed '
                      f'account-wide via hard-delete. This cannot be undone.')
                answer = input(f'To confirm, type the number of rows to hard-delete ({count}): ')
                if answer.strip() != str(count):
                    print('Aborted.')
                    return 0
            else:
                answer = input(f'About to attempt removal of {len(result.stuck)} stuck row(s) on '
                                f'"{frame.name}" (id: {frame.id}) using mechanism "{mechanism}". '
                                f'Proceed? [y/N] ')
                if answer.strip().lower() not in ('y', 'yes'):
                    print('Aborted.')
                    return 0

        # D-13: the same account-wide budget as sync/push -- reconcile has
        # no --ignore-budget escape hatch, so this is always False.
        write_budget = _build_write_budget(os.getenv('AURA_EMAIL'), False)

        apply_reconciliation(result, aura, frame.id, mechanism=mechanism, budget=write_budget)

        print(f'Removed: {len(result.removed)} succeeded, {len(result.failed)} failed')
        for asset_id, err in result.failed:
            print(f'  ! {asset_id}: {err}')

        return 1 if result.failed else 0
    except RateLimitError as e:
        # Anti-abuse throttle/lockout mid-removal -- apply_reconciliation
        # aborted the batch rather than emitting N confusing per-item 401s.
        print(f'Aborted: {e}')
        return 1
    except GeoMismatchError as e:
        print(f'VPN/exit IP in {e.found}, account expects {e.expected} — switch your VPN and retry.')
        return 1
    except BudgetExhausted as e:
        minutes = e.wait_seconds / 60
        print(f'Write budget exhausted, come back in ~{minutes:.0f} min (or pass --no-wait / raise --max-wait).')
        return 1
    except Exception as e:
        # WR-01 fail-loud (D-05 convention): surface post-login API drift
        # instead of a raw traceback.
        print(f'Failed to reconcile frame: {e}')
        return 1

    return 0


# How each removal mode is named in the plan and in the run summary. The
# wording tracks the primitive that actually runs, so a report can never say
# "delete" on a run that hid, or vice versa (D-07).
_REMOVAL_VERB_PRESENT = {'hide': 'hide', 'delete': 'delete', 'hard_delete': 'hard-delete'}
_REMOVAL_VERB_PAST = {'hide': 'Hidden', 'delete': 'Removed', 'hard_delete': 'Hard-deleted'}


def _build_write_budget(email: str, ignore_budget: bool) -> 'WriteBudget | None':
    """Factory (Phase 09, ANTI-06) constructing the per-account `WriteBudget`
    at the CLI boundary, mirroring the S3Client()/SQSClient() construction
    site (`execute_plan` itself never constructs one). Returns `None` when
    `ignore_budget` is set (the `--ignore-budget` escape hatch) -- omitting
    `budget` entirely from `exec_kwargs` bypasses the guard.

    Only `sha1(email)[:12]` (a non-cryptographic filename-uniqueness hash,
    not a security boundary) is used for the state-file name -- the email
    itself is never persisted in the file body (T-09-02).
    """
    if ignore_budget:
        return None
    state_path = AURA_STATE_DIR / f'budget-{hashlib.sha1(email.encode()).hexdigest()[:12]}.json'
    return WriteBudget.load(
        state_path, capacity=AURA_WRITE_BUDGET_CAPACITY, refill_per_min=AURA_WRITE_BUDGET_REFILL_PER_MIN,
    )


def _build_geo_check(country_override: str | None):
    """Factory (Phase 09, ANTI-06) constructing the zero-arg `geo_check`
    closure at the CLI boundary. `country_override` (the `--country` flag)
    takes precedence over `AURA_COUNTRY`; when neither is set (falsy),
    returns `None` -- the geo guard is skipped entirely, per `check_geo`'s
    own falsy-`expected_country` contract."""
    country = country_override or AURA_COUNTRY
    if not country:
        return None
    return lambda: check_geo(country, resolver=_default_resolver, fail_open=AURA_GEO_FAIL_OPEN)


def run_sync(dir_arg: str, frame_arg: str, apply: bool = False, yes: bool = False, aura=None, debug: bool = False,
             no_delete: bool = False, limit: int = None, batch_size: int = None, chunk_delay: float = None,
             verb: str = 'sync', max_wait: float = None, no_wait: bool = False,
             country: str = None, ignore_budget: bool = False,
             removal_mode: str = 'hide') -> int:
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

    verb_present = _REMOVAL_VERB_PRESENT[removal_mode]
    verb_past = _REMOVAL_VERB_PAST[removal_mode]

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

        # Opt-in probe/push affordances. Defaults (no_delete=False, limit=None)
        # leave the classic `sync` behaviour byte-identical. `no_delete` (always
        # on for the `push` verb) makes the run purely additive -- it clears
        # to_delete so no existing frame photo can ever be removed, the safe
        # primitive for pushing from a "buffet" supply directory. `limit` caps
        # how many uploads are attempted, for controlled anti-abuse budget
        # probing. Both are applied BEFORE the plan is printed so the report
        # reflects exactly what will run.
        if no_delete:
            # `push` is upload-only: it must not hide, remove, OR re-show
            # anything. A re-show is still a visibility mutation of existing
            # frame photos, so it is cleared alongside the removals.
            plan.to_delete = []
            plan.to_reshow = []
        if limit is not None:
            plan.to_upload = sorted(plan.to_upload)[:limit]

        if verb == 'push':
            print(f'Push plan for {frame.name} (id: {frame.id}) — additive (no deletes), DRY RUN, nothing will be changed')
        else:
            print(f'Sync plan for {frame.name} (id: {frame.id}) — DRY RUN, nothing will be changed')
        print(f'To upload: {len(plan.to_upload)}')
        if no_delete:
            print('To delete: 0 (additive mode — existing frame photos left untouched)')
        else:
            # Name the verb that will actually run, so the plan can never read
            # "delete" on a run that hides (or vice versa) -- D-07.
            print(f'To {verb_present}: {len(plan.to_delete)}')
            # Re-shows get their own line rather than folding into unchanged:
            # they are a write, and the user should see it coming (D-08).
            print(f'To re-show: {len(plan.to_reshow)}')
        print(f'Unchanged: {plan.unchanged}')
        if plan.already_hidden:
            print(f'Already hidden: {plan.already_hidden} (no action needed)')

        # WR-03: local_hashes (and to_upload built from it) is populated in
        # filesystem-traversal order, which is OS/filesystem dependent and
        # not sorted -- sort here so dry-run output is reproducible across
        # runs/machines (e.g. diffable, stable for bug reports).
        for path in sorted(plan.to_upload):
            print(f'  + {path}')

        for asset in plan.to_delete:
            print(f'  - {asset.id} (taken {asset.taken_at_dt})')

        for asset in plan.to_reshow:
            print(f'  ~ {asset.id} (taken {asset.taken_at_dt}) — re-show')

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
            if removal_mode == 'hard_delete':
                # A reworded y/N is too easy to answer reflexively for an
                # irreversible, account-wide destruction. Re-typing the exact
                # count forces the user to look at the number first (D-04).
                count = len(plan.to_delete)
                print(f'IRREVERSIBLE: {count} photo(s) will be permanently destroyed '
                      f'account-wide, not just removed from this frame. This cannot be undone.')
                answer = input(f'To confirm, type the number of photos to hard-delete ({count}): ')
                if answer.strip() != str(count):
                    print('Aborted.')
                    return 0
            else:
                answer = input(f'About to apply this plan to "{frame.name}" (id: {frame.id}). Proceed? [y/N] ')
                if answer.strip().lower() not in ('y', 'yes'):
                    print('Aborted.')
                    return 0

        # Real AWS clients are constructed here only, on confirmed apply --
        # execute_plan() itself never constructs them (offline-testable seam
        # from Phase 8 Plan 02).
        s3_client = S3Client()
        sqs_client = SQSClient()

        # Proactive write-rate-budget + geo pre-flight guard (Phase 09,
        # ANTI-06) -- built here for BOTH verbs (push and sync both hit the
        # exact same anti-abuse surface), so `sync --apply` also gets
        # protection by default with zero new flags. Only `--ignore-budget`
        # (push-only) omits `budget`; `write_budget`/`geo_check` being
        # `None` is exec_kwargs's signal to omit the corresponding kwarg.
        write_budget = _build_write_budget(os.getenv('AURA_EMAIL'), ignore_budget)
        geo_check = _build_geo_check(country)

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

            # Only forward batch_size/chunk_delay when explicitly supplied so
            # execute_plan keeps its own defaults (WRITE_BATCH_SIZE /
            # WRITE_CHUNK_DELAY_SECONDS) otherwise -- no hardcoded values here.
            exec_kwargs = {}
            # execute_plan defaults to 'hide' too, so forwarding is always
            # safe -- but forward explicitly so the CLI's choice is the one
            # that runs, not a default that happens to agree.
            exec_kwargs['removal_mode'] = removal_mode
            if batch_size is not None:
                exec_kwargs['batch_size'] = batch_size
            if chunk_delay is not None:
                exec_kwargs['chunk_delay_seconds'] = chunk_delay
            # budget/geo_check forwarded whenever built (both verbs, by
            # default) -- omitted only when None (--ignore-budget, or no
            # AURA_COUNTRY/--country configured), preserving
            # execute_plan's own None defaults in that case. wait_on_budget/
            # max_wait_seconds forwarded ONLY when their override flag was
            # explicitly supplied, so a classic `sync --apply`/`push --apply`
            # with no new flags forwards nothing beyond the default guard
            # objects themselves (test_sync_defaults_do_not_override_execute_plan_defaults's guarantee).
            if write_budget is not None:
                exec_kwargs['budget'] = write_budget
            if geo_check is not None:
                exec_kwargs['geo_check'] = geo_check
            # WR-01: wire the AURA_WRITE_BUDGET_WAIT / AURA_WRITE_BUDGET_MAX_WAIT
            # env defaults into the guard so a user who configures them gets an
            # effect, with the per-run --no-wait / --max-wait flags taking
            # precedence over the env. Each kwarg is forwarded ONLY when it would
            # actually change execute_plan's own default (True / 3600.0) -- so a
            # run with neither an override flag nor a non-default env var still
            # forwards nothing, preserving the Phase 08 no-override contract.
            effective_wait = False if no_wait else AURA_WRITE_BUDGET_WAIT
            if effective_wait != _EXECUTE_PLAN_DEFAULT_WAIT:
                exec_kwargs['wait_on_budget'] = effective_wait
            effective_max_wait = max_wait if max_wait is not None else AURA_WRITE_BUDGET_MAX_WAIT
            if effective_max_wait != _EXECUTE_PLAN_DEFAULT_MAX_WAIT:
                exec_kwargs['max_wait_seconds'] = effective_max_wait

            result = execute_plan(
                plan, aura, frame.id, s3_client=s3_client, sqs_client=sqs_client,
                progress=_report_progress, on_wait=_report_wait, **exec_kwargs,
            )

        # D-10: separated success/failure summary, each failed item named.
        print(f'Uploads: {result.upload_succeeded} succeeded, {len(result.upload_failures)} failed')
        for path, err in result.upload_failures:
            print(f'  ! {path}: {err}')
        # REL-01/REL-03, D-08: printed unconditionally on every --apply run
        # (never behind --debug) -- how many chunks the 401 verify-then-retry
        # path recovered and how many duplicate uploads it prevented is the
        # single most useful signal for judging whether the 401 problem is
        # actually fixed, including the (common, reassuring) all-zero case.
        print(f'Retries: {result.chunks_retried} chunk(s) retried after a 401, '
              f'{result.items_already_landed} item(s) already landed (duplicate uploads prevented)')
        print(f'{verb_past}: {result.delete_succeeded} succeeded, {len(result.delete_failures)} failed')
        for asset_id, err in result.delete_failures:
            print(f'  ! {asset_id}: {err}')
        print(f'Re-shown: {result.reshow_succeeded} succeeded, {len(result.reshow_failures)} failed')
        for asset_id, err in result.reshow_failures:
            print(f'  ! {asset_id}: {err}')

        return 1 if (result.upload_failures or result.delete_failures
                     or result.reshow_failures) else 0
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
    except GeoMismatchError as e:
        # Root-cause mitigation for the VPN-geo-mismatch write-lockout
        # (Phase 09) -- execute_plan's geo pre-flight aborted before any
        # write happened.
        print(f'VPN/exit IP in {e.found}, account expects {e.expected} — switch your VPN and retry.')
        return 1
    except BudgetExhausted as e:
        # The proactive client-side write budget ran dry and either
        # --no-wait was passed or the computed wait exceeded --max-wait
        # (Phase 09) -- surface how long a retry would need to wait.
        minutes = e.wait_seconds / 60
        print(f'Write budget exhausted, come back in ~{minutes:.0f} min (or pass --no-wait / raise --max-wait).')
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
        removal_mode = 'hard_delete' if args.hard_delete else ('delete' if args.delete else 'hide')
        return run_sync(args.dir, args.frame, apply=args.apply, yes=args.yes, debug=args.debug,
                        removal_mode=removal_mode)
    if args.command == 'push':
        return run_sync(
            args.dir, args.frame, apply=args.apply, yes=args.yes, debug=args.debug,
            no_delete=True, limit=args.limit, batch_size=args.batch_size,
            chunk_delay=args.chunk_delay, verb='push',
            max_wait=args.max_wait, no_wait=args.no_wait,
            country=args.country, ignore_budget=args.ignore_budget,
        )
    if args.command == 'reconcile':
        return run_reconcile(
            args.frame, remove=args.remove, yes=args.yes, mechanism=args.mechanism,
            max_age_hours=args.max_age_hours, include_unknown_age=args.include_unknown_age,
            debug=args.debug,
        )
    raise ValueError(f'Unhandled command: {args.command}')


if __name__ == '__main__':
    sys.exit(main())
