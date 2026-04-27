from __future__ import annotations

import datetime as dt
from typing import Any

from .formatting import md_table, serialize, trim_text
from .repository import ZentaoRepository


TODO_STATUS_LABELS = {
    "unfinished": "未完成",
    "ongoing": "进行中",
    "not-started": "未开始",
    "all": "全部",
}

TASK_STATUS_LABELS = {
    "wait": "未开始",
    "doing": "进行中",
    "done": "已完成",
    "closed": "已关闭",
    "cancel": "已取消",
    "pause": "已暂停",
    "testing": "测试中",
    "waittest": "待测试",
}

BUG_CLASSIFICATION_LABELS = {
    "0": "未分类",
    "1": "线上Bug",
    "2": "返工Bug",
    "3": "运维Bug",
    "4": "开发Bug",
    "5": "历史Bug",
}


def bug_classification_label(value: object) -> str:
    return BUG_CLASSIFICATION_LABELS.get(str(value or "0"), str(value or "未填写"))


def bug_boundary_bucket(row: dict[str, Any]) -> str:
    classification = str(row.get("classification") or "0")
    if row.get("type") == "performance":
        return "nonbug"
    if classification in {"1", "2"}:
        return "external"
    if classification == "3":
        return "ops"
    if classification in {"4", "5"}:
        return "internal"
    return "unknown"


def bug_review_suggestion(row: dict[str, Any]) -> str:
    if row.get("type") == "performance":
        return "疑似非Bug，建议人工确认后剔除"
    if str(row.get("isTypical")) == "1" or row.get("severity") in {1, 2}:
        return "建议复盘"
    if not row.get("causeAnalysis") and not row.get("dept_review"):
        return "需会前补充原因"
    if bug_boundary_bucket(row) in {"external", "internal"}:
        return "可纳入复盘候选"
    return "复盘价值待确认"


def render_todo_report(rows: list[dict[str, Any]], status: str) -> str:
    label = TODO_STATUS_LABELS.get(status, status)
    lines = [f"当前{label}待办一共 {len(rows)} 条。", ""]
    lines.append(
        md_table(
            ["ID", "状态", "待办", "部门", "责任人", "类型", "截止时间"],
            [
                [
                    row["id"],
                    row.get("status_name"),
                    trim_text(row.get("content"), 42),
                    row.get("dept_name"),
                    row.get("duty_names"),
                    row.get("type_name"),
                    serialize(row.get("deadlineTime")),
                ]
                for row in rows
            ],
        )
    )
    return "\n".join(lines)


def build_version_delay_payload(
    repo: ZentaoRepository,
    version_id: int,
    as_of: dt.date,
) -> dict[str, Any]:
    return {
        **repo.get_version_task_summary(version_id, as_of),
        "as_of": as_of,
        "overdue_open": repo.get_overdue_open_tasks(version_id, as_of),
        "finished_late": repo.get_finished_late_tasks(version_id),
        "marked_delay": repo.get_marked_delay_tasks(version_id),
    }


def render_version_delay_report(payload: dict[str, Any]) -> str:
    version = payload.get("version") or {}
    summary = payload.get("summary") or {}
    pool_delay = payload.get("pool_delay") or {}
    overdue_open = payload.get("overdue_open") or []
    finished_late = payload.get("finished_late") or []
    marked_delay = payload.get("marked_delay") or []
    as_of = serialize(payload.get("as_of"))

    title = version.get("name", "未知版本")
    lines = [
        f"{title} 延期情况",
        "",
        f"查询日期：{as_of}",
        f"版本周期：{serialize(version.get('begin'))} ~ {serialize(version.get('end'))}",
        f"版本状态：{version.get('status', '')}",
        "",
        "汇总：",
        f"- 任务总数：{serialize(summary.get('total_tasks', 0))}",
        f"- 未关闭任务：{serialize(summary.get('open_tasks', 0))}",
        f"- 当前逾期未完成：{len(overdue_open)}",
        f"- 已完成但晚于截止时间：{len(finished_late)}",
        f"- 任务延期原因已填写：{serialize(summary.get('delay_reason_count', 0))}",
        f"- 需求池延期原因已填写：{serialize(pool_delay.get('delay_reason_count', 0))}",
        f"- 需求池延期举措已填写：{serialize(pool_delay.get('delay_measure_count', 0))}",
    ]

    if overdue_open:
        lines.extend(
            [
                "",
                "当前仍逾期未完成：",
                md_table(
                    ["任务ID", "所属需求", "任务", "负责人", "状态", "截止", "逾期", "剩余工时"],
                    [
                        [
                            row["id"],
                            trim_text(row.get("root_name"), 34),
                            trim_text(row.get("name"), 34),
                            row.get("assignedName") or row.get("assignedTo"),
                            row.get("status"),
                            serialize(row.get("deadline")),
                            f"{serialize(row.get('overdue_days'))}天",
                            serialize(row.get("left")),
                        ]
                        for row in overdue_open
                    ],
                ),
            ]
        )

    if finished_late:
        lines.extend(
            [
                "",
                "已完成但延期交付：",
                md_table(
                    ["任务ID", "所属需求", "任务", "状态", "截止", "完成", "延期"],
                    [
                        [
                            row["id"],
                            trim_text(row.get("root_name"), 34),
                            trim_text(row.get("name"), 34),
                            row.get("status"),
                            serialize(row.get("deadline")),
                            serialize(row.get("finishedDate")),
                            f"{serialize(row.get('late_days'))}天",
                        ]
                        for row in finished_late
                    ],
                ),
            ]
        )

    if marked_delay:
        lines.extend(
            [
                "",
                "任务字段中显式标记过延期的记录：",
                md_table(
                    ["任务ID", "所属需求", "任务", "负责人", "延期次数", "延期原因"],
                    [
                        [
                            row["id"],
                            trim_text(row.get("root_name"), 34),
                            trim_text(row.get("name"), 34),
                            row.get("assignedName") or row.get("assignedTo"),
                            serialize(row.get("delayTimes")),
                            trim_text(row.get("delayReason"), 40),
                        ]
                        for row in marked_delay
                    ],
                ),
            ]
        )

    if not overdue_open and not finished_late and not marked_delay:
        lines.extend(["", "当前没有查到延期记录。"])

    if not summary.get("delay_reason_count") and not pool_delay.get("delay_reason_count"):
        lines.extend(["", "注意：当前延期原因字段基本为空，只能按截止时间和完成时间判断延期，不能直接得出真实原因。"])

    return "\n".join(lines)


