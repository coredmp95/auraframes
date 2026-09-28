# Phase 11: Write-Path Reliability & Format Support - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-03
**Phase:** 11-Write-Path Reliability & Format Support
**Areas discussed:** 401 retry & duplicate safety, Retry budget accounting, HEIC support/refuse, Placeholder reconciliation UX, Failure attribution & test hygiene

---

## Area selection

| Option | Description | Selected |
|--------|-------------|----------|
| 401 retry & duplicate safety | REL-01/02/04 — blind vs verify-then-retry; distinguishing genuine auth failure | ✓ |
| Retry budget accounting | REL-03 — does a retry cost WriteBudget tokens | ✓ |
| HEIC: support or refuse | FMT-03 — hard dep, optional extra, or refuse | ✓ |
| Placeholder reconciliation UX | REL-05 — where the 58-stuck-rows report lives | ✓ |

**User's choice:** all four.

---

## 401 retry & duplicate safety

### Q1 — How should the retry decide it's safe to re-send?

| Option | Description | Selected |
|--------|-------------|----------|
| Verify, then retry | Re-login, probe `get_asset_by_local_identifier()` per item, re-send only genuinely-absent items | ✓ |
| Blind retry once | Re-login and re-send the chunk verbatim; accepts duplicate placeholder rows | |
| Retry only `batch_update`, never `select_asset` | Cannot duplicate, but leaves a genuinely-failed `select_asset` unrecovered | |

**Notes:** `AssetApi.get_asset_by_local_identifier()` was surfaced as already existing, so the idempotency probe needed no new endpoint. Reads are not the anti-abuse surface, so the probe is cheap.

### Q2 — What decides genuine auth failure vs transient? (REL-04)

| Option | Description | Selected |
|--------|-------------|----------|
| The re-login is the discriminator | Login fails → genuine auth failure, abort loudly; login succeeds but write 401s again → not auth, hand to the anti-abuse backstop | ✓ |
| One retry, second 401 is genuine | Simpler, but mislabels an anti-abuse trip as an auth problem | |
| Never classify — count only | Honest about uncertainty, but gives REL-04 no attribution | |

### Q3 — Where should the retry live?

| Option | Description | Selected |
|--------|-------------|----------|
| In `execute_plan`, per write chunk | Phase 9's Approach A seam, alongside budget/attribution, injectable for offline tests | ✓ |
| In `Client`, transparent to every request | Widest coverage; invisible to budget accounting; contradicts Phase 9's rejected Approach C | |
| Once per run, at the CLI level | Coarse and simple; loses the partial chunk's attribution | |

### Q4 — How many retries, and what happens when one still fails?

| Option | Description | Selected |
|--------|-------------|----------|
| One retry per chunk, one shared re-login, continue past failure | Refreshed session reused by later chunks; Phase 8 D-08 preserved; `ConsecutiveWriteFailureError` remains the ultimate abort | ✓ |
| One retry per chunk, abort the run if it fails | Safest against burning budget; reverses Phase 8 D-08 | |
| Retry until the consecutive-failure backstop trips | Most likely to complete a flaky run; most likely to burn the ~42-request envelope | |

---

## Retry budget accounting

### Q1 — What does a verify-and-retry cost against WriteBudget?

| Option | Description | Selected |
|--------|-------------|----------|
| Charge the retry at full write cost | 2 upload chunk / 1 delete chunk; Phase 9 observed failed attempts consume budget too | ✓ |
| Retry is free | Optimises for completing a flaky run; under-counts against a real server-side limit | |
| Charge the retry, and reconcile down on a 401 | Maximally conservative; any 401 forces the ~40-minute refill | |

### Q2 — Do verify reads and the re-login cost budget?

| Option | Description | Selected |
|--------|-------------|----------|
| Reads free, re-login costs 1 | Reads kept working through v2.0 lockouts; the v2.0 incident escalated to a *login* lockout | ✓ |
| Both free | Cleanest conceptually; ignores the observed login lockout | |
| Charge reads too | Most conservative; a 50-item chunk would cost 50 read tokens | |

