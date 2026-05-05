# -*- coding: utf-8 -*-

"""Workspace 工具函数，使用 OpenAI Agents SDK @function_tool 注册。"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from agents import RunContextWrapper, function_tool

from infra_agent.tools.context import AgentContext

# 子进程执行超时（秒）
_SUBPROCESS_TIMEOUT = 30


def _resolve_workspace(ctx: RunContextWrapper[AgentContext], repository_alias: str) -> Path:
    """解析并验证 workspace 路径。"""

    workspace = ctx.context.workspace_root / repository_alias
    if not workspace.exists():
        raise FileNotFoundError(f"workspace 不存在: {workspace}")
    return workspace


def _safe_resolve(workspace: Path, file_path: str) -> Path:
    """解析文件路径并防止路径遍历。"""

    resolved = (workspace / file_path).resolve()
    if not resolved.is_relative_to(workspace.resolve()):
        raise PermissionError(f"路径遍历被拒绝: {file_path}")
    return resolved


async def _run_git(workspace: Path, *args: str) -> str:
    """在 workspace 中执行 git 命令。"""

    proc = await asyncio.create_subprocess_exec(
        "git", *args,
        cwd=str(workspace),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=_SUBPROCESS_TIMEOUT)
    if proc.returncode != 0:
        return f"git 命令失败 (exit {proc.returncode}):\n{stderr.decode().strip()}"
    return stdout.decode().strip()


@function_tool
async def inspect_workspace(
    ctx: RunContextWrapper[AgentContext],
    repository_alias: str,
) -> str:
    """列出 workspace 目录结构（最多两层）。

    Args:
        repository_alias: 仓库别名
    """

    workspace = _resolve_workspace(ctx, repository_alias)
    entries: list[str] = []
    for item in sorted(workspace.iterdir()):
        prefix = "d " if item.is_dir() else "f "
        entries.append(prefix + item.name)
        # 展开一层子目录
        if item.is_dir() and not item.name.startswith("."):
            try:
                for sub in sorted(item.iterdir()):
                    sub_prefix = "  d " if sub.is_dir() else "  f "
                    entries.append(sub_prefix + sub.name)
            except PermissionError:
                entries.append("  (权限不足)")
    return "\n".join(entries) if entries else "(空目录)"


@function_tool
async def read_file(
    ctx: RunContextWrapper[AgentContext],
    repository_alias: str,
    file_path: str,
) -> str:
    """读取 workspace 内的文件内容。

    Args:
        repository_alias: 仓库别名
        file_path: 相对于 workspace 的文件路径
    """

    workspace = _resolve_workspace(ctx, repository_alias)
    resolved = _safe_resolve(workspace, file_path)
    if not resolved.is_file():
        return f"文件不存在: {file_path}"
    content = resolved.read_text(encoding="utf-8", errors="replace")
    # 截断超大文件
    max_chars = 50_000
    if len(content) > max_chars:
        content = content[:max_chars] + f"\n\n... (已截断，总计 {len(content)} 字符)"
    return content


@function_tool
async def write_file(
    ctx: RunContextWrapper[AgentContext],
    repository_alias: str,
    file_path: str,
    content: str,
) -> str:
    """向 workspace 内的文件写入内容。

    Args:
        repository_alias: 仓库别名
        file_path: 相对于 workspace 的文件路径
        content: 要写入的内容
    """

    workspace = _resolve_workspace(ctx, repository_alias)
    resolved = _safe_resolve(workspace, file_path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(content, encoding="utf-8")
    return f"已写入 {file_path} ({len(content)} 字符)"


@function_tool
async def git_status(
    ctx: RunContextWrapper[AgentContext],
    repository_alias: str,
) -> str:
    """执行 git status 查看工作区状态。

    Args:
        repository_alias: 仓库别名
    """

    workspace = _resolve_workspace(ctx, repository_alias)
    return await _run_git(workspace, "status", "--porcelain")


@function_tool
async def git_diff(
    ctx: RunContextWrapper[AgentContext],
    repository_alias: str,
) -> str:
    """执行 git diff 查看工作区变更。

    Args:
        repository_alias: 仓库别名
    """

    workspace = _resolve_workspace(ctx, repository_alias)
    output = await _run_git(workspace, "diff")
    # 截断超大 diff
    max_chars = 30_000
    if len(output) > max_chars:
        output = output[:max_chars] + f"\n\n... (diff 已截断，总计 {len(output)} 字符)"
    return output