def render_platform_delay_report(
    repo: ZentaoRepository,
    product_name: str,
    project_name: str,
    as_of: dt.date,
) -> str:
    sprint = repo.get_current_sprint_for_product(product_name, as_of, project_name)
    if not sprint:
        return f"没有定位到 {product_name} 在 {as_of.isoformat()} 对应的当前版本。"
    payload = build_version_delay_payload(repo, int(sprint["id"]), as_of)
    report = render_version_delay_report(payload)
    return f"平台当前版本：{sprint['name']}（ID {sprint['id']}）\n\n{report}"


def build_daily_report_payload(
    repo: ZentaoRepository,
    product_name: str,
    project_name: str,
    as_of: dt.date,
) -> dict[str, Any]:
    sprint = repo.get_current_sprint_for_product(product_name, as_of, project_name)
    if not sprint:
        return {
            "ok": False,
            "as_of": as_of,
            "message": f"没有定位到 {product_name} 在 {as_of.isoformat()} 对应的当前版本。",
        }

    version_id = int(sprint["id"])
    next_sprint = repo.get_next_sprint_for_product(product_name, as_of, project_name)
    next_version_id = int(next_sprint["id"]) if next_sprint else None
    return {
        "ok": True,
        "as_of": as_of,
        "current_sprint": sprint,
        "next_sprint": next_sprint,
        "task_summary": repo.get_version_task_summary(version_id, as_of),
        "today_opened_tasks": repo.get_today_opened_tasks(version_id, as_of),
        "today_finished_tasks": repo.get_today_finished_tasks(version_id, as_of),
        "due_today_tasks": repo.get_due_today_tasks(version_id, as_of),
        "overdue_open": repo.get_overdue_open_tasks(version_id, as_of),
        "marked_delay": repo.get_marked_delay_tasks(version_id),
        "demand_summary": repo.get_version_demand_summary(version_id),
        "demands": repo.get_version_demands(version_id, limit=30),
        "bug_summary": repo.get_bug_summary(version_id, as_of),
        "active_bugs": repo.get_active_bugs(version_id),
        "unfinished_todos": repo.get_todos("unfinished"),
        "next_task_summary": repo.get_version_task_summary(next_version_id, as_of) if next_version_id else None,
        "next_demand_summary": repo.get_version_demand_summary(next_version_id) if next_version_id else None,
    }


