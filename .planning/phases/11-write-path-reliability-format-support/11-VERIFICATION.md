---
phase: 11-write-path-reliability-format-support
verified: 2026-09-03T20:18:03Z
status: passed
score: 5/5 roadmap success criteria verified (40+ plan-level must-have truths cross-checked; see breakdown)
behavior_unverified: 0
overrides_applied: 0
---

# Phase 11: Write-Path Reliability & Format Support — Verification Report

**Phase Goal:** `sync --apply` stops failing spuriously, the frame's stuck data is accounted for,
and uploads accept the file types Google albums routinely contain
**Verified:** 2026-09-03T20:18:03Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria — the contract)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A `sync --apply` run that hits a transient HTTP 401 completes without operator intervention and creates no duplicate frame asset for the retried item; the retry's `WriteBudget` cost is a stated, documented decision. | ✓ VERIFIED | `AuraError`/`AuthenticationError`/`WriteEndpointError`/`RateLimitError`/`ConsecutiveWriteFailureError` hierarchy confirmed at `auraframes/client.py:28,45,72,89`, `auraframes/sync.py:210`. Verify-then-retry loop for uploads at `auraframes/sync.py` (probe-before-resend for client-minted local_identifiers). Behavior-dependent truths confirmed by passing named tests: `test_401_on_select_asset_recovers_after_relogin_and_resend`, `test_two_item_chunk_401_resends_only_the_genuinely_absent_item`, `test_second_401_after_relogin_attributes_all_and_makes_no_third_attempt`, `test_inconclusive_probe_is_never_resent_and_is_attributed_as_failure`, `test_retried_upload_chunk_consumes_5_budget_tokens_total` (all pass — ran `tests/test_retry_401.py` directly, 81 passed across the retry/reconcile/format test files). `Retries:` summary line printed unconditionally at `auraframes/cli.py:739`. |
| 2 | Write failures are attributed honestly: a genuine authentication failure is still reported as one, a `batch_update` response that silently drops ids is reported as a failure, and an asset identity carrying neither `id` nor `local_id` is rejected at construction. | ✓ VERIFIED | `test_failed_relogin_raises_authentication_error_and_makes_no_further_write_calls` passes. `BatchUpdateResult.unacknowledged` confirmed at `auraframes/api/assetApi.py:16-127` (computed as sent-set minus acknowledged-set, order-preserving). `AssetPartialId`'s `@model_validator(mode='after')` at `auraframes/models/asset.py:145-148` raises `ValueError` when neither `id` nor `local_identifier` is set — confirmed on the ordinary construction path, not a bypassable secondary check. `Aura.upload_image` consumes `unacknowledged` (no longer discards `batch_update`'s result) per `auraframes/aura.py`. |
| 3 | A directory containing `.png` files uploads end-to-end and is verified on a real frame; `.heic` either uploads for real or is refused with a message naming the missing decoder — decided explicitly, never silent. | ✓ VERIFIED | `data_uti` derived from `Image.open(path).format` (decoded bytes), not filename — `auraframes/sync.py:435-466`. Mapping table restricted to JPEG/PNG/HEIF (`_DATA_UTI_BY_IMAGE_FORMAT`, `auraframes/sync.py:85-88`); unmapped formats fail closed with a named reason. `pillow-heif>=1.6` is a declared dependency (`pyproject.toml:19`) and `pillow_heif.register_heif_opener()` runs at import time (`auraframes/sync.py:45,60`). Live verification recorded in `11-LIVE-FINDINGS.md` Task 2: a red PNG and a blue HEIC were uploaded to the operator's real frame (`Cadre de Fabrice`), confirmed fully hydrated (non-placeholder) via `md5_hash` match, and the operator visually confirmed correct rendering on both the app library view and the physical frame's slideshow ("Le rouge s'afficher rouge et le bleu s'affiche bleu", 2026-09-03). D-10's refusal branch was correctly NOT triggered since HEIC renders; `sync.py` left unmodified for this branch, confirmed by the plan's own verification command. The HEIC decision is recorded explicitly (not silent) for Phases 12/14's consumption. |
| 4 | `aura-cli` reports how many stuck placeholder rows the frame carries, and removes them if a working mechanism is found — reporting the count either way. | ✓ VERIFIED | `find_placeholders`/`classify_placeholders` in `auraframes/reconcile.py` uses the strict three-way-null predicate (`uploaded_at is None and file_name is None and md5_hash is None`), confirmed structurally isolated from the diff engine's hashless-video bucket. Both `run_inspect` (`auraframes/cli.py:309`) and `run_reconcile` (`auraframes/cli.py:385`) call the same `find_placeholders` function — the two counts cannot disagree (verified by direct line inspection, not just a passing test). Reporting confirmed live: 53 placeholder rows / 157 assets (`11-LIVE-FINDINGS.md` Task 3, 2026-09-03). Removal confirmed live in a second same-day session (plan 11-06): a corrected `unknown_age_policy` opt-in (`--include-unknown-age`, default unchanged — `auraframes/reconcile.py:97-199`, `auraframes/cli.py:127-140`) promoted 53 unresolvable-creation-time rows into the removal-eligible bucket; `remove` (`FrameApi.remove_asset`) removed all 3 probed rows, confirmed **by re-read** (each id individually absent from a fresh `get_all_assets()` call, not by HTTP 200 alone) and by an independent follow-up `aura-cli reconcile` run showing 156 assets / 50 placeholder rows (159→156, 53→50, exactly the 3 removed). REQUIREMENTS.md's REL-05 wording ("both halves evaluated and satisfied, live, 2026-09-03") is defensible from this evidence — command, raw HTTP request/response, and re-read verification are all present in `11-LIVE-FINDINGS.md`. |
| 5 | The default test suite passes with zero failures — `test_read_03_pagination` no longer asserts equality between two counts the server does not keep consistent. | ✓ VERIFIED | `uv run pytest -m "not live" -q` → **276 passed, 6 deselected, 0 failed** (re-ran directly, matches SUMMARY claims). `test_read_03_pagination` rewritten to assert only client-controlled invariants (`pages_fetched > 1`, no duplicate id, `0 < drained <= total`) — confirmed in `auraframes/aura.py`/`tests/test_read_path.py`; live-executed per `11-LIVE-FINDINGS.md` ("drained 157 assets across 2 page(s) ... total=170"), closing REL-08 by a live run, not just a source edit. |

