# -*- coding: utf-8 -*-

"""Agent 运行上下文。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from infra_agent.core.models import AgentTask, PolicyDecision


@dataclass
class AgentContext:
    """工具函数通过 RunContextWrapper[AgentContext] 访问的运行时上下文。"""

    workspace_root: Path
    policy: PolicyDecision
    task: AgentTask
    skills_dir: Path = field(default_factory=lambda: Path("skills"))
    allowed_skills: list[str] = field(default_factory=list)
    remote_repositories: dict[str, str] = field(default_factory=dict)
