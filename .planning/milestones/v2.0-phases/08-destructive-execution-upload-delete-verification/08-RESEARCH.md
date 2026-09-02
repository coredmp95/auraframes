# Phase 8: Destructive Execution (Upload + Delete Verification) - Research

**Researched:** 2026-07-07
**Domain:** Reverse-engineered Aura Frames cloud API write path (upload round-trip + delete primitives) in a Python 3.14/`uv` CLI tool
**Confidence:** MEDIUM — the codebase itself was fully read and several claims were directly executed/verified against the installed pydantic 2.13/boto3 1.43 stack; the *live API's actual behavior* for untested endpoints (`delete_asset`, the double `select_asset` call, `data_uti`/`taken_at` field validation) remains genuinely unknown until Phase 8's own execution-time live checkpoints run — this is unavoidable for an undocumented API and is why WRITE-01/02/03 are checkpoint tasks, not research questions.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Apply Confirmation UX**
- **D-01:** Two-flag model. `--apply` alone prints the full plan (reusing Phase 7's untruncated upload/delete listing, D-07) and then prompts `Proceed? [y/N]`. `--yes` (combinable with `--apply`, e.g. `sync ... --apply --yes`) skips that interactive prompt for scripting/CI use.
- **D-02:** One confirmation gate covers the whole plan — uploads and deletes are not gated separately.
- **D-03:** When `--apply` runs non-interactively (no TTY) without `--yes`, it fails closed: print an error (e.g. `--apply requires --yes when running non-interactively`) and exit non-zero without touching anything.
- **D-04:** The confirmation prompt always echoes the resolved frame's name + id (e.g. `About to apply this plan to "Cadre de Fabrice" (id: c063b384-...). Proceed? [y/N]`).

**Delete-Primitive Live Verification**
- **D-05:** `delete_asset`'s live behavior is probed using a dedicated disposable test asset — never a real photo the user cares about.
- **D-06:** `--apply`'s delete path calls `remove_asset` exclusively. `delete_asset` is live-verified and documented but has no reachable code path from `--apply` this phase.
- **D-07:** If the live `delete_asset` probe reveals more destructive behavior than its docstring suggests, stop the live-verification checkpoint immediately and report exactly what was observed.

**Failure Handling Mid-Apply**
- **D-08:** Execution continues past a single item's failure rather than aborting the whole run; final summary reports success/fail per item; process exits non-zero if anything failed.
- **D-09:** Within a run, all uploads are attempted before any deletes.
- **D-10:** End-of-run failure summary reports uploads and deletes in separate sections, each with failed items individually named.

**SQS Queue Targeting Fix (WRITE-04)**
- **D-11:** Straightforward parameterization fix — `get_sqs()` should resolve the queue for whatever frame is being synced, not the hardcoded original-test-frame id. `SQSClient.get_queue_url(frame_id)` already accepts `frame_id` — `Aura.get_sqs()` just needs to stop hardcoding the argument it passes in.

### Claude's Discretion
- Exact wording of the `--apply`/`--yes` confirmation prompt and the plan-header frame echo, following D-01–D-04's content requirements and Phase 5's concise, no-table output style.
- How `execute_plan()` is structured relative to Phase 7's `compute_plan()` — must stay a distinct function/path from the read-only diff engine (structural, not `if apply:`-flag-based, separation).
- How the disposable test asset for the `delete_asset` probe (D-05) is created/sourced, and how the SQS fix (D-11) is implemented/tested offline.
- Exact construction of upload identity (`local_identifier`, etc.) for local files with no pre-existing Aura asset record — this is resolved by this research below (see "Upload Identity Construction").

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope. `--max-delete` circuit breaker (SYNC-05) and `--json` output (SYNC-06) are v2 requirements, explicitly not built here. Wiring `delete_asset` into any executable path is explicitly out of scope this phase (documented-only finding, per D-06).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-------------------|
| SYNC-03 | `sync ... --apply` executes the computed plan: uploads new local files, removes gone-locally frame photos via `remove_asset` | See "Upload Round-Trip Sequencing" and "Delete Path" below — exact call sequence, identity fields, and error semantics documented from source. |
| SYNC-04 | Plan output lists upload/delete/unchanged counts before applying; CLI exits non-zero on any execution failure | Phase 7 already implements the counts print (`run_sync`, `auraframes/cli.py:275-278`); D-08's exit-non-zero-on-any-failure convention extends Phase 5's `run_status`/`run_inspect` int-return pattern — documented in "Code Examples". |
| WRITE-01 | Verify the image upload round-trip live (`select_asset` → S3 → SQS confirm → `batch_update`) | Full existing (broken/unguarded) sequence documented below with exact line references; identity-construction blocker (`Asset(id=None,...)` fails validation) verified directly against the installed pydantic 2.13 and resolved via `AssetPartial`. Live confirmation is an execution-phase checkpoint, not resolvable from static reading. |
| WRITE-02 | Verify `remove_asset`'s real behavior live | `remove_asset` is already implemented and typed (`FrameApi.remove_asset`, `auraframes/api/frameApi.py:135-148`) — no code changes needed for the call itself, only the fail-loud wrapper (WRITE-05) and the live-verification checkpoint. |
| WRITE-03 | Verify `delete_asset`'s real behavior live | `AssetApi.delete_asset` exists (`auraframes/api/assetApi.py:74-88`) but its docstring admits unknown scope. This MUST be a `checkpoint:human-verify` task per D-05/D-07 — no static-analysis path resolves it. |
| WRITE-04 | Fix hardcoded frame id in `Aura.get_sqs()` | Exact location and minimal fix identified: `auraframes/aura.py:130-134`. See "SQS Queue Fix" below. |
| WRITE-05 | Extend fail-loud error handling to write/delete endpoints | Phase 7's `FrameApi.get_assets` established the `if json_response.get('error'): raise RuntimeError(...)` convention (`auraframes/api/frameApi.py:50-56`) — this research documents exactly which write endpoints currently lack it and what to add. |

</phase_requirements>

## Summary

Phase 8 turns Phase 7's read-only `compute_plan()` into a real, mutating `execute_plan()`. The codebase already has every low-level primitive needed (`FrameApi.select_asset`/`remove_asset`, `AssetApi.batch_update`/`delete_asset`, `S3Client.upload_file`, `SQSClient.get_queue_url`/`receive_message`) — none of it is new API surface. What's missing is (1) a working identity-construction path for uploading a **genuinely new local file that has never been an Aura `Asset`**, since the only existing upload orchestration (`Aura.upload_image()`) assumes a pre-hydrated `Asset` with a `local_identifier` already set, and (2) fail-loud error handling on the write endpoints, which currently silently return `number_failed`/raw JSON with no `error`-field check (unlike the already-hardened `get_assets`).

The single most load-bearing finding of this research: **`Asset(id=None, ...)` is not constructible today.** `Asset.id` is typed `str` (not `Optional[str]`), yet `Asset.is_local_asset` (`return self.id is None`) and `AssetApi.update_taken_at_date`/`delete_asset` both branch on the assumption that a "local-only, not-yet-synced" `Asset` can exist with `id=None`. This was directly verified by attempting the construction against the installed pydantic 2.13 — it raises `ValidationError: id — Input should be a valid string`. **`execute_plan()`'s upload path must not try to build a full `Asset` for a new file.** The existing `auraframes/models/meta.py:make_partial()` factory (already used for `FramePartial`) trivially solves this: `AssetPartial = make_partial(Asset, 'AssetPartial')` makes every field `Optional`, and constructing one with only the fields `AssetApi.batch_update`'s allowlist actually sends (`local_identifier`, `file_name`, `md5_hash`, `height`, `width`, `taken_at`, `data_uti`, `selected`, `upload_priority`) was directly verified to succeed and to serialize to exactly the expected payload shape.

The SQS fix (WRITE-04) is a two-line parameterization: `Aura.get_sqs()` (`auraframes/aura.py:130-134`) must accept a `frame_id` argument and pass it through to the already-parameterized `SQSClient.get_queue_url(frame_id)` instead of the hardcoded `'4ab446b4-33a7-4a76-881d-d545d153ab5a'` string; its one call site (`upload_image`, line 114) already has `frame_id` in scope.

**Primary recommendation:** Do not attempt to reuse `Aura.upload_image()` as-is for `execute_plan()`'s upload path — rebuild a new, narrower upload function that (a) generates its own `local_identifier` via `uuid.uuid4()` for files with no prior Aura identity, (b) uses `AssetPartial` (not `Asset`) for the `batch_update` payload, (c) fixes the SQS frame-id parameterization, (d) treats the SQS `receive_message` polls as best-effort/observational rather than a blocking success gate (the current code discards the first poll's result entirely and only prints the second), and (e) wraps every per-file API call in its own try/except so one file's failure doesn't abort the batch (D-08) and is individually attributable (WRITE-05).

