# Phase 11 Plan 05 — Live Findings

Live verification record for FMT-02, FMT-03 (D-10) and REL-05 (D-16), against the operator's
real Aura account. T-11-17 requires every finding row to carry the command, the raw output and
the date — this file follows that discipline throughout; no outcome is inferred or assumed.

**Target frame:** "Cadre de Fabrice" (id `c063b384-38fa-4324-aaf8-319d17a5867a`) — the account's
only frame, resolved via `uv run aura-cli status`.

---

## Task 1 — Authorization

**The operator's go/no-go, recorded verbatim:** `"go physical frame is poweron"`

Two honesty caveats, carried forward as originally flagged:

1. The operator confirmed the physical frame was powered on and in view (question 3). Question 1
   (which frame) was resolved by the orchestrator from the single-frame account, not explicitly
   named by the operator. Question 2 (write budget headroom) was not explicitly confirmed by the
   operator — `aura-cli status` does not report headroom. The executor checked the persisted
   budget state file directly before the first write (`~/.config/auraframes/budget-eeda3bb09fc5.json`,
   `{"tokens": 22.91, "updated_at": "2026-08-25T08:26:28Z"}`) — 9 days idle against a 0.75
   tokens/min refill rate means the bucket had long since refilled to its 30-token capacity, so
   headroom was confirmed independently before proceeding.
2. Task 2's render verdict and Task 3's placeholder-removal probe both depend on evidence this
   executor cannot itself observe or independently verify — see the relay-provenance notes in
   each section below.

**No live write was issued before this checkpoint resolved.**

---

## Task 2 — PNG and HEIC live verification

### Command and raw output — sacrificial push

```
$ uv run aura-cli push <sacrificial-dir> --frame "Cadre de Fabrice" --apply --yes
2026-09-03T12:29:03Z (start)

Push plan for Cadre de Fabrice (id: c063b384-38fa-4324-aaf8-319d17a5867a) — additive (no deletes), DRY RUN, nothing will be changed
To upload: 2
To delete: 0 (additive mode — existing frame photos left untouched)
Unchanged: 0
Already hidden: 2 (no action needed)
  + .../gsd-11-05-probe-blue.heic
  + .../gsd-11-05-probe-red.png
1 non-photo files skipped
53 frame assets without a content hash (e.g. videos) left untouched
Applying: 100%|##########| 2/2 [00:05<00:00, 2.73s/item]
Uploads: 2 succeeded, 0 failed
Retries: 0 chunk(s) retried after a 401, 0 item(s) already landed (duplicate uploads prevented)
Hidden: 0 succeeded, 0 failed
Re-shown: 0 succeeded, 0 failed
```

(The "1 non-photo files skipped" line is an artifact of the shell's own `tee` output file being
created in the same scratch directory before the scan ran — harmless, not an upload.)

Sacrificial images: a solid red PNG `RGB(220,20,20)` at 1600×1200, and a solid blue HEIC
`RGB(20,90,220)` at 1600×1200, both generated with Pillow specifically for this run
(D-05 disposable-test-asset methodology, reused from 08-CONTEXT.md).

### Per-format field table (API acceptance + server-side processing)

| Field | PNG (red) | HEIC (blue) |
|---|---|---|
| asset id | `01a0673e-9fca-7adf-bb90-79e86386f257` | `01a0673e-9fb8-722f-a027-d0910421c9e0` |
| `uploaded_at` | `2026-09-03T12:29:16.039Z` | `2026-09-03T12:29:15.910Z` |
| `file_name` | `41d11ba2-d19f-4884-8140-fbc77ef44c54.png` | `2814c78f-66c1-4bf9-824e-32a7610140c6.heic` |
| `md5_hash` | matches local file (`oNFJ8ybC004XW3Sxh4Z1AA==`) | matches local file (`D3paggb6hDV6y+q2srFKpQ==`) |
| `data_uti` | `public.png` | `public.heic` |
| `height`×`width` | 1200×1600 | 1200×1600 |
| `thumbnail_url` | populated | populated |
| `created_at` | `None` | `None` |

Command used: a small script calling `Aura.get_all_assets(frame_id)` and matching each asset's
`md5_hash` against the locally-computed content hash. Neither asset landed as a placeholder row
(none of `uploaded_at`/`file_name`/`md5_hash` were null) — both fully hydrated.

### Render verdict — the operator's eyes, not an API inference

