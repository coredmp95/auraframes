# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — Revive & Verify

**Shipped:** 2026-06-30
**Phases:** 3 | **Plans:** 5 | **Tasks:** 13

### What Was Built
- Toolchain revival: migrated the broken UTF-16 `requirements.txt` to a `uv`-managed `pyproject.toml` + committed `uv.lock`; 37 packages resolved on Python 3.14 as cp314 wheels (no sdist builds).
- pydantic v1→v2 migration of the whole `auraframes` model layer: `AllOptional` metaclass → `make_partial` `create_model` factory, `pydantic_encoder` → `model_dump(mode="json")`, `@validator` → `@field_validator`, guarded by an import smoke test.
- Credential-gated live read-path test suite (READ-01 login, READ-02 list, READ-03 paginated asset drain, READ-04 image download + EXIF read-back) that skips cleanly without creds, with fail-loud transport (`raise_for_status`) and on-disk secret redaction.
- Facade-only `main.py` read-path demo, README reconciled to verified reality, and a repo-root `VERIFICATION-REPORT.md` backed by a fresh live run.
- Post-verification hardening: `.env` loading in `main.py` (`python-dotenv` → runtime dep) and a fix for the HTTP 475 login failure (credentials resolved at call time, not import time).

### What Worked
- **Read-path-only "done bar."** Scoping the milestone to login → list → download (upload explicitly deferred) kept it small and produced a genuine live end-to-end proof rather than a half-built write path.
- **Fail-loud + credential-gated tests.** `raise_for_status` everywhere and a `@pytest.mark.live` skip-without-creds harness meant a green suite couldn't hide API drift, and a credential-less checkout still stays green.
- **GSD subagent isolation.** The /gsd-debug session pre-diagnosed in the orchestrator, then the session manager verified + fixed in an isolated context — the 475 root cause (early-bound default args) was found and fixed in essentially one cycle.

### What Was Inefficient
- **Worktree stale-base glitch.** A `/gsd-quick` executor's isolation worktree forked from an old phase-02 commit instead of the current tip and halted (correctly, fail-closed). Cost one round-trip and a fallback to direct-on-master execution.
- **The 475 bug shipped latent.** `main.py`'s `.env` quick task "passed" verification while the read path was still broken by the import-time default-arg bug — because the verify step proved the no-op path (no creds) but not a real login. A live smoke check after the .env change would have caught it immediately instead of one iteration later.
- **Default-arg footgun lived in the original code.** `os.getenv` in a default argument was inherited from the 2023 codebase; the revival validated imports and read flow but didn't flag the import-time evaluation until `.env` loading exposed it.

### Patterns Established
- **None-sentinel for env-backed defaults:** `def f(x=None): x = x if x is not None else os.getenv(...)` — never call `os.getenv` directly in a default argument (evaluated once at import).
- **`load_dotenv()` belongs at the top of the entry point**, mirroring `tests/conftest.py`; resolution of env-backed config must happen at call time, after it runs.
- **Verify behavior, not just structure:** an offline AST/`__defaults__` assertion is a cheap regression guard, but a capability change to an entry point also warrants a real (or mocked-transport) exercise of the changed path.

### Key Lessons
1. When a change affects *when* configuration is read (import vs. call time), test the actual consuming path, not just the guard around it — the guard and the consumer can disagree.
2. Worktree isolation can fork from a stale base; the fail-closed guard is correct — default recovery is a fresh worktree or an explicit, confirmed direct-on-main run, never a silent main edit.
3. Reviving old code: validating imports + happy-path flow is necessary but not sufficient; latent Python footguns (mutable/early-bound defaults, silent excepts) survive a naive revival and surface under new usage.

### Cost Observations
- Model mix: planning/debug on Opus; execution/verification largely Sonnet; light checks on Haiku (profile switched quality → adaptive mid-session).
- Notable: the most expensive correctness win (the 475 fix) came from a cheap pre-diagnosis in the orchestrator + a focused isolated fix agent, not a long investigation loop.

---

## Milestone: v1.1 — Client Transport Seam

**Shipped:** 2026-07-05
**Phases:** 1 | **Plans:** 3

