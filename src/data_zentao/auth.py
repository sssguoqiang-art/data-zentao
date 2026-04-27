from __future__ import annotations

import datetime as dt
import getpass
import hashlib
import hmac
import json
from pathlib import Path
import os

from .config import load_env


AUTH_HASH_ENV = "DATA_ZENTAO_START_PASSWORD_SHA256"
AUTH_HOME = Path.home() / ".data-zentao"
AUTH_FILE = AUTH_HOME / "auth.json"


def configured_password_hash() -> str | None:
    load_env()
    value = os.getenv(AUTH_HASH_ENV, "").strip().lower()
    return value or None


def is_auth_enabled() -> bool:
    return configured_password_hash() is not None


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def is_unlocked() -> bool:
    expected = configured_password_hash()
    if not expected:
        return True
    try:
        data = json.loads(AUTH_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return False
    return hmac.compare_digest(str(data.get("password_hash", "")).lower(), expected)


def unlock_with_password(password: str) -> bool:
    expected = configured_password_hash()
    if not expected:
        return True
    if not hmac.compare_digest(hash_password(password), expected):
        return False
    AUTH_HOME.mkdir(parents=True, exist_ok=True)
    AUTH_FILE.write_text(
        json.dumps(
            {
                "password_hash": expected,
                "unlocked_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    AUTH_FILE.chmod(0o600)
    return True


def prompt_unlock() -> bool:
    password = getpass.getpass("请输入 data-zentao 启动密码：")
    return unlock_with_password(password)


def lock() -> None:
    try:
        AUTH_FILE.unlink()
    except FileNotFoundError:
        return


def status() -> dict[str, object]:
    return {
        "enabled": is_auth_enabled(),
        "unlocked": is_unlocked(),
        "auth_file": str(AUTH_FILE),
    }


def ensure_unlocked() -> None:
    if not is_auth_enabled():
        return
    if is_unlocked():
        return
    print("首次使用 data-zentao 需要输入启动密码完成本机解锁。", flush=True)
    if prompt_unlock():
        print("data-zentao 已解锁。")
        return
    raise RuntimeError("启动密码不正确。")
