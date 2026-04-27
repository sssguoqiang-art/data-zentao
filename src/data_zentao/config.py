from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def load_env() -> None:
    """Load .env from the current project or parent working directory."""
    cwd = Path.cwd()
    for path in [cwd / ".env", *cwd.parents]:
        env_path = path if path.name == ".env" else path / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            return
    load_dotenv()


@dataclass(frozen=True)
class DbConfig:
    host: str
    port: int
    user: str
    password: str
    database: str = "zentao"
    charset: str = "utf8mb4"

    @classmethod
    def from_env(cls) -> "DbConfig":
        load_env()
        missing = [
            name
            for name in ["ZENTAO_DB_HOST", "ZENTAO_DB_USER", "ZENTAO_DB_PASSWORD"]
            if not os.getenv(name)
        ]
        if missing:
            names = ", ".join(missing)
            raise RuntimeError(f"缺少数据库配置：{names}。请先运行 data-zentao setup 完成本机初始化。")
        return cls(
            host=os.environ["ZENTAO_DB_HOST"],
            port=int(os.getenv("ZENTAO_DB_PORT", "3306")),
            user=os.environ["ZENTAO_DB_USER"],
            password=os.environ["ZENTAO_DB_PASSWORD"],
            database=os.getenv("ZENTAO_DB_NAME", "zentao"),
        )


@dataclass(frozen=True)
class AppConfig:
    db: DbConfig
    platform_product_name: str = "平台部"
    platform_project_name: str = "平台部"

    @classmethod
    def from_env(cls) -> "AppConfig":
        load_env()
        return cls(
            db=DbConfig.from_env(),
            platform_product_name=os.getenv("ZENTAO_PLATFORM_PRODUCT_NAME", "平台部"),
            platform_project_name=os.getenv("ZENTAO_PLATFORM_PROJECT_NAME", "平台部"),
        )
