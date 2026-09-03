---
schema_version: 1
open_count: 1
waived_count: 0
fixed_count: 0
total_count: 1
last_updated: 2026-09-03T08:37:04.342Z
---

# Broken Windows Ledger

> Cross-phase defect register. With `workflow.windows_enforce` enabled, `/gsd-ship` blocks while `open_count > 0`.
> Waive with `gsd-tools windows waive <id> "<reason>"` (reason required).
> Mark fixed with `gsd-tools windows fixed <id>`.

| id | phase | kind | file | line | description | status | reason | recorded_at | resolved_at |
|----|-------|------|------|------|-------------|--------|--------|-------------|-------------|
| 1 | 11 | deviation | auraframes/api/frameApi.py |  | Task 3 acceptance criterion expected 'raise RuntimeError' count of 4 in frameApi.py; actual count (unchanged before/after this plan) is 7 -- planner miscount, not a defect. frameApi.py was never modified by this plan. | open |  | 2026-09-03T08:37:04.342Z |  |

````json
[
  {
    "id": 1,
    "kind": "deviation",
    "phase": "11",
    "file": "auraframes/api/frameApi.py",
    "line": null,
    "description": "Task 3 acceptance criterion expected 'raise RuntimeError' count of 4 in frameApi.py; actual count (unchanged before/after this plan) is 7 -- planner miscount, not a defect. frameApi.py was never modified by this plan.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-09-03T08:37:04.342Z",
    "resolved_at": null
  }
]
````
