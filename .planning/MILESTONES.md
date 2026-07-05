# Milestones

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
