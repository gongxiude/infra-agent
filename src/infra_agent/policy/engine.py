# -*- coding: utf-8 -*-

"""最小策略引擎。"""

from __future__ import annotations

from infra_agent.core.models import AgentTask, PolicyDecision, TaskType
from infra_agent.core.settings import AppSettings


class PolicyEngine:
    """根据任务生成最小策略决策。"""

    def __init__(self, settings: AppSettings) -> None:
        """初始化策略引擎。"""

        self._settings = settings

    def evaluate(self, task: AgentTask) -> PolicyDecision:
        """评估任务。"""

        decision = PolicyDecision()
        if task.type in {
            TaskType.JENKINS_PIPELINE_CHANGE,
            TaskType.SHARED_LIBRARY_CHANGE,
            TaskType.GITOPS_REPOSITORY_CHANGE,
        }:
            decision.allowed_tools = ["inspect_workspace", "read_file", "write_file", "git_status", "git_diff"]
            decision.skill_slugs = ["git-operations"]
        else:
            decision.allowed_tools = ["inspect_workspace", "read_file"]
        return decision
