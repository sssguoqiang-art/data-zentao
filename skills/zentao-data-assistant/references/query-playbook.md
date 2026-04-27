# Query Playbook

This file maps common user intents to safe `data-zentao` workflows.

## First Checks

Run these when starting from a fresh install or when results look suspicious:

```bash
data-zentao update-check
data-zentao check
data-zentao doctor
```

If the CLI is not installed, run from the repository root:

```bash
PYTHONPATH=src python3 -c "from data_zentao.cli import main; raise SystemExit(main())" check
```

## Intent Map

| User intent | Preferred command | References to read |
|---|---|---|
| Generate daily report | `data-zentao daily-report` | `report-rules.md`, `demand-task-project.md` |
| Generate weekly summary | `data-zentao weekly-summary` | `report-rules.md` |
| Single project weekly report | `data-zentao weekly-report --product-name ... --project-name ...` | `report-rules.md`, `demand-task-project.md` |
| Version review | `data-zentao version-review` | `report-rules.md`, `bug-quality.md` |
| Bug boundary/pre-classification | `data-zentao bug-boundary` | `bug-quality.md`, `report-rules.md` |
| Demand status/detail | `data-zentao demand-status "..."` plus SQL verification if numeric ID | `demand-task-project.md` |
| Person workload | `data-zentao person-tasks "..."` | `demand-task-project.md`, `status-and-dictionaries.md` |
| Department risk | `data-zentao dept-risk "..."` | `demand-task-project.md`, `bug-quality.md` |
| Version delay | `data-zentao version-delay --version-id ...` | `demand-task-project.md`, `status-and-dictionaries.md` |
| Bug review/detail | `data-zentao bug-review` or read-only SQL | `bug-quality.md` |
| Todo/measure | `data-zentao todos`, `data-zentao measures` | `core-schema.md`, `status-and-dictionaries.md` |
| New/free-form question | `schema`, then `query` | Relevant domain reference |

## Project Scope

Known major scopes:

| Business scope | Product name | Project name | Notes |
|---|---|---|---|
| Platform | `平台部` | `平台部` | Default project in many existing commands |
| Game | `游戏部` | `游戏部` | Supported by `weekly-report` when explicitly passed |
| SG | `SG` | `SG项目` | Supported by project/product lookup, not always included in legacy summary |
| EGC/FG/AI companion | Varies | Varies | Query `zt_product`, `zt_project`, and `zt_projectproduct` before reporting |

Do not assume a user saying "all projects" means only platform and game. Query active projects/products or use an explicit project list.

## Seven Management Dimensions

When self-checking capability coverage, verify these dimensions separately:

| Dimension | Expected behavior |
|---|---|
| Management/project reports | Can summarize multiple projects, current versions, delays, active Bug, and next-version readiness |
| Different project scopes | Can handle platform, game, SG, and future project scopes without hardcoding one project |
| Department view | Can summarize a department's tasks, demands, Bug, todos, delays, and cross-project risks |
| Person view | Can list and judge a person's current tasks, Bug, todos, overdue work, and abnormal workload |
| Specific demand/task | Can identify by title or all plausible numeric IDs, then analyze status, owner, version, child tasks, and risk |
| Bug view | Can summarize all/version/project/person Bug status, severity, responsibility, cause, and review closure |
| Delay/anomaly view | Can detect overdue open tasks, late-finished tasks, explicit delay records, no owner, no deadline, stale status, and abnormal remaining effort |

## SQL Safety

Use only `SELECT`, `SHOW`, `WITH`, `DESCRIBE`, or `EXPLAIN`. Add explicit `LIMIT` unless producing a controlled aggregate. Prefer JSON output when the next step is AI reasoning:

```bash
data-zentao query --format json --limit 200 --sql "SELECT ..."
```

## Final Answer Standard

For business users, do not paste raw command output as the final answer. Include:

- Direct conclusion.
- Key IDs and counts.
- Scope: project/version/date/status filters.
- Risks or anomalies.
- Suggested next action.