## Architectural Responsibility Map

This is a single-process CLI tool, not a multi-tier web app — tiers below are this project's actual layers (per `.planning/codebase/ARCHITECTURE.md`), not generic browser/API/DB tiers.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| `--apply`/`--yes` flag + confirm prompt (D-01–D-04) | CLI (`cli.py` handler) | — | User-facing UX; no business logic beyond echo + y/N gate. |
| Plan counts before applying (SYNC-04) | Sync Engine (`sync.py` `compute_plan`, reused) | CLI (`cli.py` print) | Already built in Phase 7; this phase only adds the confirm gate in front of the existing print. |
| Upload round-trip orchestration (SYNC-03, WRITE-01) | Facade (`Aura`/new `execute_plan()`) | API Clients (`FrameApi.select_asset`, `AssetApi.batch_update`) + AWS SDK (`S3Client.upload_file`) | The facade sequences the multi-step round-trip; the API/AWS clients are thin, already-typed wrappers being reused, not modified in shape. |
| Delete execution via `remove_asset` (SYNC-03, WRITE-02) | API Clients (`FrameApi.remove_asset`, reused as-is) | Facade (calls it from `execute_plan()`) | Endpoint already exists and is typed; the only new code is the orchestration loop + fail-loud wrapper. |
| `delete_asset` live probe (WRITE-03) | API Clients (`AssetApi.delete_asset`, reused as-is) | — (one-time checkpoint, not wired into any execute path) | Investigative, not orchestration — a `checkpoint:human-verify` task, structurally isolated from `execute_plan()` per D-06. |
| SQS queue-id fix (WRITE-04) | Facade (`Aura.get_sqs`) | AWS SDK (`SQSClient.get_queue_url`, already parameterized) | Bug is entirely in how the facade calls an already-correct AWS SDK wrapper — no AWS-layer change needed. |
| Fail-loud per-endpoint + per-file error handling (WRITE-05) | API Clients (`FrameApi`/`AssetApi` methods) | Facade/`execute_plan()` (per-item try/except + continue-past-failure, D-08) | Error-field checking belongs at the same layer `get_assets` already established it (API client method); per-file continue/attribution is an orchestration concern one layer up. |

## Standard Stack

### Core
No new libraries are introduced this phase. Every primitive needed already exists in the installed stack:

| Library | Installed Version | Purpose | Why Standard (for this codebase) |
|---------|---------|---------|--------------|
| `pydantic` | 2.13 (installed; pyproject floor `>=2`) [VERIFIED: local venv] | `AssetPartial` construction for new-upload identity | Already the project's sole data-modeling layer; `make_partial()` (`auraframes/models/meta.py`) is the existing, tested factory for exactly this "all-fields-optional" need (already used for `FramePartial`). |
| `boto3` / `botocore` | 1.43.36 (installed; pyproject floor `>=1.34`) [VERIFIED: local venv] | S3 upload, SQS queue lookup/poll | Already the project's sole AWS SDK; no alternative needed. |
| `uuid` (stdlib) | n/a | Generate `local_identifier` for genuinely-new local files | Already used elsewhere in the same codebase for client-generated ids (`FrameApi.show_asset`'s `impression_id`, `S3Client.upload_file`'s S3 key) — same convention, not a new pattern. |

