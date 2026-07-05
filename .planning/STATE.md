---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Directory-to-Frame Sync
status: planning
last_updated: "2026-07-05T16:16:03.100Z"
last_activity: 2026-07-05
progress:
  total_phases: 0
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-05)

**Core value:** Prove the existing client still works end-to-end (login → list → download) on a current Python toolchain, so we know exactly what survives before building anything new.
**Current focus:** v2.0 Directory-to-Frame Sync — defining requirements and roadmap

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-07-05 — Milestone v2.0 started

## Performance Metrics

**Velocity:**

- Total plans completed: 8
- Average duration: — min
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 2 | - | - |
| 02 | 2 | - | - |
| 03 | 1 | - | - |
| 04 | 3 | - | - |

**Recent Trend:**

- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
| Phase 01 P01 | 6 | 2 tasks | 4 files |
| Phase 01 P02 | 34 | 3 tasks | 5 files |
| Phase 02 P01 | 12 | 3 tasks | 7 files |
| Phase 02 P02 | 8 | 2 tasks | 4 files |
| Phase 03 P01 | 18 | 3 tasks | 3 files |
| Phase 04 P01 | 1min | 2 tasks | 2 files |
| Phase 04 P02 | 2min | 2 tasks | 6 files |
| Phase 04 P03 | 3min | 2 tasks | 2 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Adopt `uv` + `pyproject.toml`, replacing the broken UTF-16 `requirements.txt`
- Target Python 3.14 and accept the pydantic v1→v2 migration it forces
- Done bar = read path only (login → list → download); upload deferred to v2
- [Phase ?]: Use >= floors in pyproject.toml + committed uv.lock for reproducibility (D-01/D-02)
- [Phase ?]: hatchling build backend; pytest in optional-dependencies dev extra
- [Phase ?]: Un-ignore .python-version in .gitignore so the uv interpreter pin is committed
- [Phase ?]: [Phase 1]: Replace AllOptional metaclass with public make_partial() create_model factory (no pydantic private internals, D-06)
- [Phase ?]: [Phase 1]: Add = None to all Optional base-model fields in Frame/Asset to restore v1 implicit-None semantics (Q#1)
- [Phase ?]: [Phase 1]: Faithful straight-port of AssetPartialId validator to @field_validator; model_validator correctness fix deferred to Phase 2 (Q#2)
- [Phase ?]: [Phase 2 P1]: Centralized recursive _redact() masks password/auth_token/x-token-auth in all request/response logs (D-07)
- [Phase ?]: [Phase 2 P1]: raise_for_status in all 4 Client methods so failed HTTP raises instead of returning green (D-06)
- [Phase ?]: [Phase 2 P1]: Live tests credential-gated via @pytest.mark.live + session aura fixture that skips when creds unset (D-01/D-02/D-03)
- [Phase ?]: [Phase 2 P2]: get_all_assets parametrized with limit + conditional page_delay; removed always-on 1s/page sleep (D-05)
- [Phase ?]: [Phase 2 P2]: frameApi.get_assets raises on the error key (no silent pass) so a drifted asset page can't return green (D-06)
- [Phase ?]: [Phase 2 P2]: EXIF-write except re-raises (no 0-byte saves); geocode except tolerated; Nominatim UA made ToS-compliant (D-11)
- [Phase ?]: [Phase 3 P1]: main.py is a facade-only read-path demo with a credential guard (D-06/D-07)
- [Phase ?]: [Phase 3 P1]: VERIFICATION-REPORT.md at repo root cites 02-LIVE-EVIDENCE.md (D-04); fresh 2026-06-29 run 4 passed/9 deselected
- [Phase ?]: Used native httpx.BaseTransport | None union syntax for Client transport param (RESEARCH Pattern 1)
- [Phase ?]: Removed the DI TODO comment in aura.py outright rather than rephrasing it
- [Phase ?]: [Phase 4 P2]: Fixture JSON authored entirely synthetic (no real recorded API response) — safer sanitization posture, no real secret ever exists to leak
- [Phase ?]: [Phase 4 P2]: assets_page1/page2 fixtures distinguished by next_page_cursor truthiness + distinct asset ids for Plan 03's query-param router
- [Phase ?]: [Phase 4 P3]: offline_aura()'s overrides mechanism is a plain dict keyed by the fully-resolved path, checked before the router's default branches
- [Phase ?]: [Phase 4 P3]: test_offline_http_status_error_raises builds its own one-off Client(transport=MockTransport(...)) rather than going through offline_aura(), since it only needs Client's raise_for_status behavior

### Pending Todos

None yet.

### Blockers/Concerns

- API is undocumented and may have drifted since April 2023; verification is against a moving target
- Silent error handling (`pass` on API `error` fields) can mask API drift during Phase 2 verification — watch for it
- 2022-era pins (pydantic 1.10.4, pillow 9.5.0, httpx 0.23.1, boto3 1.26.38) will not build on 3.14; expect upgrades in Phase 1

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260630-qs8 | main.py loads a local .env at startup so the read-path demo picks up AURA_EMAIL/AURA_PASSWORD without exporting them (shell vars still win; missing .env is a no-op). python-dotenv promoted to a runtime dependency. | 2026-06-30 | cd9ab6b | [260630-qs8-make-main-py-load-a-local-env-file-at-st](./quick/260630-qs8-make-main-py-load-a-local-env-file-at-st/) |

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-07-05T16:16:03.100Z
Stopped at: Milestone v2.0 (Directory-to-Frame Sync) started — defining requirements and roadmap
Resume file: None

## Operator Next Steps

- Continue /gsd-new-milestone through requirements and roadmap creation