### What Was Built
- Additive `Client(transport=...)` / `Aura(client=...)` dependency-injection seam — zero-arg callers (`main.py`, existing live tests) unaffected — closing the long-standing `# TODO: Can probably use DI` in `aura.py`.
- 5 sanitized, entirely synthetic fixture JSON files (login, frames, 2-page assets, error envelope) plus a fixture-validity pytest hydrating each against `User`/`Frame`/`Asset`.
- Reusable offline test harness (`tests/offline.py`): an `httpx.MockTransport` router keyed by resolved path, with a per-test overrides dict checked before the default routing branches.
- A 5-test offline mirror of `test_read_path.py` (`tests/test_offline_read_path.py`) covering login headers, frame hydration, pagination drain, and both error-raise mechanisms — all part of the default (unmarked) `pytest` run, zero network/credentials required.

### What Worked
- **Architecture review before planning.** A `/grilling` session settled the DI seam's exact shape (`transport=None`, `client=None`, both additive) before any code was written, so all 3 plans executed without a design change mid-flight.
- **Synthetic fixtures over recorded ones.** Hand-authoring fixture JSON instead of recording and scrubbing real API responses removed the sanitization risk entirely — there was never a real secret in the file to miss.
- **Keeping the `@live` suite as drift oracle.** Verification explicitly diffed `tests/conftest.py` and `tests/test_read_path.py` byte-for-byte against the pre-phase commit, proving the offline work was purely additive.

### What Was Inefficient
- **`Aura._init_logger()` sink leak surfaced but not fixed.** Code review flagged that repeated `Aura()` construction leaks loguru sinks/log files, amplified by the new per-test `offline_aura()` pattern — correctly deferred rather than scope-crept into this phase, but it's now a known cost every future offline test pays.
- **Milestone boundary ambiguity.** Phase 4 was executed and verified under `STATE.md`'s `milestone: v1.0`, but v1.0 had already been archived (phases 1-3) before Phase 4 started — closing this milestone required manually reconciling which version Phase 4 belonged to instead of it being unambiguous from state.

### Patterns Established
- **Path + query-param MockTransport router**, matching on the fully-resolved `/v5`-prefixed path and branching pagination fixtures on `next_page_cursor` truthiness — the template for any future offline test harness in this codebase.
- **Assign a milestone version to a phase at insertion time**, not at close time — avoids the ambiguity this milestone hit when a promoted backlog phase (`999.1` → `04`) wasn't tagged with a target version up front.

### Key Lessons
1. Settling architecture via a dedicated review session (`/grilling`) before planning pays off directly in plan stability — zero design churn across 3 plans.
2. Synthetic-not-recorded fixtures are a strictly safer default for any offline test harness touching auth-adjacent payloads.
3. When a phase is promoted from backlog outside the normal roadmap flow, tag its target milestone version immediately — don't leave it to be inferred at `/gsd-complete-milestone` time.

### Cost Observations
- Sessions: phase spanned 2026-07-01 (research/planning) → 2026-07-05 (execution/verification/close), with most execution concentrated in a single 2026-07-04 session (~6 min total across 3 plans per STATE.md timing).
- Notable: all 3 plans combined took under 10 minutes of recorded execution time — the architecture review upfront (not tracked here) was the actual bulk of the effort, not the coding.

---

## Milestone: v2.0 — Directory-to-Frame Sync

**Shipped:** 2026-09-02
**Phases:** 6 (5-10) | **Plans:** 17 | **Tasks:** 43 | **Commits:** 160 | **Span:** 51 days

### What Was Built
- Packaged `aura-cli` with four verbs — `status` (config/auth health + account frames), `inspect --frame <name|id>` (metadata + first-N photos, name-substring or exact-ID resolution), `sync <dir> --frame <name|id>` (content-hash directory mirroring), and `push` (direct upload with anti-abuse override flags).
- A dry-run diffing engine (`auraframes/sync.py`) split structurally into a pure `compute_plan()` and a mutating `execute_plan()`, matching on base64-MD5 `md5_hash` rather than filename, with a 4-way classification (re-show / unchanged / removal-candidate / already-hidden) once visibility entered the model.
- **The write path proven live for the first time in the codebase's three-year history:** the `select_asset` → S3 → SQS → `batch_update` upload round-trip, `remove_asset`'s frame-scoped disassociation, `exclude_asset`/`select_asset` hide-and-re-show, and `delete_asset`'s blast radius measured twice by before/after inventory diff.
- `auraframes/ratelimit.py` — an injected-clock `WriteBudget` token bucket persisted per account and reconciled against real anti-abuse trips, plus a fail-open `check_geo` pre-flight guard, wired as the default protection for every `--apply`.
- Hide-by-default removal: `sync --apply` now costs visibility rather than photos, restoring a local file re-shows its photo without re-uploading, and the two destructive tiers are mutually-exclusive opt-in flags behind an exact-count confirmation.
- Batched write path (`WRITE_BATCH_SIZE=50`, ~3N → ~2 Pushd calls per chunk) with a deliberate inter-chunk pause and tqdm progress feedback, all added as quick tasks under live pressure.

