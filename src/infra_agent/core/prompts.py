# -*- coding: utf-8 -*-

"""默认提示词。"""

from __future__ import annotations

from pathlib import Path

from infra_agent.core.models import AgentTask

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def _read_prompt(name: str) -> str:
    """读取提示词文件。"""

    return (PROMPTS_DIR / name).read_text(encoding="utf-8").strip()


SYSTEM_PROMPT = _read_prompt("system_prompt.txt")


def build_task_prompt(task: AgentTask) -> str:
    """构建任务提示词。"""

    return "\n".join(
        [
            f"任务类型: {task.type.value}",
            f"入口来源: {task.trigger.source.value}",
            f"仓库别名: {task.context.repository_alias or '未指定'}",
            f"优先级: {task.context.priority.value}",
            f"任务载荷: {task.payload}",
        ]
    )
