# Phase 6: Inspect + Frame Resolution - Research

**Researched:** 2026-07-06
**Domain:** CLI implementation over an already-live-verified read-path Python client (frame resolution logic, photo/metadata display, argparse wiring, offline test harness extension)
**Confidence:** HIGH (all core findings are direct reads of this repo's own source — no external library research was needed; this phase adds zero new dependencies)

## Summary

Phase 6 is pure application logic on top of code that already exists and is already
live-verified (`FrameApi.get_frames`, `FrameApi.get_frame`, `Aura.get_all_assets`). There
is no new library to select, no new package to vet, and no new external API surface to
learn — the entire research burden is grounding CONTEXT.md's D-01 through D-13 decisions
in the exact current signatures, field names, types, and nullability so the planner can
write unambiguous tasks.

Three implementation-level facts are not fully captured in CONTEXT.md and matter for
planning: (1) `Frame.contributors` is `Optional[list[User]] = None` — not a guaranteed
list, so D-10's "count plus each contributor" formatting needs an explicit `or []`
guard, not a bare `len(frame.contributors)`; (2) the offline test harness
(`tests/offline.py`) currently has **no route** for `GET /frames/{id}.json`
(`FrameApi.get_frame`) — only `login.json`, `frames.json`, and `*/assets.json` are
routed — so Wave 0 of this phase's plan must add that route plus new fixtures before any
offline `inspect` test can run; (3) the resolution flow is a **two-call** design:
`get_frames()` is reused for name/id resolution (matching D-04's explicit reuse), then a
**second**, distinct `get_frame(resolved_id)` call is made to fetch the metadata-display
Frame + its drift-corrected asset count — the two calls are not redundant, they serve
different purposes (candidate-set building vs. canonical single-frame fetch).

**Primary recommendation:** Implement frame resolution as a small pure function operating
over the `list[Frame]` already returned by `frame_api.get_frames()` (no new API call for
resolution itself); after resolving to one `frame_id`, call `frame_api.get_frame(frame_id)`
for metadata display and `aura.get_all_assets(frame_id)` for the photo list — mirroring
`Aura.dump_frame()`'s existing call sequence at `auraframes/aura.py:70-84`.

## Architectural Responsibility Map

This is a single-process synchronous CLI, not a multi-tier web app — "tiers" here map to
this codebase's own layers (`STRUCTURE.md`/`ARCHITECTURE.md`).

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Frame name/ID resolution logic | CLI layer (`auraframes/cli.py`, new helper) | — | Net-new business logic with no API equivalent (D-02/D-03/D-04); CONTEXT.md's "Claude's Discretion" allows a `cli.py`-local function or a new `frame_resolver.py` — neither belongs in `FrameApi` (no HTTP call involved) |
| Frame listing (candidate set + not-found hint) | `FrameApi.get_frames()` | Facade (`Aura`) | Existing, already used by `status`; reused as-is, zero changes |
| Frame metadata fetch (owner/contributors/asset count) | `FrameApi.get_frame()` | Facade (`Aura`) | Existing, unused until now; first new call site since Phase 2 |
| Photo listing + pagination | `Aura.get_all_assets()` | `FrameApi.get_assets()` | Existing, already used by `dump_frame`; `inspect` is a second caller |
| Output formatting (terminal text) | CLI layer (`run_inspect()`) | — | Follows `run_status()`'s precedent — no separate presentation module exists or is needed at this scale |
| `--debug` / logging config | CLI layer (`main()`, `_configure_cli_logging()`) | — | Root-level per the folded todo; a cross-cutting concern, not owned by any subcommand |
| Live `md5_hash` spike | CLI layer (manual UAT observation) | `Asset` model (`md5_hash` field, already typed) | No code changes needed — the model already has the field; the "work" is a live read + a documentation update (D-12/D-13) |

## Standard Stack

No new libraries are introduced in this phase. `pyproject.toml` [VERIFIED: local source read, `/home/fabrice/dev/auraframes/pyproject.toml`] already pins everything needed:

| Library | Version (pinned) | Purpose | Why it's already sufficient |
|---------|---------|---------|--------------|
| `argparse` (stdlib) | 3.14 stdlib | CLI subcommand parsing | Already used for `status`; `inspect` is a second subparser, same pattern |
| `pydantic` | `>=2` | `Frame`/`Asset`/`User` model hydration | Already hydrates all fields `inspect` needs; no schema changes required |
| `httpx` | `>=0.27` (`[http2]`) | HTTP transport | Already wraps `get_frame`/`get_assets`; no new endpoint types |
| `loguru` | `>=0.7` | Logging | Already wired via `_configure_cli_logging()`; `inspect` reuses it unchanged once `--debug` is promoted to root |
| `pytest` | `>=8` (dev) | Test runner | Already the project's only test framework (`tests/`) |

### Alternatives Considered
None — this phase deliberately reuses existing infrastructure per CONTEXT.md's Deferred Ideas and CLAUDE.md's "pragmatic modernization" constraint. No alternative library evaluation applies.

**Installation:** None required — no new dependencies.

## Package Legitimacy Audit

**Not applicable.** This phase adds zero new packages (confirmed against `pyproject.toml`'s dependency list — no additions needed for argparse subcommand wiring, frame-resolution logic, or terminal output formatting, all of which are stdlib + already-installed deps). The Package Legitimacy Gate is skipped per its own trigger condition ("whenever this phase installs external packages").

## Architecture Patterns

### System Architecture Diagram

```
User (terminal)
   │  aura-cli --debug inspect --frame <name-or-id>
   ▼
main() [cli.py]                    ── parses --debug (root, folded todo) + inspect subcommand
   │
   ▼
_configure_cli_logging(debug)      ── same helper Phase 5 built; called once, before any subcommand runs
   │
   ▼
run_inspect(frame_arg, aura=None, debug=False) -> int   [cli.py, new]
   │
   ├─▶ aura = aura or Aura(); aura.login()          ── same fail-loud pattern as run_status (D-05)
   │
   ├─▶ frames = aura.frame_api.get_frames()          ── EXISTING call, reused (D-04)
   │        │
   │        ▼
   │   resolve_frame(frame_arg, frames) -> Frame | AMBIGUOUS | NOT_FOUND   [new pure function]
   │        │  D-01 case-insensitive substring on Frame.name
   │        │  D-02 zero name matches -> exact match on Frame.id
   │        │  D-03 >1 name match -> ambiguous error (list name+id pairs)
   │        │  D-04 no match at all -> not-found error (list available names)
   │        ▼
   ├─▶ frame, total_asset_count = aura.frame_api.get_frame(resolved.id)   ── EXISTING call, NEW call site
   │        │  (Phase 2 drift-fix already prefers num_assets internally)
   │        ▼
   │   print name / user.name+email / len(contributors or []) / total_asset_count
   │
   └─▶ assets = aura.get_all_assets(resolved.id)     ── EXISTING call, reused from dump_frame's pattern
            │  (handles cursor pagination internally, single call)
            ▼
        print first N (id / file_name / taken_at), plus "+K more" summary (D-06/D-07)
   │
   ▼
return 0 (success) | 1 (any resolution/login/API failure, D-05 fail-loud)
```

### Recommended Project Structure
No new directories. Two additions to existing files, matching CONTEXT.md's "Files that will change":

```
auraframes/
├── cli.py              # + inspect subparser, run_inspect(), resolve_frame() (or see below)
tests/
├── offline.py          # + a get_frame route in make_router(); no new module
├── fixtures/            # + 1-2 new JSON fixtures (see Common Pitfalls)
├── test_cli_inspect.py  # new, mirrors test_cli_status.py's structure exactly
```

CONTEXT.md leaves open whether `resolve_frame()` lives inline in `cli.py` or in a new
`auraframes/frame_resolver.py`. Given `STRUCTURE.md`'s existing convention ("new
workflow/orchestration → add a method on `Aura`; do not add business logic to `*Api`
classes") and the fact this logic has **no HTTP call**, either placement is consistent
with the codebase's conventions — a top-level pure function in `cli.py` is the smaller
diff; a separate module is easier to unit-test in isolation. Both are equally valid;
recommend `cli.py`-local unless the function grows past ~30 lines, to avoid a
one-function module.

### Pattern 1: Reuse `get_frames()` for resolution, not a new query
**What:** Build the case-insensitive substring match set and the id-fallback check
entirely from the `list[Frame]` `frame_api.get_frames()` already returns — do not add a
new API method or query parameter.
**When to use:** Any time frame targeting needs a candidate set; `FrameApi` has no
name-search endpoint (`auraframes/api/frameApi.py` — confirmed no `filter`/`search`
param on `get_frames()`).
**Example:**
```python
# Source: auraframes/api/frameApi.py:13-19 (existing, unmodified)
def get_frames(self) -> list[Frame]:
    json_response = self._client.get('/frames.json')
    return [Frame(**frame_data) for frame_data in json_response.get('frames')]
```
```python
# New resolution logic (illustrative — matches D-01..D-04)
def resolve_frame(target: str, frames: list[Frame]) -> Frame:
    name_matches = [f for f in frames if target.lower() in f.name.lower()]
    if len(name_matches) == 1:
        return name_matches[0]
    if len(name_matches) > 1:
        raise AmbiguousFrameError(name_matches)          # D-03
    id_matches = [f for f in frames if f.id == target]     # exact match, case-sensitive
    if len(id_matches) == 1:
        return id_matches[0]
    raise FrameNotFoundError(frames)                       # D-04
```

### Pattern 2: Two-call metadata fetch (resolution vs. display)
**What:** After resolving to a single `frame_id`, call `frame_api.get_frame(frame_id)` —
a **second**, distinct call from the `get_frames()` used for resolution — to get the
canonical single-frame payload plus its already-corrected `total_asset_count`.
**When to use:** Whenever D-11's asset count is displayed; `get_frame()`'s
`total_asset_count` return value already implements the Phase 2 drift-fix preference
(`total_asset_count` if present, else `frame_data.num_assets`) — re-implementing that
fallback logic in `cli.py` would duplicate it.
**Example:**
```python
# Source: auraframes/api/frameApi.py:21-36 (existing, unmodified)
def get_frame(self, frame_id: str) -> tuple[Frame, int]:
    json_response = self._client.get(f'/frames/{frame_id}.json')
    frame_data = json_response.get('frame')
    total_asset_count = json_response.get('total_asset_count')
    if total_asset_count is None and frame_data:
        total_asset_count = frame_data.get('num_assets')
    return Frame(**frame_data), total_asset_count
```

### Pattern 3: `run_inspect()` mirrors `run_status()`'s testable-handler shape
**What:** Return an `int` exit code; never call `sys.exit()`; accept an optional injected
`aura` param for offline testing.
**When to use:** Every CLI subcommand handler in this codebase (established D-01/D-02 in
Phase 5, carried forward per CONTEXT.md canonical refs).
**Example:**
```python
# Source: auraframes/cli.py:55-90 (existing run_status, the exact shape to mirror)
def run_status(aura=None, debug: bool = False) -> int:
    ...
    aura = aura or Aura()
    _configure_cli_logging(debug)
    try:
        aura.login()
    except Exception as e:
        print(f'Login failed: {e}')
        return 1
    ...
    return 0
```

### Anti-Patterns to Avoid
- **Re-querying the API for existence-checking:** Don't call `get_frame(id)` speculatively
  during resolution just to check if an id exists — `get_frames()`'s already-fetched list
  has every `Frame.id` needed for D-02's exact-match fallback. An extra live call here
  adds latency and a new failure mode (404 handling) for no benefit.
- **Assuming `Frame.contributors` is always a list:** It is
  `Optional[list[User]] = None` (`auraframes/models/frame.py:47`) — `len(frame.contributors)`
  will raise `TypeError` on a frame with zero contributors if the API omits the field
  (`None`) rather than sending `[]`. Guard with `frame.contributors or []`.
- **Sorting or re-ordering the photo list client-side:** D-07 explicitly rejects this —
  print `Aura.get_all_assets()`'s list in the order returned.
- **Duplicating the `num_assets` drift-fix:** Don't read `frame.num_assets` directly off
  a `get_frames()` list entry for the asset count display — use `get_frame()`'s
  `total_asset_count` return value, which already encodes the Phase 2 fallback logic
  (`auraframes/api/frameApi.py:29-35`).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Frame asset-count fallback logic | A second `total_asset_count or num_assets` check in `cli.py` | `FrameApi.get_frame()`'s existing tuple return | Already implements the exact Phase 2 drift-fix; duplicating it in two places risks the two copies drifting apart if the API changes again |
| Cursor pagination for assets | A manual `while cursor:` loop in `cli.py` | `Aura.get_all_assets(frame_id)` | Already handles this exact drain, already used by `dump_frame`; re-implementing it in the CLI layer would violate `STRUCTURE.md`'s "orchestration belongs on `Aura`, not per-caller" convention |
| Date parsing for `Asset.taken_at` | A new `datetime.strptime(asset.taken_at, ...)` call in `cli.py` | `Asset.taken_at_dt` property (`auraframes/models/asset.py:104-106`) | Already exists, already uses the correct `AURA_DT_FORMAT` (`auraframes/utils/dt.py:3`) — a second ad-hoc parse call risks a format-string typo |

**Key insight:** Every data-fetching and parsing primitive `inspect` needs already exists
and is already exercised by `status` or `dump_frame`. The only genuinely new code in this
phase is (1) the resolution function (no prior equivalent anywhere in the codebase) and
(2) the `inspect` output formatting.

## Runtime State Inventory

Not applicable — this is a greenfield-feature phase (a new read-only CLI subcommand), not
a rename/refactor/migration. No stored data, live service config, OS-registered state,
secrets, or build artifacts carry the string `inspect` or any renamed identifier that
would require this inventory.

## Common Pitfalls

### Pitfall 1: The offline test router has no route for `get_frame()`
**What goes wrong:** `tests/offline.py`'s `make_router()` [VERIFIED: local source read,
`/home/fabrice/dev/auraframes/tests/offline.py:34-51`] only matches
`/v5/login.json`, `/v5/frames.json`, and any path ending in `/assets.json` — a request to
`/v5/frames/{id}.json` (what `FrameApi.get_frame()` calls) falls through to the router's
final `return httpx.Response(404, json=_load("error_envelope.json"))` branch. Any offline
`inspect` test that reaches the metadata-fetch step will get a 404 and fail, even with
correct application code.
**Why it happens:** `get_frame()` has never been called from any code path before this
phase (`status` only calls `get_frames()`; `dump_frame()` calls `get_frame()` but has no
offline test today).
**How to avoid:** Add an explicit `if path.startswith("/v5/frames/") and path.endswith(".json") and "assets" not in path:` branch (or an exact per-id match) to `make_router()`
before writing any `inspect` test, and add a corresponding fixture (e.g.
`fixtures/frame_detail.json` shaped `{"frame": {...}, "total_asset_count": N}`). This is
a Wave 0 test-infrastructure task, not incidental to a feature task.
**Warning signs:** A new `inspect` test passes for resolution/photo-listing (which only
touch `login.json`/`frames.json`/`assets.json`, already routed) but fails specifically at
the metadata-display assertion with a 404/`error_envelope` response.

### Pitfall 2: `frames.json`'s single fixture frame can't exercise D-03 (ambiguous match)
**What goes wrong:** The existing `tests/fixtures/frames.json` [VERIFIED: local source
read] contains exactly **one** frame (`"Fake Frame"` / `frame-fake-0001`). A test that
calls `resolve_frame("Fake", frames)` against this fixture will always resolve uniquely —
there is no way to exercise the "more than one substring match" ambiguous-error path
without either a second fixture file or a per-test `overrides` dict that returns a
two-frame `frames.json` payload inline.
**Why it happens:** The fixture was authored for `status`'s needs (any non-empty frame
list), not for name-collision testing.
**How to avoid:** Do not edit the shared `frames.json` fixture (other passing tests depend
on its exact single-frame shape, e.g. `test_offline_get_all_assets_drains_pagination`
indexes `get_frames()[0]`). Instead, use `offline_aura(overrides={...})` per-test to
substitute a two-or-three-frame `/v5/frames.json` response inline (e.g. `"Kitchen"` +
`"Kitchen 2 Upstairs"` + a distinct `"Living Room"`), matching the D-01 example directly
from CONTEXT.md.
**Warning signs:** A "test ambiguous match" test that silently resolves to a single frame
because the shared fixture only has one entry — a false-positive green test.

### Pitfall 3: `Frame.contributors: Optional[...]` vs. CONTEXT.md's "already a hydrated `list[User]`" phrasing
**What goes wrong:** CONTEXT.md's Reusable Assets section describes `Frame.contributors`
as "already a hydrated `list[User]`" — true only when the API actually sends the field.
The Pydantic model type is `Optional[list[User]] = None`
(`auraframes/models/frame.py:47`) [VERIFIED: local source read], so a real frame with zero
contributors could plausibly come back with `contributors: null` rather than
`contributors: []`, and `len(None)` raises `TypeError`.
**Why it happens:** CONTEXT.md's phrasing is a simplification of "no new API call
needed," not a claim about non-nullability.
**How to avoid:** Always read via `(frame.contributors or [])` before taking `len()` or
iterating.
**Warning signs:** A live-only crash on a frame that has no contributors (a single-user
account's own frame) — won't reproduce against the fixture unless a `contributors: null`
case is added to the new fixture.

### Pitfall 4: Two frame-list-vs-single-frame calls can disagree if the API has drifted further
**What goes wrong:** Since `get_frames()` and `get_frame()` both hydrate the same `Frame`
pydantic model but from two different endpoints (`/frames.json` vs.
`/frames/{id}.json`), it's possible (given this is an undocumented, 3-year-stale API,
per `PROJECT.md`'s Constraints) that the two responses disagree on `num_assets` or
`contributors` for the same frame at the same moment (e.g. an asset added between the two
calls). This is a low-probability, low-impact race, not a blocker.
**Why it happens:** Two sequential, uncached HTTP calls to what is effectively the same
resource.
**How to avoid:** No action needed structurally — display whatever `get_frame()` (the
second, canonical call) returns; don't attempt to reconcile it against the
`get_frames()` list entry. Document as accepted risk if raised in review, not a defect to
fix.
**Warning signs:** A live UAT session in this phase notices `num_assets` differs slightly
between `status`'s frame listing and `inspect`'s metadata display for the same frame —
expected, not a bug.

### Pitfall 5: `main()`'s dispatch has no `else` branch — silent success trap once `inspect` is added
**What goes wrong:** `05-VERIFICATION.md`'s code-review findings (carried forward, WR-02)
already flagged that `main()`'s `if args.command == 'status': ...` has no `else`/`raise`
for an unmatched command. Today this is unreachable because argparse's
`required=True` + a single choice rejects anything else — but the moment `inspect` is
added as a second subparser choice, a **typo in the dispatch chain** (e.g. forgetting the
`elif args.command == 'inspect':` branch, or a copy-paste mistake) would make `main()`
silently `return None` for a real, valid subcommand instead of erroring.
**Why it happens:** The existing single-branch `if` was written before a second
subcommand existed; adding a second branch is the natural point this class of bug
appears.
**How to avoid:** When adding the `inspect` branch, also add a final `else: raise
ValueError(f"Unhandled command: {args.command}")` (or equivalent) so a future third
subcommand (`sync`, Phase 7) can't silently no-op if its own dispatch branch is missed.
**Warning signs:** `aura-cli inspect ...` exits 0 with zero output — the classic
"forgot the dispatch branch" symptom.

## Code Examples

### `--debug` promotion to the root parser (folded todo)
```python
# Current (auraframes/cli.py:11-23) — --debug lives on the status subparser only
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='aura-cli')
    subparsers = parser.add_subparsers(dest='command', required=True)
    status_parser = subparsers.add_parser('status', help='...')
    status_parser.add_argument('--debug', action='store_true', default=False, help='...')
    return parser
```
```python
# Target shape — --debug moves to the root parser; status/inspect subparsers no longer
# each declare it. main() reads args.debug once, regardless of subcommand.
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='aura-cli')
    parser.add_argument('--debug', action='store_true', default=False,
                         help='Show verbose loguru request/response logging on stderr')
    subparsers = parser.add_subparsers(dest='command', required=True)
    subparsers.add_parser('status', help='Check config/auth health and list account frames')
    inspect_parser = subparsers.add_parser('inspect', help='Inspect a frame\'s photos and metadata')
    inspect_parser.add_argument('--frame', required=True, help='Frame name (substring) or id')
    return parser
```
```python
# main() dispatch — both branches now read the same root-level args.debug
def main(argv=None) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)
    if args.command == 'status':
        return run_status(debug=args.debug)
    if args.command == 'inspect':
        return run_inspect(args.frame, debug=args.debug)
    raise ValueError(f"Unhandled command: {args.command}")  # Pitfall 5 guard
```

### Offline router extension for `get_frame()` (Pitfall 1's fix)
```python
# tests/offline.py — add before the final 404 fallthrough in make_router()'s handler
if path.startswith("/v5/frames/") and path.endswith(".json") and "/assets" not in path and "/activities" not in path:
    return httpx.Response(200, json=_load("frame_detail.json"))
```

## State of the Art

Not applicable — no external library or API version changed; this is internal-only
feature work on code already current for this project (pydantic v2, httpx 0.27+, Python
3.14, established in Phases 1 and 4).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Frame `id` fallback matching (D-02) should be case-sensitive exact string equality | Pattern 1 | Low — if the live API's ids are always lowercase UUIDs (as `frames.json`'s `frame-fake-0001` fixture suggests), case sensitivity is moot in practice; if a user pastes an id with different casing, a case-sensitive match would incorrectly report not-found. CONTEXT.md doesn't specify case sensitivity for the id branch — flagging for the planner/discuss-phase to confirm if it matters, though low real-world impact since ids are typically copy-pasted verbatim from another `inspect`/`status` output. |
| A2 | `get_frames()`'s list-endpoint response includes the same full field set (contributors, num_assets, user) as `get_frame()`'s single-endpoint response, on the *live* API (not just the synthetic fixture) | Summary, Pattern 2 | Medium — if the live `/frames.json` list actually returns a lighter/summary shape missing `contributors` or with different `num_assets` freshness, the Phase 2 "drift fix" comment in `get_frame()` implies at least `total_asset_count` placement has drifted before; this phase's own live UAT pass (already planned per D-12) will surface this immediately if it's wrong, since `inspect` calls `get_frame()` directly for display — no design change needed even if this assumption is wrong, but worth the planner noting it's unconfirmed until the live pass runs. |
| A3 | Recommended default N for "first N photos" (D-06, Claude's Discretion) is a reasonable value like 10 | Recommended Project Structure / Pattern discussion | Low — CONTEXT.md explicitly delegates this to Claude's discretion at plan time; not a research risk, just flagging that this RESEARCH.md doesn't lock a number, per the phase's own scope note. |

## Open Questions

1. **Does the live API's `/frames.json` list response actually include `contributors` and an accurate `num_assets` per frame, or only `/frames/{id}.json` does?**
   - What we know: Both endpoints hydrate the same `Frame` pydantic model with all fields required unless `Optional` — if `num_assets` (a required, non-Optional field) were missing from a `/frames.json` list entry on the live API, `Frame(**frame_data)` would raise a pydantic `ValidationError` today, and `status` (which calls `get_frames()` already, live-verified in Phase 5) would have already surfaced this. So `num_assets` is confirmed present on both endpoints' live responses.
   - What's unclear: `contributors` is `Optional`, so its *absence* wouldn't raise — we don't know from static analysis alone whether the live list endpoint actually populates it (vs. sending `null` always, only populating it on the single-frame endpoint).
   - Recommendation: Not a blocker — `inspect`'s design already calls `get_frame(resolved_id)` for display (Pattern 2), which sidesteps this question entirely by always using the single-frame endpoint for contributor/owner display. Resolve definitively during this phase's own live UAT pass (piggybacking on D-12's md5_hash spike, same live session).

2. **Should the ambiguous-match error (D-03) also show `num_assets` or other fields to help disambiguate, beyond name+id?**
   - What we know: D-03 requires "list the matching frames' names + ids."
   - What's unclear: Whether adding a third disambiguating field (e.g., asset count) would help users pick between two similarly-named frames faster.
   - Recommendation: Follow D-03 literally (name + id only) — CONTEXT.md is explicit and this avoids an extra `get_frame()` call per ambiguous candidate (which would multiply live API calls for what's meant to be a simple error path).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Runtime | ✓ | 3.14.4 | — |
| `uv` | Dependency/venv management | ✓ | 0.11.7 | — |
| `pytest` | Offline test suite | ✓ | 9.1.1 | — |
| Live Aura account credentials (`AURA_EMAIL`/`AURA_PASSWORD`) | D-12 md5_hash live spike, live UAT | ✓ (per `PROJECT.md`/`STATE.md`: "A live Aura account (credentials ready) is available") | — | None needed — this is a hard requirement for Success Criterion 4; if credentials become unavailable mid-phase, the spike (and thus Phase 7 design) blocks, matching the existing project-wide constraint that verification is inherently against a live, credential-gated target |

No missing dependencies — this phase's tooling is 100% already installed and verified by
Phases 1-5.

## Security Domain

`security_enforcement` is enabled (`security_asvs_level: 1`, `security_block_on: "high"`
per `.planning/config.json`). This phase adds a **read-only** CLI subcommand exercising
only already-live-verified GET endpoints (`get_frame`, `get_assets`, reused
`get_frames`) — no new write/mutating calls, no new auth surface, no new user input sink
beyond a single `--frame <string>` CLI argument consumed only for local string
comparison (never interpolated into a shell command, SQL query, or file path).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No (new) | Unchanged — same `Aura.login()` path Phase 5 already covers; `inspect` doesn't touch auth |
| V3 Session Management | No | No session state introduced; `Client`'s existing header/cookie mutation is unchanged |
| V4 Access Control | No | No new authorization boundary — a logged-in account can already see all its own frames via `status`; `inspect` reveals no additional data the account couldn't already list |
| V5 Input Validation | Yes | `--frame <value>` is a free-form string used only for (a) case-insensitive Python substring comparison against `Frame.name` and (b) exact string equality against `Frame.id` — both are pure in-memory string operations with no shell/SQL/path interpolation, so injection classes don't apply; the only "validation" needed is argparse's own `required=True` (empty/missing arg handling) |
| V6 Cryptography | No | No cryptographic operation introduced; `md5_hash` display is read-only observation of a value the API itself computed, not a hash `inspect` performs |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Password/token leakage into ambiguous/not-found error output | Information Disclosure | Carried forward from Phase 5 D-07/D-09's convention: error messages print frame names/ids only, never credentials or auth tokens — `resolve_frame()`'s error paths (D-03/D-04) only ever touch `Frame.name`/`Frame.id`, which are not secrets |
| Unhandled exception on API-shape drift (undocumented API) crashing with a raw traceback instead of a clean exit | Denial of Service (availability, not security-critical) | Follow Phase 5's fail-loud convention (D-05/D-08): wrap `get_frame`/`get_all_assets` calls in the same broad `try/except` + `print(...); return 1` pattern `run_status()` uses around `login()`, per WR-01's carried-forward code-review note that this guard should eventually cover post-login calls too |

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CLI-03 | `inspect --frame <name|id>` command lists photos (id/filename/date) plus frame metadata (name, owner, contributor count, asset count) | Pattern 1-3 ground the exact call sequence (`get_frames()` → resolve → `get_frame()` → `get_all_assets()`); Asset/Frame/User field names confirmed (`file_name`, `taken_at`/`taken_at_dt`, `user.name`/`user.email`, `contributors`, `num_assets` via `get_frame()`'s tuple) |
| CLI-04 | Frame targeting by name or ID, clear error on ambiguous name match | Pattern 1 grounds the exact `Frame.name`/`Frame.id` types (both required `str`) needed for D-01-D-04's case-insensitive substring + exact-id-fallback logic; Pitfall 2 identifies the fixture gap that must be closed to test the ambiguous-match path (D-03) offline |
</phase_requirements>

## Sources

### Primary (HIGH confidence — direct local source reads)
- `auraframes/api/frameApi.py` — `get_frames()`, `get_frame()`, `get_assets()` exact signatures and Phase 2 drift-fix logic
- `auraframes/aura.py` — `Aura.get_all_assets()`, `Aura.dump_frame()`'s existing call sequence (the pattern `inspect` mirrors)
- `auraframes/models/frame.py` — `Frame.id`, `.name`, `.contributors` (Optional!), `.num_assets`, `.user` exact types
- `auraframes/models/asset.py` — `Asset.id`, `.file_name`, `.taken_at`/`.taken_at_dt`, `.md5_hash` exact types
- `auraframes/models/user.py` — `User.name`, `.email` exact types
- `auraframes/cli.py` — `build_parser()`, `main()`, `run_status()`, `_configure_cli_logging()` current shape
- `tests/offline.py`, `tests/test_cli_status.py`, `tests/test_offline_read_path.py`, `tests/conftest.py` — DI/mocking pattern, router gap
- `tests/fixtures/*.json` — exact current fixture shapes (single-frame `frames.json`, asset pages, error envelope, login)
- `.planning/phases/06-inspect-frame-resolution/06-CONTEXT.md` — locked decisions D-01 through D-13
- `.planning/phases/05-cli-skeleton-status/05-VERIFICATION.md` — carried-forward code-review findings (WR-01, WR-02) directly relevant to this phase's dispatch-chain change
- `.planning/PROJECT.md`, `.planning/STATE.md`, `.planning/REQUIREMENTS.md` — milestone context, live-credential availability, requirement text
- `pyproject.toml` — confirms no new dependency is needed

### Secondary / Tertiary
None — no web search or external documentation lookup was performed for this phase;
all findings are grounded in this repository's own source and planning artifacts, which
is both sufficient and appropriate given the phase adds no new external technology.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new libraries; all existing pins confirmed via `pyproject.toml`
- Architecture: HIGH — call sequence directly derived from existing `dump_frame()` precedent and `FrameApi`/`Aura` signatures, all read from source
- Pitfalls: HIGH — the offline-router gap and `contributors` nullability are both directly observed in source, not inferred
- Open Questions: MEDIUM — the live list-vs-detail endpoint field-completeness question (Open Question 1) is unresolved until this phase's own live pass, but the design already sidesteps it (Pattern 2)

**Research date:** 2026-07-06
**Valid until:** Should remain valid through this phase's execution (no external drift risk); re-check `Frame`/`Asset` model fields if the live API is found to have drifted further during this phase's own live spike (D-12/D-13), since that finding could reveal additional undocumented schema changes beyond `md5_hash`.
