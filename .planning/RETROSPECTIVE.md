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

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change |
|-----------|--------|-------|------------|
| v1.0 | 3 | 5 | Established read-path-only done bar, credential-gated live tests, and GSD debug/quick workflows |
| v1.1 | 1 | 3 | Architecture review (`/grilling`) before planning; additive DI seam pattern; offline `MockTransport` test harness pattern |

### Cumulative Quality

| Milestone | Live tests | Toolchain | Notes |
|-----------|-----------|-----------|-------|
| v1.0 | READ-01–04 (skip without creds) | Python 3.14 + uv + pydantic v2 | Read path proven live; upload path deferred to v2.0 |
| v1.1 | READ-01–04 unchanged (drift oracle) + 5 offline tests + 4 fixture-validity tests | unchanged | Read-path assertions now dual-covered: offline (fast, no creds) + live (drift oracle) |
