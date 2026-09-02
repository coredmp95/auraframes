# Milestones

## v2.0 Directory-to-Frame Sync (Shipped: 2026-09-02)

**Phases completed:** 6 phases, 17 plans, 43 tasks

**Key accomplishments:**

- Packaged `aura-cli` console script with an argparse subcommand skeleton and a `status` command that reports config health, logs in via the existing Aura facade, and lists account frames as name + id, all covered by an offline test suite driven through the v1.1 `Client`/`Aura` DI seam.
- Added a `--debug` flag to `aura-cli status` and a CLI-side loguru re-initialization helper that suppresses the two overlapping stderr sinks `Aura._init_logger()` accumulates, closing the only diagnosed UAT gap for Phase 5 without touching the frozen `aura.py`/`main.py`.
- `aura-cli inspect --frame <name|id>` resolving frames by case-insensitive name substring with exact-id fallback, displaying owner/contributor/asset-count metadata and the first 10 photos, fully proven offline via the existing `Aura(client=...)` DI seam.
- Confirmed live that `md5_hash` is populated for all 101 pre-existing photo assets but null for all 5 video assets on a real frame — content-hash diffing is viable for Phase 7's photo sync with no fallback needed, but videos would need a local-manifest fallback if they ever enter scope.
- Pure offline dry-run diff engine (`auraframes/sync.py`): recursive image scanner with base64-MD5 dedup, plus a `compute_plan()` diff function that classifies frame assets into upload/delete/unchanged/frame_no_hash by content hash alone.
- `aura-cli sync <dir> --frame <name|id>` prints a full, untruncated upload/delete/unchanged dry-run report by wiring Phase 6's frame resolution to Phase 7-01's compute_plan() engine — no apply/execute path exists.
- Confirmed live that local `S3Client.get_md5` and the frame's reported `md5_hash` use byte-identical base64-MD5 encoding, closing out the last open risk before the dry-run diff engine is trusted.
- Added AssetPartial model, made all four write/delete endpoints raise RuntimeError on API error/nonzero number_failed, and parameterized Aura.get_sqs(frame_id) to remove the hardcoded test-frame queue id — all offline-tested, no live API calls.
- Added `execute_plan()` and `ExecutionResult` to `auraframes/sync.py` — the sole mutating counterpart to `compute_plan()`, performing the real upload round-trip and `remove_asset` disassociation with uploads-before-deletes ordering and per-item continue-past-failure, proven entirely offline with injected S3/SQS fakes.
- Added `--apply`/`--yes` flags and a D-01..D-04 confirmation gate to `aura-cli sync`, wiring Plan 02's `execute_plan()` behind it with real `S3Client()`/`SQSClient()` construction, a D-10 separated success/failure summary, and non-zero exit on any failure — all proven offline with monkeypatched AWS clients and `execute_plan`.
- Proved the write path live for the first time in this codebase's history: the upload round-trip, `remove_asset`, and `delete_asset`'s blast radius were all confirmed against a real Aura account and frame, with `remove_asset` reaffirmed as `--apply`'s safe default and `delete_asset` confirmed broader-scoped and correctly left unwired.
- New standalone `auraframes/ratelimit.py` module — injected-clock `WriteBudget` token bucket with JSON persistence, and a fail-open `check_geo` pre-flight guard — fully offline-tested (19 new tests), zero existing source touched.
- `WriteBudget`/`check_geo` (from Plan 09-01) wired into `execute_plan` and the CLI as the default protection for both `push --apply` and `sync --apply` — env config, four `push` override flags, and two new clean-message exception branches, with the whole 120+ test pre-existing suite staying green.
- The hide mechanism is confirmed live and non-destructive — but the visibility flag lives in `asset_settings`, not on `Asset.selected`, which corrects the read signal Plan 10-02 was going to build on.
- The diff engine can now see visibility: hidden assets stay in the listing, `asset.selected` finally means what it says, and every frame asset is classified re-show / unchanged / removal-candidate / already-hidden.
- `execute_plan` now hides by default, re-shows restored photos under every mode, and can only reach the irreversible primitive if a caller names it.
- `sync` now hides by default, names the verb it will actually run, and makes irreversible deletion something you have to read a number to do.

---

## v1.0 Revive & Verify (Shipped: 2026-06-30)

**Phases completed:** 3 phases, 5 plans, 13 tasks

**Key accomplishments:**

- Migrated the broken UTF-16 requirements.txt to a uv-managed pyproject.toml, resolved 37 packages on Python 3.14 (all cp314 wheels, no sdist builds), and committed uv.lock for reproducible installs.
- Migrated the entire `auraframes` model layer to pydantic v2 — AllOptional metaclass replaced by a `make_partial` create_model factory, `pydantic_encoder` replaced by a `model_dump(mode=json)` serializer, `@validator` ported to `@field_validator` — with a committed pytest import smoke test guarding it.
- Credential-gated pytest harness with fail-loud transport (raise_for_status) and on-disk secret redaction, plus READ-01 login and READ-02 frame-listing live tests that skip cleanly without credentials.
- Parametrized the real get_all_assets cursor helper and hardened the asset-error/EXIF-write/geocoder trust edges, then added READ-03 (multi-page drain proven by len==total) and READ-04 (download one image, read DateTimeOriginal back from disk) as credential-gated live tests that skip cleanly without creds.
- Facade-only read-path demo (main.py), README reconciled to verified reality with uv commands + correct env vars, and a repo-root VERIFICATION-REPORT.md backed by a fresh 2026-06-29 live run (4 passed, 9 deselected).

---

## v1.1 Client Transport Seam (Shipped: 2026-07-05)

**Phases completed:** 1 phase, 3 plans, 6 tasks

**Key accomplishments:**

- Added an additive `Client(transport=...)` / `Aura(client=...)` dependency-injection seam so the whole `*Api`/`Aura` read-path stack can be driven through a fake transport — zero-arg callers (`main.py`, existing tests) stay unaffected — and closed the long-standing `# TODO: Can probably use DI` in `aura.py`.
- Authored 5 sanitized, entirely synthetic fixture JSON files (login, frames, 2-page assets, error envelope) plus a dedicated pytest that hydrates every fixture against `User`/`Frame`/`Asset` to guard against future field-trim regressions.
- Built a reusable offline test harness (`tests/offline.py`) — an `httpx.MockTransport` router keyed by resolved path with a per-test overrides mechanism — plus a 5-test offline mirror of `test_read_path.py` covering login headers, frame hydration, pagination drain, and both error-raise paths.
- Lifted most of `test_read_path.py`'s assertions off the live network: default `pytest` now exercises login, listing, pagination, and error handling with zero credentials/network, while the `@live` suite stays byte-identical and remains the drift oracle.
- Verified: 7/7 must-haves passed, UAT 8/8 passed with 0 issues.

**Known gaps carried to v2.0:** Architecture-review candidates #2 (authenticated value) and #4 (injected config) — the remaining "lift tests off the live network" slice; pre-existing `Aura._init_logger()` loguru sink leak on repeated construction (flagged by code review, not fixed).

---
