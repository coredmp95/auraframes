---
phase: 11-write-path-reliability-format-support
reviewed: 2026-09-03T00:00:00Z
depth: standard
files_reviewed: 22
files_reviewed_list:
  - auraframes/client.py
  - auraframes/sync.py
  - auraframes/cli.py
  - auraframes/aura.py
  - auraframes/reconcile.py
  - auraframes/api/assetApi.py
  - auraframes/models/asset.py
  - tests/offline.py
  - tests/test_retry_401.py
  - tests/test_batch_update_contract.py
  - tests/test_asset_partial.py
  - tests/test_read_path.py
  - tests/test_reconcile.py
  - tests/test_cli_reconcile.py
  - tests/test_prep_upload_formats.py
  - tests/test_write_endpoints_failloud.py
  - tests/test_write_formats_live.py
  - tests/test_write_throttling.py
  - tests/test_execute_plan.py
  - tests/test_execute_plan_budget_geo.py
  - tests/fixtures/assets_placeholders.json
  - pyproject.toml
findings:
  critical: 1
  warning: 4
  info: 1
  total: 6
status: issues_found
---

# Phase 11: Code Review Report

**Reviewed:** 2026-09-03
**Depth:** standard
**Files Reviewed:** 22
**Status:** issues_found

## Summary

The core mechanisms this phase set out to build are sound and well-tested for the
paths the test suite actually exercises: the `AuraError` hierarchy, the batch
`select_asset`/`batch_update`/`remove_asset` 401 verify-then-retry loop for
**uploads and reshow/hide/delete**, the `BatchUpdateResult.unacknowledged` contract,
the tolerant-inbound/strict-outbound `successes` parsing (with the pydantic v2
`include_input=False` fix genuinely closing the `user_id`-in-`ValidationError`
leak it targets), and the three-way-null placeholder predicate in
`reconcile.py` (which really is structurally unreachable from anything but the
strict conjunction — confirmed by direct inspection, not just the test that
greps for it).

The most substantive gap is in a corner the retry work extended without
adjusting its own reasoning: the `removal_mode='hard_delete'` /
`mechanism='hard-delete'` primitives are per-asset sequential HTTP calls (no
batch form), but `execute_plan`'s 401 retry — and `reconcile.py`'s chunk
failure handling — both apply the same "a batch endpoint's resend can't
double-send because it's idempotent" reasoning to them. That reasoning is
correct for `hide`/`delete`/`remove` (true batch endpoints) and false for
`hard_delete`/`hard-delete`, whose partial-completion state inside one chunk is
invisible to the accounting. This is the exact "can a retry double-send an
item that actually landed" question the phase brief asked me to trace, applied
to the destructive removal path rather than the upload path where the retry
logic was actually designed and tested.

A second, unrelated finding: `client.py`'s `_REDACT_KEYS` (pre-existing, not
touched this phase) still does not cover `user_id`/`email`, so the account's
email address and user id are written in cleartext to the on-disk debug log on
every HTTP response — directly adjacent to, but not covered by, this phase's
own `include_input=False` fix for the same class of leak in
`assetApi.py`.

## Critical Issues

### CR-01: `execute_plan`'s 401 retry can misreport (and re-attempt) an already-completed `hard_delete`

**File:** `auraframes/sync.py:1009-1103` (removal loop), primitive table at `auraframes/sync.py:408-415`

**Issue:** `_REMOVAL_PRIMITIVE['hard_delete']` (line 413-414) is a Python list
comprehension issuing one `delete_asset` HTTP call per asset in the chunk —
there is no batch form, unlike `'hide'`/`'delete'` (single `exclude_asset`/
`remove_asset` call per chunk). If item *k* of a hard-delete chunk returns
HTTP 401 (exactly the anti-abuse-trip shape this phase's whole retry feature
exists to handle — the project's own incident report describes a run of
successes followed by a run of 401s), items `1..k-1` have already been
irreversibly deleted, but the list comprehension aborts and **none of that
partial success is recorded** — the `for asset in chunk: result.delete_succeeded
+= 1` loop at line 1024-1027 never runs for this chunk.

