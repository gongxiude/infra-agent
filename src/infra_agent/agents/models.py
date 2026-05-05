# -*- coding: utf-8 -*-

"""子代理与技能的声明式模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AgentDefinition(BaseModel):
    """AGENT.md 解析后的子代理定义。"""

    name: str
    description: str = ""
    tools: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    tier: int = 0
    max_iterations: int = 10
    timeout_seconds: int = 900
    repository_alias: str | None = None
    requires_pr: bool = False
    instructions: str = ""


class SkillMeta(BaseModel):
    """SKILL.md frontmatter 中的轻量元数据。"""

    name: str
    description: str = ""
