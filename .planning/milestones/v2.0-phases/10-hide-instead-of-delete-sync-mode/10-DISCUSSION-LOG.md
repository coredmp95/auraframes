# Phase 10: Hide-instead-of-delete sync mode - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-09
**Phase:** 10-hide-instead-of-delete-sync-mode
**Areas discussed:** Intended hidden end-state, Opt-in removal flag / tiers, Plan & confirm wording, Re-show / diff behavior

---

## Intended hidden end-state

| Option | Description | Selected |
|--------|-------------|----------|
| Off slideshow, kept on frame | Photo not shown in rotation but stays attached to frame / visible in app (exclude_asset semantics). Most preserving. | ✓ |
| Off frame, kept in account | Photo removed from frame collection (remove_asset), asset survives in account/S3. Basically today's default — mostly a rename. | |
| You decide | Match whatever the app's "make invisible" action does. | |

**User's choice:** Off slideshow, kept on frame.
**Notes:** Scopes the hide mechanism to the `exclude_asset`-style "still shows in the app" behavior. Not a hard lock on `exclude_asset` if the live spike finds the real mechanism is elsewhere.

### Follow-up: if a safe hide mechanism can't be confirmed live

| Option | Description | Selected |
|--------|-------------|----------|
| Block & report, don't ship | Stop and report; keep remove_asset default until hide is proven. | |
| Fall back to remove_asset | Quietly keep remove_asset default; ship the flag/wording scaffolding. | |
| You decide | Let researcher/planner judge from the live spike. | ✓ |

**User's choice:** You decide.
**Notes:** Claude's recommendation recorded — follow Phase 7/8 STOP-and-report precedent rather than ship a "hide" that silently does something else.

---

## Opt-in removal flag / tiers

| Option | Description | Selected |
|--------|-------------|----------|
| `--delete` | Matches existing plan vocabulary; reads naturally vs a hide default. | ✓ |
| `--remove` | Most technically accurate (maps to remove_asset). | |
| `--hard-delete` | Signals "dangerous," but overstates remove_asset. | |

**User's choice:** `--delete`.

### Follow-up: which primitive does the opt-in call?

| Option | Description | Selected |
|--------|-------------|----------|
| remove_asset (disassociate) | Today's --apply removal; roadmap's stated fallback. delete_asset stays unwired. | |
| delete_asset (hard) | The broad asset-scoped DELETE; wires the primitive Phase 8 left unreachable. | |
| Both tiers | --delete → remove_asset, plus --hard-delete → delete_asset. Full three-tier control. | ✓ |

**User's choice:** Both tiers.

### Follow-up: handling the third tier given it reverses Phase 8 D-06

| Option | Description | Selected |
|--------|-------------|----------|
| Keep all three, this phase | Wire --hard-delete → delete_asset now, with extra guardrails + live re-verification. | ✓ |
| Ship hide + --delete now, defer --hard-delete | Two safe tiers this phase; delete_asset gets its own later phase. | |
| You decide | Claude picks the split. | |

**User's choice:** Keep all three tiers this phase.
**Notes:** Supersedes Phase 8 D-06. Requires a stronger confirmation gate for `--hard-delete` and live re-verification of `delete_asset`'s blast radius before it is trusted on real photos; STOP-and-report if that probe surprises.

---

## Plan & confirm wording

| Option | Description | Selected |
|--------|-------------|----------|
| Verb matches the mode | `To hide` / `To delete` / `To hard-delete` (+ matching summary). Real action always shown. | ✓ |
| Keep 'delete', add a mode line | Keep `To delete: N` + a mode banner. Less churn, label mismatches verb. | |
| You decide | Whatever reads cleanest. | |

**User's choice:** Verb matches the mode.

### Follow-up: confirmation gate across the three modes

| Option | Description | Selected |
|--------|-------------|----------|
| Escalate by destructiveness | Hide = normal gate; --delete = same, worded; --hard-delete = stronger explicit gate. | |
| Uniform gate, mode in the text | One gate for all three, consequence stated in the prompt. | |
| You decide | Claude picks the gate design. | ✓ |

**User's choice:** You decide.
**Notes:** Claude's recommendation recorded — escalate friction by destructiveness (extra warning line for irreversible `--hard-delete`), keeping `--yes` skip + Phase 8 single-gate model.

---

## Re-show / diff behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Un-hide it (re-show) | Local file present ⇒ frame photo visible; directory is source of truth. Requires reading hidden state + a show/include call. | ✓ |
| Leave hidden, never re-upload | Hidden counts as present (no re-upload) but sync never auto-un-hides. | |
| You decide | Based on what the mechanism allows. | |

**User's choice:** Un-hide it (re-show).

### Follow-up: how re-show surfaces in the plan

| Option | Description | Selected |
|--------|-------------|----------|
| Own plan line, runs on plain --apply | `To re-show: N` as its own count; un-hide runs on plain --apply (non-destructive). | ✓ |
| Fold into 'unchanged', re-show silently | Treat hidden-but-local as unchanged, un-hide silently. | |
| You decide | Whatever stays coherent with the plan layout. | |

**User's choice:** Own plan line, runs on plain --apply.

---

## Claude's Discretion

- Confirmation gate design across the three removal modes (lean: escalate by destructiveness).
- What Phase 10 does if the live spike cannot confirm a safe hide mechanism (lean: STOP and report, keep remove_asset default until proven).
- Exact endpoint(s) backing hide and re-show, precise CLI wording, and how visibility state is threaded through the plan/execution dataclasses.

## Deferred Ideas

- Standalone bulk visibility command (show/hide independent of a directory diff) — out of scope.
- Splitting `--hard-delete` into its own focused, safety-reviewed phase — the fallback if the live `delete_asset` re-verification reveals broader-than-documented destruction.
