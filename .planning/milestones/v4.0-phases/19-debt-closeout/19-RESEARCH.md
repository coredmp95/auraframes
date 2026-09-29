# Phase 19 Research: Debt Closeout

**Researched:** 2026-09-28 (inline research pass; no subagent runtime available —
per the established project convention from phases 16-18)
**Confidence:** high — every debt item was read in-tree at its exact lines; there
are no unknowns of design here, only small mechanical changes with grep-gates.

## Summary

Phase 19 is a closeout: three carried debts, each traced to exact lines that
still exist verbatim from the era they were flagged. Nothing is speculative. The
only design care points are (a) keeping MOD-02's behavior byte-identical when
env is unset, (b) making the MOD-04 fix instance-scoped rather than a global
logger mutation that would fight `cli.py`'s `_configure_cli_logging()`, and
(c) landing TEST-01 as two precise offline tests rather than a test-infra
project.

## Debt 1 — MOD-02: hardcoded AWS constants

**Exact current state (read 2026-09-28):**

- `auraframes/aws/s3client.py` lines 9-13:
  ```python
  BUCKET_KEY = 'images.senseapp.co'
  # TODO: May want to redact the pool ids -- read them in through config?
  UPLOAD_IDENTITY_POOL_ID = 'us-east-1:b92826c0-8274-43db-abff-136977c13598'
  ```
  used in `upload_file` (`Bucket=BUCKET_KEY`) and `__init__`
  (`pool_id if pool_id else UPLOAD_IDENTITY_POOL_ID`).
- `auraframes/aws/sqsclient.py` lines 9-11: `SQS_IDENTITY_POOL_ID =
  'us-east-1:98ccd0ff-69fe-4e9a-ad34-671b4381ab12'` + the same TODO, same
  `pool_id if pool_id else …` seam in `__init__`.
- `auraframes/aws/awsclient.py` line 9 carries a related stale TODO
  (`Convert this to use os.environ vars?`) — the constructor already takes
  `pool_id`; only the constants are the debt.

**Importer census (grep 2026-09-28):** `S3Client` is imported by
`auraframes/aura.py`, `auraframes/cli.py`, `tests/test_write_formats_live.py`;
`get_md5` by `sync.py` + 4 test files. `SQSClient` by `aura.py`, `cli.py`,
`test_write_formats_live.py`. **No module imports `BUCKET_KEY`,
`UPLOAD_IDENTITY_POOL_ID`, or `SQS_IDENTITY_POOL_ID` directly** (only their
defining modules use them) — removal is grep-safe today, and the plan adds a
grep gate to keep it true.

**Design:** settings.py extension per D-01/D-02. The `pool_id=None` constructor
seams stay; the module constants move to settings imports. Zero behavior change
when env unset is provable by asserting the settings defaults equal the shipped
literals (test sketch in CONTEXT §specifics).

## Debt 2 — MOD-04: `_init_logger()` sink leak