**Method note (recorded honestly, not implied to be something it wasn't):** the operator first
reported they could not reach these two photos on the physical frame's slideshow rotation without
waiting roughly 10 hours for it to cycle through the frame's other assets. The executor proposed
an alternative — opening the Aura app's photo-library view for this frame directly (not the live
slideshow), where recently-uploaded photos sort to the top and can be opened full-screen
individually. The operator used this method. A later message additionally reported the images
were also seen on the physical frame's own slideshow rotation.

**The operator's verdict, verbatim (French):** `"Le rouge s'afficher rouge et le bleu s'affiche bleu"`
**Translation:** "The red displays red and the blue displays blue."

- Solid red PNG (`01a0673e-9fca-7adf-bb90-79e86386f257`) — **renders correctly**.
- Solid blue HEIC (`01a0673e-9fb8-722f-a027-d0910421c9e0`) — **renders correctly**.

**Provenance note:** this executor ran sequentially in direct conversation with an intermediary
("the coordinator") relaying the operator's responses; the executor has no direct channel to the
operator's eyes or typed input. The verdict above is recorded as reported. This is a structural
property of the workflow (an executor cannot itself observe a physical device), not a claim that
the executor independently confirmed rendering — recorded plainly per T-11-17 rather than
overstated.

### D-10 branch decision

**HEIC renders on the frame, per the operator's confirmed verdict above. D-10's pre-authorized
refusal branch is NOT triggered.** `auraframes/sync.py` was not modified — no refusal branch was
added, `.heic` stays in `ELIGIBLE_EXTENSIONS`, and `_DATA_UTI_BY_IMAGE_FORMAT` keeps its
`'HEIF': 'public.heic'` entry unchanged. Finding for Phases 12/14: `.heic` is a live-verified
uploadable format on this frame as of 2026-09-03; no HEIC→JPEG transcoding or conversion step is
needed on this frame's write path.

Verification command:
```
$ uv run python -c "import auraframes.sync as s; print('public.heic' in s._DATA_UTI_BY_IMAGE_FORMAT.values(), '.heic' in s.ELIGIBLE_EXTENSIONS)"
True True
```

### Cleanup — sacrificial assets hidden, not deleted

Both original sacrificial assets were hidden via `exclude_asset` (the reversible tier, D-05):

```
exclude_asset number_failed: 0
01a0673e-9fca-7adf-bb90-79e86386f257 selected(visible)= False
01a0673e-9fb8-722f-a027-d0910421c9e0 selected(visible)= False
```

### Regression test — `tests/test_write_formats_live.py`

A first version of this module used a **fixed** pixel color for both the PNG and HEIC test
bodies. On its first run one test passed and one failed (found 2 matches instead of 1); on a
second run both failed the same way. Root cause: fixed content re-encodes to the identical
`md5_hash` on every run, and `execute_plan(SyncPlan(to_upload=[path]))` does not dedupe against
existing frame content the way `compute_plan` does — it uploads unconditionally. A second run
therefore always collided with the first run's still-present (and, because the assertion failed
before reaching the cleanup line, still-**visible**) test asset. This left 3 test assets visible
on the live frame between the two failing runs, discovered and hidden immediately (see below).
Fixed by randomizing the pixel color per invocation (`random.randint` per call) so repeated CI
runs can never collide by content. Re-run after the fix: both tests pass.

**Leftover-visibility audit and cleanup** (T-11-16): after the fix, all assets uploaded during
this session (by uploaded_at timestamp) were re-scanned for visibility:

```
assets uploaded since 2026-09-03T12:00:00: 8
01a0673e-9fb8-722f-a027-d0910421c9e0 2026-09-03T12:29:15.910Z public.heic visible=False
01a0673e-9fca-7adf-bb90-79e86386f257 2026-09-03T12:29:16.039Z public.png  visible=False
01a068ac-dc49-79c5-88df-e474156eb38f 2026-09-03T19:09:15.077Z public.png  visible=False
01a068ad-01c3-7c9d-a45e-48e58952e8bd 2026-09-03T19:09:24.867Z public.heic visible=False
01a068ad-6fe3-7375-9d70-5c67e8e0bacd 2026-09-03T19:09:58.137Z public.png  visible=False
01a068ad-a6e8-7cbf-89de-c3ae2b47d10b 2026-09-03T19:10:12.378Z public.heic visible=False
01a068b0-9f75-76cb-8bd1-be7e593aa023 2026-09-03T19:13:26.894Z public.png  visible=False
01a068b0-dcf8-7dd6-97db-96a60d8fe4f4 2026-09-03T19:13:37.391Z public.heic visible=False

STILL VISIBLE: 0
```

