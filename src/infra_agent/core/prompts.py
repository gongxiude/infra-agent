# -*- coding: utf-8 -*-

"""任务提示词构建。"""

from __future__ import annotations

from infra_agent.core.models import AgentTask


def build_task_prompt(task: AgentTask) -> str:
    """构建用户输入提示词。

    Args:
        task: 标准任务对象
    """

    parts = []

    # 用户消息是最重要的内容
    message = task.payload.get("message", "")
    if message:
        parts.append(message)

    # 附加上下文元数据
    meta: list[str] = []
    if task.context.repository_alias:
        meta.append(f"仓库: {task.context.repository_alias}")
    if task.context.priority.value != "normal":
        meta.append(f"优先级: {task.context.priority.value}")
    if task.trigger.source.value != "user":
        meta.append(f"来源: {task.trigger.source.value}")

    if meta:
        parts.append("\n[上下文: " + ", ".join(meta) + "]")

    # 如果没有消息，回退到 payload 摘要
    if not message:
        parts.append(f"任务载荷: {task.payload}")

    return "\n".join(parts)
