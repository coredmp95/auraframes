---
phase: 10-hide-instead-of-delete-sync-mode
status: passed
verified: 2026-08-25
criteria_total: 4
criteria_met: 4
requirements: [HIDE-01, HIDE-02, HIDE-03, HIDE-04, HIDE-05, HIDE-06, HIDE-07, HIDE-08]
---

# Phase 10 — Verification Report

Goal-backward check: does the shipped codebase deliver what the phase promised, independent
of whether the plans' tasks were ticked off?

**Verdict: PASSED** — all 4 ROADMAP success criteria met, all 8 requirements satisfied.

Every criterion below was observed **live against a real frame**, not only in unit tests.
That matters here: the phase's central finding was that a plausible-looking implementation
could pass its own unit tests while silently never hiding anything (see Criterion 1).

## Success criteria

### 1. `sync --apply` with no removal flag HIDES gone-local photos — the safe, reversible default (D-01) ✓

`execute_plan`'s removal loop applies `_REMOVAL_PRIMITIVE[removal_mode]` with
`removal_mode` defaulting to `'hide'` → `FrameApi.exclude_asset`. Confirmed live:

```
To hide: 1
Hidden: 1 succeeded, 0 failed
```

and the asset **remained** in `get_assets?filter=all` afterwards (frame total unchanged), so
hiding is non-destructive. Reversibility confirmed by criterion 3.

**Near-miss worth recording.** The plan specified classification keyed on `Asset.selected`.
Live probing proved that field never changes when a photo is hidden — real visibility lives
in the parallel `asset_settings` array. Implemented as written, this criterion would have
been **silently unmet**: every photo classified visible forever, nothing ever hidden, and the
unit tests green throughout. Caught by Plan 10-01's live gate and fixed by joining
`asset_settings` onto `Asset.selected` at the API boundary.

### 2. `--delete` removes via `remove_asset`, `--hard-delete` destroys via `delete_asset`, mutually exclusive (D-03) ✓

`_REMOVAL_PRIMITIVE` maps the three modes to exactly one primitive each; `delete_asset`
appears as executable code at exactly one place in `sync.py`, reachable only through
`removal_mode='hard_delete'`. Mutual exclusion is enforced at parse time:

```
aura-cli sync: error: argument --hard-delete: not allowed with argument --delete
```

Both paths confirmed live end-to-end through the CLI: `Removed: 1 succeeded` and, for hard
delete, frame 157 → 156 with the target absent on re-read. `delete_asset`'s blast radius was
re-verified by inventory diff as asset-scoped (HIDE-07).

### 3. A locally-present hidden photo is re-shown via `select_asset`, and hidden photos are never re-uploaded (D-05/D-06) ✓

Confirmed live in a single run:

```
To upload: 0
To re-show: 1
Re-shown: 1 succeeded, 0 failed
```

`To upload: 0` is the load-bearing half — the hidden photo consumed local demand and was
re-shown rather than uploaded a second time, which is exactly D-06. The re-show loop runs
under every removal mode and precedes removals, so an interrupted run leaves the least
destructive partial state.

### 4. Per-mode verbs in plan and summary; `--hard-delete` requires a distinct exact-count confirmation (D-04/D-07/D-08) ✓

Wording is derived from the mode via `_REMOVAL_VERB_PRESENT` / `_REMOVAL_VERB_PAST`, so a
report cannot name a verb that did not run. Observed live: `To hide: 96` under the default
and `To hard-delete: 96` with the flag, plus `To re-show:` / `Re-shown:` lines and an
`Already hidden: 3 (no action needed)` line.

The hard-delete gate is a different *shape*, not a reworded prompt. Driven on a real pty:

```
IRREVERSIBLE: 1 photo(s) will be permanently destroyed account-wide...
To confirm, type the number of photos to hard-delete (1): y
Aborted.
```

`y` — the answer that satisfies any ordinary y/N prompt — aborted, and the asset was verified
still present. Only the exact count proceeded. The non-interactive path still fails closed.

## Requirements

| ID | Status | Evidence |
|---|---|---|
| HIDE-01 | ✓ | Live spike confirmed hide/re-show; **corrected**: the flag is `asset_settings[].selected`, not `Asset.selected` |
| HIDE-02 | ✓ | `get_assets` sends `filter=all` (live: 154 vs 157 assets without/with) and joins `asset_settings`; `compute_plan` 4-way, pure |
| HIDE-03 | ✓ | `removal_mode` selects one primitive; `exclude_asset` widened to batch |
| HIDE-04 | ✓ | Always-runs re-show loop; verified under all three modes |
| HIDE-05 | ✓ | Mutually-exclusive flags, per-mode wording, re-show reporting |
| HIDE-06 | ✓ | Exact-count gate verified on a real pty; `--yes` still skips; non-interactive fails closed |
| HIDE-07 | ✓ | `delete_asset` re-verified asset-scoped by before/after inventory diff (158 → 157, exactly the target) |
| HIDE-08 | ✓ | 33 new offline tests across classification, 3-tier removal, re-show, CLI modes and gate. Suite: 208 passed. |

## Test suite

`uv run pytest` → **208 passed, 1 failed**.

The single failure is `tests/test_read_path.py::test_read_03_pagination`, which is
**pre-existing and not caused by this phase**. It asserts `drained == num_assets`; measurement
during UAT showed the server itself does not keep those two consistent — a single
`limit=1000` call returns 154 assets while a paginated drain returns 149, the difference being
exactly the newest placeholder rows. Logged in STATE.md with the measurement.

## Known defects (open, non-blocking)

Both were found by UAT's end-to-end runs, are logged open in STATE.md, and neither undermines
a success criterion:

1. **Intermittent write 401s** (~4 in 10 runs, cleared by retry) — a reliability defect. It
   fails loud and safe: the run reports failures and exits non-zero rather than silently
   skipping work. Recommended fix: retry once on 401 with a fresh login inside `execute_plan`.
2. **Placeholder rows are unremovable** — `delete_asset` returns 200 while removing nothing on
   rows with no uploaded image. Fails toward *not* deleting, so the destructive direction is
   safe.

## Verdict

**PASSED.** The phase delivers its goal: a mistaken `sync --apply` now costs visibility rather
than photos, the destructive tiers are opt-in and gated by their destructiveness, and restoring
a file restores the photo without re-uploading it.