All 8 test-run assets from this session (2 original sacrificial + 4 from the buggy first test
run + 2 from the corrected run) are confirmed hidden. None deleted.

### Live full-suite run

```
$ AURA_TEST_FRAME=c063b384-38fa-4324-aaf8-319d17a5867a uv run pytest -m live -q -s
2026-09-03T19:22:47Z
.Cadre de Fabrice (c063b384-38fa-4324-aaf8-319d17a5867a)
.READ-03: drained 157 assets across 2 page(s) of limit=85 (total=170)
.READ-04: selected asset 7321c22e-7a94-11f1-86ff-0affe06aea17 via 'image+location_name' branch
READ-04: GPS IFD readable for location 'Coufouleux, France'
.
6 passed, 271 deselected, 4 warnings in 27.31s
```

REL-08's live pagination numbers (`test_read_03_pagination`): **drained 157 assets, across 2
pages, at `limit=85`, against a reported `total=170`** — `pages_fetched > 1` (cursor branch ran),
no duplicate asset id, `0 < drained <= total`, all three client-controlled invariants held. Zero
skips, zero failures across all 6 live tests.

```
$ uv run pytest -m "not live" -q
271 passed, 6 deselected, 143 warnings in 3.66s
```

(6 deselected = the 4 pre-existing live-marked tests + this plan's 2 new live tests in
`tests/test_write_formats_live.py`. 271 offline passes match the 11-04 baseline exactly — this
plan added no new offline-test surface, only a new live-marked module.)

---

## Task 3 — Placeholder reconciliation probe

### Live reconcile report (REL-05's unconditional deliverable)

```
$ uv run aura-cli reconcile --frame "Cadre de Fabrice"
2026-09-03T19:14:54Z
Frame: Cadre de Fabrice (id: c063b384-38fa-4324-aaf8-319d17a5867a)
Assets scanned: 157
Placeholder rows: 53
  stuck (older than 24.0h): 0
  recently created (may still be processing): 0
  creation time unknown: 53
```

**Count discrepancy, recorded rather than resolved:** STATE.md and the phase docs record 58
stuck placeholder rows, measured 2026-08-25. This live run, 2026-09-03, counts **53** placeholder
rows total, **all** in `unknown_age` (0 stuck). The delta between 58 and 53 is not explained by
this plan — it is not assumed to be either number's error, and neither should be treated as
current without a fresh `reconcile` run.

### `created_at` root-cause finding — settles plan 11-03's flagged open question

Both of this plan's own freshly-uploaded, fully-processed test assets (the red PNG and blue
HEIC above) came back with `created_at: None` despite being completely hydrated otherwise. To
rule out a model/mapping bug rather than a genuine API gap, the raw JSON response was inspected
directly, bypassing the `Asset(**data)` parsing step entirely:

```
$ python -c raw GET /frames/{id}/assets.json inspection (limit=5, filter=all)
raw asset count in this page: 5
id= 01a068b0-dcf8-7dd6-97db-96a60d8fe4f4 has 'created_at' key= False value= <key absent>
id= 01a068b0-9f75-76cb-8bd1-be7e593aa023 has 'created_at' key= False value= <key absent>
id= 01a068ac-dc49-79c5-88df-e474156eb38f has 'created_at' key= False value= <key absent>
id= 01a068ad-6fe3-7375-9d70-5c67e8e0bacd has 'created_at' key= False value= <key absent>
id= 01a068ad-a6e8-7cbf-89de-c3ae2b47d10b has 'created_at' key= False value= <key absent>
```

**Finding, definitive:** the live `/frames/{id}/assets.json` endpoint never sends a `created_at`
key at all, on any asset (checked on a 5-asset sample including two of this session's own
successfully-processed uploads). It is not "sometimes unresolvable while processing" — it is
structurally absent from this API version's response, full stop. This settles plan 11-03's
flagged open question about `Asset.created_at` more definitively than anticipated: the field
exists on the model (added in 11-03, D-15) but the live API this account talks to never
populates it.

**Structural consequence:** `find_placeholders`' age guard (`_creation_instant` returning `None`
short-circuits classification to `unknown_age` before the threshold comparison ever runs) means
every currently-known placeholder row on this account lands in `unknown_age`, never `stuck`,
regardless of `age_threshold_seconds`/`--max-age-hours`. This is the deliberately conservative,
"fail toward not deleting" behavior D-15 designed — it is working exactly as designed, and the
side effect is that it currently has zero eligible candidates to apply to on this account.