### Supporting
| Library | Purpose | When to Use |
|---------|---------|-------------|
| `botocore.stub.Stubber` (already vendored inside `botocore`, zero new install) [CITED: botocore stubber docs] | Offline unit testing of `S3Client`/`SQSClient` boto3 calls without hitting AWS | Only if the plan wants to stub at the boto3-client level; **see "Don't Hand-Roll" below for the simpler, codebase-consistent alternative** (constructor-inject the wrapper objects themselves). |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `AssetPartial` (via existing `make_partial`) for new-upload metadata | A hand-written dataclass/dict shaped like `batch_update`'s allowlist | `AssetPartial` reuses an already-tested factory and keeps `AssetApi.batch_update`'s `.dict(include={...})` call unchanged (still receives a `BaseModel`); a bespoke dataclass would require either widening `batch_update`'s type hint to `dict` or adding an adapter — more surface area for the same result. |
| `uuid.uuid4()` client-generated `local_identifier` | Deriving an identifier from the file's content hash (already computed for diffing) | The content hash is already used as the diff key in `sync.py`; reusing it as `local_identifier` too would conflate two different identity concepts (content identity vs. upload-session identity) and isn't how `local_identifier` is used anywhere else in the codebase (it always looks like a client/device-generated opaque id, e.g. `local-fake-001` in fixtures) — a fresh UUID is the safer, convention-matching choice. |

**Installation:** None — no `uv add` needed this phase.

**Version verification:**
```
uv run python -c "import boto3, botocore; print(boto3.__version__, botocore.__version__)"
# -> 1.43.36 1.43.36  [VERIFIED: local venv, 2026-07-07]
uv run python -c "import pydantic; print(pydantic.VERSION)"
# -> 2.13.x            [VERIFIED: local venv, 2026-07-07 — see PROJECT.md's pydantic v1→v2 migration note]
```

## Package Legitimacy Audit

**No new packages are introduced by this phase.** Every dependency `execute_plan()` needs (`boto3`, `botocore`, `pydantic`, `uuid`) is already installed and already used elsewhere in this codebase. The Package Legitimacy Gate protocol is not applicable — no `npm view`/`pip index`/registry check is needed since nothing new is being installed.

| Package | Registry | Disposition |
|---------|----------|-------------|
| (none) | — | No installs this phase |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
                     ┌─────────────────────────────────────────┐
                     │  aura-cli sync <dir> --frame <x> --apply │
                     │              [--yes]                    │
                     └───────────────────┬───────────────────--┘
                                         │
                          (CLI: cli.py, existing dry-run reused)
                                         ▼
             ┌────────────────────────────────────────────────┐
             │ 1. login()  2. resolve_frame()  3. scan_directory│
             │ 4. compute_plan()  -->  SyncPlan(upload, delete) │
             └───────────────────────┬────────────────────────┘
                                     │  print counts + full lists (SYNC-04, Phase 7 reuse)
                                     ▼
                        ┌─────────────────────────┐
                        │ --apply gate (NEW, D-01) │
                        │  TTY? --yes? confirm y/N │
                        │  (D-03 fail-closed)      │
                        └────────────┬────────────-┘
                                     │ confirmed
                                     ▼
                    ┌───────────────────────────────────┐
                    │ execute_plan(plan, aura, frame)    │  <- NEW, sync.py
                    │  (the only mutating entry point)   │
                    └───────────────┬────────────────────┘
                                    │
              ┌─────────────────────┼───────────────────────────┐
              │  UPLOADS FIRST (D-09)                 DELETES SECOND
              ▼                                                  ▼
  ┌─────────────────────────────┐                 ┌──────────────────────────┐
  │ for each to_upload Path:     │                 │ for each to_delete Asset: │
  │  try:                        │                 │  try:                    │
  │   local_identifier = uuid4() │                 │   remove_asset(          │
  │   select_asset(frame_id,     │                 │     frame_id,            │
  │     AssetPartialId(          │                 │     AssetPartialId(      │
  │      local_identifier=...))  │                 │       id=asset.id))      │
  │   filename, md5 =            │                 │  except -> record        │
  │     S3Client.upload_file(    │                 │     (asset.id, error)    │
  │       path.read_bytes(),     │                 │     continue (D-08)      │
  │       path.suffix)           │                 └──────────────────────────┘
  │   batch_update(AssetPartial( │
  │     local_identifier=...,    │
  │     file_name=filename,      │
  │     md5_hash=md5, height=,   │
  │     width=, taken_at=,       │
  │     data_uti=, selected=True,│
  │     upload_priority=0))      │
  │   (SQS poll: best-effort,    │
  │    not a blocking gate)      │
  │  except -> record            │
  │     (path, error)            │
  │     continue (D-08)          │
  └───────────────────────────────┘
              │
              ▼
   ┌───────────────────────────────────────┐
   │ Print separated summary (D-10):        │
   │  Uploads: N succeeded, M failed (named)│
   │  Deletes: N succeeded, M failed (named)│
   │ exit 1 if any failure, else 0 (WRITE-05)│
   └───────────────────────────────────────┘

   (SEPARATE, one-time, non-wired checkpoint — D-05/D-06/D-07)
   ┌─────────────────────────────────────────────────────┐
   │ checkpoint:human-verify — delete_asset probe          │
   │ upload a disposable test photo -> call delete_asset  │
   │ -> observe live effect -> document finding             │
   │ NOT reachable from execute_plan() / --apply             │
   └─────────────────────────────────────────────────────┘
