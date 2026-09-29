# Phase 19: Debt Closeout - Context

**Gathered:** 2026-09-28
**Status:** Ready for planning
**Provenance:** compiled by the planning agent from ROADMAP §Phase 19, REQUIREMENTS
TEST-01/MOD-02/MOD-04 verbatim, the v1.1 deferred-debt register
(`v1.1-ROADMAP.md` Issues Deferred), `PROJECT.md`'s known-debt list, and a direct
read of every file the debt touches (`s3client.py`, `sqsclient.py`, `awsclient.py`,
`settings.py`, `aura.py`, `client.py`, `tests/offline.py`,
`tests/test_offline_read_path.py`, `tests/conftest.py`). The operator chose
"inline without a discuss session" at the 2026-09-28 planning checkpoint, matching
phases 16-18.

<domain>
## Phase Boundary

Close the three carried debts so v4.0 ships clean:

1. **MOD-02** — the AWS identity-pool IDs and the S3 bucket name move from
   hardcoded module constants (`auraframes/aws/s3client.py`,
   `auraframes/aws/sqsclient.py`) into the existing env-var config module
   (`auraframes/utils/settings.py`), with **zero behavior change when the env is
   unset** (the shipped literals become the defaults).
2. **MOD-04** — `Aura._init_logger()` stops leaking loguru sinks / log files on
   repeated `Aura()` construction in one process.
3. **TEST-01** — the two v1.1-era lift-tests-off-network candidates close:
   **#2 authenticated value** (offline test asserts the fixture's exact
   `x-token-auth` value AND its propagation onto a subsequent request's headers)
   and **#4 injected config** (offline test drives the request path through an
   injected `base_url`, proving the endpoint constant is no longer read-only at
   import time where tests cannot reach it).

Does NOT deliver: MOD-01 async migration (explicitly out of scope, carried
replan decision), MOD-03-style typed-exception expansion, any behavior change to
the live login flow, S3/SQS request-shape changes, or new CLI verbs. This is a
closeout phase: harden and test what exists, add nothing user-facing.
</domain>

<decisions>
## Implementation Decisions

### MOD-02 — config-ize the AWS constants
- **D-01:** New settings land in **`auraframes/utils/settings.py`** (the existing
  Phase-09 env-var config home), following its established convention:
  `AWS_S3_BUCKET = os.getenv('AURA_AWS_S3_BUCKET', 'images.senseapp.co')`,
  `AWS_UPLOAD_IDENTITY_POOL_ID = os.getenv('AURA_AWS_UPLOAD_POOL_ID',
  'us-east-1:b92826c0-…')`, `AWS_SQS_IDENTITY_POOL_ID =
  os.getenv('AURA_AWS_SQS_POOL_ID', 'us-east-1:98ccd0ff-…')`. The shipped
  literals become the getenv defaults — unset env ⇒ byte-identical behavior
  (ROADMAP criterion 2 verbatim). — *agent-default on env names (AURA_ prefix
  matches every existing setting); requirement text verbatim on behavior.*
- **D-02:** `s3client.py` and `sqsclient.py` keep their `pool_id=None`
  constructor seams and switch their module constants to read from settings
  (`from auraframes.utils.settings import AWS_S3_BUCKET, …`). `BUCKET_KEY` and
  the two pool-ID constants are **removed** (not deprecated) — a repo-wide grep
  must find no other importer. The explicit `TODO: May want to redact the pool
  ids` comments die with the constants. — *agent-default; the constructor seams
  already exist and are tested (18-03's fakes pass pool_id paths).*

### MOD-04 — logger hygiene
- **D-03:** `Aura._init_logger()` becomes **idempotent per instance**: an
  instance flag (`self._logger_initialized`) guards the two `logger.add()`
  calls, so re-constructing `Aura()` in one process never duplicates sinks for
  the same instance. Module-level loguru state is NOT mutated globally by this
  fix (the process-global singleton behavior stays as-is — `cli.py`'s
  `_configure_cli_logging()` remains the one place that calls
  `logger.remove()` wholesale). — *agent-default; minimal blast radius; the
  leak's user-visible symptom (log files spawned per construction: `logs/`
  shows 0-byte and duplicate files) is what the fix kills.*
- **D-04:** The offline test proves the leak closed by counting **file sinks**:
  constructing N=3 `Aura(transport=...)` instances offline then asserting the
  set of `logs/file_*.log` paths did not grow 3×. File-count-based (loguru's
  handler ids are private-ish; the on-disk symptom is the contract). Tests set
  `AURA_STATE_DIR`-style isolation via a tmp cwd (monkeypatch chdir) so they
  never write into the repo's `logs/`. — *agent-default on the assertion
  mechanism.*