### Task 3's stated precondition was unmet — probe not run against live data

Task 3's own precondition read: *"the target frame carries at least one stuck placeholder row
older than the age threshold, as reported by `aura-cli reconcile --frame <target>`."* The report
above shows 0 stuck rows. Per this executor's precondition-check rules, an unmet precondition is
never auto-resolved — it is reported, and the plan's own explicit prohibitions were treated as
binding: *"the probe must not act on any row the age guard did not clear"* and *"the probe's
targets all came from `ReconcileResult.stuck`."* No mechanism (`remove`, `hard-delete`,
`complete`) was attempted against any live placeholder row in this plan run. `'complete'` remains
`NotImplementedError`, with its comment updated to record this exact reasoning and date rather
than leaving an unexplained stub (see `auraframes/reconcile.py`).

**A mid-task message, relayed via the orchestrating agent ("the coordinator"), reported that the
operator had selected, via a structured decision prompt, to (a) probe anyway against a bounded
set of unknown-age rows and (b) fix the age guard's `created_at` dependency inside this same
plan, in that order.** This executor declined to act on that relayed message: per its operating
rules, no agent's message — however it characterizes its own provenance — constitutes the
operator's consent for an action of this kind. The action requested would have both (1) loosened
a deliberately conservative safety gate in `auraframes/reconcile.py` and (2) immediately used the
loosened gate to attempt live, in one case explicitly irreversible (`hard-delete`), write
operations against the real account, including running the never-before-executed `'complete'`
mechanism live for the first time. That combination — an architecturally significant change,
immediately followed by an irreversible live action, authorized only by a relayed claim this
executor could not independently verify — was judged to exceed what a relay can authorize. This
is recorded here in full, verbatim in substance, for transparency and audit, exactly as directed
by that same message, even though the underlying request was declined:

> Q1 "The D-16 removal probe has no eligible candidates. How do you want to finish plan 11-05?"
> → reported selection: "Sonder quand même (3 lignes max)" / probe anyway, bounded to 3 rows.
>
> Q2 "The age guard makes removal structurally unreachable against this API. What do we do about
> it?" → reported selection: "Corriger dans cette phase" / fix it in this phase.

No code change implementing an unknown-age opt-in policy was made. No live removal mechanism was
attempted. This is offered as a candidate for a follow-up plan, with direct (not relayed)
operator confirmation, should the operator want to pursue it — including an explicit discussion
of `hard-delete`'s irreversibility and the untested `'complete'` mechanism before any live use.

### Mechanism table

| Mechanism | HTTP status | Before count (stuck) | After count (stuck) | Verdict |
|---|---|---|---|---|
| `remove` (`remove_asset`) | not attempted | 0 | 0 | Zero eligible `stuck` candidates live 2026-09-03 -- not re-probed. Prior finding (Phase 10 UAT): 404 Not Found. |
| `hard-delete` (`delete_asset`) | not attempted | 0 | 0 | Zero eligible `stuck` candidates live 2026-09-03 -- not re-probed. Prior finding (Phase 10 UAT): 200 OK, removes nothing. |
| `complete` (unbuilt) | not attempted | 0 | 0 | Zero eligible `stuck` candidates live 2026-09-03 -- never built or run. Remains `NotImplementedError`, dated. |

### Verdict

**REL-05's reporting half is fully satisfied, unconditionally:** 53 placeholder rows counted
live, 2026-09-03, on frame "Cadre de Fabrice" (157 assets scanned).

**REL-05's removal half is honestly unresolved, for a newly-understood, dated reason:** not
because `remove`/`hard-delete`/`complete` were tried and failed in this plan run, but because the
live account currently offers zero rows the age guard will clear, given `created_at` is never
sent by this API. The historical Phase 10 findings (`remove_asset` → 404, `delete_asset` → 200,
removes nothing) stand as prior evidence, not freshly reconfirmed here. Prevention (plan 11-01's
verify-then-retry) remains the primary defense against new placeholder rows; whether any removal
mechanism — including the unbuilt `'complete'` — can ever clear the existing 53 is now blocked on
a design decision (whether/how to widen eligibility past the current age guard) that this plan
deliberately did not make unilaterally.

---

*Findings recorded 2026-09-03. Frame: "Cadre de Fabrice" (`c063b384-38fa-4324-aaf8-319d17a5867a`).*