### What Worked
- **Safety-first phase ordering paid for itself.** Phases 5-7 touched only already-live-verified read endpoints, so by the time Phase 8 fired the first write, frame resolution and the diff engine were already proven. A failure in Phase 8 could only be a write failure — the search space was pre-narrowed.
- **Dry-run as a *structural* default, not a flag.** Separating `compute_plan()` from `execute_plan()` meant Phase 7 shipped with no reachable mutating primitive at all. A flag can be inverted by a bug; a function containing no mutating call cannot mutate. The same seam made `execute_plan` fully offline-testable with injected S3/SQS fakes.
- **Cheap live spikes before building on an assumption — three times, three redirects.** Phase 6 asked whether `md5_hash` is populated on read (yes for photos, null for video → scoped the milestone to photos). Phase 7 asked whether local and remote hash encodings match (byte-identical → the diff engine could be trusted). Phase 10 asked which field carries visibility (`asset_settings[asset_id].selected`, *not* `Asset.selected` → caught before Plan 10-02 built on the wrong signal). Each cost one short probe and saved a rewrite.
- **Fail-loud, continue-past-failure, non-zero-exit held up under a real incident.** A live run against a near-empty directory produced a 72-item delete plan; 25 hit a mid-batch token expiry. Nothing was silently skipped, nothing was lost, and a fresh re-run completed cleanly — the design was validated by the accident rather than by a test.
- **Live UAT found what the test suite structurally could not.** The intermittent 401s, the unremovable placeholder rows, and the `Frame.smart_adds` drift were all invisible to 208 offline tests and only appeared under repeated real runs.

### What Was Inefficient
- **A wrong diagnosis shaped a whole phase.** Phase 9 was built on the theory that the persistent write lockout was a VPN geo mismatch. Phase 10 disproved it from a French residential IP — the 401 is transient token expiry. The token-bucket half of Phase 9 is genuinely valuable; the `check_geo` half solves a problem that did not exist. The evidence that would have falsified it (retry the identical call minutes later) was cheaper than the phase that assumed it.
- **The real fix was identified but not shipped.** "Retry once on 401 with a fresh login" was written down after the Phase 8 mid-batch incident, restated after Phase 10 UAT, and still ships as an open defect — after two phases of elaborate machinery built around the symptom. The cheap fix lost to the interesting one.
- **A 47-day gap between Phase 9 (2026-07-09) and Phase 10's completion (2026-08-25)**, spent blocked on the write-lockout theory. Most of that was waiting on a condition that a five-minute retry experiment would have cleared.
- **`select_asset` was called with identifiers whose uploads never completed**, permanently accumulating 58 unremovable placeholder rows on the live test frame and corrupting `num_assets` against the paginated drain. A live-verification side effect that is now permanent state.

### Patterns Established
- **Structural safety over flag safety:** when a capability is destructive, express the safe mode as a *different function* rather than a branch. `compute_plan`/`execute_plan`; `removal_mode` naming the primitive; `delete_asset` reachable only when a caller names it.
- **Probe the mechanism before modelling it.** Any assumption about an undocumented API's field semantics gets one disposable live probe against throwaway data before code depends on it.
- **Measure blast radius by inventory diff.** `delete_asset`'s scope was established twice by counting the frame before and after against a disposable asset — not by reading a docstring's guess.
- **Status codes are not a reliable rate-limit signal.** The same anti-abuse trip surfaced as 401, 429, and a non-standard 475 across attempts. A status-agnostic consecutive-failure-run counter (reset on success) is the durable backstop beneath any status-code fast path.
- **Drift convention for a moving API:** when a previously-required response field disappears, demote it to `Field(default_factory=...)` rather than chasing the schema — established in Phase 2, applied unchanged to `Frame.smart_adds` in Phase 10.

