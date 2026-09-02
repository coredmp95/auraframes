# Deferred Items — 260708-dt9

## Pre-existing live-test failure: `tests/test_read_path.py::test_read_03_pagination`

**Status:** Out of scope — not fixed.

**Observed:** `uv run pytest -q` (unfiltered, per the plan's `<verification>` block) shows
`1 failed, 100 passed` — the failure is in `test_read_03_pagination`, a `@pytest.mark.live`
test that hits the real Aura API using `AURA_EMAIL`/`AURA_PASSWORD` from the environment.

**Confirmed pre-existing and unrelated to this task's changes:** reproduced the same failure
with this task's commits (`b471189`, `dd92c9e`) stashed out via `git stash` — the test fails
identically on the pre-dispatch base commit `9239099`. This task only touched
`auraframes/sync.py`, `auraframes/cli.py`, `tests/test_execute_plan.py`, and
`tests/test_cli_apply.py` — none of which affect the pagination path this test exercises.

**Likely cause:** the live account's first frame currently has an asset count/pagination
state that this READ-03 assertion doesn't hold for (a moving-target live-API issue per
CLAUDE.md's "verification is inherently against a moving target" constraint), not a code
defect introduced here.

**Correct verification scope for this task:** the project's own pytest marker convention
(`pyproject.toml`: `"live: hits the live Aura API ... Deselect with -m 'not live'."`) is to
run `uv run pytest -q -m "not live"` for the offline suite. That command is green:
`97 passed, 4 deselected`.

**Action:** none taken here (SCOPE BOUNDARY — only auto-fix issues directly caused by this
task's changes). Left for a separate task/investigation if the live pagination test needs
attention.
