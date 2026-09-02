---
phase: 06-inspect-frame-resolution
plan: 01
subsystem: cli
tags: [argparse, cli, pydantic, offline-testing, httpx-mocktransport]

requires:
  - phase: 05-cli-skeleton-status
    provides: aura-cli entrypoint, run_status() int-return/DI-testable pattern, _configure_cli_logging() quiet-by-default helper
provides:
  - "aura-cli inspect --frame <name|id> subcommand: resolves a frame by case-insensitive name substring with exact-id fallback, then prints owner/contributor/asset-count metadata plus the first 10 photos in API order"
  - "resolve_frame()/FrameResolution: pure, reusable frame-resolution logic (resolved/ambiguous/not_found discriminator, no custom exceptions)"
  - "Root-level aura-cli --debug flag consumed once before subcommand dispatch (folded todo closed)"
  - "Offline get_frame() detail route + frame_detail.json fixture in tests/offline.py, reusable by any future subcommand needing single-frame metadata"
affects: [06-02 (live md5_hash spike will exercise this same inspect command), future sync/upload subcommands (inherit root --debug for free)]

tech-stack:
  added: []
  patterns:
    - "FrameResolution status discriminator ('resolved'/'ambiguous'/'not_found') instead of raised exceptions, per deferred MOD-03"
    - "Root-parser --debug consumed once in main() before any subcommand dispatch; subcommand handlers stay debug-parameter-only"
    - "Offline router branches ordered most-specific-first (exact path, then suffix match, then prefix+suffix match) to avoid shadowing"

key-files:
  created:
    - tests/fixtures/frame_detail.json
    - tests/test_cli_inspect.py
  modified:
    - auraframes/cli.py
    - tests/offline.py

key-decisions:
  - "N=10 for the default first-N photo truncation (D-06); a trailing '+K more' line prints when assets exceed this"
  - "Ambiguous-match resolution never attempts the id fallback (D-03) — ambiguity on name always wins over trying the value as an id"
  - "Display metadata (owner/contributors/asset count) comes from the fresh get_frame(resolved.id) call, not from the frames.json list entry used for resolution, matching the plan's exact call sequence"
  - "Post-login get_frames/get_frame/get_all_assets wrapped in one broad try/except (WR-01 fail-loud) separate from the login try/except, so API drift after a successful login still exits 1 with a message instead of a raw traceback"

patterns-established:
  - "Pure-function resolution with a status discriminator (FrameResolution) is the project's convention for ambiguous/not-found domain outcomes — prefer this over a custom exception hierarchy (MOD-03 stays deferred)"

requirements-completed: [CLI-03, CLI-04]

coverage:
  - id: D1
    description: "inspect --frame <name> resolves a unique case-insensitive name substring and prints frame metadata (name, owner name+email, contributor count+names, asset count) plus the first N photos (id/file_name/date) in API order"
    requirement: CLI-03
    verification:
      - kind: unit
        ref: "tests/test_cli_inspect.py#test_inspect_success_unique_name_match"
        status: pass
    human_judgment: false
  - id: D2
    description: "inspect --frame <id> resolves by exact Frame.id when zero name substrings match"
    requirement: CLI-04
    verification:
      - kind: unit
        ref: "tests/test_cli_inspect.py#test_inspect_id_fallback_when_no_name_matches"
        status: pass
    human_judgment: false
  - id: D3
    description: "Ambiguous name match (>1 substring hit) prints every matching frame's name+id, exits non-zero, and does not attempt the id fallback"
    requirement: CLI-04
    verification:
      - kind: unit
        ref: "tests/test_cli_inspect.py#test_inspect_ambiguous_name_lists_names_and_ids"
        status: pass
    human_judgment: false
  - id: D4
    description: "A value matching neither name nor id prints a not-found error listing the account's available frame names and exits non-zero"
    requirement: CLI-04
    verification:
      - kind: unit
        ref: "tests/test_cli_inspect.py#test_inspect_not_found_lists_available_frame_names"
        status: pass
    human_judgment: false
  - id: D5
    description: "Login failure during inspect prints 'Login failed' and exits non-zero without leaking the password"
    verification:
      - kind: unit
        ref: "tests/test_cli_inspect.py#test_inspect_login_failure_exits_nonzero"
        status: pass
    human_judgment: false
  - id: D6
    description: "inspect is quiet by default (no loguru request/response markers on stderr) and --debug is now a root-level flag shared with status"
    verification:
      - kind: unit
        ref: "tests/test_cli_inspect.py#test_inspect_quiet_by_default_suppresses_verbose_stderr"
        status: pass
      - kind: unit
        ref: "tests/test_cli_status.py (unchanged, still passes with --debug relocated to root parser)"
        status: pass
    human_judgment: false

duration: 4min
completed: 2026-07-07
status: complete
---

# Phase 06 Plan 01: Inspect + Frame Resolution Summary

