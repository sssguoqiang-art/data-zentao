from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
import sys

from .config import AppConfig
from .db import ReadOnlyDatabase
from .formatting import as_date, rows_to_md, to_json
from .repository import ZentaoRepository
from .reports import (
    build_daily_report_payload,
    build_dept_risk_payload,
    build_demand_status_payload,
    build_bug_review_payload,
    build_measures_payload,
    build_person_work_payload,
    build_version_delay_payload,
    build_weekly_report_payload,
    render_daily_report,
    render_dept_risk_report,
    render_demand_status_report,
    render_bug_review_report,
    render_measures_report,
    render_person_work_report,
    render_platform_delay_report,
    render_todo_report,
    render_version_delay_report,
    render_weekly_report,
)
from .router import answer_question


REQUIRED_SCHEMA = {
    "zt_user": ["account", "realname", "dept", "deleted"],
    "zt_dept": ["id", "name", "parent", "path"],
    "zt_product": ["id", "name", "status", "deleted"],
    "zt_project": ["id", "name", "type", "status", "parent", "begin", "end", "deleted"],
    "zt_projectproduct": ["project", "product"],
    "zt_task": [
        "id",
        "name",
        "status",
        "execution",
        "assignedTo",
        "deadline",
        "left",
        "finishedDate",
        "closedDate",
        "deleted",
        "parent",
        "delayReason",
        "delayTimes",
    ],
    "zt_pool": [
        "id",
        "title",
        "status",
        "requirementStatus",
        "pv_id",
        "type",
        "taskID",
        "storyId",
        "expectedVersion",
        "deleted",
        "delayReason",
        "delayMeasure",
    ],
    "zt_story": ["id", "title", "status", "stage", "assignedTo", "deleted"],
    "zt_bug": [
        "id",
        "title",
        "status",
        "severity",
        "pri",
        "execution",
        "assignedTo",
        "owner",
        "ownerDept",
        "type",
        "openedDate",
        "resolvedDate",
        "closedDate",
        "deleted",
        "causeAnalysis",
        "nextStep",
    ],
    "zt_bug_dept_review": ["bugId", "dept", "causeAnalysis", "nextStep"],
    "zt_to_do_list": ["id", "content", "dept", "duty_user", "status", "type", "deadlineTime", "deleted"],
    "zt_measures_management": ["id", "status", "title", "dept", "duty_user", "pv_id", "bug_ids", "deleted", "questionType"],
    "zt_pool_type": ["id", "name"],
}


def make_repo() -> tuple[AppConfig, ZentaoRepository]:
    config = AppConfig.from_env()
    return config, ZentaoRepository(ReadOnlyDatabase(config.db))


def add_common_date_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--date",
        default=None,
        help="查询日期，格式 YYYY-MM-DD；默认使用今天。",
    )


def add_common_project_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--product-name", default=None)
    parser.add_argument("--project-name", default=None)


def week_start(value: dt.date) -> dt.date:
    return value - dt.timedelta(days=value.weekday())


def resolve_version_id(
    repo: ZentaoRepository,
    config: AppConfig,
    args: argparse.Namespace,
    query_date: dt.date,
) -> int:
    if getattr(args, "version_id", None):
        return int(args.version_id)
    sprint = repo.get_current_sprint_for_product(
        getattr(args, "product_name", None) or config.platform_product_name,
        query_date,
        getattr(args, "project_name", None) or config.platform_project_name,
    )
    if not sprint:
        raise ValueError("没有定位到当前版本，请通过 --version-id 指定版本。")
    return int(sprint["id"])


def print_output(data: object, output_format: str) -> None:
    if output_format == "json":
        print(to_json(data))
    else:
        print(data)


