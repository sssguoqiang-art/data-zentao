from __future__ import annotations

import datetime as dt
import re

from .reports import (
    build_bug_boundary_payload,
    build_bug_review_payload,
    build_daily_report_payload,
    build_demand_status_payload,
    build_dept_risk_payload,
    build_measures_payload,
    build_person_work_payload,
    build_version_review_payload,
    build_weekly_report_payload,
    render_bug_boundary_report,
    render_bug_review_report,
    render_daily_report,
    render_demand_status_report,
    render_dept_risk_report,
    render_measures_report,
    render_person_work_report,
    render_platform_delay_report,
    render_todo_report,
    render_version_review_report,
    render_weekly_report,
)
from .repository import ZentaoRepository


def _quoted_text(text: str) -> str | None:
    match = re.search(r"[\"'“”‘’「](.+?)[\"'“”‘’」]", text)
    return match.group(1).strip() if match else None


def _clean_entity(text: str, words: list[str]) -> str | None:
    quoted = _quoted_text(text)
    if quoted:
        return quoted
    value = text
    for word in words:
        value = value.replace(word, "")
    value = value.strip(" ：:，,。？?！!的")
    if not value or value in {"这个", "这个需求", "一下", "现在"}:
        return None
    return value


def _person_keyword(text: str) -> str | None:
    for pattern in [
        r"查一下(.+?)相关",
        r"(.+?)手上",
        r"(.+?)有哪些(?:任务|待办|Bug|bug)",
        r"(.+?)的(?:任务|待办|Bug|bug)",
    ]:
        match = re.search(pattern, text)
        if match:
            value = match.group(1).strip(" ：:，,。？?！!的")
            if value and value not in {"某个人", "谁"}:
                return value
    return _clean_entity(text, ["查个人任务", "个人任务", "任务", "待办", "Bug", "bug", "查", "查询", "一下", "相关", "有哪些"])


def _dept_keyword(text: str) -> str | None:
    candidate = _clean_entity(
        text,
        ["查部门风险", "查询部门风险", "部门风险", "部门", "风险", "延期", "延迟", "逾期", "Bug", "bug", "查", "查询", "一下", "现在", "有什么"],
    )
    if candidate and candidate not in {"查部", "部门", "这个部门", "这个"}:
        return candidate
    matches = re.findall(r"([\w\u4e00-\u9fa5]+(?:部|组|中心|团队))", text)
    for value in reversed(matches):
        if value not in {"查部", "部门"}:
            return value
    return None


def _current_version_id(repo: ZentaoRepository, product_name: str, project_name: str, as_of: dt.date) -> int | None:
    sprint = repo.get_current_sprint_for_product(product_name, as_of, project_name)
    return int(sprint["id"]) if sprint else None


def _latest_completed_version_id(repo: ZentaoRepository, product_name: str, project_name: str, as_of: dt.date) -> int | None:
    sprint = repo.get_latest_completed_sprint_for_product(product_name, as_of, project_name)
    return int(sprint["id"]) if sprint else None


def answer_question(
    question: str,
    repo: ZentaoRepository,
    *,
    product_name: str,
    project_name: str,
    as_of: dt.date,
) -> str:
    text = question.strip()
    if not text:
        return "你可以问：生成今日报告；未完成的待办有哪些；平台项目这个版本产生的延期情况。"

    if "今日报告" in text or "日报" in text:
        payload = build_daily_report_payload(repo, product_name, project_name, as_of)
        return render_daily_report(payload)

    if "周报" in text or "周汇总" in text:
        start = as_of - dt.timedelta(days=as_of.weekday())
        payload = build_weekly_report_payload(repo, product_name, project_name, start, as_of, as_of)
        return render_weekly_report(payload)

    if "举措" in text:
        payload = build_measures_payload(repo, "unfinished")
        return render_measures_report(payload)

    if "Bug界定" in text or "bug界定" in text.lower() or "预分类" in text or "界定报告" in text:
        version_id = _latest_completed_version_id(repo, product_name, project_name, as_of)
        if not version_id:
            return "没有定位到最近已交付版本，无法生成 Bug界定。"
        return render_bug_boundary_report(build_bug_boundary_payload(repo, version_id))

    if "版本复盘" in text or "复盘报告" in text:
        version_id = _latest_completed_version_id(repo, product_name, project_name, as_of)
        if not version_id:
            return "没有定位到最近已交付版本，无法生成版本复盘。"
        payload = build_version_review_payload(repo, product_name, project_name, version_id, as_of)
        return render_version_review_report(payload)

    if "复盘" in text and not ("bug" in text.lower() or "Bug" in text):
        return "请确认要生成“版本复盘正式材料”，还是“Bug界定预分类材料”。这两个报告的用途和口径不同。"

    if ("bug" in text.lower() or "Bug" in text) and "复盘" in text:
        version_id = _current_version_id(repo, product_name, project_name, as_of)
        if not version_id:
            return "没有定位到当前版本，无法生成 Bug 复盘。"
        payload = build_bug_review_payload(repo, version_id)
        return render_bug_review_report(payload)

    if "需求" in text and any(word in text for word in ["状态", "到哪", "进度", "推进", "完成"]):
        keyword = _clean_entity(
            text,
            ["查需求状态", "查询需求状态", "需求状态", "这个需求", "需求", "现在", "到哪了", "到哪", "进度", "推进", "完成", "查", "查询", "一下"],
        )
        if not keyword:
            return "请补充需求 ID 或需求标题关键词，例如：查需求状态 \"VIP 权益功能优化\"。"
        return render_demand_status_report(build_demand_status_payload(repo, keyword))

    if any(word in text for word in ["个人任务", "手上", "相关的待办", "相关的任务"]):
        keyword = _person_keyword(text)
        if not keyword:
            return "请补充人员姓名或账号，例如：查一下某位同事相关的待办和任务。"
        return render_person_work_report(build_person_work_payload(repo, keyword))

    if "部门" in text and any(word in text for word in ["风险", "延期", "延迟", "逾期", "Bug", "bug"]):
        keyword = _dept_keyword(text)
        version_id = _current_version_id(repo, product_name, project_name, as_of)
        if not keyword:
            return "请补充部门关键词，例如：查部门风险 \"PHP1\"。"
        if not version_id:
            return "没有定位到当前版本，无法查询部门风险。"
        return render_dept_risk_report(build_dept_risk_payload(repo, keyword, version_id, as_of))

    if "待办" in text:
        if "进行中" in text:
            status = "ongoing"
        elif "未开始" in text:
            status = "not-started"
        elif "全部" in text or "所有" in text:
            status = "all"
        else:
            status = "unfinished"
        return render_todo_report(repo.get_todos(status), status)

    if ("平台" in text or product_name in text or project_name in text) and (
        "延期" in text or "延迟" in text or "逾期" in text
    ):
        return render_platform_delay_report(repo, product_name, project_name, as_of)

    return (
        "这个问题第一版还没有路由到工具。\n\n"
        "当前已支持：\n"
        "- 生成今日报告\n"
        "- 生成周报\n"
        "- Bug 复盘\n"
        "- Bug界定\n"
        "- 版本复盘\n"
        "- 查需求状态\n"
        "- 查个人任务\n"
        "- 查部门风险\n"
        "- 待办和举措\n"
        "- 未完成的待办有哪些\n"
        "- 进行中的待办有哪些\n"
        "- 平台项目这个版本产生的延期情况"
    )