### Q3 — If the budget is exhausted when a retry needs tokens?

| Option | Description | Selected |
|--------|-------------|----------|
| Same wait policy as any write | One policy, already configurable via `--no-wait`/`--max-wait`/`--ignore-budget` | ✓ |
| Retry never waits | Avoids a surprising ~40-minute stall inside error recovery | |
| Retry waits, shorter cap | Bounded surprise; second knob, second policy | |

### Q4 — How visible should retries be at runtime?

| Option | Description | Selected |
|--------|-------------|----------|
| Report retries in the run summary + document the rule in code | Chunks retried and duplicates prevented; costing rule as a comment beside the constant | ✓ |
| Code comment only, silent at runtime | Cleaner output; hides the best signal for judging whether the fix worked | |
| Report retries and remaining budget tokens | More insight; exposes an estimate only ever approximate to server reality | |

---

## HEIC: support or refuse

Live check performed during discussion: `uv pip install --dry-run pillow-heif` resolved `pillow-heif==1.6.0` on Python 3.14 with a prebuilt wheel.

### Q1 — How should `.heic` be handled? (FMT-03)

| Option | Description | Selected |
|--------|-------------|----------|
| Add `pillow-heif`, upload HEIC as-is | `data_uti=public.heic`, original bytes untouched, md5 diffing stays honest; needs a live render check | ✓ |
| Add `pillow-heif`, transcode to JPEG | Guaranteed to render; uploaded bytes stop matching the source, risking re-upload-forever | |
| Refuse `.heic` with an actionable message | No new dependency; Phase 14 inherits the gap | |

**Notes:** transcoding was rejected on diffing-contract grounds rather than image-quality grounds.

### Q2 — If the frame won't render an as-is HEIC upload?

| Option | Description | Selected |
|--------|-------------|----------|
| Fall back to refusing `.heic`, naming the real reason | Pre-authorized; phase still completes; finding recorded for Phases 12/14 | ✓ |
| Stop and report, decide then | Phase 7/8 precedent; costs a cycle on what is a capability gap, not a destructive surprise | |
| Fall back to transcoding to JPEG | Keeps the capability; reintroduces md5 drift | |

### Q3 — What should `data_uti` be derived from? (FMT-01)

| Option | Description | Selected |
|--------|-------------|----------|
| The decoded image's real format, via an explicit map | `Image.open().format` already read for dimensions; fail-closed table; bytes decide, not filename | ✓ |
| Extend the existing suffix→UTI map | Smallest change; keeps trusting the extension | |
| Sniff magic bytes independently | Most independent; duplicates what `Image.open()` already does | |

### Q4 — How wide should the accepted-format list be?

| Option | Description | Selected |
|--------|-------------|----------|
| Exactly the four already in `ELIGIBLE_EXTENSIONS` | JPEG/PNG/HEIF only — the set this phase live-verifies | ✓ |
| Add WebP as well | Google serves it in some paths; would ship unverified | |
| Anything Pillow can decode with a known UTI | Widest coverage, largest untested surface | |

---

## Placeholder reconciliation UX

### Q1 — Where does the report surface? (REL-05)

| Option | Description | Selected |
|--------|-------------|----------|
| New `reconcile` verb, plus a one-line count in `inspect` | Discoverable without knowing the verb exists; matches `research/ARCHITECTURE.md` | ✓ |
| New `reconcile` verb only | Cleanest separation; undiscoverable | |
| Fold it into `inspect` entirely | Fewer parts; puts a mutating action behind a read-only verb | |

### Q2 — How is a placeholder identified?

| Option | Description | Selected |
|--------|-------------|----------|
| All three null: `uploaded_at` AND `file_name` AND `md5_hash` | Narrowest; self-excludes videos and partially-hydrated assets | ✓ |
| Any of the three null | Catches more broken rows; also catches every video | |
| Null `md5_hash` alone | Reuses `compute_plan`'s `frame_no_hash`; that bucket includes videos by design | |

### Q3 — Avoiding an in-flight upload that matches the predicate

