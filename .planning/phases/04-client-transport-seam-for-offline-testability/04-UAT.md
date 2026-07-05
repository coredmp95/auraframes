---
status: complete
phase: 04-client-transport-seam-for-offline-testability
source: [04-01-SUMMARY.md, 04-02-SUMMARY.md, 04-03-SUMMARY.md]
started: 2026-07-05T13:28:45Z
updated: "2026-07-05T13:30:27Z"
---

## Current Test

[testing complete]

## Tests

### 1. Client.__init__ transport injection preserves request pipeline

expected: Client.__init__ accepts an optional transport and routes every request through it while keeping headers/cookies/history/_redact/raise_for_status intact
result: pass
source: automated
coverage_id: D1
requirement: R4-SEAM-CLIENT

### 2. Aura.__init__ dependency injection with DI TODO removed

expected: Aura.__init__ accepts an optional pre-built Client (defaulting to a fresh one), propagates it to every *Api, and the DI TODO comment is removed
result: pass
source: automated
coverage_id: D2
requirement: R4-SEAM-AURA

### 3. Fixture files are valid and hydrate pydantic models

expected: 5 sanitized fixture JSON files (login, frames, assets_page1, assets_page2, error_envelope) exist, are valid JSON, and hydrate their corresponding pydantic models without raising
result: pass
source: automated
coverage_id: D1
requirement: R4-FIXTURES

### 4. Pagination fixtures are distinguishable by cursor

expected: assets_page1.json/assets_page2.json are distinguishable only by next_page_cursor (truthy vs null) with distinct asset ids, ready for pagination router
result: pass
source: automated
coverage_id: D2
requirement: R4-FIXTURES

### 5. Fixtures contain no real secrets or identifiers

expected: No fixture file contains a real recorded secret, cookie, GPS coordinate, or account identifier — all values are synthetic/obviously-fake
result: pass
source: automated
coverage_id: D3
requirement: R4-FIXTURES

### 6. Offline harness routes requests and handles pagination

expected: tests/offline.py exposes make_router()/offline_aura() as plain module-level functions, correctly routes /v5-prefixed paths, and distinguishes the two-page asset pagination fixture by cursor truthiness
result: pass
source: automated
coverage_id: D1
requirement: R4-HARNESS

### 7. Offline read-path tests pass with zero network/credentials

expected: tests/test_offline_read_path.py's 5 unmarked tests (login headers, frame hydration, pagination drain, business-rule RuntimeError, HTTPStatusError) all pass offline with no network/credentials
result: pass
source: automated
coverage_id: D2
requirement: R4-OFFLINE-TESTS

### 8. Live test suite remains untouched and skips cleanly

expected: tests/test_read_path.py and tests/conftest.py remain byte-identical (no diff); the @live suite still skips cleanly without credentials and the full default pytest run exits 0
result: pass
source: automated
coverage_id: D3
requirement: R4-LIVE-UNCHANGED

## Summary

total: 8
passed: 8
issues: 0
pending: 0
skipped: 0

## Gaps

[none yet]
