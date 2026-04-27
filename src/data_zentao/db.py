from __future__ import annotations

from contextlib import contextmanager
import re
from typing import Any, Iterator, Sequence

import pymysql
from pymysql.cursors import DictCursor

from .config import DbConfig


class ReadOnlyDatabase:
    """Small read-only query wrapper.

    The public API intentionally exposes only fetch methods. First versions of
    this project should not execute user-provided SQL or any write statements.
    """

    def __init__(self, config: DbConfig):
        self.config = config

    @contextmanager
    def connect(self) -> Iterator[pymysql.connections.Connection]:
        conn = pymysql.connect(
            host=self.config.host,
            port=self.config.port,
            user=self.config.user,
            password=self.config.password,
            database=self.config.database,
            charset=self.config.charset,
            cursorclass=DictCursor,
            autocommit=True,
            connect_timeout=10,
            read_timeout=30,
        )
        try:
            yield conn
        finally:
            conn.close()

    def fetch_all(self, sql: str, params: Sequence[Any] | None = None) -> list[dict[str, Any]]:
        self._assert_read_only(sql)
        with self.connect() as conn:
            with conn.cursor() as cur:
                if params is None:
                    cur.execute(sql)
                else:
                    cur.execute(sql, params)
                return list(cur.fetchall())

    def fetch_one(self, sql: str, params: Sequence[Any] | None = None) -> dict[str, Any] | None:
        rows = self.fetch_all(sql, params)
        return rows[0] if rows else None

    def fetch_many(
        self,
        sql: str,
        params: Sequence[Any] | None = None,
        *,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        self._assert_read_only(sql)
        with self.connect() as conn:
            with conn.cursor() as cur:
                if params is None:
                    cur.execute(sql)
                else:
                    cur.execute(sql, params)
                return list(cur.fetchmany(limit))

    @staticmethod
    def _assert_read_only(sql: str) -> None:
        normalized = sql.strip().lower()
        allowed = ("select", "show", "with", "describe", "desc", "explain")
        if not normalized.startswith(allowed):
            raise ValueError("只允许执行只读查询。")

        if ";" in normalized.rstrip(";"):
            raise ValueError("不允许执行多条 SQL。")

        forbidden = [
            "alter",
            "call",
            "create",
            "delete",
            "drop",
            "grant",
            "insert",
            "load",
            "lock",
            "revoke",
            "set",
            "truncate",
            "unlock",
            "update",
        ]
        for word in forbidden:
            if re.search(rf"\b{word}\b", normalized):
                raise ValueError(f"只读模式禁止执行包含 {word.upper()} 的 SQL。")
        if re.search(r"\binto\s+(out|dump)?file\b", normalized):
            raise ValueError("只读模式禁止导出文件。")
