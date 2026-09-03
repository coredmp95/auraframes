# Phase 7: Sync-Diffing Engine (Dry-Run Only) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-07
**Phase:** 7-Sync-Diffing Engine (Dry-Run Only)
**Areas discussed:** Directory scope & file eligibility, Content-hash matching & duplicates, Plan output & delete-list identification, Hash-convention validation (SYNC-02)

---

## Directory scope & file eligibility

| Option | Description | Selected |
|--------|-------------|----------|
| Recursive | Walks all subdirectories | ✓ |
| Top-level only | Flat scan, no subfolder traversal | |

**User's choice:** Recursive

| Option | Description | Selected |
|--------|-------------|----------|
| Images only (jpg/jpeg/png/heic) | Matches frame's diffable photo assets | ✓ |
| Images + videos, videos flagged separately | Fuller inventory, more moving parts | |

**User's choice:** Images only (jpg/jpeg/png/heic)

| Option | Description | Selected |
|--------|-------------|----------|
| Skip with a summary note | Ignored files not in plan, but counted/mentioned | ✓ |
| Silently skip | No mention at all | |
| Error and abort | Any ineligible file stops the whole sync | |

**User's choice:** Skip with a summary note
**Notes:** Real photo directories likely contain stray non-image files; erroring would make the tool impractical.

---

## Content-hash matching & duplicates

| Option | Description | Selected |
|--------|-------------|----------|
| Treat as one logical photo | Dedupe local files by hash before diffing | ✓ |
| Treat each file independently | Every file is a separate line item | |

**User's choice:** Treat as one logical photo

| Option | Description | Selected |
|--------|-------------|----------|
| Match count-for-count against local | Multiset — surplus frame copies become delete candidates | ✓ |
| Any local match clears all frame dupes | Conservative — never proposes deleting a photo that exists locally anywhere | |

**User's choice:** Match count-for-count against local
**Notes:** Intentional asymmetry — local dedupes to one "want," frame duplicates are matched multiset-style so genuine extras get flagged for deletion.

---

## Plan output & delete-list identification

| Option | Description | Selected |
|--------|-------------|----------|
| Full list always | Every planned upload/delete printed in full, no truncation | ✓ |
| Truncate like inspect (first N + count) | Consistent with D-06 precedent, risks hiding deletions | |

**User's choice:** Full list always
**Notes:** Phase 8's `--apply` executes exactly this plan; deletions are irreversible, so a sampled view was rejected on safety grounds.

| Option | Description | Selected |
|--------|-------------|----------|
| Asset id + taken_at date | Reuses fields inspect already prints | ✓ |
| Asset id + taken_at + hash prefix | More precise, less readable | |

**User's choice:** Asset id + taken_at date

---

## Hash-convention validation (SYNC-02)

| Option | Description | Selected |
|--------|-------------|----------|
| One-time live check during build, documented | Like Phase 6's md5_hash spike | ✓ |
| Automated regression test using a real fixture | Permanent unit test with a committed fixture | |

**User's choice:** One-time live check during build, documented

---

## Claude's Discretion

- Exact plan output line wording/formatting (within the full-listing requirement).
- Whether scan/hash/diff logic lives in a new helper module or inline in `cli.py`.
- Exact image extension set beyond jpg/jpeg/png/heic if the test directory surfaces more, as long as videos stay excluded.
- Where the one-time hash-validation live check gets documented.

## Deferred Ideas

None — discussion stayed entirely within phase scope; no scope-creep items arose.