The `httpx.HTTPStatusError` handler at line 1028 then applies the exact same
retry reasoning used for `'hide'`/`'delete'` (comment at 1029-1033: "hiding/
removing an already-hidden/removed asset is a no-op ... no verify probe
needed") and, after a successful re-login, **re-invokes
`_REMOVAL_PRIMITIVE[removal_mode](aura, frame_id, chunk)` on the entire
original chunk again** (line 1068), including the assets from `1..k-1` that
were already destroyed on attempt 1. `delete_asset` calling on an
already-gone asset id is unverified behavior (the module's own docs elsewhere
note `delete_asset`'s effects are not fully understood). If the resend also
fails partway, `except Exception as resend_exc` (1075-1081) attributes **every
asset in the chunk** as failed via `result.delete_failures`/`note_failure`,
including assets that were genuinely, irreversibly deleted on the first
attempt.

The "no verify probe needed because a resend is a no-op" rationale that
justifies skipping `_probe_landed`-style verification for the reshow/hide/
delete loops (a true no-op for those, since they are single idempotent batch
calls) does not hold for `hard_delete`'s per-asset sequential primitive, and
nothing in the retry code special-cases it. This is untested: no test in
`tests/test_retry_401.py` or `tests/test_execute_plan.py` exercises a 401
mid-way through a `hard_delete` chunk.

**Fix:** Either (a) exclude `hard_delete` from `retry_on_auth_401`'s
resend path entirely (treat a 401 on a hard_delete chunk as a hard stop,
mirroring `AuthenticationError`'s "never retried" philosophy, since there is
no safe way to resend it blindly), or (b) make `_REMOVAL_PRIMITIVE['hard_delete']`
itself return per-item success/failure (catch each `delete_asset` call
individually instead of a list comprehension that aborts on first exception)
so a retry can resend only the assets that didn't yet succeed — the same
`_probe_landed`-before-resend discipline the upload loop already uses:

```python
def _hard_delete_all(aura, frame_id, chunk):
    succeeded, failed = [], []
    for asset in chunk:
        try:
            aura.asset_api.delete_asset(asset)
            succeeded.append(asset)
        except Exception as e:
            failed.append((asset, e))
    if failed:
        # propagate only the unresolved subset for the caller to attribute/retry
        raise PartialHardDeleteFailure(succeeded, failed)
```

## Warnings

### WR-01: `reconcile.py`'s `apply_reconciliation` has the same hard-delete partial-attribution gap, without even a retry

**File:** `auraframes/reconcile.py:357-382`, mechanism table at `auraframes/reconcile.py:273-292`

**Issue:** `_RECONCILE_PRIMITIVE['hard-delete']` (line 276-277) is the same
per-asset list-comprehension shape as `sync.py`'s. `apply_reconciliation` has
no retry, but the same root problem exists without one: if `delete_asset`
raises on the 3rd asset of a 5-asset chunk, `except Exception as e` (372-379)
attributes **all 5** as `result.failed`, even though assets 1-2 were already
irreversibly hard-deleted before the exception. A caller reading
`result.failed` has no way to know 2 of those "failures" actually succeeded.

**Fix:** For `'hard-delete'`, iterate per-asset inside the chunk loop (catching
each `delete_asset` call individually) instead of delegating to
`_RECONCILE_PRIMITIVE[mechanism](aura, frame_id, chunk)` as an atomic unit —
mirrors the fix suggested for CR-01.

### WR-02: `client.py`'s log redaction does not cover `user_id`/`email` — both are written to the on-disk debug log in cleartext

**File:** `auraframes/client.py:14` (`_REDACT_KEYS`), leak sites at `auraframes/client.py:180,193,206,219`

**Issue:** `_REDACT_KEYS = {'password', 'auth_token', 'x-token-auth'}` (line
14) is the complete allowlist `_redact()` masks. Every `Client.get/post/put/
delete` call logs the full (redacted) response body at DEBUG level
(`logger.debug(f'Response ({response.status_code}), body: {_redact(response.json())}')`
at lines 180/193/206/219). The login response (`tests/fixtures/login.json`)
and every asset/frame payload embed the account's plaintext `email` and `id`
(the `user_id`) inside a `user`/`current_user` sub-object — neither key is in
`_REDACT_KEYS`, so both are written unredacted to `logs/file_{time}.log`.
This sink is added unconditionally by both `Aura._init_logger()` (line
`logger.add('logs/file_{time}.log')`, no level filter — captures DEBUG) and
`cli.py`'s `_configure_cli_logging()` (`logger.add('logs/file_{time}.log')`,
again no level filter), so this happens on every CLI invocation, `--debug` or
not — this is not a debug-opt-in leak.

This is directly adjacent to this phase's own fix in `assetApi.py`
(`e.errors(include_url=False, include_input=False)`, T-11-06) for the exact
same class of "`user_id` leaks into a log line" issue, and the phase brief
explicitly asked to check for other instances of it. This one is pre-existing
(introduced in an earlier phase, commit `2a2314e`) and untouched by Phase 11,
but it is a live, provable gap in the same security property this phase
otherwise hardened.

**Fix:** Add `user_id`, `id` (or, more robustly, switch to an allowlist of
loggable keys rather than a denylist of redacted ones) to `_REDACT_KEYS`, or
redact the `user`/`current_user` sub-object wholesale in login/asset
responses before logging.

### WR-03: `_prep_upload` decodes the image format from one read of the file and uploads bytes from a second, later read of the same path

**File:** `auraframes/sync.py:435-466` (specifically lines 448 and 454)

**Issue:** D-11's stated guarantee is "the bytes decide [`data_uti`], not the
name" — motivated by preventing a mislabeled file from being mistyped
server-side. `_prep_upload` derives `data_uti` from `Image.open(path)` (line
448) inside a `with` block that closes before `s3_client.upload_file(path.read_bytes(), ...)`
(line 454) re-reads the same path from disk. Nothing guarantees the file's
bytes are unchanged between these two independent reads — a directory being
synced while still being edited/replaced by another process (plausible for
this tool's own use case: syncing a live local photo directory) could decode
format `X` from the first read and upload bytes of format `Y` from the
second, silently defeating the exact guarantee D-11 was built to provide.

**Fix:** Read the file once (`data = path.read_bytes()`), decode via
`Image.open(io.BytesIO(data))` for `width`/`height`/`format`, and upload
`data` itself — guaranteeing the decoded format and the uploaded bytes are
the same bytes.

### WR-04: `--include-unknown-age`'s help text understates that it disables the age guard for every placeholder row, not just some

**File:** `auraframes/cli.py:136-140` (flag help), `auraframes/reconcile.py:127-163` (`find_placeholders` docstring, which is accurate)

**Issue:** The flag's help text reads: "treat placeholder rows whose creation
time this API never sends (unknown_age) as eligible for removal too, **not
just rows old enough per --max-age-hours**" — phrased as if some rows still
get the `--max-age-hours` protection and this flag only adds a few more.
`reconcile.py`'s own docstring (127-141) states the actual, confirmed-live
fact plainly: `/frames/{id}/assets.json` **never** sends `created_at` for any
asset, so *every* row matching the three-way-null placeholder predicate has
an unresolvable creation time. With `--include-unknown-age` set, the age
guard (`RECONCILE_AGE_THRESHOLD_SECONDS`/`--max-age-hours`) is not narrowed —
it is completely inert for every candidate, including an upload that started
seconds ago and is still mid-processing. The three-way-null predicate itself
is untouched (correctly, per the module's own structural test), but the
*age* safety net this flag partially bypasses is fully bypassed in practice,
and the CLI help text reads as a partial effect.

**Fix:** Reword the `--include-unknown-age` help text (and/or add a stronger
warning to the interactive confirmation prompt in `run_reconcile` when this
flag is set) to state plainly that, given the live API's behavior, this flag
removes the age-based safety net entirely rather than "also" catching a few
more rows.

## Info

### IN-01: `reconcile --mechanism complete` burns real write-budget tokens before unconditionally raising `NotImplementedError`

**File:** `auraframes/reconcile.py:233-257` (`_complete_placeholder`), `auraframes/reconcile.py:288-292` (`_RECONCILE_REQUEST_COST['complete']`), call site `auraframes/reconcile.py:358-363`

**Issue:** `apply_reconciliation` calls `budget.acquire(_RECONCILE_REQUEST_COST[mechanism](chunk), ...)`
(line 358-360) *before* invoking `_RECONCILE_PRIMITIVE[mechanism](...)` (line
363). For `mechanism='complete'`, the primitive is `_complete_placeholder`,
which unconditionally raises `NotImplementedError` — so every
`reconcile --mechanism complete` invocation acquires (consumes) real
write-budget tokens for a call that is guaranteed to do nothing. The CLI help
text does note `'complete'` is "not yet implemented", which mitigates
surprise, but the budget cost is still spent for no effect.

**Fix:** Either skip the `budget.acquire()` call for `mechanism == 'complete'`,
or raise `NotImplementedError` from `run_reconcile`/`build_parser` before any
budget or network setup happens for that mechanism choice.

---

_Reviewed: 2026-09-03_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
