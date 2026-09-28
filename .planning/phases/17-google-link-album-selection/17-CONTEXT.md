# Phase 17: Google Link & Album Selection - Context

**Gathered:** 2026-09-28
**Status:** Ready for planning

<domain>
## Phase Boundary

The user links Google once through the **selected mechanism** (browser-automation:
dedicated-profile cookie bootstrap + internal `snAcKc` RPC, with the shared-link page
as bootstrap stage — per the signed `16-DECISION-RECORD.md`), names an album at
**album granularity**, and `aura-cli` can **enumerate every photo inside it** (plus
its exact disk weight). Production code migrates from `probes/` instruments into
`auraframes/google/`, wired into the existing CLI with a Google-aware `status`.

Delivers: `google-link` (bootstrap/re-link), `google-album` (select + enumerate),
extended `status`, album listing by name-or-link, `auraframes/google/` package fully
offline-tested (TEST-02). Does NOT deliver: sync/mirror (Phase 18), multi-album
configuration semantics beyond selection, multi-account support.

</domain>

<decisions>
## Implementation Decisions

### Surface CLI
- **D-01:** Commandes dédiées — `aura-cli google-link` (bootstrap interactif, re-link =
  même commande), `aura-cli google-album <nom|lien|id>` (sélection + énumération),
  `status` étendu avec l'état Google (lié, quel compte, session utilisable). Séparé
  du `sync` existant pour la lisibilité. — **Reversibility:** reversible — new
  subcommands; renaming later touches only the parser + docs.
- **D-02:** `status` n'imprime **jamais** le cookie/token — email du compte + indicateur
  de session seulement (LGS-03 verbatim).

### Localisation du code
- **D-03:** Le code production vit dans **`auraframes/google/`** (client RPC httpx,
  bootstrap cookie, parseurs ds:1/snAcKc), tests offline via transports injectés —
  l'emplacement esquissé par `ARCHITECTURE.md`. Les `probes/` restent des instruments
  de diagnostic committés. — **Reversibility:** costly — once the CLI and Phase 18
  sync import from this package, moving it touches every call site.

### Posture multi-comptes
- **D-04:** **Mono-compte** — coffre unique, `status` affiche l'email lié. Le
  multi-comptes (paramètre `--account`, coffres par compte) va en Future (GSF), pas
  une surface maintenant pour un besoin non démontré.

### UX de sélection d'album
- **D-05:** Sélection par **nom OU lien/ID**. Par nom : résolution via la liste des
  albums partagés du compte ; ambiguïté → liste numérotée + choix (jamais de picking
  à la photo, LGS-04). Lien/ID direct accepté tel quel.
- **D-06:** L'énumération renvoie **tous** les items (continuation `snAcKc` jusqu'à
  épuisement) et le **poids disque exact** via `measure_sizes()` (1-byte Range GETs) —
  le compte renvoyé doit égaler ce que l'UI Google Photos affiche (LGS-05, prouvé
  794/794 en phase 16).

### Claude's Discretion
- Structure interne de `auraframes/google/` (fichiers, nommage), forme du client
  injectable (transport), placement exact des flags CLI, format du résumé
  d'énumération (table vs lignes), détails de la gestion d'ambiguïté de nom.
- La réutilisation du coffre existant `~/.config/auraframes/probes/google-cookies.json`
  vs un chemin « production » (`~/.config/auraframes/google-cookies.json`) — choisir
  avec migration douce, en gardant la denylist structurelle INTACTE (D-06 phase 16).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Mechanism decision (the gate)
- `.planning/phases/16-local-mechanism-spike-decision/16-DECISION-RECORD.md` — the
  signed selection (browser+RPC, shared-link bootstrap stage) this phase builds on
- `.planning/phases/16-local-mechanism-spike-decision/16-LIVE-FINDINGS.md` — every
  live proof: snAcKc shape, 300/page, full-jar cookie requirement, Content-Range
  sizing, fidelity MATCH, get_assets drift note

### Requirements & roadmap
- `.planning/REQUIREMENTS.md` — LGS-02..05, TEST-02 verbatim; Out of Scope (closed
  dead ends not to re-open)
