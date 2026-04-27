# Core Schema

Use this as a compact field index. For full live verification, run `data-zentao schema --table <table>` or `data-zentao schema --columns <keyword>`.

## Core Objects

| Object | Main tables | Meaning |
|---|---|---|
| Product | `zt_product` | Product line or business product |
| Project/execution/version | `zt_project` | One table carries projects, executions, and sprint versions |
| Product-project relation | `zt_projectproduct` | Links `zt_project.id` and `zt_product.id` |
| Task | `zt_task` | Work item, owner, status, effort, deadline |
| Demand pool | `zt_pool` | Local custom demand pool and version demand table |
| Demand pool bucket | `zt_pool_version` | Demand pool grouping, not a release/sprint version |
| Standard story | `zt_story`, `zt_storyspec`, `zt_projectstory` | Standard ZenTao product requirements |
| Bug | `zt_bug` | Bug main table |
| Bug department review | `zt_bug_dept_review` | Department cause analysis and next step |
| Todo | `zt_to_do_list` | Todo/measure list used by custom pages |
| Measures | `zt_measures_management` | Management measures and linked Bug IDs |
| Dictionary | `zt_pool_type` | Custom statuses, todo types, issue types |
| User/dept | `zt_user`, `zt_dept` | Account, real name, department |
| History/audit | `zt_action`, `zt_history` | Object actions and field changes |
| Files/build/release | `zt_file`, `zt_build`, `zt_release` | Attachments and release artifacts |

## Important Fields

### `zt_project`

`id`, `project`, `model`, `type`, `name`, `status`, `PM`, `begin`, `end`, `realBegan`, `realEnd`, `deleted`.

`zt_project.type='sprint'` commonly represents a version tab in version progress pages.

### `zt_task`

`id`, `parent`, `project`, `execution`, `story`, `name`, `type`, `pri`, `assignedTo`, `status`, `estimate`, `consumed`, `left`, `deadline`, `openedBy`, `openedDate`, `realStarted`, `finishedBy`, `finishedDate`, `closedBy`, `closedDate`, `deleted`, `demandReview`, `marked`, `env`, `delayTimes`, `delayReason`.

There is no standalone reliable task progress field. Calculate progress as `consumed / (consumed + left)` when needed.

### `zt_pool`

`id`, `type`, `pv_id`, `title`, `desc`, `category`, `submitter`, `pm`, `tester`, `remark`, `expectedVersion`, `storyId`, `taskID`, `status`, `requirementStatus`, `delayReason`, `delayMeasure`, `createdBy`, `createdDate`, `editedBy`, `editedDate`, `deleted`.

`zt_pool.pv_id` is polymorphic. Never interpret it without `zt_pool.type`.

### `zt_bug`

`id`, `project`, `execution`, `product`, `module`, `story`, `task`, `title`, `severity`, `pri`, `type`, `status`, `resolution`, `openedBy`, `openedDate`, `assignedTo`, `resolvedBy`, `resolvedDate`, `closedBy`, `closedDate`, `deadline`, `deleted`, `classification`, `ownerDept`, `owner`, `isQuestion`, `causeAnalysis`, `tracingBack`.

### `zt_to_do_list`

`id`, `dept`, `duty_user`, `status`, `deadlineTime`, `type`, `content`, `sourceLink`, `remark`, `progress`, `deleted`, `createdBy`, `createdDate`, `editedBy`, `editedDate`.

The deletion flag is inverted from common ZenTao tables: `deleted='1'` means not deleted.

### `zt_measures_management`

`id`, `status`, `title`, `dept`, `duty_user`, `pv_id`, `bug_ids`, `remark`, `deleted`, `questionType`, `createdBy`, `createdDate`, `editedBy`, `editedDate`.

`bug_ids` can contain multiple IDs and must be split before joining `zt_bug`.

## Cross-Table Relations

| From | To | Meaning |
|---|---|---|
| `zt_projectproduct.project` | `zt_project.id` | Project/execution/version product relation |
| `zt_projectproduct.product` | `zt_product.id` | Product relation |
| `zt_task.project` | `zt_project.id` | Owning project |
| `zt_task.execution` | `zt_project.id` | Execution/sprint version |
| `zt_task.story` | `zt_story.id` | Standard story |
| `zt_task.parent` | `zt_task.id` | Only valid parent when `parent>0` and row exists |
| `zt_pool.taskID` | `zt_task.id` | Demand pool item converted to task |
| `zt_pool.expectedVersion` | `zt_project.id` | Expected/planned version |
| `zt_pool.type=0 AND pv_id` | `zt_project.id` | Version progress demand |
| `zt_pool.type=1 AND pv_id` | `zt_pool_version.id` | Demand pool bucket |
| `zt_bug.task` | `zt_task.id` | Bug related task |
| `zt_bug.story` | `zt_story.id` | Bug related standard story |
| `zt_bug_dept_review.bugId` | `zt_bug.id` | Department review |
| `zt_action.objectType + objectID` | Business object | Audit trail |
| `zt_history.action` | `zt_action.id` | Field change details |
| Account fields | `zt_user.account` | Real name mapping |
| Department ID fields | `zt_dept.id` | Department name mapping |

## Deletion Filters

Use the table's own known deletion semantics:

- Most standard tables: `deleted='0'` means not deleted.
- `zt_to_do_list`: `deleted='1'` means not deleted.
- `zt_measures_management`: `deleted='1'` means not deleted.