### Key Lessons
1. **Falsify the cheap explanation before building on the expensive one.** "Geo-blocked" was plausible, unfalsified, and cost a phase. "Token expired, retry it" was testable in five minutes and turned out to be right.
2. **A symptom worth two phases of machinery is worth one afternoon of the direct fix.** The retry-on-401 remained unwritten through a rate-limiter, a geo guard, batching, and pacing — all of which are useful, none of which addressed the defect users actually hit.
3. **Live verification leaves permanent residue.** Probes mutate real state: 58 stuck rows and a corrupted `num_assets` are the cost of proving the write path. Budget for disposable targets, and never issue a write whose completion you do not intend.
4. **Offline test count is not confidence.** 208 passing tests coexisted with a major reliability defect, an unremovable-row bug, and a schema drift that broke every CLI verb. Offline suites prove logic; only repeated live runs prove behavior.
5. **A live probe that contradicts the plan is the plan working.** Phase 10-01 invalidated its own successor's design assumption — that is what the gate was for, and it cost one plan instead of three.

### Cost Observations
- Model mix: planning/discussion and debug on Opus; execution/verification largely Sonnet; ~43 tasks across 17 plans.
- Sessions: spread over 51 calendar days, with a ~47-day stall between Phase 9 and Phase 10 that was diagnostic, not implementation, cost.
- Notable: the highest-value outputs of the milestone were three short live spikes (Phases 6, 7, 10-01), each a fraction of a plan's cost, each redirecting or de-risking everything downstream. The most expensive item was a phase built on an unfalsified hypothesis.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change |
|-----------|--------|-------|------------|
| v1.0 | 3 | 5 | Established read-path-only done bar, credential-gated live tests, and GSD debug/quick workflows |
| v1.1 | 1 | 3 | Architecture review (`/grilling`) before planning; additive DI seam pattern; offline `MockTransport` test harness pattern |
| v2.0 | 6 | 17 | Safety-first phase ordering (read-only phases before the first write); dry-run as a structural split, not a flag; disposable live spikes gating downstream plans; retroactive `/gsd-secure-phase` + `/gsd-code-review` per phase |

### Cumulative Quality

| Milestone | Live tests | Toolchain | Notes |
|-----------|-----------|-----------|-------|
| v1.0 | READ-01–04 (skip without creds) | Python 3.14 + uv + pydantic v2 | Read path proven live; upload path deferred to v2.0 |
| v1.1 | READ-01–04 unchanged (drift oracle) + 5 offline tests + 4 fixture-validity tests | unchanged | Read-path assertions now dual-covered: offline (fast, no creds) + live (drift oracle) |
| v2.0 | 208 passed / 1 failed; write path live-verified (upload, remove, hide/re-show, delete blast radius) | unchanged | Write path proven live for the first time. The 1 failure (`test_read_03_pagination`) asserts equality between two counts the server does not keep consistent. 3 defects carried forward: intermittent write 401s, 58 unremovable placeholder rows, that pagination assertion |

### Recurring Themes

| Theme | v1.0 | v1.1 | v2.0 |
|-------|------|------|------|
| **Latent bugs surface only under real use** | HTTP 475 from an import-time default arg, hidden behind a passing verification | loguru sink leak amplified by the new per-test `offline_aura()` pattern | intermittent write 401s, unremovable placeholder rows, `Frame.smart_adds` drift — all invisible to 208 offline tests |
| **Verify the consuming path, not the guard** | `.env` change "passed" while the read path stayed broken | live `@live` suite deliberately kept as the drift oracle | three live spikes gated downstream design; each one redirected it |
| **Cheap experiment beats elaborate theory** | pre-diagnosis in the orchestrator, focused fix agent | — | ⚠️ regressed: an unfalsified geo theory cost a phase and a 47-day stall |

**Carry into the next milestone:** the pattern that keeps paying is the disposable live probe *before* the design depends on an assumption. The pattern that failed in v2.0 is the inverse — building infrastructure around an unfalsified diagnosis. Before the next milestone commits to anything about the 401s, run the retry.