| Option | Description | Selected |
|--------|-------------|----------|
| Age guard on `created_at`, 24h default | Young rows reported as "may still be processing", never removal candidates; `created_at` is non-optional | ✓ |
| No age guard, confirm each row | Human in the loop; 58 rows is a long prompt and the human is doing the age check by hand | |
| No age guard — report only, never remove | Safest; REL-05 explicitly asks for removal if a mechanism is found | |

### Q4 — How hard should this phase try to find a removal mechanism?

| Option | Description | Selected |
|--------|-------------|----------|
| Time-boxed live probe, then report-only if nothing works | Includes *completing* the row via `batch_update` rather than deleting it; honest fallback allowed by REL-05's own wording | ✓ |
| Report-only, no probing | Zero risk, zero progress | |
| Probe until something works | Unbounded; every probe is a write against the ~42-request envelope | |

---

## Failure attribution & test hygiene (second pass — user chose "explore more gray areas")

### Q1 — REL-08: what should `test_read_03_pagination` assert?

| Option | Description | Selected |
|--------|-------------|----------|
| Assert the cursor loop's own correctness | >1 page fetched, no duplicate ids, drained >0 and ≤ total — the actual failure the test was written to catch | ✓ |
| Assert drained count within a tolerance of total | Bakes in a magic number that hides growing drift | |
| Move it offline against a fixture | Deterministic; stops exercising the live cursor behaviour that is the test's purpose | |

### Q2 — REL-07: where should the sent-vs-acknowledged check live?

| Option | Description | Selected |
|--------|-------------|----------|
| In `batch_update`, returned explicitly | One definition; `Aura.upload_image` (which discards the return today) finally gets a failure signal | ✓ |
| Leave it in `execute_plan` only | Smallest change; leaves `upload_image` swallowing dropped ids | |
| Raise from `batch_update` on any partial success | Contradicts the endpoint's documented contract | |

### Q3 — REL-06: strict outbound vs inbound tolerance

| Option | Description | Selected |
|--------|-------------|----------|
| Strict outbound, tolerant inbound | Hard error when constructing what we send; skip-and-log a malformed response entry so one junk row can't crash a 50-item chunk | ✓ |
| Strict in both directions | One rule; turns a server oddity into 50 falsely-attributed failures | |
| Verify it already works, change nothing | The pydantic-v2 validator may already satisfy REL-06; leaves the inbound crash risk | |

**Notes:** flagged for the planner that `auraframes/models/asset.py:137` is already a working `model_validator(mode='after')` — verify before rewriting.

### Q4 — MOD-03: how far should the typed exception hierarchy go?

| Option | Description | Selected |
|--------|-------------|----------|
| Common base + auth types, convert write-path `RuntimeError`s only | Enough structure for the retry logic to read clearly; no speculative taxonomy | ✓ |
| Minimal — just the auth exceptions | Smallest diff; four unrelated exception types with nothing in common | |
| Full hierarchy across the codebase | Most coherent; widest blast radius in a phase about trustworthiness | |

---

## Claude's Discretion

- Exception and flag naming (`AuthExpiredError` vs `AuthenticationError`; the `AuraError` base name; `reconcile`'s report-vs-remove flags).
- All user-facing message wording, following Phase 5 D-05's concise no-table style.
- Confirmation friction on `reconcile --remove` (normal `Proceed? [y/N]`, `--yes` honoured, drawing from the shared `WriteBudget`).
- Whether the verify probe issues one lookup per item or exploits a whole-chunk list/filter endpoint.
- How the PNG live verification is staged (Phase 8 D-05's disposable-test-asset methodology available).
- Physical placement of the retry logic within `execute_plan`, provided it stays injectable.

## Deferred Ideas

- WebP upload support — revisit after Phase 12 establishes what bytes the album mechanism delivers.
- HEIC → JPEG transcoding — only ever with a transcoded-bytes manifest, never a naive local hash.
- Codebase-wide typed exception hierarchy beyond the write path.
- Printing remaining budget tokens in the run summary.
- Re-tuning Phase 9's capacity/refill defaults if retries measurably shorten usable runs — a quick task, not phase scope.