def render_daily_report(payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        return str(payload.get("message", "今日报告生成失败。"))

    as_of = payload["as_of"]
    sprint = payload["current_sprint"]
    next_sprint = payload.get("next_sprint") or {}
    task_payload = payload["task_summary"]
    task_summary = task_payload.get("summary") or {}
    task_status = task_payload.get("status") or []
    pool_delay = task_payload.get("pool_delay") or {}
    demand_summary = payload.get("demand_summary", {}).get("summary") or {}
    demand_status = payload.get("demand_summary", {}).get("status") or []
    bug_summary = payload.get("bug_summary", {}).get("summary") or {}
    bug_status = payload.get("bug_summary", {}).get("status") or []
    bug_severity = payload.get("bug_summary", {}).get("severity") or []
    today_opened = payload.get("today_opened_tasks") or []
    today_finished = payload.get("today_finished_tasks") or []
    due_today = payload.get("due_today_tasks") or []
    overdue_open = payload.get("overdue_open") or []
    marked_delay = payload.get("marked_delay") or []
    active_bugs = payload.get("active_bugs") or []
    unfinished_todos = payload.get("unfinished_todos") or []
    next_task_summary = ((payload.get("next_task_summary") or {}).get("summary") or {})
    next_demand_summary = ((payload.get("next_demand_summary") or {}).get("summary") or {})

    end_date = sprint.get("end")
    days_left = None
    if isinstance(end_date, dt.datetime):
        days_left = (end_date.date() - as_of).days
    elif isinstance(end_date, dt.date):
        days_left = (end_date - as_of).days

    task_total = serialize(task_summary.get("total_tasks", 0))
    task_open = serialize(task_summary.get("open_tasks", 0))
    active_bug_count = serialize(bug_summary.get("active_bugs", 0))
    high_bug_count = serialize(bug_summary.get("active_high_bugs", 0))

    conclusion = [
        f"当前版本为 {sprint.get('name')}，计划周期 {serialize(sprint.get('begin'))} ~ {serialize(sprint.get('end'))}。",
        f"版本任务共 {task_total} 个，未关闭 {task_open} 个；今日完成 {len(today_finished)} 个，今日新建 {len(today_opened)} 个。",
        f"当前逾期未完成任务 {len(overdue_open)} 个，今日到期未完成任务 {len(due_today)} 个。",
        f"当前版本 Bug 共 {serialize(bug_summary.get('total_bugs', 0))} 个，未解决 active Bug {active_bug_count} 个，其中高严重级别 active Bug {high_bug_count} 个。",
        f"当前未完成待办 {len(unfinished_todos)} 条。",
    ]
    if days_left is not None:
        conclusion.insert(1, f"距离版本结束还有 {days_left} 天。")
    if not task_summary.get("delay_reason_count") and not pool_delay.get("delay_reason_count"):
        conclusion.append("延期原因字段基本为空，延期归因需要人工补充或结合会议信息判断。")

    lines = [
        f"# 平台项目今日报告（{serialize(as_of)}）",
        "",
        "## 一、今日结论",
        "",
        *[f"- {item}" for item in conclusion],
        "",
        "## 二、当前版本概况",
        "",
        md_table(
            ["项目", "当前版本", "版本状态", "开始", "结束", "剩余天数", "下一版本"],
            [
                [
                    sprint.get("project_name") or "平台部",
                    sprint.get("name"),
                    sprint.get("status"),
                    serialize(sprint.get("begin")),
                    serialize(sprint.get("end")),
                    "" if days_left is None else days_left,
                    next_sprint.get("name") or "",
                ]
            ],
        ),
        "",
        "### 任务状态分布",
        "",
        md_table(
            ["状态", "中文含义", "数量"],
            [
                [row.get("status"), TASK_STATUS_LABELS.get(row.get("status"), ""), serialize(row.get("count"))]
                for row in task_status
            ],
        ),
        "",
        "## 三、今日推进",
        "",
        f"今日完成任务 {len(today_finished)} 个，今日新建任务 {len(today_opened)} 个。",
    ]

    if today_finished:
        lines.extend(
            [
                "",
                "### 今日完成任务",
                "",
                md_table(
                    ["任务ID", "所属需求", "任务", "完成人", "完成时间", "延期"],
                    [
                        [
                            row.get("id"),
                            trim_text(row.get("root_name"), 28),
                            trim_text(row.get("name"), 38),
                            row.get("finishedName") or row.get("finishedBy") or row.get("assignedName"),
                            serialize(row.get("finishedDate")),
                            f"{serialize(row.get('late_days'))}天" if row.get("late_days") else "",
                        ]
                        for row in today_finished[:20]
                    ],
                ),
            ]
        )

    if today_opened:
        lines.extend(
            [
                "",
                "### 今日新建任务",
                "",
                md_table(
                    ["任务ID", "所属需求", "任务", "负责人", "创建人", "截止"],
                    [
                        [
                            row.get("id"),
                            trim_text(row.get("root_name"), 28),
                            trim_text(row.get("name"), 38),
                            row.get("assignedName") or row.get("assignedTo"),
                            row.get("openedName") or row.get("openedBy"),
                            serialize(row.get("deadline")),
                        ]
                        for row in today_opened[:20]
                    ],
                ),
            ]
        )

    lines.extend(["", "## 四、风险与延期", ""])
    if overdue_open:
        lines.extend(
            [
                f"当前仍有 {len(overdue_open)} 个逾期未完成任务：",
                "",
                md_table(
                    ["任务ID", "所属需求", "任务", "负责人", "状态", "截止", "逾期", "剩余工时"],
                    [
                        [
                            row.get("id"),
                            trim_text(row.get("root_name"), 28),
                            trim_text(row.get("name"), 38),
                            row.get("assignedName") or row.get("assignedTo"),
                            row.get("status"),
                            serialize(row.get("deadline")),
                            f"{serialize(row.get('overdue_days'))}天",
                            serialize(row.get("left")),
                        ]
                        for row in overdue_open
                    ],
                ),
            ]
        )
    else:
        lines.append("当前没有逾期未完成任务。")

    if due_today:
        lines.extend(
            [
                "",
                f"今日到期未完成任务 {len(due_today)} 个：",
                "",
                md_table(
                    ["任务ID", "所属需求", "任务", "负责人", "状态", "剩余工时"],
                    [
                        [
                            row.get("id"),
                            trim_text(row.get("root_name"), 28),
                            trim_text(row.get("name"), 38),
                            row.get("assignedName") or row.get("assignedTo"),
                            row.get("status"),
                            serialize(row.get("left")),
                        ]
                        for row in due_today
                    ],
                ),
            ]
        )

    if marked_delay:
        lines.extend(
            [
                "",
                "任务字段中显式记录延期的任务：",
                "",
                md_table(
                    ["任务ID", "所属需求", "任务", "负责人", "延期次数", "延期原因"],
                    [
                        [
                            row.get("id"),
                            trim_text(row.get("root_name"), 28),
                            trim_text(row.get("name"), 38),
                            row.get("assignedName") or row.get("assignedTo"),
                            serialize(row.get("delayTimes")),
                            trim_text(row.get("delayReason"), 36),
                        ]
                        for row in marked_delay
                    ],
                ),
        ]
    )

    if next_sprint:
        lines.extend(
            [
                "",
                "### 下一版本预览",
                "",
                md_table(
                    ["下一版本", "开始", "结束", "任务数", "未关闭任务", "需求数", "未关联任务需求"],
                    [
                        [
                            next_sprint.get("name"),
                            serialize(next_sprint.get("begin")),
                            serialize(next_sprint.get("end")),
                            serialize(next_task_summary.get("total_tasks", 0)),
                            serialize(next_task_summary.get("open_tasks", 0)),
                            serialize(next_demand_summary.get("total_demands", 0)),
                            serialize(next_demand_summary.get("without_task", 0)),
                        ]
                    ],
                ),
                "",
                "下一版本数据只做前置关注，不与当前版本交付完成率混算。",
            ]
        )

    lines.extend(
        [
            "",
            "## 五、Bug 情况",
            "",
            md_table(
                ["总数", "active", "resolved", "closed", "今日新增", "今日解决", "今日关闭", "高严重 active"],
                [
                    [
                        serialize(bug_summary.get("total_bugs", 0)),
                        serialize(bug_summary.get("active_bugs", 0)),
                        serialize(bug_summary.get("resolved_bugs", 0)),
                        serialize(bug_summary.get("closed_bugs", 0)),
                        serialize(bug_summary.get("opened_today", 0)),
                        serialize(bug_summary.get("resolved_today", 0)),
                        serialize(bug_summary.get("closed_today", 0)),
                        serialize(bug_summary.get("active_high_bugs", 0)),
                    ]
                ],
            ),
            "",
            "### Bug 状态分布",
            "",
            md_table(["状态", "数量"], [[row.get("status"), serialize(row.get("count"))] for row in bug_status]),
            "",
            "### Bug 严重级别分布",
            "",
            md_table(["严重级别", "数量"], [[row.get("severity"), serialize(row.get("count"))] for row in bug_severity]),
        ]
    )

    if active_bugs:
        lines.extend(
            [
                "",
                "### 当前 active Bug",
                "",
                md_table(
                    ["BugID", "标题", "严重", "优先级", "负责人", "创建时间", "归属"],
                    [
                        [
                            row.get("id"),
                            trim_text(row.get("title"), 46),
                            row.get("severity"),
                            row.get("pri"),
                            row.get("assignedName") or row.get("assignedTo"),
                            serialize(row.get("openedDate")),
                            row.get("ownerDeptName") or row.get("ownerDept") or row.get("type"),
                        ]
                        for row in active_bugs[:20]
                    ],
                ),
            ]
        )

    lines.extend(
        [
            "",
            "## 六、需求与待办",
            "",
            "### 当前版本需求概况",
            "",
            md_table(
                ["版本需求", "已关联任务", "未关联任务", "延期原因已填", "延期举措已填"],
                [
                    [
                        serialize(demand_summary.get("total_demands", 0)),
                        serialize(demand_summary.get("with_task", 0)),
                        serialize(demand_summary.get("without_task", 0)),
                        serialize(demand_summary.get("delay_reason_count", 0)),
                        serialize(demand_summary.get("delay_measure_count", 0)),
                    ]
                ],
            ),
        ]
    )

    if demand_status:
        lines.extend(
            [
                "",
                "### 版本需求状态分布",
                "",
                md_table(["状态", "数量"], [[row.get("status"), serialize(row.get("count"))] for row in demand_status]),
            ]
        )

    if unfinished_todos:
        lines.extend(
            [
                "",
                "### 当前未完成待办",
                "",
                md_table(
                    ["ID", "状态", "待办", "部门", "责任人", "类型", "截止"],
                    [
                        [
                            row.get("id"),
                            row.get("status_name"),
                            trim_text(row.get("content"), 44),
                            row.get("dept_name"),
                            row.get("duty_names"),
                            row.get("type_name"),
                            serialize(row.get("deadlineTime")),
                        ]
                        for row in unfinished_todos[:20]
                    ],
                ),
            ]
        )

    lines.extend(
        [
            "",
            "## 七、数据口径",
            "",
            "- 当前版本：按 `zt_product.name='平台部'` 与 `zt_project.type='sprint'`，并匹配查询日期落在版本周期内。",
            "- 任务：`zt_task.execution=当前版本ID` 且 `deleted='0'`。",
            "- 当前逾期：`deadline < 查询日期` 且状态不在 `done/closed/cancel`。",
            "- Bug：`zt_bug.execution=当前版本ID` 且 `deleted='0'`。",
            "- 待办：`zt_to_do_list.deleted='1'`，未完成排除 `已完成=8`、`已关闭=9`。",
            "- 本报告按当前数据库实时数据生成，数据会随禅道更新变化。",
        ]
    )

    return "\n".join(lines) + "\n"


def build_person_work_payload(repo: ZentaoRepository, keyword: str) -> dict[str, Any]:
    users = repo.find_users(keyword)
    if not users:
        return {"ok": False, "keyword": keyword, "message": f"没有找到人员：{keyword}"}
    user = users[0]
    account = user["account"]
    return {
        "ok": True,
        "keyword": keyword,
        "matched_users": users,
        "user": user,
        "tasks": repo.get_person_tasks(account),
        "bugs": repo.get_person_bugs(account),
        "todos": repo.get_person_todos(account),
    }


def render_person_work_report(payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        return str(payload.get("message", "人员任务查询失败。"))
    user = payload["user"]
    tasks = payload.get("tasks") or []
    bugs = payload.get("bugs") or []
    todos = payload.get("todos") or []
    lines = [
        f"# {user.get('realname') or user.get('account')} 工作项",
        "",
        f"账号：{user.get('account')}；部门：{user.get('dept_name') or ''}",
        "",
        "## 汇总",
        "",
        f"- 未关闭任务：{len(tasks)} 个",
        f"- 未关闭 Bug：{len(bugs)} 个",
        f"- 未完成待办：{len(todos)} 个",
    ]
    if tasks:
        lines.extend(
            [
                "",
                "## 未关闭任务",
                "",
                md_table(
                    ["任务ID", "任务", "版本", "状态", "截止", "逾期", "剩余工时"],
                    [
                        [
                            row.get("id"),
                            trim_text(row.get("name"), 46),
                            row.get("execution_name"),
                            row.get("status"),
                            serialize(row.get("deadline")),
                            f"{serialize(row.get('overdue_days'))}天" if row.get("overdue_days") else "",
                            serialize(row.get("left")),
                        ]
                        for row in tasks[:30]
                    ],
                ),
            ]
        )
    if bugs:
        lines.extend(
            [
                "",
                "## 未关闭 Bug",
                "",
                md_table(
                    ["BugID", "标题", "版本", "状态", "严重", "优先级", "创建时间"],
                    [
                        [
                            row.get("id"),
                            trim_text(row.get("title"), 50),
                            row.get("execution_name"),
                            row.get("status"),
                            row.get("severity"),
                            row.get("pri"),
                            serialize(row.get("openedDate")),
                        ]
                        for row in bugs[:30]
                    ],
                ),
            ]
        )
    if todos:
        lines.extend(
            [
                "",
                "## 未完成待办",
                "",
                md_table(
                    ["ID", "状态", "待办", "部门", "类型", "截止"],
                    [
                        [
                            row.get("id"),
                            row.get("status_name"),
                            trim_text(row.get("content"), 52),
                            row.get("dept_name"),
                            row.get("type_name"),
                            serialize(row.get("deadlineTime")),
                        ]
                        for row in todos[:30]
                    ],
                ),
            ]
        )
    return "\n".join(lines) + "\n"


def build_demand_status_payload(repo: ZentaoRepository, keyword: str) -> dict[str, Any]:
    rows = repo.get_demand_status(keyword)
    return {"ok": True, "keyword": keyword, "demands": rows}


def render_demand_status_report(payload: dict[str, Any]) -> str:
    keyword = payload.get("keyword")
    rows = payload.get("demands") or []
    if not rows:
        return f"没有查到需求：{keyword}\n"
    lines = [f"# 需求状态查询：{keyword}", "", f"共匹配 {len(rows)} 条需求。", ""]
    lines.append(
        md_table(
            ["需求ID", "需求", "需求池状态", "标准需求", "标准阶段", "版本", "任务", "任务状态", "负责人", "PM", "测试", "延期原因"],
            [
                [
                    row.get("id"),
                    trim_text(row.get("title"), 42),
                    row.get("status_name") or row.get("raw_status"),
                    row.get("story_status") or "",
                    row.get("story_stage") or "",
                    row.get("version_name") or row.get("expected_version_name"),
                    row.get("taskID") or "",
                    row.get("task_status"),
                    row.get("assignedName") or row.get("assignedTo"),
                    row.get("pmName") or row.get("pm"),
                    row.get("testerName") or row.get("tester"),
                    trim_text(row.get("delayReason"), 30),
                ]
                for row in rows
            ],
        )
    )
    first = rows[0]
    lines.extend(
        [
            "",
            "## 第一条匹配需求详情",
            "",
            f"- 标题：{first.get('title')}",
            f"- 需求池状态：{first.get('status_name') or first.get('raw_status')}",
            f"- 标准需求：{first.get('storyId') or '无'} / {first.get('story_status') or ''} / {first.get('story_stage') or ''}",
            f"- 当前版本：{first.get('version_name') or ''}",
            f"- 期望版本：{first.get('expected_version_name') or ''}",
            f"- 关联任务：{first.get('taskID') or '无'} / {first.get('task_status') or ''}",
            f"- 责任人：{first.get('assignedName') or first.get('assignedTo') or ''}",
            f"- 备注：{trim_text(first.get('remark'), 120)}",
        ]
    )
    return "\n".join(lines) + "\n"


def build_measures_payload(repo: ZentaoRepository, status: str) -> dict[str, Any]:
    return {"ok": True, "status": status, **repo.get_measures(status)}


def render_measures_report(payload: dict[str, Any]) -> str:
    todos = payload.get("todos") or []
    measures = payload.get("measures") or []
    status = payload.get("status")
    lines = [
        f"# 待办与举措（{status}）",
        "",
        f"- 待办：{len(todos)} 条",
        f"- 举措：{len(measures)} 条",
    ]
    if todos:
        lines.extend(
            [
                "",
                "## 待办",
                "",
                md_table(
                    ["ID", "状态", "待办", "部门", "责任人", "类型", "截止"],
                    [
                        [
                            row.get("id"),
                            row.get("status_name"),
                            trim_text(row.get("content"), 48),
                            row.get("dept_name"),
                            row.get("duty_names"),
                            row.get("type_name"),
                            serialize(row.get("deadlineTime")),
                        ]
                        for row in todos[:40]
                    ],
                ),
            ]
        )
    if measures:
        lines.extend(
            [
                "",
                "## 举措",
                "",
                md_table(
                    ["ID", "状态", "举措", "部门", "责任人", "问题类型", "版本", "关联Bug"],
                    [
                        [
                            row.get("id"),
                            row.get("status_name") or row.get("status_id"),
                            trim_text(row.get("title"), 48),
                            row.get("dept_name"),
                            row.get("duty_name") or row.get("duty_user"),
                            row.get("question_type_name") or row.get("questionType"),
                            row.get("version_name"),
                            trim_text(row.get("bug_ids"), 24),
                        ]
                        for row in measures[:40]
                    ],
                ),
            ]
        )
    return "\n".join(lines) + "\n"


def build_bug_review_payload(repo: ZentaoRepository, version_id: int) -> dict[str, Any]:
    return {"ok": True, "version_id": version_id, **repo.get_bug_review(version_id)}


def render_bug_review_report(payload: dict[str, Any]) -> str:
    summary = payload.get("summary", {}).get("summary") or {}
    dept_summary = payload.get("dept_summary") or []
    bugs = payload.get("bugs") or []
    lines = [
        f"# Bug 复盘数据（版本 {payload.get('version_id')}）",
        "",
        "## 汇总",
        "",
        md_table(
            ["总数", "active", "resolved", "closed", "高严重 active"],
            [
                [
                    serialize(summary.get("total_bugs", 0)),
                    serialize(summary.get("active_bugs", 0)),
                    serialize(summary.get("resolved_bugs", 0)),
                    serialize(summary.get("closed_bugs", 0)),
                    serialize(summary.get("active_high_bugs", 0)),
                ]
            ],
        ),
    ]
    if dept_summary:
        lines.extend(
            [
                "",
                "## 部门/归属分布",
                "",
                md_table(
                    ["归属", "Bug数", "active", "高严重"],
                    [
                        [
                            row.get("dept"),
                            serialize(row.get("bug_count")),
                            serialize(row.get("active_count")),
                            serialize(row.get("high_count")),
                        ]
                        for row in dept_summary
                    ],
                ),
            ]
        )
    if bugs:
        lines.extend(
            [
                "",
                "## Bug 明细与复盘信息",
                "",
                md_table(
                    ["BugID", "标题", "状态", "严重", "负责人", "归属", "原因", "举措", "部门复盘"],
                    [
                        [
                            row.get("id"),
                            trim_text(row.get("title"), 42),
                            row.get("status"),
                            row.get("severity"),
                            row.get("assignedName") or row.get("assignedTo"),
                            row.get("ownerDeptName") or row.get("ownerDept") or row.get("type"),
                            trim_text(row.get("causeAnalysis"), 30),
                            trim_text(row.get("nextStep"), 30),
                            trim_text(row.get("dept_review"), 50),
                        ]
                        for row in bugs[:50]
                    ],
                ),
            ]
        )
    return "\n".join(lines) + "\n"


def build_bug_boundary_payload(repo: ZentaoRepository, version_id: int) -> dict[str, Any]:
    data = repo.get_bug_boundary(version_id)
    bugs = data.get("bugs") or []
    buckets = {
        "nonbug": [row for row in bugs if bug_boundary_bucket(row) == "nonbug"],
        "external": [row for row in bugs if bug_boundary_bucket(row) == "external"],
        "ops": [row for row in bugs if bug_boundary_bucket(row) == "ops"],
        "internal": [row for row in bugs if bug_boundary_bucket(row) == "internal"],
        "unknown": [row for row in bugs if bug_boundary_bucket(row) == "unknown"],
    }
    return {"ok": True, "version_id": version_id, **data, "buckets": buckets}


def render_bug_boundary_report(payload: dict[str, Any]) -> str:
    summary = payload.get("summary", {}).get("summary") or {}
    buckets = payload.get("buckets") or {}
    external = buckets.get("external") or []
    internal = buckets.get("internal") or []
    nonbug = buckets.get("nonbug") or []
    ops = buckets.get("ops") or []
    unknown = buckets.get("unknown") or []
    low_quality = payload.get("low_quality_tasks") or []
    bugs = payload.get("bugs") or []

    dept_totals: dict[str, dict[str, int]] = {}
    for row in bugs:
        dept = row.get("ownerDeptName") or row.get("ownerDept") or row.get("type") or "未填写"
        bucket = bug_boundary_bucket(row)
        if dept not in dept_totals:
            dept_totals[dept] = {"total": 0, "external": 0, "internal": 0, "nonbug": 0, "key": 0}
        dept_totals[dept]["total"] += 1
        if bucket in dept_totals[dept]:
            dept_totals[dept][bucket] += 1
        if row.get("severity") in {1, 2} or str(row.get("isTypical")) == "1":
            dept_totals[dept]["key"] += 1

    lines = [
        f"# Bug界定预分类（版本 {payload.get('version_id')}）",
        "",
        "## 一、界定结论",
        "",
        f"- 原始 Bug：{serialize(summary.get('total_bugs', len(bugs)))} 条；active：{serialize(summary.get('active_bugs', 0))} 条。",
        f"- 疑似非Bug：{len(nonbug)} 条；外部Bug候选：{len(external)} 条；内部Bug候选：{len(internal)} 条；运维Bug：{len(ops)} 条；未分类：{len(unknown)} 条。",
        f"- 低质量任务候选：{len(low_quality)} 个。",
        "- 本报告是会前预分类材料，最终责任界定仍建议在复盘会上结合业务背景确认。",
        "",
        "## 二、部门 Bug 总览",
        "",
        md_table(
            ["归属", "总数", "外部候选", "内部候选", "疑似非Bug", "关键Bug"],
            [
                [
                    dept,
                    serialize(values["total"]),
                    serialize(values["external"]),
                    serialize(values["internal"]),
                    serialize(values["nonbug"]),
                    serialize(values["key"]),
                ]
                for dept, values in sorted(dept_totals.items(), key=lambda item: (-item[1]["total"], item[0]))
            ],
        ),
    ]

    if nonbug:
        lines.extend(
            [
                "",
                "## 三、疑似非Bug清单",
                "",
                md_table(
                    ["BugID", "标题", "类型", "状态", "原因/判断"],
                    [
                        [
                            row.get("id"),
                            trim_text(row.get("title"), 52),
                            row.get("type"),
                            row.get("status"),
                            bug_review_suggestion(row),
                        ]
                        for row in nonbug[:30]
                    ],
                ),
            ]
        )

    if external:
        lines.extend(
            [
                "",
                "## 四、外部Bug界定候选",
                "",
                md_table(
                    ["BugID", "标题", "严重", "状态", "归属", "任务", "原因", "复盘建议"],
                    [
                        [
                            row.get("id"),
                            trim_text(row.get("title"), 46),
                            row.get("severity"),
                            row.get("status"),
                            row.get("ownerDeptName") or row.get("type"),
                            trim_text(row.get("task_name"), 28),
                            trim_text(row.get("causeAnalysis") or row.get("dept_review"), 30),
                            bug_review_suggestion(row),
                        ]
                        for row in external[:50]
                    ],
                ),
            ]
        )

    if internal:
        lines.extend(
            [
                "",
                "## 五、内部Bug界定候选",
                "",
                md_table(
                    ["BugID", "标题", "分类", "严重", "典型", "归属", "任务", "复盘建议"],
                    [
                        [
                            row.get("id"),
                            trim_text(row.get("title"), 46),
                            bug_classification_label(row.get("classification")),
                            row.get("severity"),
                            "是" if str(row.get("isTypical")) == "1" else "",
                            row.get("ownerDeptName") or row.get("type"),
                            trim_text(row.get("task_name"), 28),
                            bug_review_suggestion(row),
                        ]
                        for row in internal[:50]
                    ],
                ),
            ]
        )

    if low_quality:
        lines.extend(
            [
                "",
                "## 六、低质量任务候选",
                "",
                md_table(
                    ["任务ID", "任务", "负责人", "Bug数", "外部", "内部", "关键", "关联Bug"],
                    [
                        [
                            row.get("task_id"),
                            trim_text(row.get("task_name"), 46),
                            row.get("task_assignedName") or row.get("task_assignedTo"),
                            serialize(row.get("bug_count")),
                            serialize(row.get("external_bug_count")),
                            serialize(row.get("internal_bug_count")),
                            serialize(row.get("key_bug_count")),
                            trim_text(row.get("bug_ids"), 34),
                        ]
                        for row in low_quality
                    ],
                ),
            ]
        )

    lines.extend(
        [
            "",
            "## 七、口径纠偏",
            "",
            "- Bug界定是复盘前预分类，不等同于正式版本复盘。",
            "- 疑似非Bug只按显式标记 `type='performance'` 进入，不再把原因不清的 Bug 直接剔除。",
            "- 部门展示优先将 `zt_bug.ownerDept` 数字 ID 映射到 `zt_dept.name`，避免报告出现部门编号。",
        ]
    )
    return "\n".join(lines) + "\n"


def build_version_review_payload(
    repo: ZentaoRepository,
    product_name: str,
    project_name: str,
    version_id: int,
    as_of: dt.date,
) -> dict[str, Any]:
    return {
        "ok": True,
        "as_of": as_of,
        "product_name": product_name,
        "project_name": project_name,
        "version_id": version_id,
        "version_delay": build_version_delay_payload(repo, version_id, as_of),
        "demand_summary": repo.get_version_demand_summary(version_id),
        "demands": repo.get_version_demands(version_id, limit=80),
        "bug_boundary": build_bug_boundary_payload(repo, version_id),
        "trends": repo.get_version_review_trends(product_name, project_name, as_of, limit=8),
    }


def render_version_review_report(payload: dict[str, Any]) -> str:
    version_payload = payload.get("version_delay") or {}
    version = version_payload.get("version") or {}
    summary = version_payload.get("summary") or {}
    pool_delay = version_payload.get("pool_delay") or {}
    demand_summary = (payload.get("demand_summary") or {}).get("summary") or {}
    demand_status = (payload.get("demand_summary") or {}).get("status") or []
    bug_boundary = payload.get("bug_boundary") or {}
    bug_summary = bug_boundary.get("summary", {}).get("summary") or {}
    buckets = bug_boundary.get("buckets") or {}
    low_quality = bug_boundary.get("low_quality_tasks") or []
    trends = payload.get("trends") or []
    overdue = version_payload.get("overdue_open") or []
    finished_late = version_payload.get("finished_late") or []
    marked_delay = version_payload.get("marked_delay") or []

    lines = [
        f"# 版本复盘：{version.get('name') or payload.get('version_id')}",
        "",
        f"复盘日期：{serialize(payload.get('as_of'))}",
        f"版本周期：{serialize(version.get('begin'))} ~ {serialize(version.get('end'))}",
        "",
        "## 一、复盘结论",
        "",
        f"- 版本任务：{serialize(summary.get('total_tasks', 0))} 个；未关闭：{serialize(summary.get('open_tasks', 0))} 个。",
        f"- 版本需求：{serialize(demand_summary.get('total_demands', 0))} 条；未关联任务：{serialize(demand_summary.get('without_task', 0))} 条。",
        f"- Bug总数：{serialize(bug_summary.get('total_bugs', 0))} 条；active：{serialize(bug_summary.get('active_bugs', 0))} 条；高严重active：{serialize(bug_summary.get('active_high_bugs', 0))} 条。",
        f"- 外部Bug候选：{len(buckets.get('external') or [])} 条；内部Bug候选：{len(buckets.get('internal') or [])} 条；疑似非Bug：{len(buckets.get('nonbug') or [])} 条。",
        f"- 当前逾期未完成：{len(overdue)} 个；已完成但晚于截止：{len(finished_late)} 个；显式标记延期：{len(marked_delay)} 个。",
    ]

    if trends:
        lines.extend(
            [
                "",
                "## 二、版本趋势",
                "",
                md_table(
                    ["版本", "周期", "需求", "任务", "未关闭任务", "Bug", "active Bug", "高严重 active"],
                    [
                        [
                            row.get("name"),
                            f"{serialize(row.get('begin'))}~{serialize(row.get('end'))}",
                            serialize(row.get("demands")),
                            serialize(row.get("tasks")),
                            serialize(row.get("open_tasks")),
                            serialize(row.get("bugs")),
                            serialize(row.get("active_bugs")),
                            serialize(row.get("high_active_bugs")),
                        ]
                        for row in trends
                    ],
                ),
            ]
        )

    lines.extend(
        [
            "",
            "## 三、Bug复盘",
            "",
            "### 3.1 外部Bug候选",
            "",
            md_table(
                ["BugID", "标题", "严重", "状态", "归属", "任务", "原因", "建议"],
                [
                    [
                        row.get("id"),
                        trim_text(row.get("title"), 44),
                        row.get("severity"),
                        row.get("status"),
                        row.get("ownerDeptName") or row.get("type"),
                        trim_text(row.get("task_name"), 24),
                        trim_text(row.get("causeAnalysis") or row.get("dept_review"), 30),
                        bug_review_suggestion(row),
                    ]
                    for row in (buckets.get("external") or [])[:40]
                ],
            ),
            "",
            "### 3.2 内部Bug候选",
            "",
            md_table(
                ["BugID", "标题", "分类", "严重", "典型", "归属", "任务", "建议"],
                [
                    [
                        row.get("id"),
                        trim_text(row.get("title"), 44),
                        bug_classification_label(row.get("classification")),
                        row.get("severity"),
                        "是" if str(row.get("isTypical")) == "1" else "",
                        row.get("ownerDeptName") or row.get("type"),
                        trim_text(row.get("task_name"), 24),
                        bug_review_suggestion(row),
                    ]
                    for row in (buckets.get("internal") or [])[:40]
                ],
            ),
        ]
    )

    if low_quality:
        lines.extend(
            [
                "",
                "### 3.3 低质量任务候选",
                "",
                md_table(
                    ["任务ID", "任务", "负责人", "Bug数", "外部", "内部", "关键", "关联Bug"],
                    [
                        [
                            row.get("task_id"),
                            trim_text(row.get("task_name"), 42),
                            row.get("task_assignedName") or row.get("task_assignedTo"),
                            serialize(row.get("bug_count")),
                            serialize(row.get("external_bug_count")),
                            serialize(row.get("internal_bug_count")),
                            serialize(row.get("key_bug_count")),
                            trim_text(row.get("bug_ids"), 30),
                        ]
                        for row in low_quality[:20]
                    ],
                ),
            ]
        )

    lines.extend(
        [
            "",
            "## 四、版本交付复盘",
            "",
            md_table(
                ["版本需求", "已关联任务", "未关联任务", "需求延期原因已填", "需求延期举措已填"],
                [
                    [
                        serialize(demand_summary.get("total_demands", 0)),
                        serialize(demand_summary.get("with_task", 0)),
                        serialize(demand_summary.get("without_task", 0)),
                        serialize(demand_summary.get("delay_reason_count", 0)),
                        serialize(demand_summary.get("delay_measure_count", 0)),
                    ]
                ],
            ),
        ]
    )
    if demand_status:
        lines.extend(["", "### 需求状态分布", "", md_table(["状态", "数量"], [[row.get("status"), serialize(row.get("count"))] for row in demand_status])])
    if overdue or finished_late or marked_delay:
        lines.extend(
            [
                "",
                "### 延期与风险记录",
                "",
                f"- 当前逾期未完成：{len(overdue)} 个。",
                f"- 已完成但晚于截止：{len(finished_late)} 个。",
                f"- 显式标记延期：{len(marked_delay)} 个。",
            ]
        )

    lines.extend(
        [
            "",
            "## 五、需要人工确认",
            "",
            "- 复盘会最终责任归属与管理动作。",
            "- 字段为空的 Bug 现象、影响范围、原因和举措。",
            "- 过程延期的真实原因，尤其是延期字段未填写或只填写在会议纪要中的情况。",
            "",
            "## 六、口径纠偏",
            "",
            "- 版本范围按 `zt_task.execution=版本ID` 与 `zt_pool.type=0 AND zt_pool.pv_id=版本ID` 取数。",
            "- 延期判断优先使用 `zt_task.deadline/finishedDate/delayTimes/delayReason`，不再用需求池 `deliveryDate` 代替任务截止时间。",
            "- Bug界定和版本复盘分开：Bug界定是会前预分类，版本复盘是正式复盘材料。",
        ]
    )
    return "\n".join(lines) + "\n"


def build_dept_risk_payload(
    repo: ZentaoRepository,
    dept_keyword: str,
    version_id: int,
    as_of: dt.date,
) -> dict[str, Any]:
    return {
        "ok": True,
        "dept": dept_keyword,
        "version_id": version_id,
        "as_of": as_of,
        **repo.get_dept_risk(dept_keyword, version_id, as_of),
    }


def render_dept_risk_report(payload: dict[str, Any]) -> str:
    tasks = payload.get("tasks") or []
    bugs = payload.get("bugs") or []
    depts = payload.get("departments") or []
    users = payload.get("users") or []
    overdue = [row for row in tasks if row.get("overdue_days")]
    lines = [
        f"# 部门风险：{payload.get('dept')}",
        "",
        f"版本：{payload.get('version_id')}；查询日期：{serialize(payload.get('as_of'))}",
        "",
        "## 汇总",
        "",
        f"- 匹配部门：{', '.join([row.get('name', '') for row in depts]) or '未直接匹配部门表，按关键词查归属字段'}",
        f"- 匹配人员：{len(users)} 人",
        f"- 未关闭任务：{len(tasks)} 个，其中逾期 {len(overdue)} 个",
        f"- 未关闭 Bug：{len(bugs)} 个",
    ]
    if tasks:
        lines.extend(
            [
                "",
                "## 任务风险",
                "",
                md_table(
                    ["任务ID", "任务", "负责人", "部门", "状态", "截止", "逾期", "剩余工时"],
                    [
                        [
                            row.get("id"),
                            trim_text(row.get("name"), 46),
                            row.get("assignedName") or row.get("assignedTo"),
                            row.get("dept_name"),
                            row.get("status"),
                            serialize(row.get("deadline")),
                            f"{serialize(row.get('overdue_days'))}天" if row.get("overdue_days") else "",
                            serialize(row.get("left")),
                        ]
                        for row in tasks[:40]
                    ],
                ),
            ]
        )
    if bugs:
        lines.extend(
            [
                "",
                "## Bug 风险",
                "",
                md_table(
                    ["BugID", "标题", "状态", "严重", "负责人", "归属", "创建时间"],
                    [
                        [
                            row.get("id"),
                            trim_text(row.get("title"), 50),
                            row.get("status"),
                            row.get("severity"),
                            row.get("assignedName") or row.get("assignedTo"),
                            row.get("ownerDeptName") or row.get("ownerDept") or row.get("type"),
                            serialize(row.get("openedDate")),
                        ]
                        for row in bugs[:40]
                    ],
                ),
            ]
        )
    return "\n".join(lines) + "\n"


def build_weekly_report_payload(
    repo: ZentaoRepository,
    product_name: str,
    project_name: str,
    start_date: dt.date,
    end_date: dt.date,
    as_of: dt.date,
) -> dict[str, Any]:
    sprint = repo.get_current_sprint_for_product(product_name, as_of, project_name)
    if not sprint:
        return {"ok": False, "message": f"没有定位到 {product_name} 当前版本。"}
    return {
        "ok": True,
        "start_date": start_date,
        "end_date": end_date,
        "as_of": as_of,
        "current_sprint": sprint,
        **repo.get_weekly_report_data(int(sprint["id"]), start_date, end_date, as_of),
    }


def render_weekly_report(payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        return str(payload.get("message", "周报生成失败。"))
    sprint = payload.get("current_sprint") or {}
    task_summary = payload.get("task_summary", {}).get("summary") or {}
    bug_summary = payload.get("bug_summary", {}).get("summary") or {}
    task_flow = payload.get("weekly_task_flow") or {}
    bug_flow = payload.get("weekly_bug_flow") or {}
    overdue = payload.get("overdue_open") or []
    active_bugs = payload.get("active_bugs") or []
    todos = payload.get("unfinished_todos") or []
    lines = [
        f"# 项目周报（{serialize(payload.get('start_date'))} ~ {serialize(payload.get('end_date'))}）",
        "",
        f"当前版本：{sprint.get('name')}（{serialize(sprint.get('begin'))} ~ {serialize(sprint.get('end'))}）",
        "",
        "## 一、核心结论",
        "",
        f"- 本周新建任务：{serialize(task_flow.get('opened', 0))} 个；完成任务：{serialize(task_flow.get('finished', 0))} 个；关闭任务：{serialize(task_flow.get('closed_count', 0))} 个。",
        f"- 当前版本任务总数：{serialize(task_summary.get('total_tasks', 0))} 个；未关闭：{serialize(task_summary.get('open_tasks', 0))} 个。",
        f"- 当前逾期未完成任务：{len(overdue)} 个。",
        f"- 本周新增 Bug：{serialize(bug_flow.get('opened', 0))} 个；解决 Bug：{serialize(bug_flow.get('resolved', 0))} 个；关闭 Bug：{serialize(bug_flow.get('closed_count', 0))} 个。",
        f"- 当前 active Bug：{serialize(bug_summary.get('active_bugs', 0))} 个；未完成待办：{len(todos)} 条。",
    ]
    if overdue:
        lines.extend(
            [
                "",
                "## 二、延期风险",
                "",
                md_table(
                    ["任务ID", "所属需求", "任务", "负责人", "截止", "逾期", "剩余工时"],
                    [
                        [
                            row.get("id"),
                            trim_text(row.get("root_name"), 28),
                            trim_text(row.get("name"), 42),
                            row.get("assignedName") or row.get("assignedTo"),
                            serialize(row.get("deadline")),
                            f"{serialize(row.get('overdue_days'))}天",
                            serialize(row.get("left")),
                        ]
                        for row in overdue[:30]
                    ],
                ),
            ]
        )
    if active_bugs:
        lines.extend(
            [
                "",
                "## 三、当前 Active Bug",
                "",
                md_table(
                    ["BugID", "标题", "严重", "优先级", "负责人", "创建时间"],
                    [
                        [
                            row.get("id"),
                            trim_text(row.get("title"), 52),
                            row.get("severity"),
                            row.get("pri"),
                            row.get("assignedName") or row.get("assignedTo"),
                            serialize(row.get("openedDate")),
                        ]
                        for row in active_bugs[:30]
                    ],
                ),
            ]
        )
    if todos:
        lines.extend(
            [
                "",
                "## 四、未完成待办",
                "",
                md_table(
                    ["ID", "状态", "待办", "部门", "责任人", "截止"],
                    [
                        [
                            row.get("id"),
                            row.get("status_name"),
                            trim_text(row.get("content"), 50),
                            row.get("dept_name"),
                            row.get("duty_names"),
                            serialize(row.get("deadlineTime")),
                        ]
                        for row in todos[:30]
                    ],
                ),
            ]
        )
    return "\n".join(lines) + "\n"
