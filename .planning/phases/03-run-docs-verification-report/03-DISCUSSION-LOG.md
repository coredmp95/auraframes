# Phase 3: Run Docs & Verification Report - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-29
**Phase:** 3-Run Docs & Verification Report
**Areas discussed:** README treatment, Report location & form, "Run the client" command, Report scope & evidence

---

## README Treatment

| Option | Description | Selected |
|--------|-------------|----------|
| Reconcile to reality | Rewrite README: correct AURA_EMAIL, uv setup/run, mark VERIFIED vs UNVERIFIED | ✓ |
| Fix setup only | Surgically fix env var + add a Setup/Run section; leave narrative untouched | |
| README + separate SETUP.md | Leave README narrative; put uv instructions in a new dedicated doc | |

**User's choice:** Reconcile to reality
**Notes:** —

### Follow-up: upload-flow content

| Option | Description | Selected |
|--------|-------------|----------|
| Keep, mark unverified | Retain upload/SQS narrative, flag as documented-but-not-verified | ✓ |
| Move to 'unverified' appendix | Relocate device-flow content below the fold | |
| Remove entirely | Strip upload-flow content; keep README lean | |

**User's choice:** Keep, mark unverified
**Notes:** —

---

## Report Location & Form

| Option | Description | Selected |
|--------|-------------|----------|
| Repo-root report | Developer-visible report at repo root; cites 02-LIVE-EVIDENCE.md as raw evidence | ✓ |
| Inside .planning/phases/03 | Phase artifact in .planning/, not surfaced to repo-root readers | |
| STATUS section in README | Fold status table + drift into README | |

**User's choice:** Repo-root report

### Follow-up: cross-linking

| Option | Description | Selected |
|--------|-------------|----------|
| One-line summary + link | README shows 'Read path: VERIFIED (see report)' and links out; no duplicated tables | ✓ |
| No status in README | Status lives only in the repo-root report | |
| Duplicate the status table | Full table in both README and report | |

**User's choice:** One-line summary + link
**Notes:** Report is single source of truth for detail.

---

## "Run the Client" Command

| Option | Description | Selected |
|--------|-------------|----------|
| Flesh out main.py + document it | Real read-path demo (login→list→fetch→download); document `uv run python main.py` + pytest | ✓ |
| Document pytest as the run | Leave main.py; document `uv run pytest -m live` as the canonical run | |
| Minimal main.py print | Lightly improve main.py to print counts only | |

**User's choice:** Flesh out main.py + document it

### Follow-up: main.py behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse facade, graceful no-creds | Read path via existing Aura methods; download to gitignored dir; clean exit if creds unset | ✓ |
| Demo without download | login → list → print counts only; no image download | |
| You decide details | Lock 'real demo reusing facade'; leave output/target/no-creds to planner | |

**User's choice:** Reuse facade, graceful no-creds
**Notes:** No new client logic.

---

## Report Scope & Evidence

| Option | Description | Selected |
|--------|-------------|----------|
| Re-run live, capture fresh | Run live tests/main.py in Phase 3; capture dated output; catches new drift | ✓ |
| Cite Phase 2 evidence | Reference 02-LIVE-EVIDENCE.md; no new run | |

**User's choice:** Re-run live, capture fresh

### Follow-up: drift catalog depth

| Option | Description | Selected |
|--------|-------------|----------|
| Full: drift + masking + deferred | Status table + 4 schema drifts + GPS swap + silent-error masking fixes + pagination caveat | ✓ |
| Drift + masking only | Status table + 4 drifts + masking fixes; omit deferred/edge cases | |
| Status table + schema drift | Per-step table + 4 repaired drifts only | |

**User's choice:** Full: drift + masking + deferred
**Notes:** Criterion 4 explicitly wants silent-error masking documented.

---

## Claude's Discretion

- Exact report filename (`VERIFICATION-REPORT.md` vs `STATUS.md`) and section ordering.
- `main.py` console output format, demo frame/asset selection, gitignored download path.
- Whether the fresh live run uses the Phase 2 command verbatim or a thin capture wrapper.
- How much of README's existing read/download narrative to keep vs. trim while reconciling.

## Deferred Ideas

- Fix the GPS lat/long swap (documented as a known limitation only).
- Verifying the upload round-trip (UP-01) — separate milestone.
- `.env` loader as a first-class runtime feature (currently dev/test only).
- A `[project.scripts]` console entry point — `uv run python main.py` is sufficient.
- SQS flow mapping / frame rendering reverse-engineering — carried as unverified README notes.
