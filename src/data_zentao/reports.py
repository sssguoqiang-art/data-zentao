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


def bug_boundary_state(row: dict[str, Any]) -> str:
    owner = str(row.get("ownerDeptName") or row.get("ownerDept") or "").strip()
    has_reason = bool(row.get("causeAnalysis") or row.get("dept_review"))
    if owner and owner != "未填写" and has_reason:
        return "确定"
    if owner and owner != "未填写":
        return "需会前确认"
    return "归属待补充"


def bug_severity_text(value: object) -> str:
    mapping = {
        1: "极严重",
        2: "高",
        3: "中",
        4: "低",
    }
    try:
        return mapping.get(int(value), serialize(value))
    except (TypeError, ValueError):
        return serialize(value)


def report_version_name(payload: dict[str, Any]) -> str:
    version = payload.get("version") or {}
    return str(version.get("name") or payload.get("version_id") or "未知版本")


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

    status_counts = {row.get("status"): int(row.get("count") or 0) for row in task_status}
    done_count = status_counts.get("done", 0) + status_counts.get("closed", 0)
    dev_count = status_counts.get("wait", 0) + status_counts.get("doing", 0)
    testing_count = status_counts.get("testing", 0) + status_counts.get("waittest", 0)
    release_label = "发布日" if days_left == 0 else (f"距发布 {days_left} 天" if days_left is not None else "推进核查")
    weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    date_label = f"{as_of.month}月{as_of.day}日（{weekday_names[as_of.weekday()]}）"

    lines = [
        f"# 平台项目日报 · {date_label} · {release_label}",
        "",
        f"## 当前版本 {sprint.get('name')} · 发布核查",
        "",
        (
            f"> 当前版本任务 {serialize(task_summary.get('total_tasks', 0))} 项，"
            f"已完成/关闭 {done_count} 项，未关闭 {serialize(task_summary.get('open_tasks', 0))} 项；"
            f"今日完成 {len(today_finished)} 项，今日新建 {len(today_opened)} 项。"
            f"当前 Active Bug {serialize(bug_summary.get('active_bugs', 0))} 条，"
            f"逾期未完成任务 {len(overdue_open)} 项。"
        ),
        "",
        f"**可直接发布：{done_count} 项已完成/关闭**",
        "",
        "---",
        "",
        f"**开发中/未开始（{dev_count}）**",
        "",
        md_table(
            ["状态", "中文含义", "数量"],
            [
                [row.get("status"), TASK_STATUS_LABELS.get(row.get("status"), ""), serialize(row.get("count"))]
                for row in task_status
                if row.get("status") in {"wait", "doing"}
            ],
        ),
        "",
        "---",
        "",
        f"**测试中（{testing_count}）**",
        "",
        md_table(
            ["状态", "中文含义", "数量"],
            [
                [row.get("status"), TASK_STATUS_LABELS.get(row.get("status"), ""), serialize(row.get("count"))]
                for row in task_status
                if row.get("status") in {"testing", "waittest"}
            ] or [["无", "", "0"]],
        ),
    ]

    if today_finished:
        lines.extend(
            [
                "",
                "---",
                "",
                f"**今日完成任务（{len(today_finished)}）**",
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
                "---",
                "",
                f"**今日新建任务（{len(today_opened)}）**",
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

    lines.extend(["", "---", "", f"**延期关注（{len(overdue_open)}）**", ""])
    if overdue_open:
        lines.append(
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
            )
        )
    else:
        lines.append("当前没有逾期未完成任务。")

    if due_today:
        lines.extend(
            [
                "",
                f"**今日到期未完成任务（{len(due_today)}）**",
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
                "**任务字段中显式记录延期的任务**",
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

    lines.extend(
        [
            "",
            "---",
            "",
            f"**线上/版本 Bug（{serialize(bug_summary.get('active_bugs', 0))}）**",
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
        ]
    )

    if active_bugs:
        lines.extend(
            [
                "",
                "**当前 Active Bug 明细**",
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
            "---",
            "",
            f"## 下一版本 {next_sprint.get('name') if next_sprint else '未定位'}",
            "",
            (
                f"> 下一版本需求 {serialize(next_demand_summary.get('total_demands', 0))} 项，"
                f"已关联任务 {serialize(next_demand_summary.get('with_task', 0))} 项，"
                f"未关联任务 {serialize(next_demand_summary.get('without_task', 0))} 项；"
                f"任务总数 {serialize(next_task_summary.get('total_tasks', 0))} 项，"
                f"未关闭 {serialize(next_task_summary.get('open_tasks', 0))} 项。"
            ),
            "",
            "**需求总览**",
            "",
            md_table(
                ["需求总数", "已下单/有关联任务", "未下单/未关联任务", "延期原因已填", "延期举措已填"],
                [
                    [
                        serialize(next_demand_summary.get("total_demands", 0)),
                        serialize(next_demand_summary.get("with_task", 0)),
                        serialize(next_demand_summary.get("without_task", 0)),
                        serialize(next_demand_summary.get("delay_reason_count", 0)),
                        serialize(next_demand_summary.get("delay_measure_count", 0)),
                    ]
                ],
            ),
            "",
            "**版本任务概况**",
            "",
            md_table(
                ["版本", "开始", "结束", "任务数", "未关闭任务"],
                [
                    [
                        next_sprint.get("name") if next_sprint else "未定位",
                        serialize(next_sprint.get("begin")) if next_sprint else "",
                        serialize(next_sprint.get("end")) if next_sprint else "",
                        serialize(next_task_summary.get("total_tasks", 0)),
                        serialize(next_task_summary.get("open_tasks", 0)),
                    ]
                ],
            ),
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
    version_name = report_version_name(payload)

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
        f"# {version_name}Bug 界定预分类",
        "",
        f"**数据截取时间：** {dt.datetime.now().strftime('%Y-%m-%d %H:%M')} · "
        f"**原始Bug总量：** {serialize(summary.get('total_bugs', len(bugs)))} 条 · "
        f"疑似非Bug {len(nonbug)} 条",
        "",
        md_table(
            ["外部复盘Bug", "内部复盘Bug", "低质量任务", "疑似非Bug", "未分类"],
            [[f"{len(external)} 条", f"{len(internal)} 条", f"{len(low_quality)} 个", f"{len(nonbug)} 条", f"{len(unknown)} 条"]],
        ),
        "",
        "---",
        "",
        "## 一、部门 Bug 数量总览",
        "",
        md_table(
            ["部门", "外部Bug", "内部Bug（高/典型）", "疑似非Bug", "合计"],
            [
                [
                    dept,
                    serialize(values["external"]),
                    serialize(values["internal"]),
                    serialize(values["nonbug"]),
                    f"**{serialize(values['total'])}**",
                ]
                for dept, values in sorted(dept_totals.items(), key=lambda item: (-item[1]["total"], item[0]))
            ] or [["无", "0", "0", "0", "**0**"]],
        ),
        "",
        "---",
        "",
        "## 二、疑似非Bug 清单",
        "",
    ]

    if nonbug:
        lines.append(
            md_table(
                ["BugID", "标题", "类型", "状态", "剔除原因"],
                [
                    [
                        row.get("id"),
                        trim_text(row.get("title"), 52),
                        row.get("type"),
                        row.get("status"),
                        trim_text(row.get("causeAnalysis") or bug_review_suggestion(row), 36),
                    ]
                    for row in nonbug[:30]
                ],
            )
        )
    else:
        lines.append("本版本无疑似非Bug。")

    lines.extend(["", "---", "", f"## 三、外部 Bug 责任界定（{len(external)} 条）", ""])
    if external:
        lines.append(
            md_table(
                ["BugID", "标题", "缺陷等级", "责任部门", "归属类型", "复盘建议", "可能原因"],
                [
                    [
                        row.get("id"),
                        trim_text(row.get("title"), 44),
                        bug_severity_text(row.get("severity")),
                        row.get("ownerDeptName") or row.get("type") or "未填写",
                        bug_boundary_state(row),
                        bug_review_suggestion(row),
                        trim_text(row.get("causeAnalysis") or row.get("dept_review"), 40),
                    ]
                    for row in external[:50]
                ],
            )
        )
    else:
        lines.append("本版本没有外部 Bug 责任界定候选。")

    lines.extend(["", "---", "", f"## 四、内部 Bug 责任界定（{len(internal)} 条）", ""])
    if internal:
        lines.append(
            md_table(
                ["BugID", "标题", "缺陷等级", "分类", "责任部门", "归属类型", "关联任务", "复盘建议"],
                [
                    [
                        row.get("id"),
                        trim_text(row.get("title"), 42),
                        bug_severity_text(row.get("severity")),
                        bug_classification_label(row.get("classification")),
                        row.get("ownerDeptName") or row.get("type") or "未填写",
                        bug_boundary_state(row),
                        trim_text(row.get("task_name"), 30),
                        bug_review_suggestion(row),
                    ]
                    for row in internal[:50]
                ],
            )
        )
    else:
        lines.append("本版本没有内部 Bug 责任界定候选。")

    lines.extend(["", "---", "", f"## 五、低质量任务（{len(low_quality)} 个）", ""])
    if low_quality:
        lines.append(
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
            )
        )
    else:
        lines.append("本版本没有达到低质量任务阈值的候选。")

    if ops:
        lines.extend(["", "### 运维Bug补充", "", md_table(["BugID", "标题", "状态", "归属"], [[row.get("id"), trim_text(row.get("title"), 48), row.get("status"), row.get("ownerDeptName") or row.get("type")] for row in ops[:20]])])

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
    demand_summary = (payload.get("demand_summary") or {}).get("summary") or {}
    bug_boundary = payload.get("bug_boundary") or {}
    bug_summary = bug_boundary.get("summary", {}).get("summary") or {}
    buckets = bug_boundary.get("buckets") or {}
    external = buckets.get("external") or []
    internal = buckets.get("internal") or []
    nonbug = buckets.get("nonbug") or []
    low_quality = bug_boundary.get("low_quality_tasks") or []
    trends = payload.get("trends") or []
    overdue = version_payload.get("overdue_open") or []
    finished_late = version_payload.get("finished_late") or []
    marked_delay = version_payload.get("marked_delay") or []

    version_name = str(version.get("name") or payload.get("version_id") or "未知版本")
    review_internal = [
        row for row in internal if row.get("severity") in {1, 2} or str(row.get("isTypical")) == "1"
    ] or internal[:10]

    def count_by_dept(rows: list[dict[str, Any]]) -> list[list[str]]:
        counts: dict[str, int] = {}
        for row in rows:
            dept = row.get("ownerDeptName") or row.get("ownerDept") or row.get("type") or "未填写"
            counts[dept] = counts.get(dept, 0) + 1
        return [[dept, serialize(count)] for dept, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))]

    def append_deep_analysis(lines_ref: list[str], rows: list[dict[str, Any]], prefix: str = "深度分析") -> None:
        for index, row in enumerate(rows[:6], 1):
            lines_ref.extend(
                [
                    "",
                    f"### {prefix}（{index}）",
                    "",
                    f"# {trim_text(row.get('title'), 80)}",
                    "",
                    f"**BugID：** {row.get('id')}",
                    f"**Bug现象：** {trim_text(row.get('phenomenon') or row.get('title'), 160)}",
                    f"**缺陷等级：** {bug_severity_text(row.get('severity'))}",
                    f"**责任部门：** {row.get('ownerDeptName') or row.get('ownerDept') or row.get('type') or '未填写'}",
                    f"**可能原因：** {trim_text(row.get('causeAnalysis') or row.get('dept_review') or '【待补充·人工】', 180)}",
                    f"**举措：** {trim_text(row.get('nextStep') or '【待补充·人工】', 180)}",
                    "",
                    "---",
                ]
            )

    high_internal = [row for row in internal if row.get("severity") in {1, 2}]
    bug_type_counts: dict[str, dict[str, Any]] = {}
    for row in high_internal:
        label = str(row.get("bugType") or row.get("bugTypeParent") or "原因待确认")
        dept = row.get("ownerDeptName") or row.get("ownerDept") or row.get("type") or "未填写"
        if label not in bug_type_counts:
            bug_type_counts[label] = {"count": 0, "depts": {}}
        bug_type_counts[label]["count"] += 1
        bug_type_counts[label]["depts"][dept] = bug_type_counts[label]["depts"].get(dept, 0) + 1

    lines = [
        f"# {version_name}版本复盘",
        "",
        f"**部门：** 效能组、测试组 **复盘时间：** {serialize(payload.get('as_of'))}",
        "",
        "---",
        "",
        "## 一、外部Bug复盘",
        "",
        f"### 1.1 {version_name} 外部Bug概览",
        "",
        "**外部Bug数量趋势：**",
        "",
        md_table(
            ["版本", "外部Bug", "疑似非Bug", "全部Bug"],
            [
                [
                    row.get("name"),
                    serialize(row.get("external_bugs", 0)),
                    serialize(row.get("nonbug_bugs", 0)),
                    serialize(row.get("bugs", 0)),
                ]
                for row in trends
            ] or [[version_name, len(external), len(nonbug), serialize(bug_summary.get("total_bugs", 0))]],
        ),
        "",
        f"**当前版本Bug数：** {len(external)}",
        f"**外部Bug反馈总数：** {len(external) + len(nonbug)}",
        "",
        f"**结论：** {version_name} 外部Bug候选 {len(external)} 条，疑似非Bug {len(nonbug)} 条。",
        "",
        "### 1.2 外部Bug 非Bug剔除列表",
        "",
    ]

    if nonbug:
        lines.append(
            md_table(
                ["序号", "BugID", "Bug标题", "剔除原因"],
                [
                    [
                        index,
                        row.get("id"),
                        trim_text(row.get("title"), 56),
                        trim_text(row.get("causeAnalysis") or bug_review_suggestion(row), 50),
                    ]
                    for index, row in enumerate(nonbug, 1)
                ],
            )
        )
    else:
        lines.append("本版本没有按字段识别到疑似非Bug。")

    lines.extend(
        [
            "",
            f"**结论：** 当前版本外部共产生 {len(external) + len(nonbug)} 条候选，其中 {len(nonbug)} 条按字段识别为疑似非Bug。",
            "",
            "### 1.3 外部Bug 实际复盘Bug列表",
            "",
            md_table(
                ["序号", "BugID", "Bug标题", "缺陷等级/影响", "Bug现象", "责任部门"],
                [
                    [
                        index,
                        row.get("id"),
                        trim_text(row.get("title"), 48),
                        bug_severity_text(row.get("severity")),
                        trim_text(row.get("phenomenon") or row.get("title"), 42),
                        row.get("ownerDeptName") or row.get("ownerDept") or row.get("type") or "未填写",
                    ]
                    for index, row in enumerate(external, 1)
                ] or [["-", "-", "本版本没有外部复盘Bug", "-", "-", "-"]],
            ),
            "",
            f"**结论：** 当前版本对 {len(external)} 条外部Bug进行复盘候选识别。",
            "",
            f"### 1.4 {version_name} 外部Bug责任归属 — 测试组",
            "",
            "测试组相关责任需结合复盘会确认；当前工具先保留字段中已有的归属和部门复盘信息。",
            "",
            f"### 1.5 {version_name} 外部Bug责任归属 — 其它部门",
            "",
            md_table(["部门", "Bug数量"], count_by_dept(external) or [["无", "0"]]),
        ]
    )
    append_deep_analysis(lines, external[:3])
    lines.extend(
        [
            "",
            "### 1.6 外部Bug复盘总结 核心管理问题",
            "",
            md_table(
                ["序号", "管理问题类别", "涉及Bug", "涉及部门", "待办项"],
                [
                    [
                        index,
                        trim_text(row.get("causeAnalysis") or "原因待填写（待确认）", 34),
                        row.get("id"),
                        row.get("ownerDeptName") or row.get("ownerDept") or row.get("type") or "未填写",
                        trim_text(row.get("nextStep") or "【待补充·人工】", 38),
                    ]
                    for index, row in enumerate(external[:20], 1)
                ] or [["-", "本版本无外部复盘Bug", "-", "-", "-"]],
            ),
            "",
            "---",
            "",
            "## 二、内部Bug复盘",
            "",
            f"### 2.1 {version_name} 内部Bug概览",
            "",
            "**内部Bug数量趋势：**",
            "",
            md_table(
                ["版本", "内部Bug总数", "全部Bug"],
                [[row.get("name"), serialize(row.get("internal_bugs", 0)), serialize(row.get("bugs", 0))] for row in trends]
                or [[version_name, len(internal), serialize(bug_summary.get("total_bugs", 0))]],
            ),
            "",
            f"**当前版本内部Bug总数：** {len(internal)}",
            "",
            "### 2.2 内部Bug 重要缺陷分布",
            "",
            md_table(["部门", "高/极严重Bug数量"], count_by_dept(high_internal) or [["本版本无高/极严重内部Bug", "0"]]),
            "",
            "### 2.3 内部Bug 高缺陷Bug类型分析",
            "",
            md_table(
                ["序号", "Bug类型", "涉及部门"],
                [
                    [
                        index,
                        f"{label}（{info['count']}条）",
                        "、".join(f"{dept}（{count}）" for dept, count in info["depts"].items()),
                    ]
                    for index, (label, info) in enumerate(
                        sorted(bug_type_counts.items(), key=lambda item: (-item[1]["count"], item[0])),
                        1,
                    )
                ]
                or [["-", "本版本无高缺陷内部Bug类型", "-"]],
            ),
            "",
            "### 2.4 复盘Bug列表（高缺陷Bug+典型Bug）",
            "",
            md_table(
                ["序号", "BugID", "Bug标题", "缺陷等级", "责任部门", "归属类型"],
                [
                    [
                        index,
                        row.get("id"),
                        trim_text(row.get("title"), 50),
                        bug_severity_text(row.get("severity")),
                        row.get("ownerDeptName") or row.get("ownerDept") or row.get("type") or "未填写",
                        bug_boundary_state(row),
                    ]
                    for index, row in enumerate(review_internal, 1)
                ] or [["-", "-", "本版本没有高缺陷或典型内部Bug", "-", "-", "-"]],
            ),
            "",
            "### 内部Bug 典型Bug复盘",
        ]
    )
    append_deep_analysis(lines, review_internal)
    lines.extend(
        [
            "",
            "### 2.5 低质量任务分析",
            "",
            md_table(
                ["任务ID", "任务名称", "Bug数", "含高/典型", "负责人", "管理判断"],
                [
                    [
                        row.get("task_id"),
                        trim_text(row.get("task_name"), 44),
                        serialize(row.get("bug_count")),
                        serialize(row.get("key_bug_count")),
                        row.get("task_assignedName") or row.get("task_assignedTo"),
                        "提测质量需关注；Bug较集中，建议加强自测和用例覆盖。",
                    ]
                    for row in low_quality[:20]
                ] or [["-", "本版本没有达到低质量任务阈值的候选", "0", "0", "-", "-"]],
            ),
            "",
            "### 2.6 测试组不可容忍的Bug类型总结",
            "",
            md_table(
                ["Bug类型", "本版本数量", "判定标准"],
                [["需求不明确/原因待确认", len([row for row in internal if not row.get("causeAnalysis") and not row.get("dept_review")]), "字段缺少原因或部门复盘信息，复盘会需补齐"]],
            ),
            "",
            "---",
            "",
            "## 三、版本复盘",
            "",
            "### 3.1 版本需求趋势",
            "",
            md_table(
                ["版本", "需求", "任务", "未关闭任务", "Bug"],
                [
                    [
                        row.get("name"),
                        serialize(row.get("demands")),
                        serialize(row.get("tasks")),
                        serialize(row.get("open_tasks")),
                        serialize(row.get("bugs")),
                    ]
                    for row in trends
                ]
                or [[version_name, serialize(demand_summary.get("total_demands", 0)), serialize(summary.get("total_tasks", 0)), serialize(summary.get("open_tasks", 0)), serialize(bug_summary.get("total_bugs", 0))]],
            ),
            "",
            f"**版本概况：** 本版本需求 {serialize(demand_summary.get('total_demands', 0))} 项，任务 {serialize(summary.get('total_tasks', 0))} 个，未关闭任务 {serialize(summary.get('open_tasks', 0))} 个。",
            "",
            "### 3.2 延期情况",
            "",
            f"**当前版本过程延期总数：** 当前逾期未完成 {len(overdue)} 个，已完成但晚于截止 {len(finished_late)} 个，显式标记延期 {len(marked_delay)} 个。",
            "",
            "### 3.3 延期任务记录",
            "",
            md_table(
                ["序号", "延期任务标题", "任务来源", "延期次数", "负责人", "截止时间", "延期判断"],
                [
                    [
                        index,
                        trim_text(row.get("name"), 50),
                        trim_text(row.get("root_name"), 28),
                        serialize(row.get("delayTimes") or ""),
                        row.get("assignedName") or row.get("assignedTo"),
                        serialize(row.get("deadline")),
                        f"逾期 {serialize(row.get('overdue_days'))} 天" if row.get("overdue_days") else "字段标记延期",
                    ]
                    for index, row in enumerate((overdue + marked_delay)[:30], 1)
                ] or [["-", "本版本没有查到延期任务记录", "-", "-", "-", "-", "-"]],
            ),
            "",
            "### 3.4 上周复盘待办项",
            "",
            md_table(
                ["序号", "待办", "部门", "截止时间"],
                [["【待补充·人工】", "【待补充·人工】", "【待补充·人工】", "【待补充·人工】"]],
            ),
            "",
            "---",
            "",
            "## THANK YOU",
            "",
            "复盘时间：【待补充·人工】",
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


def _weekly_version_snapshot(
    repo: ZentaoRepository,
    sprint: dict[str, Any] | None,
    as_of: dt.date,
) -> dict[str, Any] | None:
    if not sprint:
        return None
    version_id = int(sprint["id"])
    return {
        "sprint": sprint,
        "task_summary": repo.get_version_task_summary(version_id, as_of),
        "demand_summary": repo.get_version_demand_summary(version_id),
        "bug_summary": repo.get_bug_summary(version_id, as_of),
    }


def build_weekly_summary_payload(
    repo: ZentaoRepository,
    start_date: dt.date,
    end_date: dt.date,
    as_of: dt.date,
    projects: list[dict[str, str]] | None = None,
    include_history: bool = True,
) -> dict[str, Any]:
    project_specs = projects or [
        {"key": "platform", "label": "平台项目", "product_name": "平台部", "project_name": "平台部"},
        {"key": "game", "label": "游戏项目", "product_name": "游戏部", "project_name": "游戏部"},
    ]
    project_payloads: list[dict[str, Any]] = []
    warnings: list[str] = []

    for spec in project_specs:
        product_name = spec["product_name"]
        project_name = spec["project_name"]
        current = repo.get_current_sprint_for_product(product_name, as_of, project_name)
        previous = repo.get_latest_completed_sprint_for_product(product_name, as_of, project_name) if include_history else None
        next_sprint = repo.get_next_sprint_for_product(product_name, as_of, project_name) if include_history else None
        current_weekly = repo.get_weekly_report_data(int(current["id"]), start_date, end_date, as_of) if current else None
        if not current:
            warnings.append(f"{spec['label']}未定位到当前版本")
        project_payloads.append(
            {
                **spec,
                "previous": _weekly_version_snapshot(repo, previous, as_of),
                "current": _weekly_version_snapshot(repo, current, as_of),
                "next": _weekly_version_snapshot(repo, next_sprint, as_of),
                "weekly": current_weekly,
            }
        )

    return {
        "ok": any(project.get("current") for project in project_payloads),
        "start_date": start_date,
        "end_date": end_date,
        "as_of": as_of,
        "projects": project_payloads,
        "warnings": warnings,
    }


def _snapshot_summary(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    if not snapshot:
        return {}
    return (snapshot.get("task_summary") or {}).get("summary") or {}


def _snapshot_demand(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    if not snapshot:
        return {}
    return (snapshot.get("demand_summary") or {}).get("summary") or {}


def _snapshot_bug(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    if not snapshot:
        return {}
    return (snapshot.get("bug_summary") or {}).get("summary") or {}


def render_weekly_summary_report(payload: dict[str, Any], report_type: str = "summary") -> str:
    if not payload.get("ok"):
        warnings = "；".join(payload.get("warnings") or [])
        return f"周汇总生成失败：{warnings or '没有定位到当前版本。'}\n"

    title = "效能周报" if report_type == "report" else "效能周汇总"
    lines = [
        f"# {title}（{serialize(payload.get('start_date'))} ~ {serialize(payload.get('end_date'))}）",
        "",
        f"生成日期：{serialize(payload.get('as_of'))}",
        "",
        "## 一、总体结论",
        "",
    ]

    conclusion_rows = []
    for project in payload.get("projects") or []:
        current = project.get("current")
        weekly = project.get("weekly") or {}
        sprint = (current or {}).get("sprint") or {}
        task_summary = _snapshot_summary(current)
        bug_summary = _snapshot_bug(current)
        next_sprint = ((project.get("next") or {}).get("sprint") or {}).get("name") or ""
        conclusion_rows.append(
            [
                project.get("label"),
                sprint.get("name") or "未定位",
                serialize(task_summary.get("total_tasks", 0)),
                serialize(task_summary.get("open_tasks", 0)),
                len(weekly.get("overdue_open") or []),
                serialize(bug_summary.get("active_bugs", 0)),
                next_sprint,
            ]
        )

    lines.extend(
        [
            md_table(["项目", "当前版本", "任务数", "未关闭", "逾期未完成", "Active Bug", "下一版本"], conclusion_rows),
            "",
            "## 二、项目版本状态",
        ]
    )

    for project in payload.get("projects") or []:
        label = project.get("label")
        previous = project.get("previous")
        current = project.get("current")
        next_snapshot = project.get("next")
        weekly = project.get("weekly") or {}
        lines.extend(["", f"### {label}", ""])

        version_rows = []
        for name, snapshot in [("上一版本", previous), ("当前版本", current), ("下一版本", next_snapshot)]:
            sprint = (snapshot or {}).get("sprint") or {}
            task_summary = _snapshot_summary(snapshot)
            demand_summary = _snapshot_demand(snapshot)
            bug_summary = _snapshot_bug(snapshot)
            version_rows.append(
                [
                    name,
                    sprint.get("name") or "未定位",
                    f"{serialize(sprint.get('begin'))} ~ {serialize(sprint.get('end'))}" if sprint else "",
                    serialize(demand_summary.get("total_demands", 0)),
                    serialize(task_summary.get("total_tasks", 0)),
                    serialize(task_summary.get("open_tasks", 0)),
                    serialize(bug_summary.get("total_bugs", 0)),
                ]
            )
        lines.append(md_table(["版本", "名称", "周期", "需求", "任务", "未关闭任务", "Bug"], version_rows))

        if current:
            task_flow = weekly.get("weekly_task_flow") or {}
            bug_flow = weekly.get("weekly_bug_flow") or {}
            lines.extend(
                [
                    "",
                    "#### 本周推进",
                    "",
                    md_table(
                        ["新建任务", "完成任务", "关闭任务", "新增Bug", "解决Bug", "关闭Bug"],
                        [
                            [
                                serialize(task_flow.get("opened", 0)),
                                serialize(task_flow.get("finished", 0)),
                                serialize(task_flow.get("closed_count", 0)),
                                serialize(bug_flow.get("opened", 0)),
                                serialize(bug_flow.get("resolved", 0)),
                                serialize(bug_flow.get("closed_count", 0)),
                            ]
                        ],
                    ),
                ]
            )
            overdue = weekly.get("overdue_open") or []
            if overdue:
                lines.extend(
                    [
                        "",
                        "#### 延期风险",
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
                                for row in overdue[:20]
                            ],
                        ),
                    ]
                )

    lines.extend(
        [
            "",
            "## 三、重点风险与下周关注",
            "",
            md_table(
                ["项目", "关注点", "建议动作"],
                [
                    [
                        project.get("label"),
                        "延期任务、Active Bug、下一版本未关闭任务",
                        "周会优先确认延期任务责任人、Bug收敛计划和下版本准备状态。",
                    ]
                    for project in payload.get("projects") or []
                ],
            ),
            "",
            "## 四、专题进展（待补充）",
            "",
            "| 专题 | 当前状态 | 需要补充 |\n| --- | --- | --- |\n| Web5 / 性能 / AI / 招聘等专项 | 【待补充·人工】 | 请结合非禅道信息补充 |",
            "",
            "## 五、下周关注",
            "",
            "- 当前版本剩余任务和延期项是否能在发布日前收敛。",
            "- 下一版本需求是否已下单、是否存在未关联任务或负责人未明确的项目。",
            "- Active Bug 是否存在高严重级别、跨部门争议或需要复盘会提前确认的事项。",
        ]
    )
    return "\n".join(lines) + "\n"
