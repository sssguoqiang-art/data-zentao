# Report Rules

Read this before generating daily reports, weekly summaries, Bug boundary reports, or version review reports.

## General Report Rules

- Prefer existing `data-zentao` report commands when available.
- Treat generated Markdown as a draft data artifact; final user-facing answer should still include AI validation.
- Keep scope explicit: project/product, version ID/name, date range, status filters.
- Do not hide missing data. If a command cannot include a project, say so and propose the exact fix or query.
- Do not use unconfirmed fields as strong conclusions. Put them under "口径风险" or "需确认".

## Daily Report

Preferred command:

```bash
data-zentao daily-report --date YYYY-MM-DD
```

Daily report should include:

- Current version and whether it is release day.
- Demand overview.
- Department progress.
- Delays and due-today items.
- Test/Bug concerns.
- Online/external Bug concerns when available.
- Next version preparation.

Important口径:

- Current version is date-based: `begin <= date <= end`.
- Release day means current version `end == date`.
- Task deadline uses `zt_task.deadline`.
- Do not replace task deadline with demand pool delivery date.
- Progress is calculated from consumed/left, not a dedicated task progress field.

## Weekly Summary

Preferred command:

```bash
data-zentao weekly-summary --start YYYY-MM-DD --end YYYY-MM-DD --date YYYY-MM-DD
```

Legacy `weekly-summary` currently defaults to platform and game projects. If the user asks "all projects" or mentions SG/FG/EGC, do not assume the legacy default is complete. Use `weekly-report` per project or query the active project list.

Single project weekly report:

```bash
data-zentao weekly-report --product-name SG --project-name SG项目 --start YYYY-MM-DD --end YYYY-MM-DD
```

Weekly report should include:

- Current version.
- New/finished/closed tasks during the period.
- New/resolved/closed Bug during the period.
- Current open tasks and active Bug.
- Overdue open tasks.
- Next version readiness when available.
- AI risk summary and suggested actions.

## Bug Boundary

Preferred command:

```bash
data-zentao bug-boundary --version-id <version_id>
```

Bug boundary is a pre-review/pre-classification material. It should distinguish:

- External Bug.
- Internal Bug.
- Suspected non-Bug or performance/optimization records.
- Low-quality tasks.
- Missing review fields or disputed ownership.

Do not confuse Bug boundary with the formal version review.

## Version Review

Preferred command:

```bash
data-zentao version-review --version-id <version_id>
```

Formal version review should include:

- External Bug review.
- Internal Bug review.
- Low-quality task analysis even when the old report omitted it.
- Demand trend and version trend.
- Delay records and department distribution.
- Review date: default to the Friday after the version end date unless user specifies otherwise.

For old finalized reports, the goal is to reproduce the same layout and conclusions while using direct database data where old `bsg-zentao` lacked fields.

## Executive/Management View

When a user asks for a management-level view, do not simply dump project details. Summarize:

- Which projects/versions are at risk.
- Why: delay, active Bug, unassigned work, missing review, next version readiness.
- Which department/person needs follow-up.
- What action is recommended today or this week.

If the current code only supports platform/game but the question asks all projects, explicitly state that the current packaged report is incomplete and use per-project queries until a true all-project dashboard exists.
