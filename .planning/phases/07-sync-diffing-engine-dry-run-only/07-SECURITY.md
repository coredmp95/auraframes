---
phase: 07
slug: sync-diffing-engine-dry-run-only
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: 2026-07-07
---

# Phase 07 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| user → filesystem | User-supplied directory path is recursively walked and each eligible file's bytes are read for hashing (untrusted local input: symlink loops, unexpected file types, large trees). | Local file bytes → in-process hash only (bytes never leave the process). |
| user → CLI | User supplies `dir` (local path, scanned recursively) and `--frame` (resolved against account frames). | CLI args → `scan_directory`/`resolve_frame`. |
| network → app | Frame asset metadata (`md5_hash`, `id`, `taken_at`) fetched via the already-live-verified read path (`get_frames`/`get_all_assets`); consumed read-only. | Frame asset JSON → `compute_plan` (read-only). |
| operator → live API | One-time authenticated read (SYNC-02 validation) against a real account/frame using env-supplied credentials. | Env credentials → live API; result → project docs (no secrets). |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-07-01 | Denial of Service / Tampering | `scan_directory` recursive walk | medium | mitigate | `Path.rglob` does not follow directory symlinks; code additionally checks `p.is_symlink() or not p.is_file()` before reading (auraframes/sync.py:57) — stronger than the plan called for. Non-eligible files are counted, never erroring. Bounds traversal to real files under the user's own directory. | closed |
| T-07-02 | Information Disclosure | Reading arbitrary local file bytes | low | accept | Files read are exactly those under the path the invoking user chose to scan; only a hash is retained, no bytes leave the process. | closed |
| T-07-03 | Elevation / Tampering (write path) | Absence of any mutating primitive in `sync.py` | high | mitigate | `auraframes/sync.py` contains only `scan_directory`/`compute_plan` — no upload/delete/S3/SQS call. Grep of `sync.py` for mutating tokens (`put_object`, `upload_file`, `select_asset`, `remove_asset`, `delete_asset`, `.post(`, `.put(`, `.delete(`) returns zero matches. | closed |
| T-07-04 | Elevation / Tampering (write path) | `run_sync` command surface (`cli.py`) | high | mitigate | No `--apply`/`--yes` flag exists on the `sync` subparser (`auraframes/cli.py:41-43`); `run_sync` calls only `scan_directory`/`compute_plan`/`print`. Same grep gate covers `cli.py` — zero mutating-call matches. Dry-run is structural, not a runtime flag check. | closed |
| T-07-05 | Information Disclosure | Plan output (`run_sync` print) | low | mitigate | Delete candidates print as `{asset.id} (taken {asset.taken_at_dt})` only (auraframes/cli.py:288) — no filename, no hash. Credentials never printed. | closed |
| T-07-06 | Denial of Service | Scan on a huge/mistyped directory | low | accept | Dry-run only prints a plan; nothing executes, so a mis-pointed directory yields a reviewable plan, not an irreversible action. Mass-delete circuit-breaker deferred to v2/Phase 8 scope. | closed |
| T-07-07 | Information Disclosure | Live validation run (SYNC-02 spike) | low | mitigate | Credentials sourced from env, never printed. STATE.md/PROJECT.md record only a frame id (`c063b384-…`) and an equal/not-equal ("Unchanged: 1") result — no secrets, no original photo content. | closed |
| T-07-08 | Elevation / Tampering (write path) | Live validation method | high | mitigate | Validation used `aura-cli sync` dry-run (read-only, no `--apply`/`--yes` path) — confirmed in STATE.md's resolved entry. No upload/delete/mutating call was made. | closed |
| T-07-SC | Tampering | pip/uv installs (all 3 plans) | low | accept | No new packages introduced across any of the three plans — hashing/scanning/validation all reuse stdlib (`hashlib`/`base64` via existing `get_md5`, `pathlib`) and the existing CLI. No install task. | closed |

*Status: open · closed · open — below {block_on} threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-07-01 | T-07-02 | Local file bytes read are strictly those under the user-chosen scan path; only a hash is retained in-process — no exfiltration surface. | Plan 07-01 author | 2026-07-07 |
| AR-07-02 | T-07-06 | Dry-run has no execute path this phase; a mis-scanned directory only produces a reviewable plan. Circuit-breaker for mass deletes is explicitly deferred to Phase 8/v2. | Plan 07-02 author | 2026-07-07 |
| AR-07-03 | T-07-SC | No new third-party packages introduced by any of the three phase plans. | Plan 07-01/02/03 authors | 2026-07-07 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-07 | 9 | 9 | 0 | /gsd-secure-phase (L1 grep-depth, asvs_level=1, short-circuit) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-07-07
