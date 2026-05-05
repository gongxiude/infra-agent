# -*- coding: utf-8 -*-

"""策略引擎（从 AGENT.md frontmatter 生成 PolicyDecision）。"""

from __future__ import annotations

from infra_agent.agents.models import AgentDefinition
from infra_agent.core.models import PolicyDecision


def policy_from_definition(defn: AgentDefinition) -> PolicyDecision:
    """从 AgentDefinition 生成 PolicyDecision。

    Args:
        defn: 子代理定义

    Returns:
        对应的策略决策。
    """

    return PolicyDecision(
        tier=defn.tier,
        max_iterations=defn.max_iterations,
        timeout_seconds=defn.timeout_seconds,
        allowed_tools=defn.tools,
        skill_slugs=defn.skills,
        requires_pr=defn.requires_pr,
    )
