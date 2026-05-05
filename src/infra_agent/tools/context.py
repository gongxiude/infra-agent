# -*- coding: utf-8 -*-

"""Agent 运行上下文。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from infra_agent.core.models import AgentTask, PolicyDecision


@dataclass
class AgentContext:
    """工具函数通过 RunContextWrapper[AgentContext] 访问的运行时上下文。"""

    workspace_root: Path
    policy: PolicyDecision
    task: AgentTask