```

### Recommended Project Structure
No new files/directories — extend existing modules:
```
auraframes/
├── sync.py         # add execute_plan(plan, aura, frame_id) alongside compute_plan()
├── cli.py          # sync subparser gains --apply/--yes; run_sync (or a sibling run_apply)
│                   #   gains the confirm-gate + calls execute_plan() when --apply is set
├── aura.py         # get_sqs(frame_id) parameterization fix (WRITE-04);
│                   #   upload_image() likely superseded by a narrower new-file upload path,
│                   #   not reused as-is (see Common Pitfalls)
├── api/frameApi.py # select_asset/remove_asset gain fail-loud error checks (WRITE-05)
├── api/assetApi.py # batch_update/delete_asset gain fail-loud error checks (WRITE-05);
│                   #   batch_update's type hint widens to accept AssetPartial
└── models/asset.py # AssetPartial = make_partial(Asset, 'AssetPartial') added,
                    #   mirroring models/frame.py's FramePartial = make_partial(Frame, ...)
```

### Pattern 1: Upload Identity via `AssetPartial`, Not `Asset`
**What:** Represent a genuinely-new local file's pending-upload metadata with `AssetPartial` (all-Optional variant of `Asset`), never with a directly-constructed `Asset`.
**When to use:** Any time `execute_plan()`'s upload path needs to build the object passed to `AssetApi.batch_update()` for a file that has no prior Aura `Asset` record.
**Why (verified, not assumed):** Constructing `Asset(id=None, ...)` raises a pydantic `ValidationError` today — `Asset.id` is typed `str`, not `Optional[str]`, even though `Asset.is_local_asset` (`auraframes/models/asset.py:108-110`) and `AssetApi.update_taken_at_date`/`delete_asset` (`auraframes/api/assetApi.py:66-69,82-86`) both assume a local-only asset can have `id=None`. This is a real, load-bearing model gap, not a style preference.
**Example:**
```python
# Source: verified directly against auraframes/models/{asset.py,meta.py}, pydantic 2.13 installed in this repo
from auraframes.models.meta import make_partial
from auraframes.models.asset import Asset

AssetPartial = make_partial(Asset, 'AssetPartial')  # mirrors FramePartial in models/frame.py

pending = AssetPartial(
    local_identifier=local_identifier,   # client-generated uuid4, ties select_asset -> S3 -> batch_update together
    file_name=filename,                  # returned by S3Client.upload_file()
    md5_hash=md5,                        # returned by S3Client.upload_file()
    height=image.height,
    width=image.width,
    taken_at=format_dt_to_aura(get_utc_now()),  # fabricated; no EXIF-read utility exists in this codebase today
    data_uti='public.jpeg',              # ASSUMED — matches existing (synthetic) test fixture convention only
    selected=True,
    upload_priority=0,
)
# .dict(include={...}) succeeds and yields exactly batch_update's expected payload shape (verified locally).
```

### Pattern 2: Per-Item Fail-Loud, Continue-Past-Failure Execution Loop (D-08, WRITE-05)
**What:** Each upload/delete is wrapped in its own try/except; a failure is recorded with the file/asset identity and the loop continues, matching the plan's "continue past a single item's failure" decision.
**When to use:** Inside `execute_plan()`'s upload and delete loops.
**Example:**
```python
# Source: pattern extension of run_status/run_inspect's existing broad-catch convention
# (auraframes/cli.py:97-103, 168-174) applied at per-item granularity, per D-08
upload_failures: list[tuple[Path, str]] = []
for path in sorted(plan.to_upload):
    try:
        _upload_one(aura, frame_id, path)
    except Exception as e:
        upload_failures.append((path, str(e)))
        continue
