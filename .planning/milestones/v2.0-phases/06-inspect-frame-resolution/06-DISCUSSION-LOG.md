# Phase 6: Inspect + Frame Resolution - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-06
**Phase:** 6-Inspect + Frame Resolution
**Areas discussed:** Todo fold-in, Frame resolution rules, Photo listing format & scope, Frame metadata depth, md5_hash live-spike & write-up

---

## Todo Fold-In

| Option | Description | Selected |
|--------|-------------|----------|
| Fold it in | Promote `--debug` to a global `aura-cli` flag as part of Phase 6's CLI surface work | ✓ |
| Leave it pending | Keep `--debug` status-only; revisit later | |

**User's choice:** Fold it in.
**Notes:** Matched todo (score 0.9) — `--debug` moves from a `status`-only subparser flag to a root `aura-cli --debug <subcommand>` flag.

---

## Frame Resolution Rules

| Option | Description | Selected |
|--------|-------------|----------|
| Try exact name match first, then ID | Exact name match, fallback to id | |
| Try ID first, then name | ID lookup first | |
| Always try both, error on conflict | Simultaneous check, conflict error | |

**User's choice:** "Try exact name match first, then ID" (initially), later refined to case-insensitive **substring** match (see below).

| Option | Description | Selected |
|--------|-------------|----------|
| Multiple frames share the exact name | Ambiguous = exact-name duplicates only | |
| Case-insensitive or partial matches also count as ambiguous | Broader ambiguity net | ✓ |

**User's choice:** Case-insensitive or partial matches also count as ambiguous.

| Option | Description | Selected |
|--------|-------------|----------|
| Clear not-found error, exit non-zero | Simple not-found message | |
| Not-found error that also lists available frame names | Adds a hint listing account frames | ✓ |

**User's choice:** Not-found error that also lists available frame names.

**Reconciliation follow-up** (exact-match-first vs. case-insensitive/partial ambiguity were in tension):

| Option | Description | Selected |
|--------|-------------|----------|
| Case-insensitive exact match, ambiguous on multiple hits | No substring matching | |
| Case-insensitive substring match, ambiguous on multiple hits | Broader net, more forgiving of partial typing | ✓ |

**User's choice:** Case-insensitive substring match, ambiguous on multiple hits.
**Notes:** Final rule (D-01–D-05 in CONTEXT.md): case-insensitive substring match on `Frame.name` tried first; 1 match → use it; 0 matches → fall back to id; 2+ matches → ambiguous error listing name+id of each match; no match at all → not-found error listing account's frame names. All failure paths exit non-zero (Phase 5 D-08 convention).

---

## Photo Listing Format & Scope

| Option | Description | Selected |
|--------|-------------|----------|
| List all, one line per photo | No truncation | |
| Paginate with --limit/--page flag | New flag surface | |
| Summary count + first few, with verbosity hint | Default summary, full list needs a flag | (base for user's answer) |

**User's choice (free text):** "Like 3, but full list only to export to a particular format selectable (maybe json, csv, etc..), there is no point to print 2000 line on screen for any user."

| Option | Description | Selected |
|--------|-------------|----------|
| By taken_at, newest first | Chronological, most recent first | |
| By taken_at, oldest first | Chronological, oldest first | |
| API's natural order (no re-sorting) | No extra sort logic | ✓ |

**User's choice:** API's natural order (no re-sorting).

**Scope-creep flag raised:** the requested `--format json/csv` export overlaps with `SYNC-06` (v2, already deferred in REQUIREMENTS.md).

| Option | Description | Selected |
|--------|-------------|----------|
| Default to summary count + first N, defer full --format flag | Keep Phase 6 to plain terminal listing; note --format as deferred | ✓ |
| Always plain text, no truncation, no format flag | Simplest; no new flag | |
| Build --format json/csv now, in this phase | Treat as in-scope for inspect | |

**User's choice:** Default to summary count + first N, defer full --format flag.
**Notes:** Captured as a Deferred Idea (D-08) — to be designed together with SYNC-06 in a future phase, covering both JSON and CSV per the user's explicit mention of both formats.

---

## Frame Metadata Depth

| Option | Description | Selected |
|--------|-------------|----------|
| Owner's email | Unambiguous, matches status's existing pattern | |
| Owner's display name | More human-readable | |
| Both email and name | Full detail | ✓ |

**User's choice:** Both email and name.

| Option | Description | Selected |
|--------|-------------|----------|
| Count only | Matches literal wording of success criterion | |
| Count plus each contributor's name/email listed | More detail than criterion requires | ✓ |

**User's choice:** Count plus each contributor's name/email listed.
**Notes:** Both fields already exist on the hydrated `User` model (`Frame.user`, `Frame.contributors`) — no new API calls needed.

---

## md5_hash Live-Spike & Write-Up

| Option | Description | Selected |
|--------|-------------|----------|
| Piggyback on inspect's own live-tested assets | Reuse inspect's live verification pass, no separate script | ✓ |
| One-off throwaway script against the live API | Separate ad-hoc script, discarded after | |

**User's choice:** Piggyback on `inspect`'s own live-tested assets.

| Option | Description | Selected |
|--------|-------------|----------|
| PROJECT.md Context + STATE.md Blockers/Concerns | Update existing canonical locations | ✓ |
| Dedicated new file (06-MD5-FINDING.md) | New standalone artifact | |

**User's choice:** PROJECT.md Context + STATE.md Blockers/Concerns.
**Notes:** Local-manifest fallback for Phase 7 remains conditional per REQUIREMENTS.md Out of Scope — only added if this spike finds md5_hash absent.

---

## Claude's Discretion

- Exact value of N for the default "first N photos" truncation.
- Exact wording of ambiguous/not-found error messages (content requirements fixed; wording is discretionary).
- Whether frame resolution lives in a new helper module or inline in the CLI handler.
- Exact terminal formatting of the photo list / metadata block (follows Phase 5's no-table precedent).

## Deferred Ideas

- **`--format json`/`--format csv` full photo-list export** — duplicates the already-deferred v2 requirement SYNC-06; should be designed once for both `inspect` and `sync` in a future phase. User explicitly wants both JSON and CSV covered when it's eventually built.
