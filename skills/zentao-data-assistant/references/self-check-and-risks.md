# Self-Check And Known Risks

Read this when verifying whether an answer can be trusted, when field meaning is uncertain, or when adding a new report/query.

## Minimum Self-Check

Before making a strong business claim:

1. Confirm the target scope: project/product/version/date/person/department.
2. Confirm the object IDs and join path.
3. Confirm status filters.
4. Confirm deletion filters.
5. Map accounts to real names and department names.
6. Check risky fields below.
7. State remaining uncertainty if a field is not fully page-calibrated.

## P0 Risk Fields

| Table | Field | Risk | Required handling |
|---|---|---|---|
| `zt_pool` | `pv_id` | Polymorphic | Always include `zt_pool.type` |
| `zt_task` | `parent` | `0` and `-1` are not valid parent tasks | Only treat `parent>0` with matched task row as parent-child |
| `zt_to_do_list` | `duty_user` | Single or comma-separated accounts | Split or use `FIND_IN_SET` |
| `zt_project` | `type` | One table carries projects/executions/sprints | Use `type`, `project`, and product relation |
| `zt_file` | `objectType`, `objectID` | `objectID` alone can join the wrong object | Use both fields |
| `zt_to_do_list` | `deleted` | Inverted deletion flag | `deleted='1'` means not deleted |
| `zt_measures_management` | `deleted` | Inverted deletion flag | `deleted='1'` means not deleted |

## P1 Fields To Use Carefully

- `zt_pool.status`, `requirementStatus`, `category`, `priority`, `scale`, `maturity`, `storyType`.
- `zt_pool.delayReason`, `delayMeasure`, `adjustLog`.
- `zt_task.demandReview`, `artReview`, `review`, `env`, `marked`, `isSelfTest`, `rejectReason`, `rejectCount`, `is_delay`, `delayTimes`.
- `zt_bug.classification`, `type`, `owner`, `ownerDept`, `questionType`, `causeAnalysis`, `nextStep`, `tracingBack`, `isTypical`, `isDispute`.
- `zt_to_do_list.progress`, `sourceLink`.
- `zt_measures_management.pv_id`, `bug_ids`, `questionType`.
- `zt_pool_type.type`, because actual categories include more than older comments may suggest.

Use these fields when needed, but avoid overclaiming without page or sample verification.

## Known Implementation Gaps To Watch

- Numeric demand lookup must handle task IDs. A demand can be visible to users by `zt_task.id` while `zt_pool.id` is different.
- Legacy `weekly-summary` does not automatically include every project such as SG.
- Department risk currently may not be a full department dashboard; it is usually version-scoped.
- Person task output may list work but not fully judge workload or abnormal patterns.
- Bug department ownership can be incomplete or mixed with type fields in old data.
- Delay reason fields are often blank; deadline-based delay can be detected, but root cause may need history, page notes, or manual input.
- Parallel or repeated DB calls can time out. Prefer fewer, scoped queries and retry if the database is slow.

## Self-Check Commands

```bash
data-zentao doctor
data-zentao schema --table zt_pool
data-zentao schema --table zt_task
data-zentao schema --table zt_bug
data-zentao schema --columns 状态
```

For a single object:

```bash
data-zentao query --format json --sql "SELECT ... WHERE id=<id> LIMIT 20"
```

## Answer Confidence

Use these levels internally:

| Level | Meaning |
|---|---|
| High | Table, field, relationship, and status口径 are verified by references or schema and sample data |
| Medium | Relationship is likely but page wording or custom field meaning is not fully confirmed |
| Low | Field exists but business meaning is uncertain; answer should be framed as a clue, not a conclusion |

When confidence is medium or low, tell the user what can be guaranteed and what still needs verification.
