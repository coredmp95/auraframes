---
phase: 11-write-path-reliability-format-support
plan: 06
subsystem: write-path-reliability
tags: [reconcile, placeholder-rows, live-verification, cli, opt-in]

# Dependency graph
requires:
  - phase: 11-03
    provides: "auraframes/reconcile.py's find_placeholders/apply_reconciliation, extended by this plan's opt-in"
  - phase: 11-05
    provides: "The raw-JSON-confirmed finding that /frames/{id}/assets.json never sends created_at at all, which this plan's Task 1 fix directly addresses"
provides:
  - "find_placeholders' explicit, keyword-only unknown_age_policy opt-in ('unknown_age' default, byte-for-byte unchanged; 'stuck' promotes an unresolvable-creation-time row into the removal-eligible bucket)"
  - "aura-cli reconcile --include-unknown-age flag, required alongside --remove to reach unknown-age rows; bare --remove unchanged"
  - "Live-confirmed working removal mechanism: --mechanism remove (FrameApi.remove_asset) cleared all 3 probed rows, verified by re-read not HTTP status"
  - "REL-05's REQUIREMENTS.md status now cites the mechanism and the exact evidence location instead of resting on an untested condition"
affects: []

# Actuals (#2632)
actuals:
  tokens: 12650
  tasks: 3
  commits: 4

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Keyword-only, explicitly-named opt-in argument (unknown_age_policy) as the pattern for widening a conservative default without touching it -- no positional slot, no bare boolean, default reproduces prior behaviour byte-for-byte"
    - "Removal confirmed by re-reading and diffing state (a fresh get_all_assets() call, id-by-id absence check), never by an HTTP status code alone -- delete_asset is already known to return 200 and remove nothing, so a 200 alone proves nothing"
    - "A live probe script run via `uv run python -c` (inline) or with find_dotenv(usecwd=True) when it must live in a file outside the project tree -- python-dotenv's default load_dotenv() walks up from the calling script's own file location, not the process cwd, and silently loads nothing if that walk never reaches the project root"

key-files:
  created: []
  modified:
    - auraframes/reconcile.py
    - tests/test_reconcile.py
    - auraframes/cli.py
    - docs/CLI.md
    - .planning/phases/11-write-path-reliability-format-support/11-LIVE-FINDINGS.md
    - .planning/REQUIREMENTS.md
    - .planning/STATE.md

key-decisions:
  - "unknown_age_policy is a keyword-only string ('unknown_age'/'stuck'), not a bare boolean -- self-documenting at the call site and leaves room for a future third policy without a breaking signature change"
  - "The live probe attempted mechanisms in order (remove, then hard-delete, then complete) and stopped as soon as one cleared every remaining target, rather than running all three regardless -- 'remove' worked on the first attempt, so hard-delete and complete were correctly never touched"
  - "A development-time bug is disclosed in full rather than silently fixed: the probe script's first run sent one live login call with email=None/password=None (a dotenv path-resolution bug, not a credentials problem) and got HTTP 475. Caught immediately, root-caused, fixed, and the account's post-fix login was confirmed normal before any removal attempt was made"
  - "REQUIREMENTS.md's traceability table Status cell for REL-05 was left as plain 'Complete' rather than annotated, to avoid disturbing gsd-tools' exact-match Pending/In-Progress/Gaps-Found -> Complete transition regex; the defensible evidence citation lives in the requirement's own checkbox bullet instead, which both the checkbox and the table agree with"

patterns-established:
  - "A conservative guard's default-vs-opt-in split: prove the default is byte-for-byte unchanged with an explicit test, before ever exercising the opt-in against live data"

requirements-completed: [REL-05]

coverage:
  - id: D1
    description: "find_placeholders gains an explicit, keyword-only unknown_age_policy opt-in; the default reproduces prior behaviour byte-for-byte and the three-way-null predicate / recently_created semantics are untouched"
    requirement: REL-05
    verification:
      - kind: unit
        ref: "tests/test_reconcile.py#test_unknown_age_policy_default_still_parks_unresolvable_row_in_unknown_age"
        status: pass
      - kind: unit
        ref: "tests/test_reconcile.py#test_unknown_age_policy_stuck_promotes_unresolvable_row_to_stuck"
        status: pass
      - kind: unit
        ref: "tests/test_reconcile.py#test_unknown_age_policy_stuck_does_not_promote_a_resolvable_too_young_row"
        status: pass
      - kind: unit
        ref: "tests/test_reconcile.py#test_unknown_age_policy_stuck_still_excludes_video_shaped_asset"
        status: pass
      - kind: unit
        ref: "tests/test_reconcile.py#test_unknown_age_policy_rejects_unrecognized_value"
        status: pass
    human_judgment: false
  - id: D2
    description: "A bounded live probe (at most 3 rows) through the corrected age guard found a working removal mechanism -- remove (FrameApi.remove_asset) -- confirmed by re-reading the frame and diffing asset counts, not by HTTP status code alone"
    requirement: REL-05
    verification:
      - kind: e2e
        ref: "11-LIVE-FINDINGS.md, 'Plan 11-06' section -- probe script raw output (command, HTTP 200 body, re-read verification of all 3 target ids as GONE, 159->156 assets), independent follow-up `aura-cli reconcile` confirmation (156 assets / 50 placeholder rows)"
        status: pass
    human_judgment: false
  - id: D3
    description: "REL-05's REQUIREMENTS.md status is defensible from the artifacts alone -- the checkbox bullet names the confirmed mechanism and cites the exact evidence location, rather than resting on an untested condition"
    requirement: REL-05
    verification: []
    human_judgment: true
    rationale: "Whether a written justification is 'defensible from the artifacts alone' is a documentation-quality judgment no automated test asserts -- the underlying technical claim (a working mechanism was found) is independently verified under D2, but the adequacy of the written record is best confirmed by a human reader following the citation."