### TEST-01 — the two offline-test candidates
- **D-05 (candidate #2, authenticated value):** extend
  `tests/test_offline_read_path.py` with a test asserting the **exact value**:
  after `aura.login(email='fake@example.invalid', password='fake-pw')` against
  the fixture, `headers['x-token-auth'] == 'fake-auth-token-0001'` (the
  fixture's literal), `headers['x-user-id'] == 'user-fake-0001'`, AND a
  follow-up request through the same client carries both headers on the wire
  (captured by a capturing MockTransport handler). This is the "authenticated
  value" the v1.1 review deferred — presence was already tested; value +
  propagation were not. — *requirement text verbatim ("authenticated value");
  mechanism agent-default.*
- **D-06 (candidate #4, injected config):** `Client.__init__` gains an additive
  **`base_url: str | None = None`** keyword (None ⇒ today's
  `AURA_API_BASE_URL/AURA_API_VERSION` composition, byte-identical); an offline
  test injects `base_url='https://mock.invalid/v9'` and asserts the request
  lands on that host+path (capturing handler). This is the v1.1 deferral
  verbatim: "`base_url` stays hardcoded (endpoint config deferred to candidate
  #4)". No env var is introduced for it this phase (endpoint is not ops-tunable
  config; injection is the point). — *v1.1-ROADMAP settled-design text;
  mechanism agent-default.*

### Closeout discipline
- **D-07:** Both plans carry a **repo-wide grep gate**: after MOD-02, no
  module outside settings/s3client/sqsclient references the removed constants;
  after MOD-04, no second `logger.add('logs/…')` outside `aura.py` +
  `cli.py`. The offline suite must stay fully green (`uv run pytest -q -m "not
  live"`) with the pre-phase count as floor (390+). — *agent-default; matches
  the verify-command-paths probe convention.*

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `.planning/REQUIREMENTS.md` — TEST-01, MOD-02, MOD-04 verbatim (the phase contract)
- `.planning/ROADMAP.md` §Phase 19 — success criteria 1-3 (criterion 1 includes
  "no credentials and no network" for the whole default suite)
- `.planning/milestones/v1.1-ROADMAP.md` — Issues Deferred (the debt's origin
  record: candidates #2/#4 definitions + the MOD-04 warning)
- `auraframes/aws/s3client.py` — `BUCKET_KEY`, `UPLOAD_IDENTITY_POOL_ID`, the TODO
- `auraframes/aws/sqsclient.py` — `SQS_IDENTITY_POOL_ID`, the TODO
- `auraframes/utils/settings.py` — the env-var convention to extend (incl. `_bool_env`)
- `auraframes/aura.py` — `_init_logger()` (the leak), `login()` (the auth-header mutation)
- `auraframes/client.py` — `Client.__init__` base_url composition (candidate #4's target)
- `tests/offline.py` + `tests/test_offline_read_path.py` — the harness and the file to extend
- `tests/test_settings_budget.py` — the existing settings-module test pattern

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `settings.py`'s `os.getenv(NAME, default)` convention — MOD-02 is a pure
  extension of an established pattern (Phase 09 precedent)
- `S3Client(pool_id=…)`/`SQSClient(pool_id=…)` constructor seams already accept
  injected pools — the constants are the only hardcoded part
- `Aura(client=…)` DI seam (v1.1) — MOD-04's test constructs offline instances
  without touching the network
- `offline_aura()`/`make_router` overrides + capturing-handler pattern (Phase
  17's routers do this) — both TEST-01 tests are plain extensions
- `tests/test_imports.py` — the right home for a "constants gone" import-level
  regression test if wanted

### Established Patterns
- Env-var config with safe defaults, parsed at import time in settings.py only
- pytest offline: MockTransport routers, monkeypatch tmp cwd, no live marks
- Fail-loud; the suite must stay 100% offline-green (TEST-02 discipline)
- CLI/config secrets never printed (vault denylist untouched by this phase)

### Integration Points
- `s3client.upload_file` reads `BUCKET_KEY` per call — switching to a settings
  import is call-site-invisible
- `Aura.__init__` calls `_init_logger()` first — the guard flag lives on the
  instance, set before any sink registration
- `Client.__init__(transport=…)` already takes optional seams — `base_url`
  joins the same signature additively (zero-arg callers unaffected)

</code_context>

<specifics>
## Specific Ideas

- MOD-04 test sketch: `monkeypatch.chdir(tmp_path)`; construct 3 `Aura`s
  offline; `sorted(Path('logs').glob('file_*.log'))` grows by exactly ONE file
  (loguru's first sink), not three.
- Candidate #2 test sketch: `offline_aura()` login, assert exact header values
  from `login.json` fixture (`fake-auth-token-0001` / `user-fake-0001`); then a
  `capturing = {}` handler around `aura._client.http2_client` — simplest via a
  fresh `Client(transport=capturing_router)` whose `headers` dict is asserted
  after `add_default_headers`.
- Candidate #4 test sketch: `Client(transport=capture, base_url='https://mock.invalid/v9')`
  + a GET; assert `capture['host'] == 'mock.invalid'` and path startswith `/v9/`.
- MOD-02 test sketch: `monkeypatch.setenv('AURA_AWS_S3_BUCKET', 'other.invalid')`
  then re-import settings via `importlib.reload` — or better, assert the
  DEFAULTS equal the shipped literals and that s3client/sqsclient reference
  settings (grep gate), avoiding reload flakiness.

</specifics>

<deferred>
## Deferred Ideas

- Env var for the Pushd API base_url (candidate #4 deliberately stops at
  injection; an ops-tunable endpoint is not requested by any requirement)
- MOD-01 async migration (out of scope, carried decision)
- Typed-exception expansion beyond the write path (MOD-03's scoped decision)
- Log-file rotation/retention policy (the leak fix does not add rotation)
- Redaction audit of the pool IDs themselves (the old TODO's stretch goal —
  the IDs are Cognito identity pools, not account secrets; config-ization is
  what the requirement asks)

</deferred>

---

*Phase: 19-Debt Closeout*
*Context gathered: 2026-09-28*
