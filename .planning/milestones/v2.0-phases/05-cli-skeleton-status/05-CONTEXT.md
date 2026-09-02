# Phase 5: CLI Skeleton + Status - Context

**Gathered:** 2026-07-06
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers a **runnable CLI entrypoint**, distinct from the existing `main.py`
facade-demo script, whose only working command is `status`. `status` reports config/auth
health (are `AURA_EMAIL`/`AURA_PASSWORD` set? does login succeed? which account?) plus
account info (frames on the account, name + id). This is the first phase of the v2.0
milestone and exercises **zero new API risk** — it only drives the already-live-verified
login/list read path from v1.0/v1.1.

In scope: CLI packaging (`[project.scripts]` entry point), argument parsing skeleton with
room for `inspect`/`sync` subcommands to be added in later phases, and the `status` command
itself.

Out of scope: `inspect` (Phase 6), `sync` (Phases 7-8), any write/mutating API calls, frame
targeting by name/id resolution logic (Phase 6, CLI-04).

</domain>

<decisions>
## Implementation Decisions

### CLI Framework & Packaging
- **D-01:** Use **`argparse`** (stdlib), not `click`. No new runtime dependency; matches
  this codebase's existing minimal-dependency, pragmatic-modernization philosophy. Research
  confidence is HIGH that this is a standard, well-documented pattern regardless of which
  framework was picked.
- **D-02:** **One binary, subcommand-based structure** — `aura-cli status`, with `aura-cli
  inspect ...` and `aura-cli sync ...` added as sibling subcommands in Phases 6-8 (via
  `argparse` subparsers). Not separate scripts per command.
