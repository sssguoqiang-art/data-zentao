from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal
from typing import Any, Iterable


def as_date(value: str | dt.date | None) -> dt.date:
    if value is None:
        return dt.date.today()
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(value)


def serialize(value: Any) -> Any:
    if isinstance(value, dt.datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    return value


def to_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, default=serialize)


def md_table(headers: list[str], rows: Iterable[Iterable[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        cells = [str(serialize(cell) if cell is not None else "") for cell in row]
        cells = [cell.replace("\n", "<br>").replace("|", "\\|") for cell in cells]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def rows_to_md(rows: list[dict[str, Any]], *, empty_text: str = "没有查到数据。") -> str:
    if not rows:
        return empty_text
    headers = list(rows[0].keys())
    return md_table(headers, ([row.get(header) for header in headers] for row in rows))


def trim_text(value: Any, limit: int = 80) -> str:
    if value is None:
        return ""
    text = str(value).strip().replace("\n", " ")
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"
