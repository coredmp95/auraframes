# Phase 8: Destructive Execution (Upload + Delete Verification) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-07
**Phase:** 8-Destructive Execution (Upload + Delete Verification)
**Areas discussed:** Apply confirmation UX, Delete-primitive live test, Failure handling mid-apply, SQS queue targeting fix

---

## Apply Confirmation UX

### Q: What should `--apply` do on its own — execute immediately, or print the plan and require an interactive y/n confirmation first?

| Option | Description | Selected |
|--------|-------------|----------|
| Two-flag model | `--apply` alone prints the plan and prompts 'Proceed? [y/N]'; `--yes` (combinable with `--apply`) skips the prompt for scripting/CI | ✓ |
| Single flag, no prompt | `--apply` executes immediately, no confirmation step; `--yes` becomes a no-op alias | |
| Let Claude decide | | |

**User's choice:** Two-flag model (recommended)

### Q: Should deletions get extra friction beyond whatever general apply-confirmation you just chose?

| Option | Description | Selected |
|--------|-------------|----------|
| Same gate as uploads | One confirmation covers the whole plan (uploads + deletes together) | ✓ |
| Extra gate only when deletes exist | A second, more explicit prompt naming the delete count, even under `--yes` for the first apply run | |
| Let Claude decide | | |

**User's choice:** Same gate as uploads

### Q: When `--apply` runs non-interactively (no TTY) without `--yes`, what should happen?

| Option | Description | Selected |
|--------|-------------|----------|
| Fail closed | Print an error and exit non-zero without touching anything | ✓ |
| Proceed without prompting | Treat missing TTY as implicit consent and execute the plan | |
| Let Claude decide | | |

**User's choice:** Fail closed (recommended)

### Q: Should the confirmation prompt echo back which frame it's about to modify?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — always show frame name + id | Guards against `--frame` resolving to the wrong frame right before an irreversible action | ✓ |
| No — the plan header already shows it | run_sync's dry-run output already prints the frame name/id | |
| Let Claude decide | | |

**User's choice:** Yes — always show frame name + id

**Notes:** User confirmed "Next area" after this batch — no follow-up questions needed.

---

## Delete-Primitive Live Test

### Q: How should we live-verify `delete_asset` without risking a real photo?

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated disposable test asset | Upload a throwaway test photo specifically to probe `delete_asset` against, confirm behavior, document the finding | ✓ |
| Don't call `delete_asset` live at all | Trust the docstring, verify only `remove_asset` live | |
| Let Claude decide | | |

**User's choice:** Dedicated disposable test asset (recommended)

### Q: Should `delete_asset` be wired into `--apply`'s execute path at all this phase?

| Option | Description | Selected |
|--------|-------------|----------|
| `remove_asset` only | `--apply`'s delete path calls `remove_asset` exclusively; `delete_asset` is live-verified but not wired | ✓ |
| Wire both behind a future flag | `delete_asset` gets a reserved-but-unexposed code path for a future `--hard-delete` flag | |
| Let Claude decide | | |

**User's choice:** remove_asset only — don't wire delete_asset

### Q: If the live test reveals `delete_asset` is more destructive than documented, what's the stop condition?

| Option | Description | Selected |
|--------|-------------|----------|
| Stop and report immediately | Halt the live-verification checkpoint the moment unexpected destructive behavior is observed | ✓ |
| Note it and continue | Record the finding as a caveat and continue with `remove_asset` as the default regardless | |

**User's choice:** Stop and report immediately (recommended)

**Notes:** User confirmed "Next area" after this batch.

---

## Failure Handling Mid-Apply

### Q: If one file fails to upload or delete partway through `--apply`, should the whole run stop, or continue?

| Option | Description | Selected |
|--------|-------------|----------|
| Continue, report summary at end | Keep processing remaining items; print a final per-file success/failure summary; exit non-zero if anything failed | ✓ |
| Abort on first failure | Stop immediately at the first error, leaving the rest of the plan un-executed | |
| Let Claude decide | | |

**User's choice:** Continue, report summary at end (recommended)

### Q: Should uploads and deletes be attempted in a specific order?

| Option | Description | Selected |
|--------|-------------|----------|
| Uploads first, then deletes | Safer partial-failure state if interrupted — new content added, nothing removed yet | ✓ |
| Deletes first, then uploads | No functional reason favors this; offered as the explicit alternative | |
| Let Claude decide | | |

**User's choice:** Uploads first, then deletes (recommended)

### Q: Should the failure summary distinguish upload failures from delete failures?

| Option | Description | Selected |
|--------|-------------|----------|
| Separate sections | 'Uploads: X succeeded, Y failed' / 'Deletes: X succeeded, Y failed', each with failed items named individually | ✓ |
| One combined failure list | A single flat list regardless of upload/delete | |
| Let Claude decide | | |

**User's choice:** Separate sections (recommended)

**Notes:** User confirmed "Next area" after this batch.

---

## SQS Queue Targeting Fix

### Q: get_sqs() hardcodes a queue id from the original test frame. Any preference on the fix approach?

| Option | Description | Selected |
|--------|-------------|----------|
| Let Claude decide | Straightforward parameterization bug fix (WRITE-04), no product-level tradeoff | ✓ |
| I want to weigh in on the approach | Pick this if you have a specific preference (caching, retry/timeout behavior) | |

**User's choice:** Let Claude decide (recommended)

**Notes:** User confirmed readiness for context after this area — no additional gray areas explored.

---

## Claude's Discretion

- Exact wording of the `--apply`/`--yes` confirmation prompt and the plan-header frame echo.
- How `execute_plan()` is structured relative to Phase 7's `compute_plan()`.
- How the disposable test asset for the `delete_asset` probe is created/sourced, and how the SQS fix is implemented/tested offline.
- Exact construction of upload identity (`local_identifier`, etc.) for local files with no pre-existing Aura asset record.

## Deferred Ideas

None — discussion stayed within phase scope.
