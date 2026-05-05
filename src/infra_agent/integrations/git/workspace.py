# -*- coding: utf-8 -*-

"""Git workspace 管理。"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from infra_agent.core.settings import GitSettings

logger = logging.getLogger(__name__)

# git 操作超时（秒）
_GIT_TIMEOUT = 120


class GitWorkspaceManager:
    """管理本地仓库工作区。"""

    def __init__(self, settings: GitSettings) -> None:
        """初始化工作区管理器。"""

        self._settings = settings

    def ensure_workspace(self, repository_alias: str) -> dict[str, str | bool]:
        """确保本地工作区存在。"""

        workspace_root = Path(self._settings.workspace_root)
        workspace_root.mkdir(parents=True, exist_ok=True)
        workspace_path = workspace_root / repository_alias
        existed = workspace_path.exists()
        workspace_path.mkdir(parents=True, exist_ok=True)
        remote_url = self._settings.remote_repositories.get(repository_alias, "")

        # 若配置了远程仓库且目录还不是 git repo，尝试 clone
        if remote_url and not (workspace_path / ".git").exists():
            try:
                self._clone_sync(remote_url, workspace_path)
                existed = False
            except Exception:
                logger.warning("git clone 失败: %s -> %s", remote_url, workspace_path, exc_info=True)

        return {
            "repository_alias": repository_alias,
            "remote_url": remote_url,
            "workspace_path": str(workspace_path),
            "existed": existed,
        }

    async def clone_if_needed(self, repository_alias: str) -> Path:
        """异步确保 workspace 已 clone。

        Args:
            repository_alias: 仓库别名

        Returns:
            workspace 路径。
        """

        workspace_root = Path(self._settings.workspace_root)
        workspace_path = workspace_root / repository_alias
        workspace_path.mkdir(parents=True, exist_ok=True)
        remote_url = self._settings.remote_repositories.get(repository_alias, "")

        if remote_url and not (workspace_path / ".git").exists():
            await self._clone_async(remote_url, workspace_path)

        return workspace_path

    def _clone_sync(self, remote_url: str, target: Path) -> None:
        """同步执行 git clone。"""

        import subprocess

        result = subprocess.run(
            ["git", "clone", remote_url, str(target)],
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
        )
        if result.returncode != 0:
            raise RuntimeError(f"git clone 失败: {result.stderr.strip()}")
        logger.info("已 clone %s -> %s", remote_url, target)

    async def _clone_async(self, remote_url: str, target: Path) -> None:
        """异步执行 git clone。"""

        proc = await asyncio.create_subprocess_exec(
            "git", "clone", remote_url, str(target),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=_GIT_TIMEOUT)
        if proc.returncode != 0:
            raise RuntimeError(f"git clone 失败: {stderr.decode().strip()}")
        logger.info("已 clone %s -> %s", remote_url, target)