```

### Anti-Patterns to Avoid
- **Reusing `Aura.upload_image()` unmodified:** it requires a pre-hydrated `Asset` with `local_identifier` already set (line 106-112), which a genuinely-new local file doesn't have; it also calls `self.sqsClient` only after `self.get_sqs()` sets that attribute (no guard, `auraframes/aura.py:114-115`), and constructs a brand-new `S3Client()` inline every call (triggers a fresh Cognito auth every invocation — expensive in a loop).
- **Constructing a full `Asset` object with placeholder values for all 20+ required fields just to satisfy the type hint:** this both papers over the real `id=None` validation bug and produces a payload with meaningless placeholder data outside `batch_update`'s allowlist; use `AssetPartial` instead (Pattern 1).
- **Treating the SQS `receive_message` response as a pass/fail gate for upload success:** the existing code already discards the first poll's return value entirely (`auraframes/aura.py:115`) and only prints (never asserts on) the second (`auraframes/aura.py:127-128`); `.planning/codebase/INTEGRATIONS.md` explicitly notes "SQS polling behavior is not fully understood; the queue result may not be used meaningfully." Success should be confirmed via a subsequent read (matches WRITE-01 success criterion 1: "verified visually and via `inspect`"), not by parsing the SQS message.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| All-fields-optional variant of `Asset` for partial-update payloads | A new dataclass or manually-declared Optional-field pydantic model | `make_partial(Asset, 'AssetPartial')` (`auraframes/models/meta.py`, already used for `FramePartial`) | Zero new code, already tested, keeps `.dict(include={...})` compatibility with `AssetApi.batch_update()` unchanged. |
| Client-generated opaque upload-session identifier | A custom id scheme (counter, hash-derived, timestamp-based) | `str(uuid.uuid4())` (stdlib) | Already the exact convention used elsewhere in this codebase for client-generated ids (`FrameApi.show_asset`'s `impression_id`, `S3Client.upload_file`'s S3 key). |
| Offline testing of AWS SDK calls (S3 upload, SQS poll) without hitting AWS | A bespoke mock-AWS server, or adopting `moto` as a new test dependency | Constructor-inject already-instantiated `S3Client`/`SQSClient`-shaped fake objects (`unittest.mock.MagicMock` or a tiny local fake class with `.upload_file`/`.get_queue_url`/`.receive_message`), mirroring the existing `Client(transport=...)`/`Aura(client=...)` DI seam | `AWSClient.__init__` eagerly calls `self.auth(pool_id)` (a real Cognito network call) whenever `pool_id` is truthy — which it always is today (hardcoded pool-id defaults) — so constructing `S3Client()`/`SQSClient()` directly is not offline-testable without a DI seam. `botocore.stub.Stubber` is a heavier, more "correct-AWS-SDK-way" alternative that requires no new install either, but duck-typed fakes are simpler and match this codebase's existing, lightweight DI style (no other file in this project uses `Stubber`). |
| Non-interactive/CI detection for the confirm gate (D-03) | A custom "is this a script" heuristic (env var sniffing, etc.) | stdlib `sys.stdin.isatty()` | Standard, portable, zero-dependency way to detect a non-interactive stdin; combined with the existing `input()` builtin for the prompt itself. |

**Key insight:** Every "new" piece of Phase 8 is a thin recombination of primitives that already exist somewhere in this codebase (partial models, uuid ids, DI seams, fail-loud error checks). The actual net-new code is orchestration glue in `sync.py`/`cli.py`/`aura.py`, not new abstractions — resist inventing a new identity scheme, mocking framework, or validation layer.

## Common Pitfalls

### Pitfall 1: `Asset(id=None, ...)` cannot be constructed (verified)
**What goes wrong:** Any code path that tries to build a full `Asset` instance to represent a not-yet-uploaded local file will raise a pydantic `ValidationError` on the `id` field.
**Why it happens:** `Asset.id: str` is non-Optional in the current model, but `Asset.is_local_asset` and two `AssetApi` methods assume `id=None` is a valid, constructible state — a latent contradiction in the model, most likely a casualty of the pydantic v1→v2 migration (Phase 4) where a previously-lax/Optional field became strict.
**How to avoid:** Use `AssetPartial` (Pattern 1) for any new-upload metadata construction. Do not attempt to "fix" `Asset.id` to `Optional[str]` as part of this phase unless the plan explicitly scopes that model change — it's out of this phase's stated file-change list (`.planning/phases/08.../08-CONTEXT.md`'s "Files that will change" does not include `models/asset.py`'s `id` field, only adding `AssetPartial`).
**Warning signs:** A `pydantic.ValidationError` mentioning `id — Input should be a valid string` during upload-path development.

### Pitfall 2: `get_sqs()`/`SQSClient()`/`S3Client()` construction is not offline-testable as-is
**What goes wrong:** `AWSClient.__init__` (`auraframes/aws/awsclient.py:12-18`) calls `self.auth(pool_id)` unconditionally whenever `pool_id` is truthy, which triggers two live Cognito network calls (`get_id`, `get_credentials_for_identity`). `S3Client`/`SQSClient` both default `pool_id` to a hardcoded non-empty constant, so simply constructing either class — even in a unit test — hits the network.
**Why it happens:** No DI seam exists for the AWS layer (unlike `Client(transport=...)` for the REST API layer, added in v1.1).
**How to avoid:** Design `execute_plan()` to receive already-constructed S3/SQS client objects (or a small factory) as parameters rather than constructing them internally, so tests can substitute fakes. This is Claude's discretion per CONTEXT.md but is effectively required for any offline test coverage of the upload/delete path.
**Warning signs:** Tests for the upload/delete path hang or fail with network/credentials errors when run without `AURA_EMAIL`/`AURA_PASSWORD`/AWS reachability.

### Pitfall 3: Silent failure on write endpoints (WRITE-05's exact target)
**What goes wrong:** `FrameApi.select_asset`/`remove_asset`/`exclude_asset` return `json_response.get('number_failed')` with no check for the `error` field or a nonzero `number_failed` (`auraframes/api/frameApi.py:105-148`). `AssetApi.batch_update` returns `json_response.get('ids'), [...]` with no `error` check either (`auraframes/api/assetApi.py:19-41`) — if the API returns an error envelope instead of the expected shape, this will raise an unhelpful `TypeError`/`KeyError` (iterating `None`) rather than a clear, attributable error. `AssetApi.delete_asset` returns the raw, unchecked `json_response` (`auraframes/api/assetApi.py:74-88`).
**Why it happens:** These endpoints were never exercised live before Phase 8 (this milestone's entire premise), so the read-path-only fail-loud convention (`FrameApi.get_assets`, `auraframes/api/frameApi.py:50-56`) was never extended to them.
**How to avoid:** Extend the exact same `if json_response.get('error'): raise RuntimeError(...)` pattern to `select_asset`, `remove_asset`, `batch_update`, and `delete_asset`; additionally raise when `number_failed > 0` for `select_asset`/`remove_asset` (each call already carries exactly one `AssetPartialId`, per their own docstrings, so a nonzero `number_failed` unambiguously means *this* file/asset failed — a natural fit for per-file attribution, WRITE-05).
**Warning signs:** An upload/delete "succeeds" (no exception) but the frame's asset list doesn't reflect the change on a subsequent `inspect`.

### Pitfall 4: The existing upload sequence calls `select_asset` twice and discards the first SQS poll's result
**What goes wrong:** `Aura.upload_image()` (`auraframes/aura.py:106-128`) calls `self.frame_api.select_asset(...)` with the *identical* `AssetPartialId` twice (lines 113 and 116), with an SQS `receive_message` poll in between whose return value is never used. This could be (a) an accidental duplicate left over from experimentation, or (b) an intentional "register, wait, re-confirm" handshake the undocumented API actually expects.
**Why it happens:** This code has never been exercised live in the ~3-year history of this codebase (per PROJECT.md/STATE.md) — it's unverified, not just unused.
**How to avoid:** Do not "clean up" the duplicate call speculatively before a live checkpoint confirms which behavior is correct. The safest default is to preserve the double-call + both-polls shape for the first live attempt (least deviation from the only prior — if untested — implementation of this sequence), and only simplify if/when a live checkpoint shows one call suffices. Flag this explicitly as an open question for the plan's live-verification checkpoint (mirrors Phase 7's D-09 "confirm via real usage" methodology).
**Warning signs:** A live attempt fails or behaves unexpectedly when the duplicate call is removed prematurely.

### Pitfall 5: `data_uti`/`taken_at` values for new files are fabricated, not derived
**What goes wrong:** There is no existing utility in this codebase that extracts a "taken at" date or a UTI-style type string from an arbitrary local image file — `auraframes/exif.py` only *writes* EXIF into already-downloaded frame images, it never *reads* EXIF from a local upload candidate. Any value chosen for `taken_at`/`data_uti` on upload is a guess until the live checkpoint confirms the API accepts it.
**Why it happens:** The project's only recorded example of these field values (`tests/fixtures/assets_page1.json`: `data_uti: "public.jpeg"`) is explicitly **synthetic, author-written test data** (per PROJECT.md Key Decisions: "Fixture JSON authored entirely synthetic, not recorded from the live API"), not a captured real API response — so it cannot be treated as confirmation of what the live API expects or requires.
**How to avoid:** Use a reasonable default (`data_uti='public.jpeg'` for JPEG; current UTC time via the existing `format_dt_to_aura(get_utc_now())` helper for `taken_at`) and treat WRITE-01's live checkpoint as the moment this is actually confirmed — document the outcome (accepted as-is / API rejected it / API ignored it) the same way Phase 7's D-09 documented the hash-convention finding.
**Warning signs:** `batch_update` returns an `error` for a new upload, or the asset's `taken_at`/type renders incorrectly on the frame/app after upload.

## Code Examples

### WRITE-04 fix — `Aura.get_sqs()` parameterization
```python
# Source: auraframes/aura.py:130-134 (current, hardcoded)
def get_sqs(self):
    self.sqsClient = SQSClient()
    # TODO: Is this a hardcoded queue URL?
    queueUrl = self.sqsClient.get_queue_url('4ab446b4-33a7-4a76-881d-d545d153ab5a')
    return queueUrl