**Score:** 5/5 roadmap success criteria verified. All 12 requirement IDs (REL-01..08, FMT-01..03,
MOD-03) are declared across the six plans' `requirements:` frontmatter with no orphans, and each
maps to concrete, re-checked evidence above.

### Plan-Level Must-Have Truths (supporting detail)

Each of the six plans' `must_haves.truths` blocks (40+ individual statements across 11-01
through 11-06) was cross-checked against the code and the offline/live test suite rather than
trusted from SUMMARY.md prose. All resolved to VERIFIED with one exception noted below (not a
declared must-have, but a review finding worth surfacing — see Anti-Patterns). Representative
spot-checks beyond the roadmap-level table above:

- `AssetApi.batch_update`'s malformed-entry tolerance (REL-06 inbound) — confirmed at
  `auraframes/api/assetApi.py:95-121`, per-entry try/except with `logger.warning`, never raises
  for one bad row in a batch.
- `test_read_03_pagination`'s integer-only, no-tolerance assertions (REL-08) — confirmed by
  reading `tests/test_read_path.py` directly.
- `find_placeholders`' age guard and its new `unknown_age_policy` opt-in (plan 11-06) — 5 new
  tests in `tests/test_reconcile.py` (23 total, 18 pre-existing unmodified), including
  `test_unknown_age_policy_default_still_parks_unresolvable_row_in_unknown_age`, confirming the
  default is byte-for-byte unchanged.
