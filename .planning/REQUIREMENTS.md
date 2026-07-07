# Requirements: Aura Frames Python Client — Revive & Verify

**Defined:** 2026-07-05
**Core Value (this milestone):** Prove the write path the same way v1.0/v1.1 proved the read path, and turn that proof into a real usable capability — mirroring a local photo directory to an Aura frame — rather than another internal-only verification pass.

## v1 Requirements

Requirements for milestone v2.0 (Directory-to-Frame Sync). Each maps to roadmap phases.

### Write-Path Verification

- [ ] **WRITE-01**: Verify the image upload round-trip live (`select_asset` → S3 → SQS confirm → `batch_update`) against a real account/frame
- [ ] **WRITE-02**: Verify `remove_asset`'s real behavior live against a disposable test asset (confirm it disassociates from the frame without deleting from S3/Glacier, per its docstring's claim)
- [ ] **WRITE-03**: Verify `delete_asset`'s real behavior live, to confirm or refute its broader/unknown deletion scope
- [ ] **WRITE-04**: Fix the hardcoded frame ID in the SQS upload-confirmation lookup (`Aura.get_sqs`) so uploads work correctly for any frame, not just the original test frame
- [ ] **WRITE-05**: Extend fail-loud error handling (raise on API `error` field) to the write/delete endpoints, matching the existing read-path pattern (`get_assets` already does this; write endpoints currently only report a bare `number_failed` count)

### CLI Foundation

- [x] **CLI-01**: CLI entrypoint packaged as a runnable command, distinct from the existing `main.py` facade-demo script
- [x] **CLI-02**: `status` command reports config/auth health (are `AURA_EMAIL`/`AURA_PASSWORD` set? does login succeed? which account?) plus account info (frames on the account)
- [x] **CLI-03**: `inspect --frame <name|id>` command lists photos currently on the frame (id/filename/date) plus frame metadata (name, owner, contributor count, asset count)
- [x] **CLI-04**: Frame targeting works by human-readable name or opaque ID, with a clear error if a name match is ambiguous

### Sync Engine

- [x] **SYNC-01**: `sync <dir> --frame <name|id>` computes a full-mirror plan (upload new / delete gone-locally / unchanged) by comparing local file content-hashes to frame asset `md5_hash` values, without executing anything — dry-run by default
- [x] **SYNC-02**: Content-hash comparison uses the same base64-MD5 convention as the existing S3 upload path (`S3Client.get_md5`), validated against a real downloaded asset before being trusted for diffing
- [ ] **SYNC-03**: `sync ... --apply` (or `--yes`) executes the computed plan for real: uploads new local files, removes frame photos no longer present locally (via `remove_asset`, the safer of the two delete primitives)
- [ ] **SYNC-04**: Sync plan output clearly lists planned upload/delete/unchanged counts and the CLI exits non-zero on any execution failure

## v2 Requirements

Deferred to a future release. Tracked but not in the current roadmap.

### Sync Engine (deferred)

- **SYNC-05**: `--max-delete` circuit breaker to guard against a mass-delete triggered by a misconfigured or empty local directory
- **SYNC-06**: `--json` machine-readable output for scripting

### Reverse Engineering / Hardening (carried forward from v1.0/v1.1)

- **MOD-01**: Async HTTP client migration
- **MOD-02**: Config-ize AWS pool IDs / bucket name
- **MOD-03**: Typed exception hierarchy
- **MOD-04**: Fix `Aura._init_logger()` loguru sink leak on repeated construction
- **TEST-01**: Complete the remaining "lift tests off the live network" slice — architecture-review candidates #2 (authenticated value) and #4 (injected config)

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Watch mode / background daemon sync | Too risky to run unattended against a write path that has never been exercised live before this milestone |
| Bidirectional sync (frame → local pull) | Not requested; this milestone is local-directory-is-source-of-truth only |
| Storage/quota reporting in `status`/`inspect` | Confirmed absent from the API's data model (no such field on `Frame` or `User`) — reporting `Frame.num_assets`/`contributors` instead |
| Local manifest/state file for sync tracking | Only added if the Phase 6 live spike shows `md5_hash` isn't populated on read for pre-existing assets; not committed scope upfront |
| Device-on-LAN / MITM traffic capture | Cloud-API is the goal; device recon is a later reverse-engineering milestone (carried forward from v1.0) |
| Frame rendering / firmware reverse-engineering | Advanced track, depends on a working baseline first (carried forward from v1.0) |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CLI-01 | Phase 5 | Complete |
| CLI-02 | Phase 5 | Complete |
| CLI-03 | Phase 6 | Complete |
| CLI-04 | Phase 6 | Complete |
| SYNC-01 | Phase 7 | Complete |
| SYNC-02 | Phase 7 | Complete |
| SYNC-03 | Phase 8 | Pending |
| SYNC-04 | Phase 8 | Pending |
| WRITE-01 | Phase 8 | Pending |
| WRITE-02 | Phase 8 | Pending |
| WRITE-03 | Phase 8 | Pending |
| WRITE-04 | Phase 8 | Pending |
| WRITE-05 | Phase 8 | Pending |

**Coverage:**

- v1 requirements: 13 total
- Mapped to phases: 13 ✓
- Unmapped: 0 ✓ (100% coverage — every v1 requirement maps to exactly one phase)

---
*Requirements defined: 2026-07-05*
*Last updated: 2026-07-05 after roadmap creation — all 13 v1 requirements mapped to Phases 5-8*