# Minimal fix (D-11) — SQSClient.get_queue_url already accepts frame_id;
# get_sqs() just needs to stop hardcoding the argument it passes in.
def get_sqs(self, frame_id: str):
    self.sqsClient = SQSClient()
    return self.sqsClient.get_queue_url(frame_id)

# One call site to update — upload_image already has frame_id in scope:
# auraframes/aura.py:114 -> queue_url = self.get_sqs(frame_id)
```

### WRITE-05 fix — extending the fail-loud convention to write endpoints
```python
# Source: existing convention, auraframes/api/frameApi.py:50-56 (get_assets, Phase 7 D-06)
if json_response.get('error'):
    raise RuntimeError(
        f"get_assets failed for frame {frame_id}: "
        f"{json_response.get('message') or json_response.get('error')}"
    )

# Apply the same shape to select_asset/remove_asset (auraframes/api/frameApi.py:105-148),
# additionally raising on a nonzero number_failed since each call carries exactly one
# AssetPartialId (docstring: "Typical use of this endpoint results in a single
# AssetPartialId being sent per call"):
def select_asset(self, frame_id: str, asset_partial_id: AssetPartialId) -> int:
    json_response = self._client.post(f'/frames/{frame_id}/select_asset.json',
                                      data={'assets': [asset_partial_id.to_request_format()]})
    if json_response.get('error'):
        raise RuntimeError(f"select_asset failed for frame {frame_id}: {json_response.get('error')}")
    number_failed = json_response.get('number_failed')
    if number_failed:
        raise RuntimeError(f"select_asset reported {number_failed} failure(s) for frame {frame_id}")
    return number_failed
```

### Upload identity construction for a genuinely-new local file
```python
# Source: verified directly against this repo's models (pydantic 2.13 installed)
import uuid
from PIL import Image
from auraframes.aws.s3client import S3Client
from auraframes.models.asset import Asset, AssetPartialId
from auraframes.models.meta import make_partial
from auraframes.utils.dt import format_dt_to_aura, get_utc_now

AssetPartial = make_partial(Asset, 'AssetPartial')

def _upload_one(aura, frame_id: str, path):
    local_identifier = str(uuid.uuid4())
    image = Image.open(path)  # matches upload_image()'s existing width/height read

    aura.frame_api.select_asset(frame_id, AssetPartialId(local_identifier=local_identifier))
    # (SQS poll here is best-effort/observational, per Pitfall 4 -- do not gate on it)

    s3 = S3Client()  # see Pitfall 2 for offline-testability implications
    filename, md5 = s3.upload_file(path.read_bytes(), path.suffix)

    pending = AssetPartial(
        local_identifier=local_identifier,
        file_name=filename,
        md5_hash=md5,
        height=image.height,
        width=image.width,
        taken_at=format_dt_to_aura(get_utc_now()),  # fabricated -- see Pitfall 5
        data_uti='public.jpeg',                     # ASSUMED -- see Pitfall 5
        selected=True,
        upload_priority=0,
    )
    aura.asset_api.batch_update(pending)  # batch_update's type hint must widen to accept AssetPartial
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| pydantic v1 `BaseModel`/`@validator`/`AllOptional` metaclass | pydantic v2 `BaseModel`/`@field_validator`/`make_partial()` factory | Phase 4 (v1.1), per PROJECT.md Key Decisions | Already fully migrated; this phase's `AssetPartial` slots directly into the existing `make_partial()` pattern, no new migration work. |
| `.dict(include={...})` | `.model_dump(include={...})` | pydantic 2.0 (`.dict()` deprecated, not yet removed) [VERIFIED: local venv deprecation warning] | Every existing call site (`frameApi.py`, `assetApi.py`) still uses `.dict()` and emits a `PydanticDeprecatedSince20` warning; not yet broken. Claude's discretion whether new Phase 8 code matches existing `.dict()` calls for consistency or uses `.model_dump()` to avoid new warnings — either is fine, but don't silently mix conventions within the same new function. |

