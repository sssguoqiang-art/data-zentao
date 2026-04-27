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
    bug_type = str(row.get("type") or "")
    if classification in {"1", "2"} and bug_type == "performance":
        return "nonbug"
    if classification in {"1", "2"}:
        return "external"
    if classification == "3":
        return "ops"
    if classification in {"4", "5"} and bug_type in {"performance", "DDProblem"}:
        return "excluded"
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


def review_bug_severity_text(value: object, *, with_impact: bool = False) -> str:
    mapping = {
        1: "极严重缺陷",
        2: "高等缺陷",
        3: "中等缺陷",
        4: "低等缺陷",
    }
    try:
        text = mapping.get(int(value), str(serialize(value) or "未填写"))
    except (TypeError, ValueError):
        text = str(serialize(value) or "未填写")
    if with_impact and text == "中等缺陷":
        return "中等缺陷 影响较小"
    return text


def report_version_name(payload: dict[str, Any]) -> str:
    version = payload.get("version") or {}
    return str(version.get("name") or payload.get("version_id") or "未知版本")


def display_dept(value: object) -> str:
    text = str(value or "未填写")
    replacements = {
        "PHP1部": "PHP1组",
        "PHP2部": "PHP2组",
        "Web部": "Web组",
        "Cocos部": "Cocos组",
        "产品部": "产品组",
        "测试部": "测试组",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text


def split_depts(value: object) -> list[str]:
    raw = str(value or "")
    separators = [",", "，", "、", " "]
    for separator in separators[1:]:
        raw = raw.replace(separator, separators[0])
    return [display_dept(part.strip()) for part in raw.split(",") if part.strip()]


def parse_dept_review(value: object) -> list[dict[str, str]]:
    text = str(value or "").strip()
    if not text:
        return []
    rows: list[dict[str, str]] = []
    if "||ROW||" in text or "||" in text:
        for item in text.split("||ROW||"):
            parts = item.split("||")
            if len(parts) >= 3:
                rows.append(
                    {
                        "dept": display_dept(parts[0]),
                        "cause": parts[1].strip(),
                        "next": parts[2].strip(),
                    }
                )
        return [row for row in rows if row["dept"] or row["cause"] or row["next"]]
    for item in text.split(" | "):
        parts = item.split("：", 2)
        if len(parts) == 3:
            rows.append({"dept": display_dept(parts[0]), "cause": parts[1].strip(), "next": parts[2].strip()})
        elif len(parts) == 2:
            rows.append({"dept": display_dept(parts[0]), "cause": parts[1].strip(), "next": ""})
    return rows


def bug_url(bug_id: object) -> str:
    return f"https://cd.baa360.cc:20088/index.php?m=bug&f=view&bugID={bug_id}"


def task_url(task_id: object) -> str:
    return f"https://cd.baa360.cc:20088/index.php?m=task&f=view&taskID={task_id}"


def markdown_link(label: object, url: str) -> str:
    return f"[{label}]({url})"


def compact_dept_list(value: object) -> str:
    return "、".join(split_depts(value)) or "未填写"


def format_short_date(value: object) -> str:
    if isinstance(value, dt.datetime):
        return f"{value.month:02d}-{value.day:02d}"
    if isinstance(value, dt.date):
        return f"{value.month:02d}-{value.day:02d}"
    text = str(value or "")
    try:
        parsed = dt.date.fromisoformat(text[:10])
    except ValueError:
        return ""
    return f"{parsed.month:02d}-{parsed.day:02d}"


def format_month_day(value: object) -> str:
    if isinstance(value, dt.datetime):
        return f"{value.month}-{value.day}"
    if isinstance(value, dt.date):
        return f"{value.month}-{value.day}"
    text = str(value or "")
    try:
        parsed = dt.date.fromisoformat(text[:10])
    except ValueError:
        return ""
    return f"{parsed.month}-{parsed.day}"


def review_date_after_version(version: dict[str, Any]) -> dt.date | None:
    end = version.get("end")
    if isinstance(end, dt.datetime):
        end_date = end.date()
    elif isinstance(end, dt.date):
        end_date = end
    elif end:
        try:
            end_date = dt.date.fromisoformat(str(end)[:10])
        except ValueError:
            return None
    else:
        return None
    return end_date + dt.timedelta(days=(4 - end_date.weekday()) % 7)


def format_cn_date(value: dt.date | None) -> str:
    if not value:
        return "【待补充·人工】"
    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    return f"{value.year}年{value.month}月{value.day}日（{weekdays[value.weekday()]}）"


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
        "excluded": [row for row in bugs if bug_boundary_bucket(row) == "excluded"],
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
        "review_requirement_counts": repo.get_review_requirement_counts(version_id),
        "demands": repo.get_version_demands(version_id, limit=80),
        "bug_boundary": build_bug_boundary_payload(repo, version_id),
        "adjusted_pool_items": repo.get_version_adjusted_pool_items(version_id),
        "review_todos": repo.get_todos("all"),
        "trends": repo.get_version_review_trends(product_name, project_name, as_of, limit=5),
    }


