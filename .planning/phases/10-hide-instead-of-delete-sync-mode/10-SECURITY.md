---
phase: 10-hide-instead-of-delete-sync-mode
audited: 2026-08-25
threats_total: 13
threats_open: 0
threats_mitigated: 8
threats_accepted: 5
verdict: SECURED
---

# Phase 10 — Security Verification

Retroactive verification that every threat in the phase's STRIDE registers (spread across
`10-01`..`10-04-PLAN.md`) is actually mitigated in the shipped code, not merely planned.

**Verdict: SECURED** — 8 `mitigate` threats verified present in code, 5 `accept` threats
confirmed still-accepted. 0 open.

The phase's whole subject is destructive-action safety, so most of these threats are about
one question: *can an irreversible operation be reached without the user meaning it?*

## Mitigated threats (8) — verified in code

| ID | Severity | Threat | Verified mitigation |
|---|---|---|---|
| T-10-01 | high | `exclude_asset` might hide by *disassociating* (i.e. be destructive) | Live tripwire held: the asset remained in `get_assets?filter=all` across the hide (frame total unchanged 158→158). Recorded in `10-LIVE-FINDINGS.md`. |
| T-10-02 | high | `delete_asset` blast radius may have drifted broader since Phase 8 | Re-verified live with a full before/after inventory diff: exactly 1 of 158 assets removed, no collateral. Asset-scoped, unchanged from Phase 8. |
| T-10-03 | high | A probe might run against a real photo instead of a disposable | Every destructive probe targeted an 8×8 throwaway uploaded for the purpose. In the UAT session the removal set was scoped with a mirror directory so exactly one chosen asset was ever in range. |
| T-10-04 | medium | `compute_plan` misclassifies visibility, re-showing or removing unintentionally | 4-way classification unit-tested for all combinations; purity asserted programmatically — `'removal_mode' in inspect.getsource(compute_plan)` is `False`, so behaviour is deterministic from inputs. |
| T-10-07 | high | `hard_delete` reaches the irreversible primitive on the removal set | `delete_asset` appears in `sync.py` exactly once as executable code — inside `_REMOVAL_PRIMITIVE['hard_delete']` (line 327) — and that dict has a single call site (line 692) keyed by `removal_mode`. It is unreachable unless a caller names the mode. Blast radius re-verified (T-10-02); the exact-count gate (T-10-10) stands in front of it. |
| T-10-08 | high | Un-batched hide/show, or `hard_delete`'s N calls, run the budget dry and re-trip anti-abuse | `_REMOVAL_REQUEST_COST` charges `len(chunk)` for `hard_delete` versus `1` for the batch modes, so the budget reflects real call volume. Both new loops reuse the existing `throttle`/`interchunk_pause`/budget machinery rather than a parallel loop. |
| T-10-10 | high | `--hard-delete` confirmed too easily, destroying the wrong set irreversibly | The gate is a different *shape*, not merely different words: `cli.py:469` requires re-typing the exact removal count behind an `IRREVERSIBLE` warning. Verified live on a real pty — typing `y` aborted and the asset was confirmed still present; only the exact count proceeded. |
| T-10-12 | medium | `push` accidentally mutates frame visibility via re-show | `cli.py:407` clears `plan.to_reshow` alongside `to_delete` under `no_delete`, so `push` cannot hide, remove **or** re-show. Covered by a dedicated test. |

## Accepted threats (5) — re-confirmed

| ID | Severity | Threat | Why still accepted |
|---|---|---|---|
| T-10-05 | medium | The visibility signal may be per-contributor rather than global | Single-user tool acting as the authenticated account. The live probe surfaced the raw shape (`asset_settings` carries `reason: "user"`), and nothing observed contradicts the single-account model. Documented, not guarded at runtime. |
| T-10-06 | low | New read path logs raw asset content | `Client._redact` covers the HTTP layer; no new logging was added on the read path. |
| T-10-09 | low | New re-show/removal loops leak token or asset content in logs | The new loops log only `asset.id`, identical to the pre-existing delete loop. |
| T-10-11 | medium | `--delete` and `--hard-delete` both passed → ambiguous destructiveness | Not merely accepted — hardened: `cli.py:73` puts them in an `add_mutually_exclusive_group()`, so argparse rejects the combination before any code runs. Verified live. |
| T-10-SC | low | Supply-chain risk from package installs | No packages were added in this phase. `pyproject.toml` dependencies are unchanged. |

## Notes for the reviewer

Two defects were found during UAT that are **not** security threats but bear on operational
trust, and are logged open in `STATE.md`:

- **Intermittent write 401s** (~4 in 10 runs, cleared by retry). It fails *loud and safe* —
  the run reports the failure and exits non-zero rather than silently skipping work — so it
  is a reliability defect, not a safety one.
- **Placeholder rows are unremovable.** `delete_asset` returns HTTP 200 while removing
  nothing on these rows. Worth noting because a success code that does nothing is exactly the
  shape of a dangerous silent failure — but here it fails toward *not* deleting, so the
  destructive direction is safe.

Neither weakens a mitigation above.