**Deprecated/outdated:** None specific to this phase beyond the `.dict()` note above (pre-existing, project-wide, not newly introduced).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `data_uti='public.jpeg'` is an accepted value for a new JPEG upload | Upload identity construction / Pitfall 5 | API may reject or silently ignore the field; only discoverable via the WRITE-01 live checkpoint. Low risk since `batch_update`'s docstring says it only affects subsequent-read metadata, not the frame display itself. |
| A2 | A fabricated `taken_at` (current UTC time) is acceptable for new uploads with no real EXIF-read path in this codebase | Upload identity construction / Pitfall 5 | Photo may display with a wrong "date taken" on the frame/app; cosmetic, not a data-loss risk. Live checkpoint should confirm. |
| A3 | The double `select_asset` call + first discarded SQS poll in `Aura.upload_image()` is either dead/duplicate code or an intentional handshake — undetermined from static reading | Pitfall 4 | If it's actually required and removed prematurely, the live upload attempt may fail in a way that's hard to diagnose (undocumented API). Recommendation: preserve the sequence for the first live attempt. |
| A4 | `Frame.client_queue_url` (a field already present on the hydrated `Frame` model, `auraframes/models/frame.py`) might be a per-frame SQS queue URL usable as an alternative to `SQSClient.get_queue_url(frame_id)`'s naming-convention lookup | SQS Queue Fix / Open Questions | Not acted on — D-11 already locked the minimal parameterization fix using the existing `SQSClient.get_queue_url` call; this is noted only as a discovered field worth a future look, not a reason to deviate from the locked decision. |

