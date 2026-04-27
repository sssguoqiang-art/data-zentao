---
name: zentao-data-assistant
description: Use when answering questions about ZenTao data, data-zentao, project/version progress, demand/task/Bug/todo analysis, database field meaning, report generation, or when Codex needs to query the company's ZenTao database without guessing table fields.
metadata:
  short-description: ZenTao database and report assistant
---

# Zentao Data Assistant

Use this skill to answer ZenTao questions through `data-zentao` and the bundled references. The skill exists so a new Codex session does not need local Obsidian notes or prior memory to understand the database.

## Default Workflow

1. Locate the `data-zentao` repository if the current directory is not already inside it.
2. Before using repository commands, run `data-zentao update-check` when the command is available. If it says the remote is ahead, tell the user and ask whether to update before continuing.
3. If the CLI is not installed, use `PYTHONPATH=src python3 -c "from data_zentao.cli import main; raise SystemExit(main())"` from the repository root.
4. If database config is missing, ask for the required `.env` values or tell the user which variables are missing. Do not write credentials into tracked files or final answers.
5. Classify the user request: project/version report, demand/task detail, person, department, Bug/quality, todo/measure, schema/field explanation, or free SQL analysis.
6. Read only the relevant reference files below, then call `data-zentao` commands or read-only SQL.
7. Treat command output as data material, not the final answer. The final answer must include AI judgment: conclusion, evidence, risk, and next action.

## Reference Loading

- For command selection and end-to-end workflows, read `references/query-playbook.md`.
- For table and field lookup, read `references/core-schema.md`.
- For project/version/demand/task questions, read `references/demand-task-project.md`.
- For Bug, testing, quality review, or Bug boundary questions, read `references/bug-quality.md`.
- For status, type, dictionary, and completion logic, read `references/status-and-dictionaries.md`.
- For daily, weekly, Bug boundary, and version review reports, read `references/report-rules.md`.
- For self-checks, known risky fields, and accuracy guardrails, read `references/self-check-and-risks.md`.

## Hard Rules

- Do not guess field meaning when a reference or schema command can verify it.
- Use read-only database access only. Never run write SQL or schema changes.
- Do not expose database credentials in files, commits, reports, or replies.
- Always map accounts to `zt_user.realname` when presenting people to business users.
- Explain uncertainty when a field is listed as risky or page-calibrated rather than fully confirmed.
- If a numeric ID is provided for a demand-like object, check all plausible IDs: `zt_pool.id`, `zt_pool.taskID`, `zt_task.id`, and `zt_story.id`.
- If the user asks for a report, prefer an existing `data-zentao` report command, then add AI validation and explanation.

## High-Frequency Commands

```bash
data-zentao check
data-zentao doctor
data-zentao schema --table zt_task
data-zentao schema --columns 延期
data-zentao query --format json --sql "SELECT id, name FROM zt_project LIMIT 20"
data-zentao daily-report
data-zentao weekly-summary
data-zentao weekly-report --product-name 游戏部 --project-name 游戏部
data-zentao demand-status "需求关键词或ID"
data-zentao person-tasks "姓名或账号"
data-zentao dept-risk "部门关键词"
data-zentao bug-review
data-zentao bug-boundary
data-zentao version-review
data-zentao version-delay --version-id 405
```

## When Accuracy Matters

Use a two-pass pattern:

1. First pass: retrieve raw data with IDs, versions, statuses, owners, and dates.
2. Second pass: verify the join path and business meaning against the references.
3. Only then write the final business-facing conclusion.

If the answer depends on a currently unsupported command, use `schema + query` and state the exact SQL口径 in concise Chinese.
