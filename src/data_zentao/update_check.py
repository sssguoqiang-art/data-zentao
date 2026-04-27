from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from typing import Any


SKIP_ENV = "DATA_ZENTAO_SKIP_UPDATE_CHECK"


def _run_git(repo_root: Path, args: list[str], timeout: float = 8.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _repo_root() -> Path | None:
    candidate = Path(__file__).resolve().parents[2]
    try:
        result = _run_git(candidate, ["rev-parse", "--show-toplevel"], timeout=3.0)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip())


def _remote_ref(repo_root: Path) -> str | None:
    upstream = _run_git(repo_root, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], timeout=3.0)
    if upstream.returncode == 0 and upstream.stdout.strip():
        return upstream.stdout.strip()
    fallback = _run_git(repo_root, ["rev-parse", "--verify", "--quiet", "origin/main"], timeout=3.0)
    if fallback.returncode == 0:
        return "origin/main"
    return None


def check_update(fetch: bool = True) -> dict[str, Any]:
    repo_root = _repo_root()
    if not repo_root:
        return {"ok": False, "checked": False, "reason": "not_git_repo"}

    remotes = _run_git(repo_root, ["remote"], timeout=3.0)
    if remotes.returncode != 0 or "origin" not in remotes.stdout.splitlines():
        return {"ok": False, "checked": False, "reason": "no_origin", "repo_root": str(repo_root)}

    if fetch:
        try:
            _run_git(repo_root, ["fetch", "--quiet", "origin"], timeout=10.0)
        except subprocess.TimeoutExpired:
            return {"ok": False, "checked": False, "reason": "fetch_timeout", "repo_root": str(repo_root)}

    remote_ref = _remote_ref(repo_root)
    if not remote_ref:
        return {"ok": False, "checked": False, "reason": "no_upstream", "repo_root": str(repo_root)}

    local = _run_git(repo_root, ["rev-parse", "--short", "HEAD"], timeout=3.0)
    remote = _run_git(repo_root, ["rev-parse", "--short", remote_ref], timeout=3.0)
    counts = _run_git(repo_root, ["rev-list", "--left-right", "--count", f"HEAD...{remote_ref}"], timeout=3.0)
    dirty = _run_git(repo_root, ["status", "--porcelain"], timeout=3.0)
    if local.returncode != 0 or remote.returncode != 0 or counts.returncode != 0:
        return {"ok": False, "checked": False, "reason": "git_error", "repo_root": str(repo_root)}

    ahead_text, behind_text = (counts.stdout.strip().split() + ["0", "0"])[:2]
    ahead = int(ahead_text)
    behind = int(behind_text)
    return {
        "ok": True,
        "checked": True,
        "repo_root": str(repo_root),
        "remote_ref": remote_ref,
        "local": local.stdout.strip(),
        "remote": remote.stdout.strip(),
        "ahead": ahead,
        "behind": behind,
        "dirty": bool(dirty.stdout.strip()),
        "update_available": behind > 0,
    }


def update_notice(data: dict[str, Any]) -> str | None:
    if not data.get("update_available"):
        return None
    repo_root = data.get("repo_root") or "data-zentao"
    command = f"cd {repo_root!r} && git pull --ff-only && pip install -e ."
    dirty_note = "当前本地有未提交改动，更新前建议先让 AI 帮你确认这些改动是否需要保留。\n" if data.get("dirty") else ""
    return (
        "\n[data-zentao 更新提醒]\n"
        f"远端 {data.get('remote_ref')} 有新版本：本地 {data.get('local')}，远端 {data.get('remote')}，落后 {data.get('behind')} 个提交。\n"
        f"{dirty_note}"
        "建议先确认是否更新；确认后执行：\n"
        f"{command}\n"
        f"如果本次暂不检查，可设置：{SKIP_ENV}=1\n"
    )


def maybe_print_update_notice() -> None:
    if os.getenv(SKIP_ENV) == "1":
        return
    try:
        notice = update_notice(check_update(fetch=True))
    except Exception:
        return
    if notice:
        print(notice, file=sys.stderr)
