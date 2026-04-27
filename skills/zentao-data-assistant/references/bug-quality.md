# Bug And Quality Review

Read this for Bug detail, active Bug summary, Bug boundary, quality review, and version review.

## Core Tables

| Table | Meaning |
|---|---|
| `zt_bug` | Bug main table |
| `zt_bug_dept_review` | Department review, cause analysis, and next step |
| `zt_case` | Test case |
| `zt_testtask` | Test task/plan |
| `zt_testrun` | Test task case execution row |
| `zt_testresult` | Test execution result |

## `zt_bug` Fields

| Field | Meaning |
|---|---|
| `id` | Bug ID |
| `project`, `execution`, `product` | Project/version/product scope |
| `story`, `task` | Related story/task |
| `title` | Bug title |
| `severity`, `pri` | Severity and priority |
| `type` | Bug type; `performance` can mean performance record, not true Bug for some reports |
| `status` | `active`, `resolved`, `closed` |
| `openedBy`, `openedDate` | Reporter and time |
| `assignedTo` | Current assignee |
| `resolvedBy`, `resolvedDate` | Resolver and time |
| `closedBy`, `closedDate` | Closer and time |
| `classification` | Local Bug classification |
| `owner`, `ownerDept` | Responsibility owner and department |
| `isQuestion` | Whether marked as problem/question |
| `causeAnalysis`, `tracingBack` | Cause and tracing fields |

## Department Review

`zt_bug_dept_review.bugId -> zt_bug.id`.

Use `zt_bug_dept_review.dept -> zt_dept.id` to map department names. Review content can exist even when the main Bug row has incomplete cause fields.

## Classification Rules

The local `classification` field is used by review reports. Known business meaning:

| Value | Common meaning |
|---|---|
| `1` | Online/external Bug |
| `2` | Rework/external review Bug |
| `3` | Ops/maintenance type |
| `4` | Development/internal Bug |
| `5` | Historical/internal Bug |

For some reports:

- `classification IN ('1','2')` is external-facing review scope.
- `classification IN ('4','5')` is internal review scope.
- `type='performance'` should be excluded from true Bug counts in old report口径.
- `resolved` is not the same as `closed`.

## Bug Detail Query Checklist

For a specific Bug, collect:

- `zt_bug` main row.
- Linked task `zt_bug.task -> zt_task.id`.
- Linked demand pool row if `zt_pool.taskID` matches the task.
- `zt_bug_dept_review` rows.
- User real names for reporter, assignee, owner, resolver, closer.
- Department names for `ownerDept` and review depts.

## Quality Summary Checklist

For version/project quality reports, include:

- Total Bug count.
- Active/resolved/closed split.
- Severity distribution.
- External/internal classification split.
- Department responsibility distribution.
- Unreviewed or missing-cause Bug.
- Low-quality tasks: tasks linked to multiple Bug or high-severity Bug.
- Typical/disputed Bug if fields are available.

## Risk Notes

- Do not use `assignedTo` as final responsibility without checking `owner` and `ownerDept`.
- Some rows have weak or missing department ownership; label these as unconfirmed rather than forcing a department.
- Department review data can be more reliable for复盘 than main-row cause fields.
