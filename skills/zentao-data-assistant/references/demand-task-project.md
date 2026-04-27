# Project, Demand, Task, And Effort

Read this for project progress, version status, demand details, task lists, person workload, department risk, and delay analysis.

## Project And Version Model

`zt_project` is not only a project table. It also stores executions and sprint versions.

| Field | Meaning |
|---|---|
| `zt_project.id` | Project/execution/version object ID |
| `zt_project.project` | Parent project ID for executions/sprints |
| `zt_project.type` | Object type; sprint versions commonly use `sprint` |
| `zt_project.name` | Project or version name |
| `zt_project.status` | `wait`, `doing`, `suspended`, `closed` |
| `zt_project.begin`, `zt_project.end` | Planned period |

Current version by product/project normally means:

```sql
SELECT p.*
FROM zt_project p
JOIN zt_projectproduct pp ON pp.project = p.id
JOIN zt_product prod ON prod.id = pp.product
WHERE p.deleted = '0'
  AND p.type = 'sprint'
  AND prod.name = '<product name>'
  AND p.project = <project id when known>
  AND p.begin <= CURDATE()
  AND p.end >= CURDATE();
```

## Demand Systems

There are two demand systems:

| System | Tables | Usage |
|---|---|---|
| Custom demand pool | `zt_pool`, `zt_pool_version` | Demand pool and version progress pages |
| Standard ZenTao story | `zt_story`, `zt_storyspec`, `zt_projectstory` | Standard product requirement/story |

Do not assume "需求" means `zt_story`. Version progress and demand pool pages often use `zt_pool`.

## `zt_pool.pv_id`

This is a high-risk polymorphic field.

| Condition | `pv_id` points to | Meaning |
|---|---|---|
| `zt_pool.type=0` | `zt_project.id` | Version progress demand under a sprint |
| `zt_pool.type=1` | `zt_pool_version.id` | Demand pool bucket/group |

Always include `zt_pool.type` when explaining or querying `pv_id`.

## Demand Detail Rules

For a demand detail query, collect:

- Demand pool row: `zt_pool.id`, `title`, `desc`, `status`, `requirementStatus`, `pm`, `tester`, `submitter`, `expectedVersion`, `pv_id`, `type`, `taskID`, `storyId`, `createdDate`, `editedDate`.
- Associated task: `zt_pool.taskID -> zt_task.id`.
- Actual version: `zt_pool.taskID -> zt_task.execution -> zt_project.id/name`.
- Standard story if present: `zt_pool.storyId -> zt_story.id`.
- Child tasks: tasks whose `parent` points to the demand task ID, when present.

## Numeric ID Search Rule

When the user gives a numeric ID for a "需求" or says "查这个单", do not check only `zt_pool.id`.

Check all of these:

```sql
SELECT p.id AS poolID, p.taskID, p.title, p.storyId,
       t.id AS taskIDReal, t.name AS taskName, t.status AS taskStatus,
       s.id AS storyID, s.title AS storyTitle
FROM zt_pool p
LEFT JOIN zt_task t ON t.id = p.taskID
LEFT JOIN zt_story s ON s.id = p.storyId
WHERE p.deleted = '0'
  AND (
    p.id = <id>
    OR p.taskID = <id>
    OR t.id = <id>
    OR s.id = <id>
  );
```

Also query `zt_task` directly if no `zt_pool` row matches:

```sql
SELECT id, parent, project, execution, story, name, assignedTo, status, deadline, consumed, `left`
FROM zt_task
WHERE deleted='0' AND id=<id>;
```

This prevents missing a demand whose visible ID is actually the linked task ID.

## Task And Effort Rules

| Metric | Recommended source |
|---|---|
| Task status | `zt_task.status` |
| Owner | `zt_task.assignedTo -> zt_user.account` |
| Deadline | `zt_task.deadline` |
| Estimate | `zt_task.estimate` |
| Consumed | `zt_task.consumed`, optionally verify with `zt_effort` |
| Remaining | `zt_task.left` |
| Progress | `consumed / (consumed + left)` |
| Finished time | `zt_task.finishedDate` |
| Explicit delay count | `zt_task.delayTimes` |
| Delay reason | `zt_task.delayReason` |

Parent/child tasks:

- `parent>0` and parent row exists means child task.
- `parent=0` or `parent=-1` means top-level/no valid parent.
- Decide whether a report counts all tasks or only leaf tasks; state the口径 if it matters.

## Delay Rules

Open overdue:

```sql
deadline < <as_of_date>
AND status NOT IN ('done','closed','cancel')
AND deleted='0'
```

Finished late:

```sql
DATE(finishedDate) > deadline
AND finishedDate NOT IN ('0000-00-00 00:00:00')
AND deleted='0'
```

Do not use `zt_pool.deliveryDate` as a substitute for task deadline.

## Person And Department Views

Person view should map the input to `zt_user.account` and `zt_user.realname`, then collect:

- Assigned open tasks.
- Assigned or owned Bug.
- Todos where `zt_to_do_list.duty_user` contains the account.
- Overdue items and remaining effort.

Department view should collect:

- Department users from `zt_dept` and `zt_user`.
- Tasks assigned to department users.
- Bug whose owner/assigned user belongs to the department.
- Todos/measures with department fields where available.
- Cross-project/version scope, if the user asks for all department status.