def render_version_review_report(payload: dict[str, Any]) -> str:
    version_payload = payload.get("version_delay") or {}
    version = version_payload.get("version") or {}
    summary = version_payload.get("summary") or {}
    review_req_counts = payload.get("review_requirement_counts") or {}
    bug_boundary = payload.get("bug_boundary") or {}
    buckets = bug_boundary.get("buckets") or {}
    external = sorted(buckets.get("external") or [], key=lambda row: int(row.get("id") or 0))
    internal = sorted(buckets.get("internal") or [], key=lambda row: int(row.get("id") or 0))
    nonbug = sorted(buckets.get("nonbug") or [], key=lambda row: int(row.get("id") or 0))
    low_quality = bug_boundary.get("low_quality_tasks") or []
    trends = payload.get("trends") or []
    marked_delay = version_payload.get("marked_delay") or []
    adjusted_pool_items = payload.get("adjusted_pool_items") or []
    review_todos = payload.get("review_todos") or []

    version_name = str(version.get("name") or payload.get("version_id") or "未知版本")
    version_id = int(payload.get("version_id") or version.get("id") or 0)
    review_date = review_date_after_version(version)
    review_date_text = format_cn_date(review_date)
    review_internal = sorted(
        [row for row in internal if row.get("severity") in {1, 2} or str(row.get("isTypical")) == "1"] or internal[:10],
        key=lambda row: int(row.get("id") or 0),
    )

    def clean_version_name(value: object) -> str:
        return str(value or "").strip()

    def trend_internal_count(row: dict[str, Any]) -> int:
        if int(row.get("id") or 0) == version_id:
            return len(internal)
        return int(row.get("internal_bugs_raw") or row.get("internal_bugs") or 0)

    def count_by_dept(rows: list[dict[str, Any]]) -> list[list[str]]:
        counts: dict[str, int] = {}
        for row in rows:
            for dept in split_depts(row.get("ownerDeptName") or row.get("ownerDept") or row.get("type") or "未填写"):
                counts[dept] = counts.get(dept, 0) + 1
        return [[dept, serialize(count)] for dept, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))]

    def count_other_external_depts(rows: list[dict[str, Any]]) -> list[list[str]]:
        counts: dict[str, int] = {}
        for row in rows:
            for dept in split_depts(row.get("ownerDeptName") or row.get("ownerDept") or row.get("type")):
                if dept == "测试组":
                    continue
                counts[dept] = counts.get(dept, 0) + 1
        return [[dept, serialize(count)] for dept, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))]

    def append_deep_analysis(
        lines_ref: list[str],
        rows: list[dict[str, Any]],
        *,
        heading_level: int = 3,
        include_bug_id: bool = False,
        include_phenomenon: bool = True,
        role_labels: bool = False,
    ) -> None:
        marker = "#" * heading_level
        for index, row in enumerate(rows[:6], 1):
            reviews = parse_dept_review(row.get("dept_review"))
            title = trim_text(row.get("phenomenon") or row.get("title"), 80)
            heading = f"{marker} 深度分析（{index}）"
            if include_bug_id:
                heading += f"— {row.get('id')}"
            lines_ref.extend(
                [
                    "",
                    heading,
                    "",
                    f"# {title}",
                    "",
                    f"**Bug标题：** {markdown_link(str(row.get('id')) + ' ' + str(row.get('title') or ''), bug_url(row.get('id')))}",
                    f"**缺陷等级：** {review_bug_severity_text(row.get('severity'))}",
                ]
            )
            if include_phenomenon:
                lines_ref.append(f"**Bug现象：** {trim_text(row.get('phenomenon') or row.get('title'), 160)}")
            root_cause = "；".join(
                part
                for part in [
                    trim_text(row.get("causeAnalysis"), 140),
                    trim_text(row.get("nextStep"), 140),
                ]
                if part
            )
            if root_cause:
                lines_ref.append(f"**溯源：** {root_cause}")
            if reviews:
                owner_depts = set(split_depts(row.get("ownerDeptName") or row.get("ownerDept")))
                has_test = "测试组" in owner_depts
                non_test_depts = owner_depts - {"测试组"}
                for review in reviews:
                    dept = display_dept(review.get("dept"))
                    role = ""
                    if role_labels and has_test and non_test_depts:
                        role = " · 次责" if dept == "测试组" else " · 主责"
                    cause = review.get("cause") or "暂无"
                    next_step = review.get("next") or "暂无"
                    lines_ref.extend(
                        [
                            "",
                            f"**{dept}{role}**",
                            "",
                            f"- 原因：{cause}",
                            f"- 举措：{next_step}",
                        ]
                    )
            else:
                lines_ref.extend(
                    [
                        f"**责任部门：** {compact_dept_list(row.get('ownerDeptName') or row.get('ownerDept') or row.get('type') or '未填写')}",
                        f"**可能原因：** {trim_text(row.get('causeAnalysis') or '【待补充·人工】', 180)}",
                        f"**举措：** {trim_text(row.get('nextStep') or '【待补充·人工】', 180)}",
                    ]
                )
            lines_ref.extend(
                [
                    "",
                    "---",
                ]
            )

    def management_items(rows: list[dict[str, Any]]) -> list[list[Any]]:
        items: dict[str, dict[str, set[str] | str]] = {}

        def add(category: str, dept: str, action: str) -> None:
            if category not in items:
                items[category] = {"depts": set(), "action": action}
            depts = items[category]["depts"]
            if isinstance(depts, set):
                depts.add(dept)
            if action and action != "暂无":
                items[category]["action"] = action

        for row in rows:
            for review in parse_dept_review(row.get("dept_review")):
                dept = display_dept(review.get("dept"))
                text = f"{review.get('cause', '')} {review.get('next', '')}"
                if "AI" in text or "ai" in text:
                    add("对于AI产出的代码，审查不足", dept, review.get("next") or "加强AI产出后的人工审核")
                if any(keyword in text for keyword in ["测试", "覆盖", "边界", "用例", "认知"]):
                    add("关联性测试、边界测试不足", dept, review.get("next") or "补充边界场景和关联场景覆盖")
            if not parse_dept_review(row.get("dept_review")):
                add(
                    trim_text(row.get("causeAnalysis") or "问题原因待复盘归纳", 30),
                    compact_dept_list(row.get("ownerDeptName") or row.get("ownerDept") or row.get("type")),
                    trim_text(row.get("nextStep") or "待复盘会确认", 38),
                )
        return [
            [index, category, "、".join(sorted(data["depts"])) if isinstance(data["depts"], set) else "", data["action"]]
            for index, (category, data) in enumerate(items.items(), 1)
        ]

    def delay_dept(row: dict[str, Any]) -> str:
        return display_dept(
            row.get("finishedDeptName")
            or row.get("closedDeptName")
            or row.get("assignedDeptName")
            or row.get("category")
            or "未填写"
        )

    def delay_source(row: dict[str, Any]) -> str:
        source = str(row.get("source") or row.get("category") or "")
        if source == "operation" or row.get("category") == "operation":
            return "运维需求"
        if source in {"customer", "version"}:
            return "版本需求"
        return "内部需求"

    def delay_range(row: dict[str, Any]) -> str:
        start = format_short_date(row.get("estStarted")) or format_short_date(row.get("openedDate"))
        end = format_short_date(row.get("finishedDate")) or format_short_date(row.get("deadline"))
        return f"{start}至{end}" if start and end else start or end or ""

    def delay_judgement(row: dict[str, Any]) -> str:
        if row.get("adjustLog"):
            return "调下版本"
        if row.get("delayReason"):
            return trim_text(row.get("delayReason"), 18)
        return "字段标记延期"

    def delay_reason(row: dict[str, Any]) -> str:
        return trim_text(row.get("delayReason") or row.get("adjustLog") or "字段记录延期，需复盘会确认原因", 42)

    high_internal = [row for row in internal if row.get("severity") in {1, 2}]
    critical_internal = [row for row in internal if row.get("severity") == 1]
    severe_internal = [row for row in internal if row.get("severity") == 2]
    process_delay_rows = [*marked_delay, *adjusted_pool_items]
    delay_dept_counts: dict[str, int] = {}
    for row in process_delay_rows:
        dept = delay_dept(row)
        delay_dept_counts[dept] = delay_dept_counts.get(dept, 0) + int(row.get("delayTimes") or 1)

    todo_window_start = (review_date or dt.date.today()) - dt.timedelta(days=7)
    todo_window_end = review_date or dt.date.today()

    def todo_deadline(row: dict[str, Any]) -> dt.date | None:
        value = row.get("deadlineTime")
        if isinstance(value, dt.datetime):
            return value.date()
        if isinstance(value, dt.date):
            return value
        if value:
            try:
                return dt.date.fromisoformat(str(value)[:10])
            except ValueError:
                return None
        return None

    def todo_status(row: dict[str, Any]) -> int:
        try:
            return int(row.get("status_id") or 0)
        except (TypeError, ValueError):
            return 0

    def todo_type(row: dict[str, Any]) -> int:
        try:
            return int(row.get("type_id") or 0)
        except (TypeError, ValueError):
            return 0

    completed_todos = [
        row
        for row in review_todos
        if todo_status(row) == 8
        and todo_type(row) in {17, 18}
        and (deadline := todo_deadline(row))
        and todo_window_start <= deadline <= todo_window_end
    ][:10]
    ongoing_todos = [
        row
        for row in review_todos
        if todo_status(row) in {7, 19}
        and todo_type(row) in {17, 18, 35}
        and (not todo_deadline(row) or todo_deadline(row) >= todo_window_end)
    ][:12]
    bug_type_counts: dict[str, dict[str, Any]] = {}
    for row in high_internal:
        label = str(row.get("bugType") or row.get("bugTypeParent") or "原因待确认")
        dept = compact_dept_list(row.get("ownerDeptName") or row.get("ownerDept") or row.get("type") or "未填写")
        if label not in bug_type_counts:
            bug_type_counts[label] = {"count": 0, "depts": {}}
        bug_type_counts[label]["count"] += 1
        bug_type_counts[label]["depts"][dept] = bug_type_counts[label]["depts"].get(dept, 0) + 1

    lines = [
        f"# {version_name}版本复盘",
        "",
        f"**部门：** 效能组、测试组 **复盘时间：** {review_date_text}",
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
            ["版本", "Bug数量"],
            [
                [
                    clean_version_name(row.get("name")),
                    serialize(row.get("external_bugs", 0)),
                ]
                for row in trends
            ] or [[version_name, len(external)]],
        ),
        "",
        f"**当前版本Bug数：{len(external)}**",
        "",
        f"**外部Bug反馈总数：{len(external) + len(nonbug)}**",
        "",
        f"**结论：** {version_name}版本外部Bug反馈数量{len(external) + len(nonbug)}条，其中复盘Bug数量为{len(external)}条。",
        "",
        "---",
        "",
        "### 1.2 外部Bug 非Bug剔除列表",
        "",
    ]

    if nonbug:
        lines.append(
            md_table(
                ["序号", "Bug标题", "剔除原因"],
                [
                    [
                        index,
                        markdown_link(str(row.get("id")) + " " + trim_text(row.get("title"), 52), bug_url(row.get("id"))),
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
            f"**结论：** 当前版本外部共产生{len(external) + len(nonbug)}条Bug，其中有{len(nonbug)}条属于优化、非Bug或配置问题，不再进行Bug复盘。",
            "",
            "---",
            "",
            "### 1.3 外部Bug 实际复盘Bug列表",
            "",
            md_table(
                ["序号", "Bug标题", "缺陷等级/影响", "Bug现象", "责任部门"],
                [
                    [
                        index,
                        markdown_link(str(row.get("id")) + " " + trim_text(row.get("title"), 48), bug_url(row.get("id"))),
                        review_bug_severity_text(row.get("severity"), with_impact=True),
                        trim_text(row.get("phenomenon") or row.get("title"), 42),
                        compact_dept_list(row.get("ownerDeptName") or row.get("ownerDept") or row.get("type") or "未填写"),
                    ]
                    for index, row in enumerate(external, 1)
                ] or [["-", "本版本没有外部复盘Bug", "-", "-", "-"]],
            ),
            "",
            f"**结论：** 当前版本对{len(external)}条Bug进行了Bug复盘，均无争议。",
            "",
            "---",
            "",
            f"### 1.4 {version_name} 外部Bug责任归属 — 测试组",
            "",
            "**测试组Bug数量趋势：**",
            "",
            md_table(
                ["版本", "Bug数量"],
                [[clean_version_name(row.get("name")), serialize(row.get("test_external_bugs", 0))] for row in trends],
            ),
            "",
            f"**结论：** {len(external)}条Bug中有{sum(1 for row in external if '测试组' in split_depts(row.get('ownerDeptName') or row.get('ownerDept')))}条和测试相关。",
            "",
            "---",
            "",
            f"### 1.5 {version_name} 外部Bug责任归属 — 其它部门",
            "",
            "**其它部门Bug数量分布：**",
            "",
            md_table(["部门", "Bug数量"], count_other_external_depts(external) or [["无", "0"]]),
            "",
            f"**结论：** 本版本各部门外部Bug数量均较少（{'、'.join(f'{dept}{count}条' for dept, count in count_other_external_depts(external)) or '无其它部门责任Bug'}）。",
        ]
    )
    append_deep_analysis(lines, external[:3], role_labels=True)
    lines.extend(
        [
            "",
            "### 1.6 外部Bug复盘总结 核心管理问题",
            "",
            md_table(
                ["序号", "管理问题类别", "涉及部门", "待办项"],
                management_items(external) or [["-", "本版本无外部复盘Bug", "-", "-"]],
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
                ["版本", "内部Bug总数"],
                [[clean_version_name(row.get("name")), serialize(trend_internal_count(row))] for row in trends]
                or [[version_name, len(internal)]],
            ),
            "",
            f"**当前版本内部Bug总数：{len(internal)}**",
            "",
            "**内部Bug趋势概况：** 本版本内部Bug按已界定口径统计，疑似优化/需求调整类问题不纳入正式内部Bug复盘。",
            "",
            "### 2.2 内部Bug 重要缺陷分布",
            "",
            "**极严重Bug数量：**",
            "",
            md_table(["部门", "Bug数量"], count_by_dept(critical_internal) or [["本版本无极严重Bug", "0"]]),
            "",
            "**高严重Bug数量：**",
            "",
            md_table(["部门", "Bug数量"], count_by_dept(severe_internal) or [["本版本无高等缺陷Bug", "0"]]),
            "",
            f"**重要缺陷分布结论：** 当前版本重要缺陷共有{len(high_internal)}条：",
            "",
            f"1. 极严重Bug {len(critical_internal)}条，{'、'.join(f'{dept}{count}条' for dept, count in count_by_dept(critical_internal)) or '本版本无极严重Bug'}",
            f"2. 高等缺陷Bug {len(severe_internal)}条，{'、'.join(f'{dept}{count}条' for dept, count in count_by_dept(severe_internal)) or '本版本无高等缺陷Bug'}",
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
                ["序号", "Bug标题", "缺陷等级", "责任部门"],
                [
                    [
                        index,
                        markdown_link(str(row.get("id")) + " " + trim_text(row.get("title"), 50), bug_url(row.get("id"))),
                        review_bug_severity_text(row.get("severity")),
                        compact_dept_list(row.get("ownerDeptName") or row.get("ownerDept") or row.get("type") or "未填写"),
                    ]
                    for index, row in enumerate(review_internal, 1)
                ] or [["-", "本版本没有高缺陷或典型内部Bug", "-", "-"]],
            ),
            "",
            "### 内部Bug 典型Bug复盘",
        ]
    )
    append_deep_analysis(lines, review_internal, heading_level=4, include_bug_id=True, include_phenomenon=False)
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
                [["功能实现偏差", len(review_internal), "没有认真对照需求进行实现，自测不足"]],
            ),
            "",
            "---",
            "",
            "## 三、版本复盘",
            "",
            "### 3.1 版本需求趋势",
            "",
            md_table(
                ["版本", "外部需求", "内部需求"],
                [
                    [
                        clean_version_name(row.get("name")),
                        serialize(row.get("ext_reqs")),
                        serialize(row.get("int_reqs")),
                    ]
                    for row in trends
                ]
                or [[version_name, serialize(review_req_counts.get("ext_reqs", 0)), serialize(review_req_counts.get("int_reqs", 0))]],
            ),
            "",
            f"**版本概况：** 本版本外部需求{serialize(review_req_counts.get('ext_reqs', 0))}项、内部需求{serialize(review_req_counts.get('int_reqs', 0))}项，任务{serialize(summary.get('total_tasks', 0))}个，未关闭任务{serialize(summary.get('open_tasks', 0))}个。",
            "",
            "### 3.2 延期情况",
            "",
            "**过程延期次数部门分布：**",
            "",
            md_table(
                ["部门", "延期次数"],
                [[dept, count] for dept, count in sorted(delay_dept_counts.items(), key=lambda item: (-item[1], item[0]))]
                or [["本版本无过程延期", "0"]],
            ),
            "",
            f"**当前版本过程延期总数：** {len(process_delay_rows)}个任务，共{sum(int(row.get('delayTimes') or 1) for row in process_delay_rows)}次延期",
            "",
            f"**延期情况：** 当前版本共有{len(process_delay_rows)}个任务发生延期，其中{'、'.join(f'{dept}{count}次' for dept, count in sorted(delay_dept_counts.items(), key=lambda item: (-item[1], item[0]))) or '无部门延期分布'}。",
            "",
            "### 3.3 延期任务记录",
            "",
            md_table(
                ["序号", "延期任务标题", "任务来源", "延期次数", "负责部门", "任务起止时间", "延期天数", "原因", "需求是否明确"],
                [
                    [
                        index,
                        markdown_link(
                            trim_text(row.get("name") or row.get("task_name") or row.get("title"), 50),
                            task_url(row.get("id") or row.get("taskID")),
                        ),
                        delay_source(row),
                        serialize(row.get("delayTimes") or 1),
                        delay_dept(row),
                        delay_range(row),
                        delay_judgement(row),
                        delay_reason(row),
                        "是" if str(row.get("isSureStory") or "") == "sure" else "否",
                    ]
                    for index, row in enumerate(process_delay_rows[:30], 1)
                ] or [["-", "本版本没有查到延期任务记录", "-", "-", "-", "-", "-", "-", "-"]],
            ),
            "",
            "### 3.4 待办项",
            "",
            "#### 上周已完成",
            "",
            md_table(
                ["事项", "责任人"],
                [
                    [trim_text(row.get("content"), 42), row.get("duty_names") or row.get("duty_user")]
                    for row in completed_todos
                ]
                or [["本周期暂无已完成待办", "-"]],
            ),
            "",
            "#### 进行中",
            "",
            md_table(
                ["事项", "截止时间", "责任人"],
                [
                    [
                        trim_text(row.get("content"), 42),
                        format_month_day(row.get("deadlineTime")),
                        row.get("duty_names") or row.get("duty_user"),
                    ]
                    for row in ongoing_todos
                ]
                or [["本周期暂无进行中待办", "-", "-"]],
            ),
            "",
            "---",
            "",
            "## THANK YOU",
            "",
            f"复盘时间：{review_date_text}",
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
    prepared_projects: list[dict[str, Any]] = []
    snapshot_ids: list[int] = []

    for spec in project_specs:
        product_name = spec["product_name"]
        project_name = spec["project_name"]
        current = repo.get_current_sprint_for_product(product_name, as_of, project_name)
        previous = repo.get_latest_completed_sprint_for_product(product_name, as_of, project_name) if include_history else None
        next_sprint = repo.get_next_sprint_for_product(product_name, as_of, project_name) if include_history else None
        current_weekly = repo.get_weekly_report_data(int(current["id"]), start_date, end_date, as_of) if current else None
        if not current:
            warnings.append(f"{spec['label']}未定位到当前版本")
        for sprint in [previous, current, next_sprint]:
            if sprint:
                snapshot_ids.append(int(sprint["id"]))
        prepared_projects.append(
            {
                **spec,
                "previous_sprint": previous,
                "current_sprint": current,
                "next_sprint": next_sprint,
                "weekly": current_weekly,
            }
        )

    snapshots = repo.get_version_snapshot_summaries(snapshot_ids, as_of)

    def snapshot_for(sprint: dict[str, Any] | None, weekly: dict[str, Any] | None = None) -> dict[str, Any] | None:
        if not sprint:
            return None
        version_id = int(sprint["id"])
        snapshot = {**(snapshots.get(version_id) or {}), "sprint": sprint}
        if weekly:
            snapshot["task_summary"] = weekly.get("task_summary") or snapshot.get("task_summary") or {}
            snapshot["bug_summary"] = weekly.get("bug_summary") or snapshot.get("bug_summary") or {}
        return snapshot

    for prepared in prepared_projects:
        current = prepared.get("current_sprint")
        previous = prepared.get("previous_sprint")
        next_sprint = prepared.get("next_sprint")
        current_weekly = prepared.get("weekly")
        project_payloads.append(
            {
                **{key: prepared[key] for key in ["key", "label", "product_name", "project_name"]},
                "previous": snapshot_for(previous),
                "current": snapshot_for(current, current_weekly),
                "next": snapshot_for(next_sprint),
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