**`aura-cli inspect --frame <name|id>` resolving frames by case-insensitive name substring with exact-id fallback, displaying owner/contributor/asset-count metadata and the first 10 photos, fully proven offline via the existing `Aura(client=...)` DI seam.**

## Performance

- **Duration:** ~4 min (task commits spanned 02:03:52Z–02:06:40Z)
- **Started:** 2026-07-07T02:03:00Z (approx.)
- **Completed:** 2026-07-07T02:07:01Z
- **Tasks:** 3 completed
- **Files modified:** 4 (2 created, 2 modified)

## Accomplishments
- Extended the offline test harness (`tests/offline.py`) with a `get_frame()` detail route and a new `tests/fixtures/frame_detail.json` fixture, positioned so it can't shadow the existing `/v5/frames.json` or `/assets.json` branches
- Implemented `resolve_frame()`/`FrameResolution` — a pure, reusable resolution function with a `resolved`/`ambiguous`/`not_found` status discriminator (no custom exception hierarchy, per deferred MOD-03) — plus `run_inspect()` mirroring `run_status()`'s testable int-return/DI shape
- Promoted `--debug` from the `status`-only subparser to the root `aura-cli` parser (folded todo), parsed once in `main()` before dispatch, so `inspect` and every future subcommand share the quiet-by-default logging convention for free
- Wrote six offline tests in `tests/test_cli_inspect.py` covering all four resolution branches, login failure, and quiet-by-default stderr — zero network access, zero live credentials

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend offline router + add frame_detail fixture** - `fdbdb4b` (test)
2. **Task 2: Implement resolve_frame(), run_inspect(), and root-level --debug + inspect wiring** - `db8ad38` (feat)
3. **Task 3: Offline tests for inspect resolution + display** - `de23c9f` (test)

**Plan metadata:** committed after this SUMMARY

## Files Created/Modified
- `auraframes/cli.py` - added `resolve_frame()`/`FrameResolution`, `run_inspect()`, root-level `--debug`, `inspect` subparser, and `main()`'s inspect dispatch + unhandled-command guard
- `tests/offline.py` - added the `get_frame()` detail route to `make_router()`
- `tests/fixtures/frame_detail.json` - new fixture: single Frame payload (id `frame-fake-0001`, name "Fake Frame", one contributor) plus `total_asset_count: 3`
- `tests/test_cli_inspect.py` - new offline test module, six test cases

## Decisions Made
- **N=10** for the default first-N photo truncation (D-06 discretion). Documented here per the plan's `<output>` instruction; a trailing `+K more` line prints when the frame has more assets than shown.
- Display metadata is sourced from the fresh `get_frame(resolved.frame.id)` call, not the `frames.json`-list entry used during resolution — this matches the plan's exact call sequence (`get_frames()` -> `resolve_frame()` -> `get_frame(resolved.id)` -> `get_all_assets(resolved.id)`) and is the reason the id-fallback offline test had to override the specific `/v5/frames/<id>.json` detail path (see Issues Encountered).
- Post-login `get_frames`/`get_frame`/`get_all_assets` calls are wrapped in one broad `try/except` separate from the login `try/except` (WR-01 fail-loud), so API drift discovered after a successful login still exits 1 with a printed message instead of a raw traceback.

## Deviations from Plan

None - plan executed exactly as written. The one adjustment made was inside Task 3's test design (see Issues Encountered below), which is test-authoring detail rather than a deviation from any `<action>`/`<acceptance_criteria>` in the plan.

## Issues Encountered

- **Offline fixture is not id-parameterized.** `tests/offline.py`'s new `get_frame()` route (added in Task 1, exactly as specified) always returns the same static `frame_detail.json` regardless of the requested frame id — it routes on path *shape*, not path *value*. This is correct and matches Task 1's acceptance criteria. It meant the Task 3 id-fallback test (D-02) needed to add a *specific* override for `/v5/frames/frame-fake-bedroom.json` (in addition to overriding `/v5/frames.json`'s list) so the test could prove `get_frame()` was called with the *resolved* id, not just that resolution itself picked the right frame. Resolved by adding that targeted override in the test; no production code changed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `aura-cli inspect --frame <name|id>` is fully offline-tested and available for Plan 02's live `md5_hash` spike — Plan 02 should invoke this exact command against the real account/frame to check whether `Asset.md5_hash` is populated for pre-existing (non-client-uploaded) assets (D-12/D-13), then record the finding in `STATE.md`'s Blockers/Concerns and `PROJECT.md`'s Context section per the phase's locked decisions.
- A live smoke run (`uv run aura-cli --debug inspect --frame <value>`) was executed against the real account during verification (read-only: login + `get_frames`); it correctly printed a not-found error listing the real frame ("Cadre de Fabrice") without leaking the password, confirming the command also behaves correctly against live data, not just fixtures.
- No blockers for Plan 02.

---
*Phase: 06-inspect-frame-resolution*
*Completed: 2026-07-07*

## Self-Check: PASSED
