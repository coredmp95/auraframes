---
phase: 04-client-transport-seam-for-offline-testability
plan: 01
subsystem: testing
tags: [httpx, dependency-injection, transport, offline-testing]

# Dependency graph
requires: []
provides:
  - "Client.__init__(transport=...) — optional httpx.BaseTransport injection, additive/zero-arg-safe"
  - "Aura.__init__(client=...) — optional Client injection, additive/zero-arg-safe, DI TODO closed"
affects: [04-02, 04-03, offline-test-harness]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Additive-only constructor injection: new param defaults to None, real path unchanged for all existing zero-arg callers"
    - "Injection chain Aura <- Client <- transport, each layer composing via `x or DefaultConstruction()`"

key-files:
  created: []
  modified:
    - auraframes/client.py
    - auraframes/aura.py

key-decisions:
  - "Used native `httpx.BaseTransport | None = None` union syntax for the new transport param (per RESEARCH Pattern 1), not typing.Optional"
  - "Removed the DI TODO comment in aura.py outright rather than rephrasing it — this phase closes it"

requirements-completed: [R4-SEAM-CLIENT, R4-SEAM-AURA]

coverage:
  - id: D1
    description: "Client.__init__ accepts an optional transport and routes every request through it while keeping headers/cookies/history/_redact/raise_for_status intact"
    requirement: "R4-SEAM-CLIENT"
    verification:
      - kind: unit
        ref: "uv run python -c \"import httpx; from auraframes.client import Client; Client(); c=Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={'ok': True}))); assert c.get('/frames.json') == {'ok': True}; print('PASS')\""
        status: pass
    human_judgment: false
  - id: D2
    description: "Aura.__init__ accepts an optional pre-built Client (defaulting to a fresh one), propagates it to every *Api, and the DI TODO comment is removed"
    requirement: "R4-SEAM-AURA"
    verification:
      - kind: unit
        ref: "uv run python -c \"from auraframes.aura import Aura; from auraframes.client import Client; Aura(); c=Client(); a=Aura(client=c); assert a._client is c; assert a.frame_api._client is c; print('PASS')\""
        status: pass
      - kind: other
        ref: "grep -v '^#' auraframes/aura.py | grep -c 'Can probably use DI' == 0"
        status: pass
    human_judgment: false

# Metrics
duration: 1min
completed: 2026-07-04
status: complete
---

# Phase 4 Plan 1: Client transport seam Summary

**Client.__init__ gains an optional `transport: httpx.BaseTransport | None` param and Aura.__init__ gains an optional `client: Client | None` param, forming the `Aura <- Client <- transport` DI chain the offline test harness (Plan 03) needs — both additive, zero-arg callers unaffected.**

## Performance

- **Duration:** 1 min
- **Started:** 2026-07-04T16:36:11Z
- **Completed:** 2026-07-04T16:37:13Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- `Client.__init__` accepts an optional `transport` and forwards it straight into the inner `httpx.Client(...)` call — verified with `httpx.MockTransport` that headers/cookies/history/`_redact`/`raise_for_status` still all fire correctly on an injected transport.
- `Aura.__init__` accepts an optional `client` (`self._client = client or Client()`), propagating the injected instance to every `*Api` — verified `a._client is c` and `a.frame_api._client is c`.
- The long-standing DI TODO comment in `aura.py` (`# TODO: Can probably use DI for passing around the client?`) is removed, not rephrased — this phase closes it.
- No behavior change on the real network path; zero-arg `Client()` and `Aura()` construction verified to still work exactly as before.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add additive transport param to Client.__init__** - `dc25434` (feat)
2. **Task 2: Add additive client param to Aura.__init__ and close the DI TODO** - `36441d4` (feat)

**Plan metadata:** (pending — final metadata commit follows this SUMMARY)

## Files Created/Modified
- `auraframes/client.py` - `Client.__init__` gains `transport: httpx.BaseTransport | None = None`, forwarded into the inner `httpx.Client(...)` call
- `auraframes/aura.py` - `Aura.__init__` gains `client: Client | None = None`; body is `self._client = client or Client()`; DI TODO comment removed

## Decisions Made
- Used native `httpx.BaseTransport | None = None` union syntax (matches RESEARCH.md Pattern 1's recommended signature) rather than `typing.Optional`, since this is a fresh param rather than a retrofit of the file's existing `Optional[dict]` style.
- Removed the DI TODO comment entirely rather than leaving a replacement — this plan is explicitly the closure of that TODO per PLAN.md acceptance criteria.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- The `Aura <- Client <- transport` injection chain is now fully wired and verified, unblocking Plan 03's offline test harness (`tests/offline.py`, fixtures, offline read-path tests) described in `04-PATTERNS.md`.
- `uv run pytest -m "not live"` remains green (10 passed, 4 deselected) — no regression to the default suite.
- No blockers for the next plan in this phase.

---
*Phase: 04-client-transport-seam-for-offline-testability*
*Completed: 2026-07-04*

## Self-Check: PASSED

- FOUND: auraframes/client.py
- FOUND: auraframes/aura.py
- FOUND: .planning/phases/04-client-transport-seam-for-offline-testability/04-01-SUMMARY.md
- FOUND: dc25434 (Task 1 commit)
- FOUND: 36441d4 (Task 2 commit)
- FOUND: eb6377d (Summary commit)
