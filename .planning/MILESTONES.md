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