- **D-03:** The installed command name is **`aura-cli`** (user's explicit choice — overrides
  the researched default suggestions of `aura`/`auraframes`). Wire this as the
  `[project.scripts]` entry in `pyproject.toml`, pointing at a new `auraframes/cli.py`
  module (per research's suggested architecture) exposing a `main()` entry function.
- **D-04:** `main.py` stays **untouched** as the existing facade-demo script — the new CLI
  is an additive layer alongside it, not a replacement (per PROJECT.md/research: "keeping
  `main.py`'s existing facade-demo role untouched").

### Status Command Output
- **D-05:** **Concise summary format**, not a table. E.g.:
  ```
  Logged in as you@email.com
  3 frames:
    - Living Room (id: abc123)
    - Kitchen (id: def456)
    - Bedroom (id: ghi789)
  ```
  No column-aligned table formatting — this is a 3-command CLI, not a data-dense tool.
- **D-06:** Frame listing shows **name + id only**. No asset count, owner, or contributor
  count in `status` — those richer fields belong to `inspect --frame <name|id>` (Phase 6),
  which targets a single frame. `status` is an account-level overview only.
- **D-07:** Config health check reports **pass/fail per required env var** only —
  `AURA_EMAIL: set` / `AURA_EMAIL: NOT SET`, same for `AURA_PASSWORD`. No dump of optional
  vars (`AURA_LOCALE`, `AURA_APP_IDENTIFIER`, `AURA_DEVICE_IDENTIFIER`) and — critically —
  **never print the password value**, not even partially redacted.

### Failure / Exit-Code Behavior
- **D-08:** If login fails for any reason (bad credentials, network error, API drift),
  `status` **prints what failed and exits non-zero**. This is a milestone-wide precedent:
  the CLI is meant to be scriptable/CI-friendly, consistent with SYNC-04's requirement that
  sync exits non-zero on failure. Establish this convention now so later commands don't
  need to retrofit it.
- **D-09:** If `AURA_EMAIL`/`AURA_PASSWORD` are unset, `status` **stops immediately after
  the config check** — it does not attempt login with known-missing credentials. Report
  `NOT SET` for the missing var(s) and exit non-zero without making a network call.

### Claude's Discretion
- Exact argparse subparser wiring/help text formatting, as long as `--help` works and the
  subcommand structure (D-02) is followed.
- Exact wording of the pass/fail and error messages (D-07/D-08/D-09), as long as they
  clearly state what's wrong and never leak the password.
- Whether `status` needs its own thin helper module or lives directly in `auraframes/cli.py`
  — small enough either way at this phase's scope.
- Ordering of config-check vs. login-attempt output lines, as long as config check runs
  first (D-09 depends on this ordering).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project & milestone scope
- `.planning/PROJECT.md` — Core Value (v2.0 shifts to proving the write path via a real
  CLI), Current Milestone section (target features for `status`/`inspect`/`sync`).
- `.planning/REQUIREMENTS.md` — **CLI-01** (CLI entrypoint packaged as a runnable command,
  distinct from `main.py`) and **CLI-02** (`status` command) are this phase's requirements.
- `.planning/ROADMAP.md` §"Phase 5: CLI Skeleton + Status" — goal + the 4 success criteria.

### v2.0 research (primary design input for this phase)
- `.planning/research/SUMMARY.md` §"Architecture Approach" — recommends `auraframes/cli.py`
  as a new `[project.scripts]` entrypoint, kept alongside (not replacing) `main.py`; §"Build
  order" places CLI skeleton + status first as the zero-risk phase.
- `.planning/research/STACK.md` — argparse vs. click comparison; confirms no new runtime
  dependency is required for the MVP.
- `.planning/research/FEATURES.md` — confirms `status` is table-stakes and zero-new-risk;
  confirms no quota/storage field exists on `Frame`/`User` (do not attempt to report it).

### Codebase analysis (structure/architecture already mapped)
- `.planning/codebase/STRUCTURE.md` — naming conventions, "Where to Add New Code" guidance
  (new workflow/orchestration methods go on `Aura`, not `*Api` classes).
- `.planning/codebase/ARCHITECTURE.md` — Facade pattern (`Aura` is the single entry point);
  confirms `login()` must be called before any other method; documents the existing
  Authentication Flow this phase's `status` command drives.

### Files that will change
- `pyproject.toml` — add `[project.scripts]` entry `aura-cli = "auraframes.cli:main"`.
- `auraframes/cli.py` (new) — argparse setup, `status` subcommand, `main()` entry function.
- `auraframes/aura.py` — reused as-is (`Aura.login()`, `frame_api.get_frames()`); no changes
  expected unless a small helper is needed.
- `auraframes/utils/settings.py` — reused as-is for reading `AURA_EMAIL`/`AURA_PASSWORD`
  presence.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Aura` facade (`auraframes/aura.py`) — `login()` and `frame_api.get_frames()` are already
  live-verified (v1.0/v1.1); `status` calls these directly, no new API logic needed.
- `Client`/`Aura` DI transport seam (v1.1) — `Aura(client=...)` can be used to drive `status`
  offline in tests via the existing `httpx.MockTransport` harness (`tests/offline.py`),
  without needing new test infrastructure.
- `auraframes/utils/settings.py` — already reads `AURA_EMAIL`/`AURA_PASSWORD` from env at
  import time; `status`'s config-health check reads the same source of truth.

### Established Patterns
- Facade-only orchestration: new workflow logic belongs on `Aura` or a thin CLI-layer
  function that calls `Aura`, not inside `*Api` classes (`STRUCTURE.md`).
- Fail-loud pattern established in v1.0 (`raise_for_status()` in `Client`, error-field
  raising in `accountApi.login`/`frameApi.get_assets`) — `status`'s non-zero-exit-on-failure
  (D-08) is a CLI-layer extension of this existing philosophy, not a new one.
- Credential resolution happens at **call time**, not import time (v1.1 fix for the HTTP 475
  null-creds bug) — `status`'s login attempt will naturally pick up `.env`-loaded creds the
  same way `main.py` does.

### Integration Points
- `auraframes/cli.py` is a **new** module sitting alongside `main.py`, not replacing it —
  both import and use `Aura`, but serve different purposes (demo vs. real CLI).
- `pyproject.toml` `[project.scripts]` is the packaging mechanism — confirmed absent today
  (checked directly), so this is a net-new section, not a modification of existing entries.

</code_context>

<specifics>
## Specific Ideas

- The user explicitly overrode both researched command-name suggestions (`aura`,
  `auraframes`) with **`aura-cli`** — a deliberate, more explicit/less collision-prone name.
  Downstream agents (researcher, planner) must use `aura-cli`, not `aura`, anywhere the
  installed command name is referenced.
- The non-zero-exit-on-failure convention (D-08) is meant to be a **milestone-wide
  precedent**, not just a Phase 5 detail — Phase 8's SYNC-04 (non-zero exit on sync failure)
  should follow the same pattern established here.

</specifics>

<deferred>
## Deferred Ideas

- **Frame asset count / contributor count in an account overview** — considered for
  `status` (D-06) but deferred entirely to `inspect --frame <name|id>` (Phase 6, CLI-03),
  which is scoped to single-frame detail.
- **Full optional-env-var diagnostic dump** (`AURA_LOCALE`, `AURA_APP_IDENTIFIER`,
  `AURA_DEVICE_IDENTIFIER`) — considered for the config-health check (D-07) but deferred;
  not needed for this phase's success criteria, could be a future `status --verbose` flag
  if ever requested.

None of the above expanded the phase scope — discussion stayed within CLI skeleton + status.

</deferred>

---

*Phase: 5-CLI Skeleton + Status*
*Context gathered: 2026-07-06*