**Exact current state:** `aura.py` lines 151-160 — `_init_logger()` runs
`os.makedirs('logs/', exist_ok=True)` then TWO unconditional `logger.add(...)`
(stderr + `logs/file_{time}.log`). `Aura.__init__` calls it first thing (line
26). Consequence observed live in this repo: `logs/` contains 0-byte files and
near-duplicate timestamps from single-invocation CLIs constructing `Aura()` more
than once (e.g. `run_status`'s login path + the UAT probes), and the v1.1
research already flagged the per-test `offline_aura()` amplification.

**Constraints that shape the fix:**
- loguru's `logger` is a process-global singleton; **`cli.py`
  `_configure_cli_logging()` (lines 211-214) is the established wholesale
  `logger.remove()` + re-add point** and must keep working (its `debug=False`
  path relies on removing everything `_init_logger` added).
- Tests across the suite already call `logger.remove()` twice as their own
  hygiene (`test_cli_status.py` comments document the singleton pattern).
- The fix must therefore be **instance-scoped**: an instance flag prevents
  double-registration for the same instance, without touching global state —
  so `cli.py`'s contract and every existing test's `logger.remove()` calls are
  unaffected.

Wait — one honest correction from the research pass: a pure instance flag
prevents *re-registration by the same instance*, but the actual leak is
**distinct instances each adding sinks**. The minimal correct fix is therefore:
`_init_logger()` skips registration if **any** logger file sink for this
process was already registered by a previous `Aura` construction — implemented
as a **module-level flag in `aura.py`** (not instance-level), still not
touching loguru's global state directly. First `Aura()` in a process configures
logging; subsequent constructions are no-ops for sinks. This matches the
CLI's real usage (one process = one logging config) and kills the file-spam
symptom entirely. D-03 of 19-CONTEXT is amended to module-level scope by this
research (the CONTEXT file's "per instance" wording is superseded here; the
plan states the module-level truth).

**Test design (D-04, refined):** `monkeypatch.chdir(tmp_path)`; construct
`Aura(client=offline_client)` ×3; assert exactly ONE
`logs/file_*.log` file exists after the third construction (not three). Also
assert log records still flow (a `logger.info` lands in the file) so the fix
cannot be "accidentally removed logging".

## Debt 3 — TEST-01: candidates #2 and #4

**Origin record:** v1.1-ROADMAP settled design verbatim: "`base_url` stays
hardcoded (endpoint config deferred to candidate #4). … Auth/login mechanism
untouched (the `add_default_headers` mutation is candidate #2's concern)."

**Candidate #2 (authenticated value) — what already exists vs what closes it:**
`tests/test_offline_read_path.py::test_offline_login_sets_auth_headers` asserts
**presence** only (`assert headers.get("x-token-auth")`). The live
`test_read_path.py` mirror has the same shape. What the debt asks is the
authenticated VALUE driven offline: after login against the `login.json`
fixture (`auth_token: "fake-auth-token-0001"`, `id: "user-fake-0001"`), assert
exact equality on both headers AND that a subsequent request through the same
client carries them (the propagation is what `add_default_headers` exists for
and what only the live suite exercised implicitly). One new test in
`test_offline_read_path.py` closes it; no production change.

**Candidate #4 (injected config) — the one production change in TEST-01:**
`Client.__init__` composes `base_url=f'{AURA_API_BASE_URL}/{AURA_API_VERSION}'`
inline (client.py line ~160). v1.1 deliberately deferred injection. The change:
additive keyword `base_url: str | None = None`, None ⇒ identical composition.
Test: capturing MockTransport handler; `Client(transport=handler,
base_url='https://mock.invalid/v9')`; GET; assert handler saw
`request.url.host == 'mock.invalid'` and path prefix `/v9/`. Offline,
zero network, closes the candidate verbatim.

**Requirement-1 overlap check:** ROADMAP criterion 1 ("default suite runs green
with no credentials and no network") is already true suite-wide (390 passing
offline today); the criterion's *named* content — the two candidates — is what
this phase adds. No suite re-architecture is in scope.

## Risks / Notes

- **Log-file assertion flakiness:** loguru timestamps make filenames unique;
  tests must glob-count, never hardcode names. tmp-cwd isolation is mandatory
  (the repo's own `logs/` must never receive test writes).
- **Import-time config caution:** settings values are read at import time by
  convention; MOD-02's tests assert defaults + source references (grep) rather
  than reload games — reload-based env tests are flaky by import caching and
  are explicitly not used (test sketch in CONTEXT §specifics).
- **`test_imports.py` regression:** a one-line addition asserts the three old
  constants no longer exist as module attributes (`not
  hasattr(s3client, 'BUCKET_KEY')`), catching accidental reintroduction.
- **Zero live network:** all new tests are unmarked offline tests; the live
  suite is untouched (`R4-LIVE-UNCHANGED` precedent).

## Verification Commands (plan-level, deterministic)

- MOD-02: `uv run pytest tests/test_settings_budget.py tests/test_imports.py -q`
  + `! grep -n "BUCKET_KEY\|IDENTITY_POOL_ID = 'us-east-1" auraframes/aws/s3client.py auraframes/aws/sqsclient.py`
- MOD-04: `uv run pytest tests/test_aura_logger.py -q` (new file) + the
  3-constructions-one-file assertion inside it
- TEST-01: `uv run pytest tests/test_offline_read_path.py -q`
- Whole-phase floor: `uv run pytest -q -m "not live"` ≥ 390 passed

---
*Phase: 19-Debt Closeout*
