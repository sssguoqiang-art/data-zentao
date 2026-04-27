# Status And Dictionaries

Read this when interpreting task status, Bug status, todo status, demand status, type fields, or any Chinese label mapping.

## Task Status

| Value | Common meaning |
|---|---|
| `wait` | Not started / waiting |
| `doing` | In progress |
| `done` | Done |
| `pause` | Paused |
| `cancel` | Canceled |
| `closed` | Closed |
| `rejected` | Rejected |
| `reviewing` | In review |
| `unsure` | Unconfirmed |
| `waittest` | Waiting for test |
| `testing` | Testing |

Default unfinished task status means not in `done`, `closed`, `cancel`. Whether `pause` is considered actionable depends on report口径.

## Bug Status

| Value | Meaning |
|---|---|
| `active` | Open/unresolved |
| `resolved` | Resolved but not necessarily closed |
| `closed` | Closed |

Use "unclosed Bug" as `status != 'closed'`, and "unresolved Bug" as `status='active'`.

## Project Status

| Value | Meaning |
|---|---|
| `wait` | Not started |
| `doing` | In progress |
| `suspended` | Suspended |
| `closed` | Closed |

Because `zt_project` stores projects and sprint versions, always interpret status with `type` and parent project.

## `zt_pool_type`

`zt_pool_type` is the local business dictionary. Its `type` field is the dictionary category.

| `type` | Usage | Examples |
|---|---|---|
| `0` | Demand pool status | 未下单, 已取消, 待确认, 长期需求, 已关闭 |
| `2` | Todo/measure status | 未开始, 进行中, 已完成, 已关闭 |
| `4` | Todo type | 短期任务, 周期任务, AI专项 |
| `6` | Issue/measure type | 时间调整, 任务延期, 需求不明确 |

Known IDs:

| Category | ID | Name |
|---|---:|---|
| Demand pool status | 1 | 未下单 |
| Demand pool status | 3 | 已取消 |
| Demand pool status | 4 | 待确认 |
| Demand pool status | 5 | 长期需求 |
| Demand pool status | 6 | 已关闭 |
| Todo/measure status | 7 | 未开始 |
| Todo/measure status | 19 | 进行中 |
| Todo/measure status | 8 | 已完成 |
| Todo/measure status | 9 | 已关闭 |
| Todo type | 18 | 短期任务 |
| Todo type | 17 | 周期任务 |
| Todo type | 35 | AI专项 |
| Issue/measure type | 33 | 时间调整 |
| Issue/measure type | 31 | 待跟客户沟通时间 |
| Issue/measure type | 32 | 任务无法按时完成 |
| Issue/measure type | 23 | 有完成风险 |
| Issue/measure type | 28 | 延期 |
| Issue/measure type | 27 | 产品需求不明确 |
| Issue/measure type | 29 | 需求待评审 |
| Issue/measure type | 30 | 需求待调整 |
| Issue/measure type | 34 | 任务调整较大 |

## Todo Status

`zt_to_do_list.deleted='1'` means not deleted.

Unfinished todos generally exclude status IDs 8 and 9:

```sql
WHERE deleted='1'
  AND status NOT IN (8, 9)
```

The responsible field `duty_user` can be a single account or comma-separated account list. Split it or use `FIND_IN_SET` against `zt_user.account`.

## Demand Status

Demand pool status can come from multiple places:

- `zt_pool.status` and `zt_pool.requirementStatus`.
- `zt_pool_type` for Chinese labels when numeric.
- Associated task `zt_pool.taskID -> zt_task.status`.

For version progress pages, associated task status is often more useful than demand pool raw status.
