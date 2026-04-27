from __future__ import annotations

import datetime as dt
import re
from typing import Any

from .db import ReadOnlyDatabase


DONE_STATUSES = ("done", "closed", "cancel")


class ZentaoRepository:
    def __init__(self, db: ReadOnlyDatabase):
        self.db = db

    def check(self) -> dict[str, Any]:
        row = self.db.fetch_one(
            """
            SELECT
              DATABASE() AS database_name,
              COUNT(*) AS user_count
            FROM zt_user
            """
        )
        table_row = self.db.fetch_one(
            """
            SELECT COUNT(*) AS table_count
            FROM information_schema.tables
            WHERE table_schema = DATABASE()
              AND table_type = 'BASE TABLE'
            """
        )
        return {
            "database": row["database_name"] if row else None,
            "users": row["user_count"] if row else 0,
            "tables": table_row["table_count"] if table_row else 0,
        }

    def list_tables(self, search: str | None = None, limit: int = 300) -> list[dict[str, Any]]:
        where = ["table_schema = DATABASE()", "table_type = 'BASE TABLE'"]
        params: list[Any] = []
        if search:
            where.append("(table_name LIKE %s OR table_comment LIKE %s)")
            keyword = f"%{search}%"
            params.extend([keyword, keyword])
        params.append(limit)
        return self.db.fetch_all(
            f"""
            SELECT
              table_name,
              table_comment,
              table_rows,
              ROUND((data_length + index_length) / 1024 / 1024, 2) AS size_mb
            FROM information_schema.tables
            WHERE {" AND ".join(where)}
            ORDER BY table_name
            LIMIT %s
            """,
            tuple(params),
        )

    def describe_table(self, table_name: str) -> list[dict[str, Any]]:
        self._assert_safe_identifier(table_name)
        return self.db.fetch_all(
            """
            SELECT
              ordinal_position,
              column_name,
              column_type,
              is_nullable,
              column_default,
              column_key,
              column_comment
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = %s
            ORDER BY ordinal_position
            """,
            (table_name,),
        )

    def search_columns(self, keyword: str, limit: int = 300) -> list[dict[str, Any]]:
        pattern = f"%{keyword}%"
        return self.db.fetch_all(
            """
            SELECT
              table_name,
              column_name,
              column_type,
              column_comment
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND (
                table_name LIKE %s
                OR column_name LIKE %s
                OR column_comment LIKE %s
              )
            ORDER BY table_name, ordinal_position
            LIMIT %s
            """,
            (pattern, pattern, pattern, limit),
        )

    def run_read_only_query(self, sql: str, limit: int = 200) -> list[dict[str, Any]]:
        return self.db.fetch_many(sql, limit=limit)

    def get_todos(self, status: str = "unfinished") -> list[dict[str, Any]]:
        where = ["t.deleted = '1'"]
        if status == "unfinished":
            where.append("t.status NOT IN (8, 9)")
        elif status == "ongoing":
            where.append("t.status = 19")
        elif status == "not-started":
            where.append("t.status = 7")
        elif status == "all":
            pass
        else:
            raise ValueError("待办状态只支持 unfinished、ongoing、not-started、all。")

        sql = f"""
            SELECT
                t.id,
                t.content,
                MAX(d.name) AS dept_name,
                t.duty_user,
                GROUP_CONCAT(
                    DISTINCT COALESCE(u.realname, u.account)
                    ORDER BY u.realname
                    SEPARATOR ', '
                ) AS duty_names,
                t.status AS status_id,
                MAX(ps.name) AS status_name,
                t.type AS type_id,
                MAX(pt.name) AS type_name,
                t.deadlineTime,
                t.progress,
                t.remark,
                t.sourceLink,
                t.createdBy,
                MAX(cu.realname) AS createdByName,
                t.createdDate,
                t.editedBy,
                MAX(eu.realname) AS editedByName,
                t.editedDate
            FROM zt_to_do_list t
            LEFT JOIN zt_dept d ON d.id = t.dept
            LEFT JOIN zt_pool_type ps ON ps.id = t.status
            LEFT JOIN zt_pool_type pt ON pt.id = t.type
            LEFT JOIN zt_user u ON FIND_IN_SET(u.account, REPLACE(t.duty_user, ' ', '')) > 0
            LEFT JOIN zt_user cu ON cu.account = t.createdBy
            LEFT JOIN zt_user eu ON eu.account = t.editedBy
            WHERE {" AND ".join(where)}
            GROUP BY
                t.id, t.content, t.duty_user, t.status, t.type, t.deadlineTime,
                t.progress, t.remark, t.sourceLink, t.createdBy, t.createdDate,
                t.editedBy, t.editedDate
            ORDER BY
              CASE WHEN t.status = 19 THEN 0 WHEN t.status = 7 THEN 1 ELSE 2 END,
              CASE
                WHEN t.deadlineTime IS NULL
                  OR t.deadlineTime IN ('0000-00-00', '0000-00-00 00:00:00')
                THEN 1 ELSE 0
              END,
              t.deadlineTime ASC,
              t.id DESC
        """
        return self.db.fetch_all(sql)

    @staticmethod
    def _assert_safe_identifier(identifier: str) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_]+", identifier):
            raise ValueError("表名只能包含字母、数字和下划线。")

    @staticmethod
    def _dept_ids_from_value(value: object) -> list[int]:
        if value is None:
            return []
        ids: list[int] = []
        for part in str(value).replace("，", ",").split(","):
            part = part.strip()
            if part.isdigit():
                ids.append(int(part))
        return ids

    def _dept_name_map(self, values: list[object]) -> dict[int, str]:
        dept_ids = sorted({dept_id for value in values for dept_id in self._dept_ids_from_value(value)})
        if not dept_ids:
            return {}
        placeholders = ",".join(["%s"] * len(dept_ids))
        rows = self.db.fetch_all(
            f"""
            SELECT id, name
            FROM zt_dept
            WHERE id IN ({placeholders})
            """,
            tuple(dept_ids),
        )
        return {int(row["id"]): row["name"] for row in rows}

    def _dept_names_from_value(self, value: object, dept_map: dict[int, str]) -> str | None:
        ids = self._dept_ids_from_value(value)
        if not ids:
            return None
        names = [dept_map[dept_id] for dept_id in ids if dept_id in dept_map]
        return ",".join(names) if names else None

    def _normalize_bug_owner_depts(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        dept_map = self._dept_name_map([row.get("ownerDept") for row in rows])
        if not dept_map:
            return rows
        for row in rows:
            mapped = self._dept_names_from_value(row.get("ownerDept"), dept_map)
            if mapped:
                row["ownerDeptName"] = mapped
        return rows

    def _normalize_dept_labels(self, rows: list[dict[str, Any]], key: str = "dept") -> list[dict[str, Any]]:
        dept_map = self._dept_name_map([row.get(key) for row in rows])
        if not dept_map:
            return rows
        for row in rows:
            mapped = self._dept_names_from_value(row.get(key), dept_map)
            if mapped:
                row[key] = mapped
        return rows

    def find_product_id(self, product_name: str) -> int | None:
        row = self.db.fetch_one(
            """
            SELECT id
            FROM zt_product
            WHERE deleted = '0'
              AND name = %s
            ORDER BY status = 'normal' DESC, id ASC
            LIMIT 1
            """,
            (product_name,),
        )
        return int(row["id"]) if row else None

    def get_current_sprint_for_product(
        self,
        product_name: str,
        as_of: dt.date,
        project_name: str | None = None,
    ) -> dict[str, Any] | None:
        product_id = self.find_product_id(product_name)
        if product_id is None:
            return None

        params: list[Any] = [product_id, as_of, as_of]
        project_filter = ""
        if project_name:
            project_filter = "AND (root.name = %s OR p.name = %s)"
            params.extend([project_name, project_name])

        row = self.db.fetch_one(
            f"""
            SELECT DISTINCT
              p.id, p.name, p.type, p.status, p.parent, p.begin, p.end,
              root.name AS project_name,
              prod.id AS product_id,
              prod.name AS product_name
            FROM zt_project p
            JOIN zt_projectproduct pp ON pp.project = p.id
            JOIN zt_product prod ON prod.id = pp.product
            LEFT JOIN zt_project root ON root.id = p.parent
            WHERE p.deleted = '0'
              AND p.type = 'sprint'
              AND pp.product = %s
              AND p.begin <= %s
              AND p.end >= %s
              {project_filter}
            ORDER BY p.begin DESC, p.id DESC
            LIMIT 1
            """,
            tuple(params),
        )
        if row:
            return row

        fallback_params: list[Any] = [product_id, as_of]
        fallback_filter = ""
        if project_name:
            fallback_filter = "AND (root.name = %s OR p.name = %s)"
            fallback_params.extend([project_name, project_name])
        return self.db.fetch_one(
            f"""
            SELECT DISTINCT
              p.id, p.name, p.type, p.status, p.parent, p.begin, p.end,
              root.name AS project_name,
              prod.id AS product_id,
              prod.name AS product_name
            FROM zt_project p
            JOIN zt_projectproduct pp ON pp.project = p.id
            JOIN zt_product prod ON prod.id = pp.product
            LEFT JOIN zt_project root ON root.id = p.parent
            WHERE p.deleted = '0'
              AND p.type = 'sprint'
              AND pp.product = %s
              AND p.begin <= %s
              {fallback_filter}
            ORDER BY
              p.status = 'doing' DESC,
              p.begin DESC,
              p.id DESC
            LIMIT 1
            """,
            tuple(fallback_params),
        )

    def get_next_sprint_for_product(
        self,
        product_name: str,
        as_of: dt.date,
        project_name: str | None = None,
    ) -> dict[str, Any] | None:
        product_id = self.find_product_id(product_name)
        if product_id is None:
            return None

        params: list[Any] = [product_id, as_of]
        project_filter = ""
        if project_name:
            project_filter = "AND (root.name = %s OR p.name = %s)"
            params.extend([project_name, project_name])

        return self.db.fetch_one(
            f"""
            SELECT DISTINCT
              p.id, p.name, p.type, p.status, p.parent, p.begin, p.end,
              root.name AS project_name,
              prod.id AS product_id,
              prod.name AS product_name
            FROM zt_project p
            JOIN zt_projectproduct pp ON pp.project = p.id
            JOIN zt_product prod ON prod.id = pp.product
            LEFT JOIN zt_project root ON root.id = p.parent
            WHERE p.deleted = '0'
              AND p.type = 'sprint'
              AND pp.product = %s
              AND p.begin > %s
              {project_filter}
            ORDER BY p.begin ASC, p.id ASC
            LIMIT 1
            """,
            tuple(params),
        )

    def get_latest_completed_sprint_for_product(
        self,
        product_name: str,
        as_of: dt.date,
        project_name: str | None = None,
    ) -> dict[str, Any] | None:
        product_id = self.find_product_id(product_name)
        if product_id is None:
            return None

        params: list[Any] = [product_id, as_of]
        project_filter = ""
        if project_name:
            project_filter = "AND (root.name = %s OR p.name = %s)"
            params.extend([project_name, project_name])

        return self.db.fetch_one(
            f"""
            SELECT DISTINCT
              p.id, p.name, p.type, p.status, p.parent, p.begin, p.end,
              root.name AS project_name,
              prod.id AS product_id,
              prod.name AS product_name
            FROM zt_project p
            JOIN zt_projectproduct pp ON pp.project = p.id
            JOIN zt_product prod ON prod.id = pp.product
            LEFT JOIN zt_project root ON root.id = p.parent
            WHERE p.deleted = '0'
              AND p.type = 'sprint'
              AND pp.product = %s
              AND p.end <= %s
              {project_filter}
            ORDER BY p.end DESC, p.id DESC
            LIMIT 1
            """,
            tuple(params),
        )

    def get_recent_sprints_for_product(
        self,
        product_name: str,
        as_of: dt.date,
        project_name: str | None = None,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        product_id = self.find_product_id(product_name)
        if product_id is None:
            return []

        params: list[Any] = [product_id, as_of, limit]
        project_filter = ""
        if project_name:
            project_filter = "AND (root.name = %s OR p.name = %s)"
            params = [product_id, as_of, project_name, project_name, limit]

        return self.db.fetch_all(
            f"""
            SELECT DISTINCT
              p.id, p.name, p.type, p.status, p.parent, p.begin, p.end,
              root.name AS project_name,
              prod.id AS product_id,
              prod.name AS product_name
            FROM zt_project p
            JOIN zt_projectproduct pp ON pp.project = p.id
            JOIN zt_product prod ON prod.id = pp.product
            LEFT JOIN zt_project root ON root.id = p.parent
            WHERE p.deleted = '0'
              AND p.type = 'sprint'
              AND pp.product = %s
              AND p.end <= %s
              {project_filter}
            ORDER BY p.end DESC, p.id DESC
            LIMIT %s
            """,
            tuple(params),
        )

    def get_version_task_summary(self, version_id: int, as_of: dt.date) -> dict[str, Any]:
        version = self.db.fetch_one(
            """
            SELECT id, name, begin, end, status
            FROM zt_project
            WHERE id = %s
            """,
            (version_id,),
        )
        summary = self.db.fetch_one(
            """
            SELECT
              COUNT(*) AS total_tasks,
              SUM(IF(status NOT IN ('done','closed','cancel'), 1, 0)) AS open_tasks,
              SUM(IF(
                deadline IS NOT NULL
                  AND deadline NOT IN ('0000-00-00')
                  AND deadline < %s
                  AND status NOT IN ('done','closed','cancel'),
                1, 0
              )) AS overdue_open,
              SUM(IF(
                finishedDate IS NOT NULL
                  AND finishedDate NOT IN ('0000-00-00 00:00:00')
                  AND deadline IS NOT NULL
                  AND deadline NOT IN ('0000-00-00')
                  AND DATE(finishedDate) > deadline,
                1, 0
              )) AS finished_late,
              SUM(IF(
                TRIM(COALESCE(delayReason, '')) <> '',
                1, 0
              )) AS delay_reason_count,
              SUM(IF(
                COALESCE(delayTimes, 0) > 0,
                1, 0
              )) AS delay_times_count
            FROM zt_task
            WHERE deleted = '0'
              AND execution = %s
            """,
            (as_of, version_id),
        )
        status_rows = self.db.fetch_all(
            """
            SELECT status, COUNT(*) AS count
            FROM zt_task
            WHERE deleted = '0'
              AND execution = %s
            GROUP BY status
            ORDER BY count DESC
            """,
            (version_id,),
        )
        pool_delay = self.db.fetch_one(
            """
            SELECT
              COUNT(*) AS total_pool_items,
              SUM(TRIM(COALESCE(delayReason, '')) <> '') AS delay_reason_count,
              SUM(TRIM(COALESCE(delayMeasure, '')) <> '') AS delay_measure_count
            FROM zt_pool
            WHERE deleted = '0'
              AND type = 0
              AND pv_id = %s
            """,
            (version_id,),
        )
        return {
            "version": version,
            "summary": summary,
            "status": status_rows,
            "pool_delay": pool_delay,
        }

    def get_overdue_open_tasks(self, version_id: int, as_of: dt.date) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            """
            SELECT
              t.id,
              t.parent,
              IFNULL(parent.name, t.name) AS root_name,
              t.name,
              t.status,
              t.assignedTo,
              u.realname AS assignedName,
              t.deadline,
              t.finishedDate,
              DATEDIFF(%s, t.deadline) AS overdue_days,
              t.estimate,
              t.consumed,
              t.left,
              t.delayTimes,
              t.delayReason
            FROM zt_task t
            LEFT JOIN zt_task parent ON parent.id = t.parent AND t.parent > 0
            LEFT JOIN zt_user u ON u.account = t.assignedTo
            WHERE t.deleted = '0'
              AND t.execution = %s
              AND t.deadline IS NOT NULL
              AND t.deadline NOT IN ('0000-00-00')
              AND t.deadline < %s
              AND t.status NOT IN ('done','closed','cancel')
            ORDER BY overdue_days DESC, t.deadline ASC, t.id
            """,
            (as_of, version_id, as_of),
        )

    def get_finished_late_tasks(self, version_id: int) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            """
            SELECT
              t.id,
              t.parent,
              IFNULL(parent.name, t.name) AS root_name,
              t.name,
              t.status,
              t.assignedTo,
              u.realname AS assignedName,
              t.deadline,
              t.finishedDate,
              DATEDIFF(DATE(t.finishedDate), t.deadline) AS late_days,
              t.estimate,
              t.consumed,
              t.left
            FROM zt_task t
            LEFT JOIN zt_task parent ON parent.id = t.parent AND t.parent > 0
            LEFT JOIN zt_user u ON u.account = t.assignedTo
            WHERE t.deleted = '0'
              AND t.execution = %s
              AND t.finishedDate IS NOT NULL
              AND t.finishedDate NOT IN ('0000-00-00 00:00:00')
              AND t.deadline IS NOT NULL
              AND t.deadline NOT IN ('0000-00-00')
              AND DATE(t.finishedDate) > t.deadline
            ORDER BY late_days DESC, t.deadline ASC, t.id
            """,
            (version_id,),
        )

    def get_marked_delay_tasks(self, version_id: int) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            """
            SELECT
              t.id,
              t.parent,
              IFNULL(parent.name, t.name) AS root_name,
              t.name,
              t.status,
              t.source,
              t.category,
              t.isSureStory,
              t.assignedTo,
              u.realname AS assignedName,
              au_dept.name AS assignedDeptName,
              t.openedDate,
              t.estStarted,
              t.deadline,
              t.finishedDate,
              t.finishedBy,
              fu.realname AS finishedName,
              fu_dept.name AS finishedDeptName,
              t.closedBy,
              cu.realname AS closedName,
              cu_dept.name AS closedDeptName,
              t.delayTimes,
              t.delayReason,
              t.left
            FROM zt_task t
            LEFT JOIN zt_task parent ON parent.id = t.parent AND t.parent > 0
            LEFT JOIN zt_user u ON u.account = t.assignedTo
            LEFT JOIN zt_dept au_dept ON au_dept.id = u.dept
            LEFT JOIN zt_user fu ON fu.account = t.finishedBy
            LEFT JOIN zt_dept fu_dept ON fu_dept.id = fu.dept
            LEFT JOIN zt_user cu ON cu.account = t.closedBy
            LEFT JOIN zt_dept cu_dept ON cu_dept.id = cu.dept
            WHERE t.deleted = '0'
              AND t.execution = %s
              AND (
                COALESCE(t.delayTimes, 0) > 0
                OR TRIM(COALESCE(t.delayReason, '')) <> ''
              )
            ORDER BY t.delayTimes DESC, t.id
            """,
            (version_id,),
        )

    def get_today_opened_tasks(
        self,
        version_id: int,
        as_of: dt.date,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            """
            SELECT
              t.id,
              IFNULL(parent.name, t.name) AS root_name,
              t.name,
              t.status,
              t.assignedTo,
              u.realname AS assignedName,
              t.openedBy,
              ou.realname AS openedName,
              t.openedDate,
              t.deadline,
              t.estimate,
              t.left
            FROM zt_task t
            LEFT JOIN zt_task parent ON parent.id = t.parent AND t.parent > 0
            LEFT JOIN zt_user u ON u.account = t.assignedTo
            LEFT JOIN zt_user ou ON ou.account = t.openedBy
            WHERE t.deleted = '0'
              AND t.execution = %s
              AND DATE(t.openedDate) = %s
            ORDER BY t.openedDate DESC, t.id DESC
            LIMIT %s
            """,
            (version_id, as_of, limit),
        )

    def get_today_finished_tasks(
        self,
        version_id: int,
        as_of: dt.date,
        limit: int = 40,
    ) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            """
            SELECT
              t.id,
              IFNULL(parent.name, t.name) AS root_name,
              t.name,
              t.status,
              t.assignedTo,
              u.realname AS assignedName,
              t.finishedBy,
              fu.realname AS finishedName,
              t.finishedDate,
              t.deadline,
              IF(
                t.deadline IS NOT NULL
                  AND t.deadline NOT IN ('0000-00-00')
                  AND DATE(t.finishedDate) > t.deadline,
                DATEDIFF(DATE(t.finishedDate), t.deadline),
                0
              ) AS late_days,
              t.consumed
            FROM zt_task t
            LEFT JOIN zt_task parent ON parent.id = t.parent AND t.parent > 0
            LEFT JOIN zt_user u ON u.account = t.assignedTo
            LEFT JOIN zt_user fu ON fu.account = t.finishedBy
            WHERE t.deleted = '0'
              AND t.execution = %s
              AND t.finishedDate IS NOT NULL
              AND t.finishedDate NOT IN ('0000-00-00 00:00:00')
              AND DATE(t.finishedDate) = %s
            ORDER BY t.finishedDate DESC, t.id DESC
            LIMIT %s
            """,
            (version_id, as_of, limit),
        )

    def get_due_today_tasks(self, version_id: int, as_of: dt.date) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            """
            SELECT
              t.id,
              IFNULL(parent.name, t.name) AS root_name,
              t.name,
              t.status,
              t.assignedTo,
              u.realname AS assignedName,
              t.deadline,
              t.estimate,
              t.consumed,
              t.left
            FROM zt_task t
            LEFT JOIN zt_task parent ON parent.id = t.parent AND t.parent > 0
            LEFT JOIN zt_user u ON u.account = t.assignedTo
            WHERE t.deleted = '0'
              AND t.execution = %s
              AND t.deadline = %s
              AND t.status NOT IN ('done','closed','cancel')
            ORDER BY t.left DESC, t.id
            """,
            (version_id, as_of),
        )

    def get_version_demand_summary(self, version_id: int) -> dict[str, Any]:
        summary = self.db.fetch_one(
            """
            SELECT
              COUNT(*) AS total_demands,
              SUM(IF(taskID > 0, 1, 0)) AS with_task,
              SUM(IF(taskID = 0, 1, 0)) AS without_task,
              SUM(IF(TRIM(COALESCE(delayReason, '')) <> '', 1, 0)) AS delay_reason_count,
              SUM(IF(TRIM(COALESCE(delayMeasure, '')) <> '', 1, 0)) AS delay_measure_count
            FROM zt_pool
            WHERE deleted = '0'
              AND type = 0
              AND pv_id = %s
            """,
            (version_id,),
        )
        status_rows = self.db.fetch_all(
            """
            SELECT
              COALESCE(pt.name, NULLIF(p.status, ''), '未填写') AS status,
              COUNT(*) AS count
            FROM zt_pool p
            LEFT JOIN zt_pool_type pt
              ON p.status REGEXP '^[0-9]+$'
              AND pt.id = CAST(p.status AS UNSIGNED)
            WHERE p.deleted = '0'
              AND p.type = 0
              AND p.pv_id = %s
            GROUP BY COALESCE(pt.name, NULLIF(p.status, ''), '未填写')
            ORDER BY count DESC, status
            """,
            (version_id,),
        )
        return {"summary": summary or {}, "status": status_rows}

    def get_version_demands(self, version_id: int, limit: int = 30) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            """
            SELECT
              p.id,
              p.title,
              p.status,
              p.pm,
              pm.realname AS pmName,
              p.tester,
              tester.realname AS testerName,
              p.taskID,
              t.status AS taskStatus,
              t.assignedTo,
              au.realname AS assignedName,
              p.delayReason,
              p.delayMeasure
            FROM zt_pool p
            LEFT JOIN zt_task t ON t.id = p.taskID
            LEFT JOIN zt_user pm ON pm.account = p.pm
            LEFT JOIN zt_user tester ON tester.account = p.tester
            LEFT JOIN zt_user au ON au.account = t.assignedTo
            WHERE p.deleted = '0'
              AND p.type = 0
              AND p.pv_id = %s
            ORDER BY p.sortOrder ASC, p.id ASC
            LIMIT %s
            """,
            (version_id, limit),
        )

    def get_bug_summary(self, version_id: int, as_of: dt.date) -> dict[str, Any]:
        summary = self.db.fetch_one(
            """
            SELECT
              COUNT(*) AS total_bugs,
              SUM(IF(status = 'active', 1, 0)) AS active_bugs,
              SUM(IF(status = 'resolved', 1, 0)) AS resolved_bugs,
              SUM(IF(status = 'closed', 1, 0)) AS closed_bugs,
              SUM(IF(status = 'active' AND severity IN (1, 2), 1, 0)) AS active_high_bugs,
              SUM(IF(DATE(openedDate) = %s, 1, 0)) AS opened_today,
              SUM(IF(DATE(resolvedDate) = %s, 1, 0)) AS resolved_today,
              SUM(IF(DATE(closedDate) = %s, 1, 0)) AS closed_today
            FROM zt_bug
            WHERE deleted = '0'
              AND execution = %s
            """,
            (as_of, as_of, as_of, version_id),
        )
        status_rows = self.db.fetch_all(
            """
            SELECT status, COUNT(*) AS count
            FROM zt_bug
            WHERE deleted = '0'
              AND execution = %s
            GROUP BY status
            ORDER BY count DESC
            """,
            (version_id,),
        )
        severity_rows = self.db.fetch_all(
            """
            SELECT severity, COUNT(*) AS count
            FROM zt_bug
            WHERE deleted = '0'
              AND execution = %s
            GROUP BY severity
            ORDER BY severity ASC
            """,
            (version_id,),
        )
        return {
            "summary": summary or {},
            "status": status_rows,
            "severity": severity_rows,
        }

    def get_active_bugs(self, version_id: int, limit: int = 30) -> list[dict[str, Any]]:
        rows = self.db.fetch_all(
            """
            SELECT
              b.id,
              b.title,
              b.status,
              b.severity,
              b.pri,
              b.assignedTo,
              au.realname AS assignedName,
              b.owner,
              ou.realname AS ownerName,
              b.openedDate,
              b.resolvedDate,
              b.type,
              b.ownerDept,
              COALESCE(od.name, NULLIF(b.ownerDept, ''), NULLIF(b.type, ''), '未填写') AS ownerDeptName
            FROM zt_bug b
            LEFT JOIN zt_user au ON au.account = b.assignedTo
            LEFT JOIN zt_user ou ON ou.account = b.owner
            LEFT JOIN zt_dept od
              ON b.ownerDept REGEXP '^[0-9]+$'
              AND od.id = CAST(b.ownerDept AS UNSIGNED)
            WHERE b.deleted = '0'
              AND b.execution = %s
              AND b.status = 'active'
            ORDER BY b.severity ASC, b.pri ASC, b.openedDate DESC, b.id DESC
            LIMIT %s
            """,
            (version_id, limit),
        )
        return self._normalize_bug_owner_depts(rows)

    def find_users(self, keyword: str, limit: int = 20) -> list[dict[str, Any]]:
        pattern = f"%{keyword}%"
        return self.db.fetch_all(
            """
            SELECT
              u.account,
              u.realname,
              u.dept AS dept_id,
              d.name AS dept_name,
              u.role,
              u.deleted
            FROM zt_user u
            LEFT JOIN zt_dept d ON d.id = u.dept
            WHERE u.deleted = '0'
              AND (
                u.account = %s
                OR u.realname = %s
                OR u.account LIKE %s
                OR u.realname LIKE %s
                OR u.pinyin LIKE %s
              )
            ORDER BY
              (u.account = %s OR u.realname = %s) DESC,
              u.realname ASC
            LIMIT %s
            """,
            (keyword, keyword, pattern, pattern, pattern, keyword, keyword, limit),
        )

    def get_person_tasks(self, account: str, limit: int = 80) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            """
            SELECT
              t.id,
              t.name,
              t.status,
              t.project,
              proj.name AS project_name,
              t.execution,
              exec.name AS execution_name,
              t.deadline,
              t.estimate,
              t.consumed,
              t.left,
              t.openedDate,
              t.finishedDate,
              IF(
                t.deadline IS NOT NULL
                  AND t.deadline NOT IN ('0000-00-00')
                  AND t.deadline < CURDATE()
                  AND t.status NOT IN ('done','closed','cancel'),
                DATEDIFF(CURDATE(), t.deadline),
                0
              ) AS overdue_days
            FROM zt_task t
            LEFT JOIN zt_project proj ON proj.id = t.project
            LEFT JOIN zt_project exec ON exec.id = t.execution
            WHERE t.deleted = '0'
              AND t.assignedTo = %s
              AND t.status NOT IN ('done','closed','cancel')
            ORDER BY overdue_days DESC, t.deadline ASC, t.id DESC
            LIMIT %s
            """,
            (account, limit),
        )

    def get_person_bugs(self, account: str, limit: int = 80) -> list[dict[str, Any]]:
        rows = self.db.fetch_all(
            """
            SELECT
              b.id,
              b.title,
              b.status,
              b.severity,
              b.pri,
              b.execution,
              exec.name AS execution_name,
              b.assignedTo,
              b.owner,
              b.openedDate,
              b.deadline,
              b.resolvedDate,
              b.type,
              b.ownerDept,
              COALESCE(od.name, NULLIF(b.ownerDept, ''), NULLIF(b.type, ''), '未填写') AS ownerDeptName
            FROM zt_bug b
            LEFT JOIN zt_project exec ON exec.id = b.execution
            LEFT JOIN zt_dept od
              ON b.ownerDept REGEXP '^[0-9]+$'
              AND od.id = CAST(b.ownerDept AS UNSIGNED)
            WHERE b.deleted = '0'
              AND b.status <> 'closed'
              AND (b.assignedTo = %s OR b.owner = %s OR b.openedBy = %s)
            ORDER BY b.status = 'active' DESC, b.severity ASC, b.pri ASC, b.openedDate DESC
            LIMIT %s
            """,
            (account, account, account, limit),
        )
        return self._normalize_bug_owner_depts(rows)

    def get_person_todos(self, account: str, limit: int = 80) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            """
            SELECT
              t.id,
              t.content,
              d.name AS dept_name,
              t.duty_user,
              ps.name AS status_name,
              pt.name AS type_name,
              t.deadlineTime,
              t.progress,
              t.sourceLink
            FROM zt_to_do_list t
            LEFT JOIN zt_dept d ON d.id = t.dept
            LEFT JOIN zt_pool_type ps ON ps.id = t.status
            LEFT JOIN zt_pool_type pt ON pt.id = t.type
            WHERE t.deleted = '1'
              AND t.status NOT IN (8, 9)
              AND FIND_IN_SET(%s, REPLACE(t.duty_user, ' ', '')) > 0
            ORDER BY t.deadlineTime ASC, t.id DESC
            LIMIT %s
            """,
            (account, limit),
        )

    def get_demand_status(self, keyword: str, limit: int = 20) -> list[dict[str, Any]]:
        id_value = int(keyword) if keyword.isdigit() else None
        pattern = f"%{keyword}%"
        where = ["p.deleted = '0'"]
        params: list[Any] = []
        if id_value is not None:
            where.append(
                """
                (
                  p.id = %s
                  OR p.taskID = %s
                  OR p.storyId = %s
                  OR t.id = %s
                  OR s.id = %s
                )
                """
            )
            params.extend([id_value, id_value, id_value, id_value, id_value])
        else:
            where.append(
                """
                (
                  p.title LIKE %s
                  OR p.`desc` LIKE %s
                  OR p.sourceLink LIKE %s
                  OR s.title LIKE %s
                  OR s.storyNo LIKE %s
                )
                """
            )
            params.extend([pattern, pattern, pattern, pattern, pattern])
        params.append(limit)
        return self.db.fetch_all(
            f"""
            SELECT
              p.id,
              p.title,
              p.type AS pool_type,
              p.status AS raw_status,
              COALESCE(ps.name, NULLIF(p.status, ''), '未填写') AS status_name,
              p.requirementStatus,
              rs.name AS requirement_status_name,
              p.pv_id,
              pv.name AS version_name,
              p.expectedVersion,
              ev.name AS expected_version_name,
              p.storyId,
              s.title AS story_title,
              s.status AS story_status,
              s.stage AS story_stage,
              s.assignedTo AS story_assignedTo,
              su.realname AS story_assignedName,
              s.pri AS story_pri,
              s.storyNo,
              p.taskID,
              t.name AS task_name,
              t.status AS task_status,
              t.assignedTo,
              au.realname AS assignedName,
              p.pm,
              pm.realname AS pmName,
              p.tester,
              tester.realname AS testerName,
              p.submitter,
              submitter.realname AS submitterName,
              p.createdDate,
              p.editedDate,
              p.delayReason,
              p.delayMeasure,
              p.sourceLink,
              p.remark
            FROM zt_pool p
            LEFT JOIN zt_project pv ON p.type = 0 AND pv.id = p.pv_id
            LEFT JOIN zt_project ev ON ev.id = p.expectedVersion
            LEFT JOIN zt_story s ON s.id = p.storyId AND s.deleted = '0'
            LEFT JOIN zt_user su ON su.account = s.assignedTo
            LEFT JOIN zt_task t ON t.id = p.taskID
            LEFT JOIN zt_user au ON au.account = t.assignedTo
            LEFT JOIN zt_user pm ON pm.account = p.pm
            LEFT JOIN zt_user tester ON tester.account = p.tester
            LEFT JOIN zt_user submitter ON submitter.account = p.submitter
            LEFT JOIN zt_pool_type ps
              ON p.status REGEXP '^[0-9]+$'
              AND ps.id = CAST(p.status AS UNSIGNED)
            LEFT JOIN zt_pool_type rs ON rs.id = p.requirementStatus
            WHERE {" AND ".join(where)}
            ORDER BY
              pv.begin DESC,
              pv.id DESC,
              p.editedDate DESC,
              p.id DESC
            LIMIT %s
            """,
            tuple(params),
        )

    def get_measures(self, status: str = "unfinished", limit: int = 100) -> dict[str, Any]:
        todo_rows = self.get_todos(status if status in {"unfinished", "ongoing", "not-started", "all"} else "unfinished")
        where = ["m.deleted = '1'"]
        params: list[Any] = []
        if status == "unfinished":
            where.append("m.status NOT IN (8, 9)")
        elif status == "ongoing":
            where.append("m.status = 19")
        elif status == "not-started":
            where.append("m.status = 7")
        elif status == "all":
            pass
        else:
            where.append("(ms.name LIKE %s OR m.status = %s)")
            params.extend([f"%{status}%", status])
        params.append(limit)
        measure_rows = self.db.fetch_all(
            f"""
            SELECT
              m.id,
              m.title,
              COALESCE(d.name, m.dept) AS dept_name,
              m.duty_user,
              u.realname AS duty_name,
              m.status AS status_id,
              ms.name AS status_name,
              m.questionType,
              qt.name AS question_type_name,
              m.pv_id,
              pv.name AS version_name,
              m.bug_ids,
              m.remark,
              m.createdDate,
              m.editedDate
            FROM zt_measures_management m
            LEFT JOIN zt_dept d
              ON m.dept REGEXP '^[0-9]+$'
              AND d.id = CAST(m.dept AS UNSIGNED)
            LEFT JOIN zt_user u ON u.account = m.duty_user
            LEFT JOIN zt_pool_type ms ON ms.id = m.status
            LEFT JOIN zt_pool_type qt ON qt.id = m.questionType
            LEFT JOIN zt_project pv ON pv.id = m.pv_id
            WHERE {" AND ".join(where)}
            ORDER BY m.editedDate DESC, m.id DESC
            LIMIT %s
            """,
            tuple(params),
        )
        return {"todos": todo_rows[:limit], "measures": measure_rows}

    def get_bug_review(self, version_id: int, limit: int = 80) -> dict[str, Any]:
        summary = self.get_bug_summary(version_id, dt.date.today())
        bugs = self.db.fetch_all(
            """
            SELECT
              b.id,
              b.title,
              b.status,
              b.severity,
              b.pri,
              b.assignedTo,
              au.realname AS assignedName,
              b.owner,
              ou.realname AS ownerName,
              b.openedDate,
              b.resolvedDate,
              b.closedDate,
              b.type,
              b.ownerDept,
              COALESCE(od.name, NULLIF(b.ownerDept, ''), NULLIF(b.type, ''), '未填写') AS ownerDeptName,
              b.causeAnalysis,
              b.nextStep,
              b.phenomenon,
              b.scopeInfluence,
              GROUP_CONCAT(
                DISTINCT CONCAT(
                  COALESCE(rd.name, r.dept),
                  '||',
                  REPLACE(REPLACE(COALESCE(r.causeAnalysis, ''), '\r', ' '), '\n', ' '),
                  '||',
                  REPLACE(REPLACE(COALESCE(r.nextStep, ''), '\r', ' '), '\n', ' ')
                )
                ORDER BY r.dept SEPARATOR '||ROW||'
              ) AS dept_review
            FROM zt_bug b
            LEFT JOIN zt_user au ON au.account = b.assignedTo
            LEFT JOIN zt_user ou ON ou.account = b.owner
            LEFT JOIN zt_dept od
              ON b.ownerDept REGEXP '^[0-9]+$'
              AND od.id = CAST(b.ownerDept AS UNSIGNED)
            LEFT JOIN zt_bug_dept_review r ON r.bugId = b.id
            LEFT JOIN zt_dept rd
              ON r.dept REGEXP '^[0-9]+$'
              AND rd.id = CAST(r.dept AS UNSIGNED)
            WHERE b.deleted = '0'
              AND b.execution = %s
            GROUP BY
              b.id, b.title, b.status, b.severity, b.pri, b.assignedTo, au.realname,
              b.owner, ou.realname, b.openedDate, b.resolvedDate, b.closedDate,
              b.type, b.ownerDept, od.name, b.causeAnalysis, b.nextStep, b.phenomenon, b.scopeInfluence
            ORDER BY b.status = 'active' DESC, b.severity ASC, b.pri ASC, b.openedDate DESC
            LIMIT %s
            """,
            (version_id, limit),
        )
        dept_rows = self.db.fetch_all(
            """
            SELECT
              COALESCE(od.name, NULLIF(b.ownerDept, ''), NULLIF(b.type, ''), '未填写') AS dept,
              COUNT(*) AS bug_count,
              SUM(IF(b.status = 'active', 1, 0)) AS active_count,
              SUM(IF(b.severity IN (1, 2), 1, 0)) AS high_count
            FROM zt_bug b
            LEFT JOIN zt_dept od
              ON b.ownerDept REGEXP '^[0-9]+$'
              AND od.id = CAST(b.ownerDept AS UNSIGNED)
            WHERE b.deleted = '0'
              AND b.execution = %s
            GROUP BY COALESCE(od.name, NULLIF(b.ownerDept, ''), NULLIF(b.type, ''), '未填写')
            ORDER BY bug_count DESC, high_count DESC
            """,
            (version_id,),
        )
        return {
            "summary": summary,
            "bugs": self._normalize_bug_owner_depts(bugs),
            "dept_summary": self._normalize_dept_labels(dept_rows),
        }

    def get_bug_boundary(self, version_id: int, limit: int = 160) -> dict[str, Any]:
        version = self.db.fetch_one(
            """
            SELECT id, name, begin, end, status
            FROM zt_project
            WHERE id = %s
            """,
            (version_id,),
        )
        summary = self.get_bug_summary(version_id, dt.date.today())
        bugs = self.db.fetch_all(
            """
            SELECT
              b.id,
              b.title,
              b.status,
              b.severity,
              b.pri,
              b.classification,
              b.type,
              b.bugTypeParent,
              b.bugType,
              b.isTypical,
              b.assignedTo,
              au.realname AS assignedName,
              b.owner,
              ou.realname AS ownerName,
              b.ownerDept,
              COALESCE(od.name, NULLIF(b.ownerDept, ''), NULLIF(b.type, ''), '未填写') AS ownerDeptName,
              b.openedDate,
              b.resolvedDate,
              b.closedDate,
              b.task,
              t.name AS task_name,
              t.assignedTo AS task_assignedTo,
              tu.realname AS task_assignedName,
              t.status AS task_status,
              t.deadline AS task_deadline,
              t.estimate AS task_estimate,
              t.consumed AS task_consumed,
              t.`left` AS task_left,
              t.demandReview,
              t.isSureStory,
              t.delayReason AS task_delayReason,
              b.causeAnalysis,
              b.nextStep,
              b.phenomenon,
              b.scopeInfluence,
              r.dept_review
            FROM zt_bug b
            LEFT JOIN zt_user au ON au.account = b.assignedTo
            LEFT JOIN zt_user ou ON ou.account = b.owner
            LEFT JOIN zt_dept od
              ON b.ownerDept REGEXP '^[0-9]+$'
              AND od.id = CAST(b.ownerDept AS UNSIGNED)
            LEFT JOIN zt_task t ON t.id = b.task
            LEFT JOIN zt_user tu ON tu.account = t.assignedTo
            LEFT JOIN (
              SELECT
                r.bugId,
                GROUP_CONCAT(
                  DISTINCT CONCAT(
                    COALESCE(d.name, r.dept),
                    '||',
                    REPLACE(REPLACE(COALESCE(r.causeAnalysis, ''), '\r', ' '), '\n', ' '),
                    '||',
                    REPLACE(REPLACE(COALESCE(r.nextStep, ''), '\r', ' '), '\n', ' ')
                  )
                  ORDER BY r.dept SEPARATOR '||ROW||'
                ) AS dept_review
              FROM zt_bug_dept_review r
              LEFT JOIN zt_dept d
                ON r.dept REGEXP '^[0-9]+$'
                AND d.id = CAST(r.dept AS UNSIGNED)
              GROUP BY r.bugId
            ) r ON r.bugId = b.id
            WHERE b.deleted = '0'
              AND b.execution = %s
            ORDER BY
              b.classification ASC,
              b.severity ASC,
              b.pri ASC,
              b.isTypical DESC,
              b.openedDate DESC,
              b.id DESC
            LIMIT %s
            """,
            (version_id, limit),
        )
        low_quality_tasks = self.db.fetch_all(
            """
            SELECT
              b.task AS task_id,
              t.name AS task_name,
              t.assignedTo AS task_assignedTo,
              tu.realname AS task_assignedName,
              t.status AS task_status,
              t.deadline AS task_deadline,
              t.estimate AS task_estimate,
              t.consumed AS task_consumed,
              COUNT(*) AS bug_count,
              SUM(IF(b.classification IN ('1','2'), 1, 0)) AS external_bug_count,
              SUM(IF(b.classification IN ('4','5'), 1, 0)) AS internal_bug_count,
              SUM(IF(b.severity IN (1, 2) OR b.isTypical = '1', 1, 0)) AS key_bug_count,
              GROUP_CONCAT(b.id ORDER BY b.severity ASC, b.id DESC SEPARATOR ',') AS bug_ids
            FROM zt_bug b
            JOIN zt_task t ON t.id = b.task
            LEFT JOIN zt_user tu ON tu.account = t.assignedTo
            WHERE b.deleted = '0'
              AND b.execution = %s
              AND b.task > 0
              AND b.type <> 'performance'
            GROUP BY
              b.task, t.name, t.assignedTo, tu.realname, t.status, t.deadline,
              t.estimate, t.consumed
            HAVING bug_count >= 2
            ORDER BY key_bug_count DESC, bug_count DESC, external_bug_count DESC
            LIMIT 30
            """,
            (version_id,),
        )
        return {
            "version": version,
            "summary": summary,
            "bugs": self._normalize_bug_owner_depts(bugs),
            "low_quality_tasks": low_quality_tasks,
        }

    def get_version_review_trends(
        self,
        product_name: str,
        project_name: str,
        as_of: dt.date,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        trends: list[dict[str, Any]] = []
        for sprint in reversed(self.get_recent_sprints_for_product(product_name, as_of, project_name, limit)):
            version_id = int(sprint["id"])
            task_summary = self.get_version_task_summary(version_id, as_of).get("summary") or {}
            bug_summary = self.get_bug_summary(version_id, as_of).get("summary") or {}
            req_counts = self.get_review_requirement_counts(version_id)
            bug_classification = self.db.fetch_one(
                """
                SELECT
                  SUM(IF(classification IN ('1','2') AND type <> 'performance', 1, 0)) AS external_bugs,
                  SUM(IF(classification IN ('4','5') AND type NOT IN ('performance','DDProblem'), 1, 0)) AS internal_bugs,
                  SUM(IF(classification IN ('4','5'), 1, 0)) AS internal_bugs_raw,
                  SUM(IF(classification IN ('1','2') AND type = 'performance', 1, 0)) AS nonbug_bugs,
                  SUM(IF(
                    classification IN ('1','2')
                    AND type <> 'performance'
                    AND FIND_IN_SET('45', REPLACE(ownerDept, ' ', '')) > 0,
                    1, 0
                  )) AS test_external_bugs
                FROM zt_bug
                WHERE deleted = '0'
                  AND execution = %s
                """,
                (version_id,),
            ) or {}
            trends.append(
                {
                    "id": version_id,
                    "name": sprint.get("name"),
                    "begin": sprint.get("begin"),
                    "end": sprint.get("end"),
                    "tasks": task_summary.get("total_tasks", 0),
                    "open_tasks": task_summary.get("open_tasks", 0),
                    "demands": req_counts.get("total_reqs", 0),
                    "ext_reqs": req_counts.get("ext_reqs", 0),
                    "int_reqs": req_counts.get("int_reqs", 0),
                    "bugs": bug_summary.get("total_bugs", 0),
                    "active_bugs": bug_summary.get("active_bugs", 0),
                    "high_active_bugs": bug_summary.get("active_high_bugs", 0),
                    "external_bugs": bug_classification.get("external_bugs", 0),
                    "internal_bugs": bug_classification.get("internal_bugs", 0),
                    "internal_bugs_raw": bug_classification.get("internal_bugs_raw", 0),
                    "nonbug_bugs": bug_classification.get("nonbug_bugs", 0),
                    "test_external_bugs": bug_classification.get("test_external_bugs", 0),
                }
            )
        return trends

    def get_review_requirement_counts(self, version_id: int) -> dict[str, Any]:
        pool_rows = self.db.fetch_all(
            """
            SELECT
              p.category,
              COUNT(*) AS count
            FROM zt_pool p
            LEFT JOIN zt_task t ON t.id = p.taskID
            WHERE p.deleted = '0'
              AND p.type = 0
              AND p.pv_id = %s
              AND COALESCE(t.status, '') <> 'cancel'
            GROUP BY p.category
            """,
            (version_id,),
        )
        missing_task_rows = self.db.fetch_all(
            """
            SELECT
              CASE
                WHEN t.source = 'customer' THEN 'version'
                WHEN t.source = 'operation' THEN 'operation'
                ELSE 'internal'
              END AS category,
              COUNT(*) AS count
            FROM zt_task t
            LEFT JOIN zt_pool p
              ON p.deleted = '0'
              AND p.type = 0
              AND p.pv_id = %s
              AND p.taskID = t.id
            WHERE t.deleted = '0'
              AND t.execution = %s
              AND t.parent <= 0
              AND t.status <> 'cancel'
              AND p.id IS NULL
            GROUP BY
              CASE
                WHEN t.source = 'customer' THEN 'version'
                WHEN t.source = 'operation' THEN 'operation'
                ELSE 'internal'
              END
            """,
            (version_id, version_id),
        )
        counts = {"version": 0, "operation": 0, "internal": 0}
        for row in [*pool_rows, *missing_task_rows]:
            category = str(row.get("category") or "")
            if category in counts:
                counts[category] += int(row.get("count") or 0)
        return {
            "ext_reqs": counts["version"] + counts["operation"],
            "int_reqs": counts["internal"],
            "version_reqs": counts["version"],
            "operation_reqs": counts["operation"],
            "total_reqs": counts["version"] + counts["operation"] + counts["internal"],
        }

    def get_version_adjusted_pool_items(self, version_id: int) -> list[dict[str, Any]]:
        version = self.db.fetch_one(
            """
            SELECT name
            FROM zt_project
            WHERE id = %s
            """,
            (version_id,),
        )
        version_token = ""
        if version:
            match = re.search(r"\d{4}", str(version.get("name") or ""))
            version_token = match.group(0) if match else ""
        adjust_filters = [
            "src.adjustLog LIKE '%%调下版本%%'",
        ]
        params: list[Any] = [version_id]
        if version_token:
            adjust_filters.extend(
                [
                    "src.adjustLog LIKE %s",
                    "src.adjustLog LIKE %s",
                ]
            )
            params.extend([f"%{version_token}调整成%", f"%{version_token}调整到%"])
        return self.db.fetch_all(
            f"""
            SELECT
              p.id AS pool_id,
              p.title,
              p.category,
              COALESCE(child.id, t.id, p.taskID) AS taskID,
              COALESCE(child.name, t.name, p.title) AS task_name,
              COALESCE(child.source, t.source, p.category) AS source,
              COALESCE(child.category, t.category, p.category) AS task_category,
              COALESCE(child.isSureStory, t.isSureStory) AS isSureStory,
              COALESCE(child.assignedTo, t.assignedTo) AS assignedTo,
              u.realname AS assignedName,
              au_dept.name AS assignedDeptName,
              COALESCE(child.openedDate, t.openedDate) AS openedDate,
              COALESCE(child.estStarted, t.estStarted) AS estStarted,
              COALESCE(child.status, t.status) AS task_status,
              COALESCE(child.deadline, t.deadline) AS deadline,
              COALESCE(child.finishedDate, t.finishedDate) AS finishedDate,
              COALESCE(child.finishedBy, t.finishedBy) AS finishedBy,
              fu.realname AS finishedName,
              fu_dept.name AS finishedDeptName,
              COALESCE(child.closedBy, t.closedBy) AS closedBy,
              cu.realname AS closedName,
              cu_dept.name AS closedDeptName,
              COALESCE(child.delayTimes, t.delayTimes) AS delayTimes,
              src.adjustLog,
              src.delayReason,
              src.delayMeasure
            FROM zt_pool p
            JOIN zt_pool src ON src.id = p.sourceId
            LEFT JOIN zt_task t ON t.id = p.taskID
            LEFT JOIN (
              SELECT parent, MIN(id) AS child_id
              FROM zt_task
              WHERE deleted = '0'
                AND name LIKE '【开发单】%%'
              GROUP BY parent
            ) dev_task ON dev_task.parent = t.id
            LEFT JOIN zt_task child ON child.id = dev_task.child_id
            LEFT JOIN zt_user u ON u.account = COALESCE(child.assignedTo, t.assignedTo)
            LEFT JOIN zt_dept au_dept ON au_dept.id = u.dept
            LEFT JOIN zt_user fu ON fu.account = COALESCE(child.finishedBy, t.finishedBy)
            LEFT JOIN zt_dept fu_dept ON fu_dept.id = fu.dept
            LEFT JOIN zt_user cu ON cu.account = COALESCE(child.closedBy, t.closedBy)
            LEFT JOIN zt_dept cu_dept ON cu_dept.id = cu.dept
            WHERE p.deleted = '0'
              AND p.type = 0
              AND p.pv_id = %s
              AND p.sourceId > 0
              AND ({" OR ".join(adjust_filters)})
            ORDER BY p.id
            """,
            tuple(params),
        )

    def find_departments(self, keyword: str, limit: int = 20) -> list[dict[str, Any]]:
        pattern = f"%{keyword}%"
        return self.db.fetch_all(
            """
            SELECT id, name, parent, path, manager
            FROM zt_dept
            WHERE name = %s OR name LIKE %s
            ORDER BY (name = %s) DESC, grade ASC, `order` ASC
            LIMIT %s
            """,
            (keyword, pattern, keyword, limit),
        )

    def get_dept_risk(self, dept_keyword: str, version_id: int, as_of: dt.date, limit: int = 80) -> dict[str, Any]:
        departments = self.find_departments(dept_keyword)
        dept_ids = [int(row["id"]) for row in departments]
        accounts: list[str] = []
        if dept_ids:
            placeholders = ",".join(["%s"] * len(dept_ids))
            users = self.db.fetch_all(
                f"""
                SELECT account, realname, dept
                FROM zt_user
                WHERE deleted = '0'
                  AND dept IN ({placeholders})
                ORDER BY realname
                """,
                tuple(dept_ids),
            )
            accounts = [row["account"] for row in users]
        else:
            users = []

        if accounts:
            account_placeholders = ",".join(["%s"] * len(accounts))
            task_filter = f"t.assignedTo IN ({account_placeholders})"
            task_params: list[Any] = [version_id, *accounts, limit]
            bug_filter = f"(b.assignedTo IN ({account_placeholders}) OR b.owner IN ({account_placeholders}) OR b.ownerDept LIKE %s OR b.type LIKE %s)"
            bug_params: list[Any] = [version_id, *accounts, *accounts, f"%{dept_keyword}%", f"%{dept_keyword}%", limit]
        else:
            task_filter = "d.name LIKE %s"
            task_params = [version_id, f"%{dept_keyword}%", limit]
            bug_filter = "(b.ownerDept LIKE %s OR b.type LIKE %s)"
            bug_params = [version_id, f"%{dept_keyword}%", f"%{dept_keyword}%", limit]

        tasks = self.db.fetch_all(
            f"""
            SELECT
              t.id,
              t.name,
              t.status,
              t.assignedTo,
              u.realname AS assignedName,
              d.name AS dept_name,
              t.deadline,
              t.left,
              IF(
                t.deadline IS NOT NULL
                  AND t.deadline NOT IN ('0000-00-00')
                  AND t.deadline < %s
                  AND t.status NOT IN ('done','closed','cancel'),
                DATEDIFF(%s, t.deadline),
                0
              ) AS overdue_days
            FROM zt_task t
            LEFT JOIN zt_user u ON u.account = t.assignedTo
            LEFT JOIN zt_dept d ON d.id = u.dept
            WHERE t.deleted = '0'
              AND t.execution = %s
              AND t.status NOT IN ('done','closed','cancel')
              AND {task_filter}
            ORDER BY overdue_days DESC, t.left DESC, t.deadline ASC
            LIMIT %s
            """,
            tuple([as_of, as_of] + task_params),
        )
        bugs = self.db.fetch_all(
            f"""
            SELECT
              b.id,
              b.title,
              b.status,
              b.severity,
              b.pri,
              b.assignedTo,
              au.realname AS assignedName,
              b.owner,
              ou.realname AS ownerName,
              b.ownerDept,
              COALESCE(od.name, NULLIF(b.ownerDept, ''), NULLIF(b.type, ''), '未填写') AS ownerDeptName,
              b.type,
              b.openedDate
            FROM zt_bug b
            LEFT JOIN zt_user au ON au.account = b.assignedTo
            LEFT JOIN zt_user ou ON ou.account = b.owner
            LEFT JOIN zt_dept od
              ON b.ownerDept REGEXP '^[0-9]+$'
              AND od.id = CAST(b.ownerDept AS UNSIGNED)
            WHERE b.deleted = '0'
              AND b.execution = %s
              AND b.status <> 'closed'
              AND {bug_filter}
            ORDER BY b.status = 'active' DESC, b.severity ASC, b.pri ASC, b.openedDate DESC
            LIMIT %s
            """,
            tuple(bug_params),
        )
        return {"departments": departments, "users": users, "tasks": tasks, "bugs": self._normalize_bug_owner_depts(bugs)}

    def get_weekly_report_data(
        self,
        version_id: int,
        start_date: dt.date,
        end_date: dt.date,
        as_of: dt.date,
    ) -> dict[str, Any]:
        task_summary = self.get_version_task_summary(version_id, as_of)
        bug_summary = self.get_bug_summary(version_id, as_of)
        weekly_task_flow = self.db.fetch_one(
            """
            SELECT
              SUM(IF(DATE(openedDate) BETWEEN %s AND %s, 1, 0)) AS opened,
              SUM(IF(DATE(finishedDate) BETWEEN %s AND %s, 1, 0)) AS finished,
              SUM(IF(DATE(closedDate) BETWEEN %s AND %s, 1, 0)) AS closed_count
            FROM zt_task
            WHERE deleted = '0'
              AND execution = %s
            """,
            (start_date, end_date, start_date, end_date, start_date, end_date, version_id),
        )
        weekly_bug_flow = self.db.fetch_one(
            """
            SELECT
              SUM(IF(DATE(openedDate) BETWEEN %s AND %s, 1, 0)) AS opened,
              SUM(IF(DATE(resolvedDate) BETWEEN %s AND %s, 1, 0)) AS resolved,
              SUM(IF(DATE(closedDate) BETWEEN %s AND %s, 1, 0)) AS closed_count
            FROM zt_bug
            WHERE deleted = '0'
              AND execution = %s
            """,
            (start_date, end_date, start_date, end_date, start_date, end_date, version_id),
        )
        overdue = self.get_overdue_open_tasks(version_id, as_of)
        active_bugs = self.get_active_bugs(version_id)
        todos = self.get_todos("unfinished")
        return {
            "task_summary": task_summary,
            "bug_summary": bug_summary,
            "weekly_task_flow": weekly_task_flow or {},
            "weekly_bug_flow": weekly_bug_flow or {},
            "overdue_open": overdue,
            "active_bugs": active_bugs,
            "unfinished_todos": todos,
        }
