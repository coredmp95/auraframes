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

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change |
|-----------|--------|-------|------------|
| v1.0 | 3 | 5 | Established read-path-only done bar, credential-gated live tests, and GSD debug/quick workflows |

### Cumulative Quality

| Milestone | Live tests | Toolchain | Notes |
|-----------|-----------|-----------|-------|
| v1.0 | READ-01–04 (skip without creds) | Python 3.14 + uv + pydantic v2 | Read path proven live; upload path deferred to v2.0 |
