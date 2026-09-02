# Phase 5: CLI Skeleton + Status - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-06
**Phase:** 5-CLI Skeleton + Status
**Areas discussed:** CLI framework & naming, Status command output, Failure/exit-code behavior

---

## CLI framework & naming

| Option | Description | Selected |
|--------|-------------|----------|
| argparse (Recommended) | Stdlib, no new dependency | ✓ |
| click | Extra dependency, nicer subcommand ergonomics + CliRunner | |

**User's choice:** argparse (Recommended)
**Notes:** Matches the codebase's existing pragmatic-modernization/minimal-dependency ethos.

| Option | Description | Selected |
|--------|-------------|----------|
| One binary, subcommands (Recommended) | `aura-cli status` / `aura-cli inspect` / `aura-cli sync` | ✓ |
| Separate scripts per command | e.g. `aura-status`, `aura-inspect`, `aura-sync` | |

**User's choice:** One binary, subcommands (Recommended)
**Notes:** Standard convention (git/aws/docker style); one `[project.scripts]` entry.

| Option | Description | Selected |
|--------|-------------|----------|
| aura (Recommended) | Short, matches `Aura` facade class name | |
| auraframes | Matches pyproject.toml project name exactly | |
| aura-cli (free text) | User-provided override | ✓ |

**User's choice:** `aura-cli` (free-text override of both suggested options)
**Notes:** Explicit user preference — more descriptive/less collision-prone than either
researched suggestion. Locked in as the `[project.scripts]` command name.

---

## Status command output

| Option | Description | Selected |
|--------|-------------|----------|
| Concise summary (Recommended) | Terse, scannable text — no table | ✓ |
| Detailed table | Formatted table with Name/ID/Owner/Asset Count/Contributors columns | |

**User's choice:** Concise summary (Recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Name + ID only (Recommended) | Matches what's needed to target a frame later (CLI-04) | ✓ |
| Name + ID + asset count | Doubles status as an account overview | |

**User's choice:** Name + ID only (Recommended)
**Notes:** Asset count / contributor detail deferred to `inspect --frame X` (Phase 6).

| Option | Description | Selected |
|--------|-------------|----------|
| Just pass/fail per required var (Recommended) | "AURA_EMAIL: set" / "NOT SET" | ✓ |
| Full env dump | Also shows optional vars and resolved values | |

**User's choice:** Just pass/fail per required var (Recommended)

---

## Failure/exit-code behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Report + non-zero exit (Recommended) | Scriptable/CI-friendly, consistent with SYNC-04 | ✓ |
| Always exit 0 | status is purely diagnostic, never fails the process | |

**User's choice:** Report + non-zero exit (Recommended)
**Notes:** Established as a milestone-wide precedent, not just a Phase 5 detail.

| Option | Description | Selected |
|--------|-------------|----------|
| Stop after config check (Recommended) | Skip login attempt if creds are missing | ✓ |
| Attempt login anyway | Call login() with empty/missing creds to show the API's own error | |

**User's choice:** Stop after config check (Recommended)

---

## Claude's Discretion

- Exact argparse subparser wiring and `--help` text formatting.
- Exact wording of pass/fail and error messages (must never leak the password value).
- Whether `status` gets its own helper module or lives directly in `auraframes/cli.py`.
- Ordering of config-check vs. login-attempt output lines (config check runs first, per D-09).

## Deferred Ideas

- Frame asset count / contributor count in `status` — deferred to `inspect --frame <name|id>` (Phase 6).
- Full optional-env-var diagnostic dump — deferred; possible future `status --verbose` flag, not requested.