def cmd_check(_: argparse.Namespace) -> int:
    _, repo = make_repo()
    data = repo.check()
    print("数据库连接正常。")
    print(f"数据库：{data['database']}")
    print(f"基础表数量：{data['tables']}")
    print(f"用户数量：{data['users']}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    config, repo = make_repo()
    query_date = as_date(args.date)
    results: list[dict[str, str]] = []

    def add(area: str, status: str, detail: str) -> None:
        results.append({"检查项": area, "状态": status, "说明": detail})

    try:
        data = repo.check()
        add("数据库连接", "OK", f"库={data['database']}；表={data['tables']}；用户={data['users']}")
    except Exception as exc:
        add("数据库连接", "FAIL", str(exc))
        print_output(results, args.format)
        return 1

    for table_name, required_columns in REQUIRED_SCHEMA.items():
        try:
            columns = {row["column_name"] for row in repo.describe_table(table_name)}
        except Exception as exc:
            add(f"表结构 {table_name}", "FAIL", str(exc))
            continue
        missing = [column for column in required_columns if column not in columns]
        if missing:
            add(f"表结构 {table_name}", "FAIL", f"缺少字段：{', '.join(missing)}")
        else:
            add(f"表结构 {table_name}", "OK", f"字段通过：{len(required_columns)} 个")

    sprint = repo.get_current_sprint_for_product(
        args.product_name or config.platform_product_name,
        query_date,
        args.project_name or config.platform_project_name,
    )
    if sprint:
        version_id = int(sprint["id"])
        add("当前版本定位", "OK", f"{sprint['name']}（ID {version_id}，{sprint['begin']} ~ {sprint['end']}）")
    else:
        version_id = None
        add("当前版本定位", "FAIL", "没有定位到当前版本，请检查 product/project 配置或通过 --date 指定日期。")

    if version_id:
        try:
            payload = build_version_delay_payload(repo, version_id, query_date)
            summary = payload.get("summary") or {}
            add("查版本推进", "OK", f"任务={summary.get('total_tasks', 0)}；未关闭={summary.get('open_tasks', 0)}")
        except Exception as exc:
            add("查版本推进", "FAIL", str(exc))

        try:
            demands = repo.get_version_demands(version_id, limit=1)
            if demands:
                payload = build_demand_status_payload(repo, str(demands[0]["id"]))
                add("查需求状态", "OK", f"样本需求={demands[0]['id']}；匹配={len(payload.get('demands') or [])}")
            else:
                add("查需求状态", "WARN", "当前版本没有样本需求；命令可用但本次无法做样本验证。")
        except Exception as exc:
            add("查需求状态", "FAIL", str(exc))

        try:
            payload = build_bug_review_payload(repo, version_id)
            summary = payload.get("summary", {}).get("summary") or {}
            add("查 Bug 复盘", "OK", f"Bug={summary.get('total_bugs', 0)}；active={summary.get('active_bugs', 0)}")
        except Exception as exc:
            add("查 Bug 复盘", "FAIL", str(exc))

        try:
            dept_rows = repo.db.fetch_all(
                """
                SELECT name
                FROM zt_dept
                WHERE name <> ''
                ORDER BY id
                LIMIT 1
                """
            )
            dept_name = dept_rows[0]["name"] if dept_rows else ""
            if dept_name:
                payload = build_dept_risk_payload(repo, dept_name, version_id, query_date)
                add("查部门风险", "OK", f"样本部门={dept_name}；任务={len(payload.get('tasks') or [])}；Bug={len(payload.get('bugs') or [])}")
            else:
                add("查部门风险", "WARN", "没有找到样本部门；命令可用但本次无法做样本验证。")
        except Exception as exc:
            add("查部门风险", "FAIL", str(exc))

        try:
            payload = build_daily_report_payload(
                repo,
                args.product_name or config.platform_product_name,
                args.project_name or config.platform_project_name,
                query_date,
            )
            add("生成日报", "OK" if payload.get("ok") else "FAIL", payload.get("message") or f"版本={payload.get('current_sprint', {}).get('name')}")
        except Exception as exc:
            add("生成日报", "FAIL", str(exc))

        try:
            start_date = week_start(query_date)
            payload = build_weekly_report_payload(
                repo,
                args.product_name or config.platform_product_name,
                args.project_name or config.platform_project_name,
                start_date,
                query_date,
                query_date,
            )
            add("生成周报", "OK" if payload.get("ok") else "FAIL", payload.get("message") or f"周期={start_date} ~ {query_date}")
        except Exception as exc:
            add("生成周报", "FAIL", str(exc))

    try:
        users = repo.find_users("", limit=1)
        if users:
            payload = build_person_work_payload(repo, users[0]["account"])
            add("查个人任务", "OK", f"样本账号={users[0]['account']}；任务={len(payload.get('tasks') or [])}；待办={len(payload.get('todos') or [])}")
        else:
            add("查个人任务", "WARN", "没有找到样本用户；命令可用但本次无法做样本验证。")
    except Exception as exc:
        add("查个人任务", "FAIL", str(exc))

    try:
        payload = build_measures_payload(repo, "unfinished")
        add("查待办举措", "OK", f"待办={len(payload.get('todos') or [])}；举措={len(payload.get('measures') or [])}")
    except Exception as exc:
        add("查待办举措", "FAIL", str(exc))

    if args.format == "json":
        print(to_json({"ok": not any(row["状态"] == "FAIL" for row in results), "results": results}))
    else:
        print("# data-zentao 安装自检")
        print()
        print(rows_to_md(results))
    return 1 if any(row["状态"] == "FAIL" for row in results) else 0


def cmd_todos(args: argparse.Namespace) -> int:
    _, repo = make_repo()
    rows = repo.get_todos(args.status)
    if args.format == "json":
        print(to_json(rows))
    else:
        print(render_todo_report(rows, args.status))
    return 0


def cmd_schema(args: argparse.Namespace) -> int:
    _, repo = make_repo()
    if args.table:
        rows = repo.describe_table(args.table)
    elif args.columns:
        rows = repo.search_columns(args.columns, args.limit)
    else:
        rows = repo.list_tables(args.search, args.limit)

    if args.format == "json":
        print(to_json(rows))
    else:
        print(rows_to_md(rows))
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    _, repo = make_repo()
    sql = args.sql
    if args.file:
        with open(args.file, "r", encoding="utf-8") as handle:
            sql = handle.read()
    if not sql:
        raise ValueError("请通过 --sql 或 --file 提供只读 SQL。")

    rows = repo.run_read_only_query(sql, args.limit)
    if args.format == "json":
        print(to_json(rows))
    else:
        print(rows_to_md(rows))
    return 0


def cmd_platform_delay(args: argparse.Namespace) -> int:
    config, repo = make_repo()
    query_date = as_date(args.date)
    if args.format == "json":
        sprint = repo.get_current_sprint_for_product(
            args.product_name or config.platform_product_name,
            query_date,
            args.project_name or config.platform_project_name,
        )
        if not sprint:
            print(to_json({"ok": False, "message": "没有定位到当前版本"}))
            return 1
        payload = build_version_delay_payload(repo, int(sprint["id"]), query_date)
        payload["current_sprint"] = sprint
        print(to_json(payload))
    else:
        print(
            render_platform_delay_report(
                repo,
                args.product_name or config.platform_product_name,
                args.project_name or config.platform_project_name,
                query_date,
            )
        )
    return 0


def cmd_version_delay(args: argparse.Namespace) -> int:
    _, repo = make_repo()
    query_date = as_date(args.date)
    payload = build_version_delay_payload(repo, args.version_id, query_date)
    if args.format == "json":
        print(to_json(payload))
    else:
        print(render_version_delay_report(payload))
    return 0


def cmd_daily_report(args: argparse.Namespace) -> int:
    config, repo = make_repo()
    query_date = as_date(args.date)
    payload = build_daily_report_payload(
        repo,
        args.product_name or config.platform_product_name,
        args.project_name or config.platform_project_name,
        query_date,
    )

    if args.format == "json":
        print(to_json(payload))
        return 0 if payload.get("ok") else 1

    report = render_daily_report(payload)
    if args.save:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        project_label = args.project_name or config.platform_project_name
        output_path = output_dir / f"{query_date.strftime('%Y%m%d')}_{project_label}_今日报告.md"
        output_path.write_text(report, encoding="utf-8")
        print(f"已生成：{output_path}")
        if not args.quiet:
            print()
            print(report)
    else:
        print(report)
    return 0 if payload.get("ok") else 1


def cmd_person_tasks(args: argparse.Namespace) -> int:
    _, repo = make_repo()
    payload = build_person_work_payload(repo, args.person)
    if args.format == "json":
        print(to_json(payload))
    else:
        print(render_person_work_report(payload))
    return 0 if payload.get("ok") else 1


def cmd_demand_status(args: argparse.Namespace) -> int:
    _, repo = make_repo()
    payload = build_demand_status_payload(repo, args.keyword)
    if args.format == "json":
        print(to_json(payload))
    else:
        print(render_demand_status_report(payload))
    return 0


def cmd_measures(args: argparse.Namespace) -> int:
    _, repo = make_repo()
    payload = build_measures_payload(repo, args.status)
    if args.format == "json":
        print(to_json(payload))
    else:
        print(render_measures_report(payload))
    return 0


def cmd_bug_review(args: argparse.Namespace) -> int:
    config, repo = make_repo()
    query_date = as_date(args.date)
    version_id = resolve_version_id(repo, config, args, query_date)
    payload = build_bug_review_payload(repo, version_id)
    if args.format == "json":
        print(to_json(payload))
    else:
        print(render_bug_review_report(payload))
    return 0


def cmd_dept_risk(args: argparse.Namespace) -> int:
    config, repo = make_repo()
    query_date = as_date(args.date)
    version_id = resolve_version_id(repo, config, args, query_date)
    payload = build_dept_risk_payload(repo, args.dept, version_id, query_date)
    if args.format == "json":
        print(to_json(payload))
    else:
        print(render_dept_risk_report(payload))
    return 0


def cmd_weekly_report(args: argparse.Namespace) -> int:
    config, repo = make_repo()
    query_date = as_date(args.date)
    start_date = as_date(args.start) if args.start else week_start(query_date)
    end_date = as_date(args.end) if args.end else query_date
    payload = build_weekly_report_payload(
        repo,
        args.product_name or config.platform_product_name,
        args.project_name or config.platform_project_name,
        start_date,
        end_date,
        query_date,
    )
    if args.format == "json":
        print(to_json(payload))
        return 0 if payload.get("ok") else 1
    report = render_weekly_report(payload)
    if args.save:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        project_label = args.project_name or config.platform_project_name
        output_path = output_dir / f"{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}_{project_label}_周报.md"
        output_path.write_text(report, encoding="utf-8")
        print(f"已生成：{output_path}")
        if not args.quiet:
            print()
            print(report)
    else:
        print(report)
    return 0 if payload.get("ok") else 1


def cmd_ask(args: argparse.Namespace) -> int:
    config, repo = make_repo()
    query_date = as_date(args.date)
    print(
        answer_question(
            args.question,
            repo,
            product_name=args.product_name or config.platform_product_name,
            project_name=args.project_name or config.platform_project_name,
            as_of=query_date,
        )
    )
    return 0


def cmd_chat(args: argparse.Namespace) -> int:
    config, repo = make_repo()
    query_date = as_date(args.date)
    print("data-zentao 对话模式。输入 exit 或 quit 退出。")
    while True:
        try:
            question = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if question.lower() in {"exit", "quit", "q"}:
            return 0
        print(
            answer_question(
                question,
                repo,
                product_name=args.product_name or config.platform_product_name,
                project_name=args.project_name or config.platform_project_name,
                as_of=query_date,
            )
        )
        print()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="data-zentao",
        description="禅道数据查询和报告生成工具。",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check", help="检查数据库连接。")
    check.set_defaults(func=cmd_check)

    doctor = subparsers.add_parser("doctor", help="安装后自检数据库结构和核心能力。")
    add_common_date_arg(doctor)
    add_common_project_args(doctor)
    doctor.add_argument("--format", choices=["markdown", "json"], default="markdown")
    doctor.set_defaults(func=cmd_doctor)

    todos = subparsers.add_parser("todos", help="查询待办。")
    todos.add_argument(
        "--status",
        choices=["unfinished", "ongoing", "not-started", "all"],
        default="unfinished",
        help="待办状态口径。",
    )
    todos.add_argument("--format", choices=["markdown", "json"], default="markdown")
    todos.set_defaults(func=cmd_todos)

    schema = subparsers.add_parser("schema", help="查看禅道库表结构，供自由查询前定位字段。")
    schema.add_argument("--table", default=None, help="查看某张表字段，例如 zt_task。")
    schema.add_argument("--search", default=None, help="按表名或表注释搜索表。")
    schema.add_argument("--columns", default=None, help="按字段名或字段注释搜索字段。")
    schema.add_argument("--limit", type=int, default=300)
    schema.add_argument("--format", choices=["markdown", "json"], default="markdown")
    schema.set_defaults(func=cmd_schema)

    query = subparsers.add_parser("query", help="执行只读 SQL，用于 AI Agent 自由查询数据。")
    query.add_argument("--sql", default=None, help="只允许 SELECT/SHOW/WITH/DESCRIBE/EXPLAIN。")
    query.add_argument("--file", default=None, help="从文件读取只读 SQL。")
    query.add_argument("--limit", type=int, default=200, help="最多返回行数，默认 200。")
    query.add_argument("--format", choices=["markdown", "json"], default="markdown")
    query.set_defaults(func=cmd_query)

    platform_delay = subparsers.add_parser("platform-delay", help="查询平台当前版本延期情况。")
    add_common_date_arg(platform_delay)
    add_common_project_args(platform_delay)
    platform_delay.add_argument("--format", choices=["markdown", "json"], default="markdown")
    platform_delay.set_defaults(func=cmd_platform_delay)

    version_delay = subparsers.add_parser("version-delay", help="按版本 ID 查询延期情况。")
    version_delay.add_argument("--version-id", type=int, required=True)
    add_common_date_arg(version_delay)
    version_delay.add_argument("--format", choices=["markdown", "json"], default="markdown")
    version_delay.set_defaults(func=cmd_version_delay)

    daily_report = subparsers.add_parser("daily-report", help="生成今日项目报告。")
    add_common_date_arg(daily_report)
    add_common_project_args(daily_report)
    daily_report.add_argument("--output-dir", default="reports/日报")
    daily_report.add_argument("--format", choices=["markdown", "json"], default="markdown")
    daily_report.add_argument("--save", action=argparse.BooleanOptionalAction, default=True)
    daily_report.add_argument("--quiet", action="store_true", help="保存文件后不在终端打印全文。")
    daily_report.set_defaults(func=cmd_daily_report)

    person_tasks = subparsers.add_parser("person-tasks", help="查询个人任务、Bug 和待办。")
    person_tasks.add_argument("person", help="姓名、账号或拼音。")
    person_tasks.add_argument("--format", choices=["markdown", "json"], default="markdown")
    person_tasks.set_defaults(func=cmd_person_tasks)

    demand_status = subparsers.add_parser("demand-status", help="查询需求当前状态。")
    demand_status.add_argument("keyword", help="需求 ID 或标题关键词。")
    demand_status.add_argument("--format", choices=["markdown", "json"], default="markdown")
    demand_status.set_defaults(func=cmd_demand_status)

    measures = subparsers.add_parser("measures", help="查询待办和举措。")
    measures.add_argument(
        "--status",
        default="unfinished",
        help="unfinished、ongoing、not-started、all，或状态关键词。",
    )
    measures.add_argument("--format", choices=["markdown", "json"], default="markdown")
    measures.set_defaults(func=cmd_measures)

    bug_review = subparsers.add_parser("bug-review", help="生成 Bug 复盘数据。")
    add_common_date_arg(bug_review)
    add_common_project_args(bug_review)
    bug_review.add_argument("--version-id", type=int, default=None)
    bug_review.add_argument("--format", choices=["markdown", "json"], default="markdown")
    bug_review.set_defaults(func=cmd_bug_review)

    dept_risk = subparsers.add_parser("dept-risk", help="查询部门风险。")
    dept_risk.add_argument("dept", help="部门名称关键词，例如 PHP1、产品部、测试部。")
    add_common_date_arg(dept_risk)
    add_common_project_args(dept_risk)
    dept_risk.add_argument("--version-id", type=int, default=None)
    dept_risk.add_argument("--format", choices=["markdown", "json"], default="markdown")
    dept_risk.set_defaults(func=cmd_dept_risk)

    weekly_report = subparsers.add_parser("weekly-report", help="生成项目周报。")
    add_common_date_arg(weekly_report)
    add_common_project_args(weekly_report)
    weekly_report.add_argument("--start", default=None, help="开始日期，默认本周一。")
    weekly_report.add_argument("--end", default=None, help="结束日期，默认查询日期。")
    weekly_report.add_argument("--output-dir", default="reports/周报")
    weekly_report.add_argument("--format", choices=["markdown", "json"], default="markdown")
    weekly_report.add_argument("--save", action=argparse.BooleanOptionalAction, default=True)
    weekly_report.add_argument("--quiet", action="store_true", help="保存文件后不在终端打印全文。")
    weekly_report.set_defaults(func=cmd_weekly_report)

    ask = subparsers.add_parser("ask", help="一句话查询。")
    ask.add_argument("question")
    add_common_date_arg(ask)
    ask.add_argument("--product-name", default=None)
    ask.add_argument("--project-name", default=None)
    ask.set_defaults(func=cmd_ask)

    chat = subparsers.add_parser("chat", help="进入简单对话模式。")
    add_common_date_arg(chat)
    chat.add_argument("--product-name", default=None)
    chat.add_argument("--project-name", default=None)
    chat.set_defaults(func=cmd_chat)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