- Two planner-miscount deviations (RuntimeError count in `frameApi.py`; `reconcile` substring
  count in `sync.py`) recorded in `.planning/WINDOWS.md` — both independently re-verified here as
  genuine non-defects: `grep -c "raise RuntimeError" auraframes/api/frameApi.py` → 7 (matches the
  SUMMARY's corrected count), and `git log` confirms `frameApi.py` was never touched in any phase
  11 commit; `grep -n reconcile auraframes/sync.py` shows only 5 pre-existing, unrelated
  `budget.reconcile_tripped(...)` matches, no import of the new `reconcile` module.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `auraframes/client.py` | `AuraError` hierarchy, redaction | ✓ VERIFIED | Classes present and used |
| `auraframes/sync.py` | 401 retry, format detection | ✓ VERIFIED | Both features present, wired, tested |
| `auraframes/cli.py` | Retry summary, `reconcile`/`inspect` verbs, `--include-unknown-age` | ✓ VERIFIED | All present and wired |
| `auraframes/api/assetApi.py` | `BatchUpdateResult.unacknowledged` | ✓ VERIFIED | Present, wired into `Aura.upload_image` |
| `auraframes/reconcile.py` | `find_placeholders`, `apply_reconciliation`, `unknown_age_policy` | ✓ VERIFIED | Present, wired, live-confirmed working (`remove` mechanism) |
| `auraframes/models/asset.py` | `AssetPartialId` cross-field validator | ✓ VERIFIED | `@model_validator(mode='after')` raises on ordinary construction |
| `pyproject.toml` | `pillow-heif>=1.6` dependency | ✓ VERIFIED | Present |
| `tests/test_retry_401.py`, `test_batch_update_contract.py`, `test_reconcile.py`, `test_cli_reconcile.py`, `test_prep_upload_formats.py`, `test_write_formats_live.py` | New test coverage | ✓ VERIFIED | All present, all pass (offline: 276/276; live: 6/6 per `11-LIVE-FINDINGS.md`) |
| `.planning/phases/11-write-path-reliability-format-support/11-LIVE-FINDINGS.md` | Live evidence record | ✓ VERIFIED | Command + raw output + date for every claimed live finding, including the D-10 HEIC decision and the REL-05 removal-half evidence |
| `docs/CLI.md` | `reconcile` verb docs, `--include-unknown-age` | ✓ VERIFIED | Documented, including the "why this matters more than it sounds" caveat |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `execute_plan`'s upload/reshow/removal chunk loops | `AuraError` subclasses | `except` ladder ordering | ✓ WIRED | `RateLimitError`/`AuthenticationError`/`BudgetExhausted`/`ConsecutiveWriteFailureError` all explicitly excluded before the generic `except Exception` catch-all, in that order, across all three loops |
| `batch_update`'s `BatchUpdateResult` | `execute_plan` + `Aura.upload_image` | destructuring call sites | ✓ WIRED | Both call sites updated together (per plan 11-02's key-link requirement) |
| `find_placeholders` | `run_inspect` (`cli.py:309`) and `run_reconcile` (`cli.py:385`) | shared pure function | ✓ WIRED | Same function, two callers — counts cannot drift apart |
| `run_reconcile` | `apply_reconciliation` | mechanism dispatch table | ✓ WIRED | Only network-touching path, unreachable without `--remove` |
| `Image.open(path)` decoded format | `_DATA_UTI_BY_IMAGE_FORMAT` | `_prep_upload` | ✓ WIRED | Format comes from decoded bytes, not filename/extension |
| `pillow_heif.register_heif_opener()` | Pillow's format registry | import-time side effect | ✓ WIRED | Confirmed live: `.heic` opens and uploads successfully |

### Behavioral Spot-Checks / Test Execution

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full offline suite | `uv run pytest -m "not live" -q` | `276 passed, 6 deselected, 0 failed` | ✓ PASS |
| Live-marked tests exist and are enumerable | `uv run pytest -m live --collect-only -q` | 6 tests collected (`test_read_path.py` x4, `test_write_formats_live.py` x2) | ✓ PASS |
| Retry/reconcile/format-specific test files | `uv run pytest tests/test_retry_401.py tests/test_batch_update_contract.py tests/test_execute_plan.py tests/test_reconcile.py tests/test_cli_reconcile.py tests/test_prep_upload_formats.py -q` | `81 passed` | ✓ PASS |
| `raise RuntimeError` count in `frameApi.py` (deviation re-check) | `grep -c "raise RuntimeError" auraframes/api/frameApi.py` | `7` | ✓ PASS (matches corrected SUMMARY claim, git-log confirms file untouched by phase 11) |
| Live 401-retry, format, pagination, and REL-05 removal probe | recorded in `11-LIVE-FINDINGS.md` with command + raw output + date for each | all pass/confirmed | ✓ PASS (accepted per T-11-17 discipline; visual frame rendering cannot be re-run offline, but is honestly sourced and dated) |