- `.planning/ROADMAP.md` §Phase 17 — success criteria 1-5 (the planner's checklist)

### Working code to migrate (proven live, tests included)
- `probes/browser_bootstrap.py` — bootstrap + list subcommands; full-jar httpx client;
  snAcKc continuation loop (the exact code that enumerated 794/794)
- `probes/shared_link_probe.py` — `parse_af_initdata` (ds:1 parser), `measure_sizes()`
  (disk weight via Range GETs), `download_original` (=d + frame's get_md5)
- `probes/cookie_vault.py` — the 0600 vault + structural denylist to preserve as-is
- `probes/rpc_capture.py` — diagnostic instrument for re-learning RPC shapes on Google
  redeploys (stays in probes/)
- `tests/test_probe_browser.py`, `tests/test_probe_shared_link.py` — offline tests to
  migrate alongside the code into the package's test modules

### Architecture & patterns
- `.planning/research/ARCHITECTURE.md` — the GoogleClient/cookie_bootstrap seam sketch
  this package should mirror
- `auraframes/cli.py` — existing subcommand conventions (build_parser, run_*)
- `tests/offline.py` — the injectable-transport harness pattern (make_router/overrides)
- `auraframes/models/asset.py` — Asset model shape for future Phase 18 integration

### Research
- `.planning/research/ALBUM-ACCESS.md` §1 — share-page structure (ds:1 item shape,
  `=d` convention, URL stability)
- `.planning/research/ALBUM-ACCESS-V4-ADDENDUM.md` — Q1 pagination prior-art absence
  (now superseded by the captured snAcKc), Q2 cookie-expiry framing, Q3 fidelity

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `probes/browser_bootstrap.py list` — the proven enumeration loop (full-jar client,
  at-token extraction, verbatim-body replay with token swap, exhaustion detection):
  becomes `auraframes/google/`'s core listing method nearly verbatim
- `probes/shared_link_probe.py` `parse_af_initdata` — dual-purpose parser (share page
  AND RPC response payloads share the item shape `[id, [baseUrl, w, h, ...], ts]`)
- `measure_sizes()` — Content-Range sizing, live-proven (album C = 86.6 MiB exact)
- `probes/cookie_vault.py` — the structural denylist must be carried over unchanged
  (sync paths can never read cookies); vault path may move but the boundary stays

### Established Patterns
- Fail-loud error convention (RuntimeError with context, no silent passes)
- Redaction discipline (`redact_link`/`redact_tokens`) at every print/commit site
- `tests/offline.py` injected-transport testing; fixtures fully synthetic
- CLI: argparse subcommands via `build_parser()`, `run_<name>` handlers, `resolve_frame`
  style resolution — `google-album` should mirror `resolve_frame`'s substring-match
  + ambiguity UX for album names

### Integration Points
- `aura-cli status` (`run_status`) gains the Google link section
- `Client`/`FrameApi` DI seam shape (`transport=`) is the model for the Google client
- Write budget (WriteBudget) untouched this phase (reads only; no frame writes)

</code_context>

<specifics>
## Specific Ideas

- The album name resolution should also match **substring** (like `resolve_frame`)
  before falling back to numbered-choice ambiguity — consistent CLI muscle memory.
- `google-album` output should print: resolved album id (redacted shape), item count,
  disk weight, and a per-item table — the exact fields Phase 18's planner needs for
  cache/budget design.
- Re-link is the same `google-link` command (LGS-02) — the command must detect an
  expired session and guide the interactive re-bootstrap without other flags.

</specifics>

<deferred>
## Deferred Ideas

- Multi-account support (`--account`, per-account vaults) — Future (GSF), per D-04.
- Cache/manifest design, mirror semantics, hide-on-removal — Phase 18's scope entirely.
- Scheduled/unattended sync — GSF-02, re-evaluated after Phase 18.
- Videos enumeration (`=dv`) — videos are excluded from sync scope (carried replan
  decision); if ever needed, the RPC payload likely carries them with a different shape.

</deferred>

---

*Phase: 17-Google Link & Album Selection*
*Context gathered: 2026-09-28*