# Metrics
duration: ~40min
completed: 2026-09-03
status: complete
---

# Phase 11 Plan 06: Age-Guard Opt-In and Live Removal Probe Summary

**Corrected `find_placeholders`' age guard with an explicit, default-unchanged opt-in, then used it in a bounded 3-row live probe that found `remove` (`FrameApi.remove_asset`) genuinely clears stuck placeholder rows — confirmed by re-read, not HTTP status — closing REL-05's previously-untested removal half.**

## Performance

- **Duration:** ~40 min
- **Started:** 2026-09-03T19:20:00Z (approx, session start)
- **Completed:** 2026-09-03T19:59:30Z
- **Tasks:** 3 (all `type="auto"`)
- **Files modified:** 7 (0 created)

## Accomplishments

- `auraframes/reconcile.py`'s `find_placeholders` gained a keyword-only `unknown_age_policy` argument (`'unknown_age'` default, `'stuck'` explicit opt-in) that corrects D-15's unconditional form — the form that plan 11-05 discovered makes the removal path permanently unreachable against an API that never sends `created_at` at all. The default is proven byte-for-byte unchanged: all 18 pre-existing tests in `tests/test_reconcile.py` pass unmodified, plus 5 new tests cover the opt-in, its non-effect on `recently_created`, and its non-effect on the three-way-null predicate.
- `aura-cli reconcile` gained `--include-unknown-age`, an explicitly-named flag required alongside `--remove` to reach unknown-age rows; bare `--remove` is unchanged.
- A time-boxed live probe, bounded to 3 rows (the plan's hard cap), targeted rows promoted from `unknown_age` to `stuck` via the opt-in. `--mechanism remove` (the CLI default) cleared all 3, verified by re-reading the frame afterward (159 → 156 assets; each of the 3 target ids individually confirmed absent) rather than by trusting the `HTTP 200 {"number_failed":0}` response alone. `hard-delete` and `complete` were never needed since `remove` cleared every target. An independent follow-up `aura-cli reconcile` report confirmed 156 assets / 50 placeholder rows.
- This supersedes the Phase 10 UAT finding that `remove_asset` returned 404: that earlier probe never had a genuinely `stuck`-classified row to send, for the exact structural reason plan 11-05 diagnosed.
- REL-05's `REQUIREMENTS.md` bullet now names the confirmed mechanism and cites `11-LIVE-FINDINGS.md`'s "Plan 11-06" section directly, rather than resting on the previously-untested removal condition. `STATE.md`'s "Placeholder rows are unremovable" blocker is marked resolved with the same evidence.
- A development-time bug in the probe script itself (a `python-dotenv` path-resolution mistake that sent one live login call with `email=None`/`password=None` and got `HTTP 475`) is disclosed in full in `11-LIVE-FINDINGS.md`, per this project's T-11-17 evidence discipline — caught immediately, root-caused, fixed, and the account's subsequent login confirmed normal before any removal attempt was made.

## Task Commits

1. **Task 1: An explicit opt-in for unknown-age rows, default unchanged** — `b08fcc8` (feat)
2. **Task 2: Time-boxed live probe for a placeholder-removal mechanism** — `64ac0ff` (docs), `6fc724d` (docs, help-text follow-up)
3. **Task 3: Make REL-05's recorded status match what was established** — `72eeebb` (docs)

**Plan metadata:** (this commit)

## Files Created/Modified

- `auraframes/reconcile.py` — `find_placeholders` gains `unknown_age_policy`; dispatch-table and `_complete_placeholder` comments updated to record the confirmed-working `remove` result (no behavior change to the dispatch itself)
- `tests/test_reconcile.py` — 5 new tests covering the opt-in's default-unchanged guarantee, its promotion behavior, and its non-effect on `recently_created`/the video-exclusion predicate
- `auraframes/cli.py` — new `--include-unknown-age` flag on `reconcile`, wired through `run_reconcile`; `--mechanism` help text updated to reflect the confirmed result
- `docs/CLI.md` — `reconcile`/`--remove`/Known-issues sections updated with the flag, the corrected example, and the live evidence cross-reference
- `.planning/phases/11-write-path-reliability-format-support/11-LIVE-FINDINGS.md` — new "Plan 11-06" section: the dev-bug disclosure, read-only baseline, full probe transcript, follow-up confirmation, mechanism table, and verdict
- `.planning/REQUIREMENTS.md` — REL-05 bullet rewritten to cite the confirmed mechanism and evidence location
- `.planning/STATE.md` — placeholder-rows blocker marked resolved; stale "removal mechanism untested" concern removed; new Decisions entry added

## Decisions Made

- `unknown_age_policy` is a keyword-only string, not a bare boolean — self-documenting at the call site, room for a future third policy.
- The probe attempted mechanisms in order and stopped once one cleared every remaining target — `remove` worked immediately, so `hard-delete`/`complete` were never exercised against live data.
- The dev-time dotenv-path bug is disclosed in full rather than silently fixed and omitted from the record.
- REQUIREMENTS.md's traceability table `Status` cell for REL-05 stays plain `Complete` (unannotated) to avoid disturbing `gsd-tools`' exact-match transition regex; the defensible citation lives in the requirement bullet itself.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Live probe script's first run sent a login call with `email=None`/`password=None`**
- **Found during:** Task 2, while preparing the live probe
- **Issue:** The probe script initially lived in a scratch/tmp directory outside the project tree. `python-dotenv`'s default `load_dotenv()` resolves `.env` by walking UP from the *calling script's own file location*, not the process's working directory — from a scratch path, that walk never reached the project root, so `AURA_EMAIL`/`AURA_PASSWORD` stayed unset. The first script run therefore called `aura.login()` with both credentials `None`, which the live API answered with `HTTP 475` ("The email or password was incorrect").
- **Fix:** Resolved `.env` via `find_dotenv(usecwd=True)` (forcing cwd-based resolution, which the Bash tool guarantees is the project root) and added a hard `assert` that both credentials are non-empty before any `aura.login()` call. A subsequent plain, read-only login (`get_frames()` only) confirmed the account was not left in a degraded state.
- **Files modified:** none in the repo (the probe script itself is a one-shot scratch artifact, not committed; the incident and fix are recorded in full in `11-LIVE-FINDINGS.md`'s "Plan 11-06" section per T-11-17 discipline)
- **Verification:** the corrected script's subsequent login succeeded (`LOGIN OK`, 1 frame returned); the full 3-row probe then ran cleanly with no further errors
- **Committed in:** `64ac0ff` (documented in `11-LIVE-FINDINGS.md`, no source-code commit needed since the bug never touched tracked code)

---

**Total deviations:** 1 auto-fixed (1 Rule 1 — bug, caught before it affected any write path, fully disclosed).
**Impact on plan:** None on the plan's deliverables. The bug was in ephemeral tooling used to run the probe, not in any committed code path, and it never reached a removal call. Disclosed in full rather than omitted, per this project's evidence-discipline convention.

## Issues Encountered

None beyond the disclosed deviation above, which was caught and resolved before any live write was attempted.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

Phase 11 (Write-Path Reliability & Format Support) is now fully complete: all 12 requirements (REL-01..08, FMT-01..03, MOD-03) are closed, REL-05 with genuine live evidence for both its reporting and removal halves. `uv run pytest -m "not live" -q` remains green (276 passed, 6 deselected). No blockers carried forward from this plan. Phase 11's own gap-closure loop is closed; the milestone is ready to proceed to Phase 12 (album-access mechanism spike).

## Self-Check: PASSED

- `auraframes/reconcile.py` exists and contains `unknown_age_policy`: confirmed
- `tests/test_reconcile.py` exists and contains the 5 new test names: confirmed
- `auraframes/cli.py` contains `--include-unknown-age`: confirmed
- Commits `b08fcc8`, `64ac0ff`, `72eeebb`, `6fc724d` all present in `git log --oneline --all`: confirmed
- All plan-level `<acceptance_criteria>` re-run: Task 1 (5 new tests + 18 unmodified pre-existing tests, `uv run pytest -m "not live" -q` green), Task 2 (≤3 rows, command+raw output+date recorded, removal confirmed by re-read), Task 3 (checkbox/table agree, reasoning written down, offline suite green) — all pass
- `uv run pytest -m "not live" -q`: 276 passed, 6 deselected

---
*Phase: 11-write-path-reliability-format-support*
*Completed: 2026-09-03*