Live/physical-device checks (HEIC/PNG rendering on the operator's frame) were not re-run by this
verifier — they cannot be reproduced offline. `11-LIVE-FINDINGS.md` was read closely for the
required discipline (command, raw output, date, honest provenance caveats) rather than trusted at
face value; it meets that bar for both FMT-02/FMT-03's render verdict and REL-05's removal-half
re-read verification.

### Requirements Coverage

| Requirement | Source Plan | Status | Evidence |
|---|---|---|---|
| REL-01 | 11-01 | ✓ SATISFIED | Verify-then-retry loop, tested |
| REL-02 | 11-01 | ✓ SATISFIED | Probe-before-resend, tested |
| REL-03 | 11-01 | ✓ SATISFIED | Retry charged via existing `WriteBudget.acquire` calls, tested |
| REL-04 | 11-01 | ✓ SATISFIED | Failed re-login raises `AuthenticationError`, never retried, tested |
| REL-05 | 11-03, 11-05, 11-06 | ✓ SATISFIED | Both reporting and removal halves confirmed live with re-read evidence |
| REL-06 | 11-02 | ✓ SATISFIED | Inbound tolerant / outbound strict validator confirmed |
| REL-07 | 11-02 | ✓ SATISFIED | `BatchUpdateResult.unacknowledged` confirmed and consumed |
| REL-08 | 11-02, 11-05 | ✓ SATISFIED | Integer-only invariant assertions, live-executed |
| FMT-01 | 11-04 | ✓ SATISFIED | Decoded-bytes-derived `data_uti` confirmed |
| FMT-02 | 11-05 | ✓ SATISFIED | Live PNG upload + operator-confirmed rendering |
| FMT-03 | 11-04, 11-05 | ✓ SATISFIED | `pillow-heif` dependency + live HEIC upload/render confirmed |
| MOD-03 | 11-01 | ✓ SATISFIED | `AuraError` hierarchy confirmed, exception routing order preserved |

No orphaned requirements — all IDs in the ROADMAP's phase 11 `Requirements:` line are claimed by
exactly one plan's frontmatter.

### Anti-Patterns Found (from `11-REVIEW.md`, independently re-confirmed against the code)

| File | Finding | Severity | Impact on phase goal |
|------|---------|----------|----------------------|
| `auraframes/sync.py:1009-1103`, `_REMOVAL_PRIMITIVE['hard_delete']` (`sync.py:413-414`) | **CR-01 (re-confirmed):** the per-asset `hard_delete` primitive is a list comprehension with no per-item try/except; a 401 partway through a chunk loses track of already-succeeded deletions, and the resend logic (correctly reasoned as a safe no-op for `hide`/`delete`, true batch endpoints) is applied unchanged to `hard_delete`, which is not idempotent-safe in the same way. `tests/test_retry_401.py` has a passing `test_removal_chunk_second_401_attributes_all_and_makes_no_third_attempt`, but confirmed by reading it directly (`removal_mode='hide'`) — **no test anywhere exercises a 401 mid-`hard_delete`-chunk.** | Warning (narrow, not a phase-goal blocker) | `hard_delete` is reachable only via the explicit `--hard-delete` flag plus a second typed-confirmation gate (`cli.py:641-648`) — an opt-in, heavily-gated, already-documented-as-riskier path, distinct from the default `hide` mode `sync --apply` uses. None of phase 11's declared must-have truths (all explicitly scoped to "upload chunk" or "frame asset duplication") cover this path, and ROADMAP Success Criterion 1 speaks specifically to duplicate-asset risk (an upload concern). This is a real, disclosed defect worth a follow-up plan — it does undermine the general "sync --apply stops failing spuriously" framing for users of `--hard-delete` specifically — but it does not fail any of the truths this phase actually committed to, and does not touch the default/primary write path this phase's own tests exercise. **Recommend:** file as a follow-up plan/issue rather than block phase 11; do not ship `--hard-delete` as "reliable under 401" without it. |
| `auraframes/reconcile.py:357-382` | WR-01: same attribution gap in `apply_reconciliation`'s `hard-delete` mechanism, without even a retry — a raised exception on item 3 of 5 attributes all 5 as failed even if 1-2 already succeeded. | Warning | Same reasoning as CR-01: narrow, opt-in, gated path (`--mechanism hard-delete`, itself already labeled "unconfirmed" in the CLI help text). Not exercised by the live probe (which used `remove`, not `hard-delete`). |
| `auraframes/client.py:14` | WR-02: `_REDACT_KEYS` does not cover `user_id`/`email` — both leak in cleartext to `logs/file_{time}.log` on every HTTP call, unconditionally (not `--debug`-gated). Pre-existing (commit `2a2314e`, not introduced by phase 11), but directly adjacent to this phase's own `include_input=False` fix for the same class of issue in `assetApi.py`. | Warning (pre-existing, security-relevant) | Does not affect any phase 11 requirement's correctness. Flagged because `workflow.security_enforcement: true` is active in `.planning/config.json` and no `11-SECURITY.md` exists for this phase — worth a `/gsd-secure-phase` pass or a follow-up fix before this account's logs are shared/inspected by anyone else. |
| `auraframes/sync.py:448,454` | WR-03: `_prep_upload` decodes format from one `Image.open(path)` read and uploads bytes from a second, later `path.read_bytes()` read of the same path — a file mutated between the two reads (e.g. a directory being synced while still edited) could decode format X and upload bytes of format Y, silently defeating D-11's "bytes decide" guarantee. Confirmed at the cited lines. | Warning | Edge case requiring concurrent file mutation during a sync run; does not affect the FMT-01 truth under normal single-writer conditions, which is what the passing tests exercise. |
| `auraframes/cli.py:136-140` | WR-04: `--include-unknown-age` help text implies a partial bypass ("not just rows old enough") when, given this API never sends `created_at` for any asset, it is a total bypass of the age safety net for every candidate. `reconcile.py`'s own docstring states this correctly. | Warning (documentation clarity) | No functional impact — the flag's actual behavior (confirmed in code) matches the more conservative reading; only the CLI help wording undersells the effect. |
| `auraframes/reconcile.py:358-363` | IN-01: `reconcile --mechanism complete` acquires real `WriteBudget` tokens before unconditionally raising `NotImplementedError`. Confirmed: `budget.acquire(...)` precedes the primitive call. | Info | Minor, non-blocking, already disclosed via CLI help text ("not yet implemented"). |

No debt markers (`TBD`/`FIXME`/`XXX`) found in any phase-11-modified file. The one
`NotImplementedError` (`reconcile.py`'s `_complete_placeholder`) is dated, reasoned, and
cross-references `11-LIVE-FINDINGS.md` rather than being an unexplained stub — it does not trip
the debt-marker gate.

### Deviations Cross-Checked

Both deviations recorded in `.planning/WINDOWS.md` (`open_count: 1`, one ledger entry — the
`RuntimeError` count) and the second one recorded only in `11-03-SUMMARY.md`'s Issues Encountered
(the `reconcile` substring count) were independently re-verified against the current codebase and
confirmed genuine planner miscounts, not implementation defects, per the SUMMARY's own reasoning.
The `WINDOWS.md` ledger entry remains `status: open` (not `waived`/`fixed`) — this is a
`workflow.windows_enforce` consideration for `/gsd-ship`, not a phase-11-verification blocker,
since the underlying claim (frameApi.py untouched by phase 11, 7 not 4 `RuntimeError` raises) was
independently confirmed true here.

### Human Verification Required

None outstanding. The items that would ordinarily require human verification — visual rendering
of the PNG/HEIC test uploads on the physical frame, and confirmation that a live removal
mechanism actually removes rows rather than merely returning HTTP 200 — were already performed
live by the operator during plan execution and are recorded with command, raw output, date, and
honest provenance caveats in `11-LIVE-FINDINGS.md`. This verifier read that record closely rather
than trusting SUMMARY.md's characterization of it, and found the evidentiary bar (T-11-17: no
outcome inferred or assumed) genuinely met.

### Gaps Summary

No gaps block the phase goal. All 12 requirement IDs are satisfied with re-checked code and test
evidence; all 5 ROADMAP success criteria hold. Five review findings (CR-01/WR-01/WR-02/WR-03/WR-04)
plus one info-level finding (IN-01) are real, independently re-confirmed defects — all on narrow,
mostly opt-in/gated paths (`--hard-delete`, `--mechanism hard-delete`, `--mechanism complete`, a
pre-existing log-redaction gap, and a low-probability concurrent-file-mutation race) that do not
invalidate any must-have truth this phase declared or any ROADMAP success criterion. They are
flagged here for follow-up rather than as blockers, consistent with the review's own severity
grading once re-examined against what the phase actually committed to deliver.

---

_Verified: 2026-09-03T20:18:03Z_
_Verifier: Claude (gsd-verifier)_
