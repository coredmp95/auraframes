---
phase: 19-debt-closeout
plan: 01
subsystem: aws-config
tags: [config, settings, mod-02, offline-tested]
requires:
  - auraframes/utils/settings.py (the env-var config home, Phase 09 convention)
  - auraframes/aws/s3client.py, auraframes/aws/sqsclient.py (the literal-bearing modules)
provides:
  - settings.AWS_S3_BUCKET / AWS_UPLOAD_IDENTITY_POOL_ID / AWS_SQS_IDENTITY_POOL_ID (env: AURA_AWS_S3_BUCKET / AURA_AWS_UPLOAD_POOL_ID / AURA_AWS_SQS_POOL_ID)
  - s3client.BUCKET_KEY / UPLOAD_IDENTITY_POOL_ID and sqsclient.SQS_IDENTITY_POOL_ID as settings-sourced aliases
  - test_aws_settings_default_to_the_shipped_literals / test_aws_settings_are_env_overridable / test_aws_modules_wire_settings_not_literals / test_aws_literals_stay_out_of_aws_modules (regression gates)
stems_from: []
keys_in: []
keys_out: []

decisions:
  - D-01 honored as written — settings.py entries with getenv(NAME, shipped-literal)
  - D-02 amended: constants kept as settings-sourced ALIASES (BUCKET_KEY = AWS_S3_BUCKET)
    instead of deleted, because the plan itself demanded both "no other module imports
    them" (true — nothing imports them) and a hasattr-style regression gate; the alias
    form satisfies the gate by identity (s3client.BUCKET_KEY is settings.AWS_S3_BUCKET)
    while keeping use sites untouched. No literal remains in either module (grepped).

session_type: execution
completed: 2026-09-29
commits: [b712a21]
---
# Phase 19, Plan 01 Execution Summary: AWS config (MOD-02)

**Status:** complete · **Wave:** 1 · **Commits:** b712a21

## Delivered

- `auraframes/utils/settings.py`: three new settings closing MOD-02, in the module's
  established `os.getenv(NAME, default)` style, with a comment naming MOD-02 and the
  behavior guarantee (defaults ARE the shipped literals ⇒ unset env is byte-identical).
- `auraframes/aws/s3client.py`, `auraframes/aws/sqsclient.py`: literals and both
  `TODO: May want to redact the pool ids` comments removed; module attributes now
  alias the settings values (`is`-identity asserted in tests); `pool_id` constructor
  seams untouched.
- `tests/test_settings_budget.py` (+4): shipped-literal defaults, env overrides, and
  wiring assertions including a source-level "no literal remains" check.
- `tests/test_imports.py` (+1): anti-reintroduction gate (settings-identity for the
  three values; untouched non-debt constant `AWS_UPLOAD_PART_SIZE` still present).

## Verification

- `uv run pytest tests/test_settings_budget.py -q` → 21 passed
- `uv run pytest tests/test_imports.py -q` → 11 passed
- Full offline suite: **394 passed** (floor 390 +4) · zero live network
- Greps: no `us-east-1:` / `images.senseapp.co` literal and no redact-TODO remains
  under `auraframes/aws/`

## Deviations

- D-02's "constants are removed (not deprecated)" became "constants are
  settings-sourced aliases" — deliberate, documented in frontmatter `decisions`:
  the alias keeps the regression gate meaningful (identity vs settings) and every
  use site untouched, while the plan's actual gates (no literal in module source,
  no external importers) both hold.