**If this table is empty:** N/A — see rows above; all four are genuine unknowns that only a live checkpoint (in-scope for this phase's execution, not for research) can resolve.

## Open Questions

1. **Is the double `select_asset` call in `Aura.upload_image()` intentional?**
   - What we know: The exact same `AssetPartialId` is passed to `select_asset` twice (lines 113, 116), with an SQS poll in between whose result is discarded.
   - What's unclear: Whether the live API's upload flow actually requires a "register → wait for ack → re-confirm" two-step handshake, or this is leftover/duplicate code that has simply never been exercised to reveal the bug.
   - Recommendation: Preserve the sequence unchanged for the first live attempt (matches this phase's overall "confirm before changing" methodology, D-05/D-09 precedent); only collapse to a single call if the live checkpoint shows the second call/poll has no observable effect.

2. **Does `delete_asset` reach S3/Glacier, or only the frame association (same effect as `remove_asset`)?**
   - What we know: The docstring itself says "Currently unknown if this is used... maybe this deletes it from S3/Glacier."
   - What's unclear: Everything about its actual blast radius — this is precisely why D-05/D-06/D-07 require a disposable-asset live probe before any documentation claim is made.
   - Recommendation: This is the plan's `checkpoint:human-verify` task (WRITE-03), not resolvable here; if the probe reveals broader-than-documented destruction, D-07 requires stopping and reporting immediately rather than proceeding.

3. **What does the SQS message actually confirm, if anything?**
   - What we know: `.planning/codebase/INTEGRATIONS.md` already flags "SQS polling behavior is not fully understood; the queue result may not be used meaningfully," and the existing code never inspects the poll's contents.
   - What's unclear: Whether the plan should attempt to parse/assert on the message at all, or treat SQS purely as an observational side-channel this phase.
   - Recommendation: Treat as best-effort/observational only; rely on a subsequent read (`inspect`/`get_all_assets`) as the actual proof of upload success, matching WRITE-01's stated success criterion ("verified visually and via `inspect`").

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.14 | Runtime | ✓ | 3.14.4 [VERIFIED: local] | — |
| `uv` | Env/dependency management | ✓ | 0.11.7 [VERIFIED: local] | — |
| `boto3`/`botocore` | S3 upload, SQS queue lookup/poll | ✓ | 1.43.36 [VERIFIED: local venv] | — |
| `pydantic` | `AssetPartial`, all models | ✓ | 2.13 [VERIFIED: local venv] | — |
| DNS reachability to `api.pushd.com` | Aura REST API | ✓ (resolves) [VERIFIED: local DNS lookup] | — | — |
| DNS reachability to `cognito-identity.us-east-1.amazonaws.com` | AWS Cognito auth (S3/SQS) | ✓ (resolves) [VERIFIED: local DNS lookup] | — | — |
| `AURA_EMAIL`/`AURA_PASSWORD` (live credentials) | Live checkpoints (WRITE-01/02/03) | Likely ✓ — a local `.env` file exists in the repo root (existence-only check, contents not read) | — | If absent at execution time, the live-verification checkpoints cannot proceed and must block per their `checkpoint:human-verify` gate. |

**Missing dependencies with no fallback:** None identified from static/DNS checks. Actual live-credential validity and AWS Cognito pool health can only be confirmed at execution time (this phase's own checkpoint tasks), not from research.

**Missing dependencies with fallback:** None.

## Security Domain

`security_enforcement` is enabled (`.planning/config.json`, `security_asvs_level: 1`). This is the first phase in the project with genuine write/destructive capability — the security posture shifts substantially from every prior (read-only) phase.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V1 Architecture | yes | Structural dry-run/execute separation (no `if apply:` flag branching a shared function) — already the locked pattern from Phase 7, extended here; `execute_plan()` is the only function permitted to call a mutating primitive. |
| V2 Authentication | no (unchanged) | Reuses the already-live-verified `Aura.login()` token flow; no new auth surface. |
| V4 Access Control | no | Single-user tool acting with the authenticated account's own permissions; no multi-tenant concern. |
| V5 Input Validation | yes | `--frame` resolution (reused from Phase 6, D-01–D-04) plus the new `--apply`/`--yes` flag combination and non-TTY detection (D-03) are the only new CLI input surface. |
| V6 Cryptography | no | No new crypto; AWS Cognito/S3/SQS auth reuses existing `AWSClient`/boto3 flow unchanged. |
| V7 Error Handling & Logging | yes | WRITE-05's fail-loud extension is squarely a V7 concern: errors must be raised (not silently swallowed) and attributable per-file, without leaking secrets into logs. `Client._redact()` (`auraframes/client.py:18-32`) already masks `password`/`auth_token`/`x-token-auth` on every `post`/`put`/`delete` call, including the new write endpoints exercised this phase — no new redaction work needed, just confirm it still applies (it does, since redaction is generic at the `Client` layer, not endpoint-specific). |
| V9 Communications | no | HTTPS/HTTP2 via `httpx.Client(http2=True, ...)` already in place; AWS SDK calls use TLS by default via boto3. No change. |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Wrong-frame destructive action from `--frame`'s substring-match resolution landing on an unintended frame | Tampering | D-04's redundant frame name+id echo in the confirmation prompt, on top of Phase 6's existing ambiguous/not-found guards. |
| Mass-delete from a misconfigured or empty local directory (no `--max-delete` circuit breaker this phase, SYNC-05 deferred to v2) | Tampering / Denial of Service | Residual, accepted risk this phase: the full untruncated plan listing (Phase 7 D-07) is shown before the y/N gate, giving the user one last look at every delete candidate; document as an accepted risk in `08-SECURITY.md`, not silently ignored. |
| `delete_asset`'s unknown/possibly-broader-than-documented deletion scope (S3/Glacier reach) | Tampering / Repudiation | D-05/D-06/D-07: probed only against a disposable asset, structurally unreachable from any executable path this phase (not even behind a hidden flag). |
| Unattended non-interactive run silently proceeding on an irreversible first-ever live write path | Elevation of Privilege / Tampering | D-03: fail-closed when `--apply` runs with no TTY and no `--yes` — explicit error + non-zero exit, never a hang or silent proceed. |
| Partial-failure batch leaving the user unaware some uploads/deletes silently failed | Repudiation | WRITE-05 + D-08/D-10: every per-file failure is caught, named, and surfaced in a separate end-of-run summary section; process exits non-zero on any failure. |
| Secret leakage (AWS Cognito temp credentials, Aura auth token) into logs/error messages during new write-path exercising | Information Disclosure | `Client._redact()` already covers the Aura REST layer generically for any new POST/PUT body; AWS Cognito credentials (`AccessKeyId`/`SecretKey`/`SessionToken`) are held in-memory only in `AWSClient.credentials` and never logged today — confirm no new logging statement in `execute_plan()` prints these. |

## Sources

### Primary (HIGH confidence — direct codebase reads and executed verification)
- `auraframes/aura.py` — `Aura.upload_image`, `Aura.get_sqs`, `Aura._init_logger` (full read)
- `auraframes/api/frameApi.py` — `select_asset`, `remove_asset`, `exclude_asset`, `get_assets` (fail-loud precedent) (full read)
- `auraframes/api/assetApi.py` — `batch_update`, `delete_asset`, `update_taken_at_date`, `get_asset_by_local_identifier` (full read)
- `auraframes/aws/s3client.py`, `auraframes/aws/sqsclient.py`, `auraframes/aws/awsclient.py` (full read)
- `auraframes/models/asset.py`, `auraframes/models/meta.py`, `auraframes/models/frame.py` (full read)
- `auraframes/sync.py`, `auraframes/cli.py`, `auraframes/client.py` (full read)
- `tests/offline.py`, `tests/conftest.py`, `tests/test_cli_sync.py`, `tests/fixtures/assets_page1.json` (full read)
- Direct execution against the installed stack: `Asset(id=None, ...)` raises `ValidationError` (pydantic 2.13); `make_partial(Asset, 'AssetPartial')` constructs and serializes successfully; `boto3`/`botocore` 1.43.36 and `pydantic` 2.13 confirmed installed; `botocore.stub` importable with zero new install; DNS resolution confirmed for `api.pushd.com` and `cognito-identity.us-east-1.amazonaws.com`.
- `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/INTEGRATIONS.md`, `.planning/PROJECT.md`, `.planning/STATE.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/phases/07-.../07-03-PLAN.md`, `07-PATTERNS.md`, `07-SECURITY.md` (full reads)

### Secondary (MEDIUM confidence)
- [Stubber Reference — botocore documentation](https://botocore.amazonaws.com/v1/documentation/api/latest/reference/stubber.html) — confirms `botocore.stub.Stubber` API shape (`add_response`, context-manager activation); used only to document an alternative offline-testing approach, not adopted as the primary recommendation.

### Tertiary (LOW confidence)
- `data_uti='public.jpeg'` convention — sourced only from this project's own synthetic test fixture (explicitly documented as author-written, not a live capture, per PROJECT.md Key Decisions) — tagged `[ASSUMED]` throughout, not treated as confirmed API behavior.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new libraries, all versions directly verified against the installed venv.
- Architecture/upload-identity construction: HIGH for what's verifiable statically (the `Asset(id=None)` failure and `AssetPartial` fix were directly executed and confirmed); MEDIUM overall because the live round-trip's actual success/failure modes remain genuinely unverified until execution.
- Pitfalls: HIGH — all five are grounded in specific, cited line numbers or directly-reproduced errors, not speculation.
- `delete_asset`/double-`select_asset`/SQS-message-meaning: explicitly LOW/unknown — flagged as Open Questions and Assumptions requiring this phase's own live checkpoints, not resolvable from research.

**Research date:** 2026-07-07
**Valid until:** 2026-07-14 (7 days — this phase's core value is proving a previously-never-exercised live write path against an undocumented, drift-prone third-party API; any finding here that depends on live behavior is provisional until the phase's own execution-time checkpoints confirm it).
