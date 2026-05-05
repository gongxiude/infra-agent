# -*- coding: utf-8 -*-

"""核心 Agent 封装，使用 triage + subagent handoff 架构。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from agents import Runner, set_default_openai_key

from infra_agent.agents.loader import build_triage_agent
from infra_agent.core.models import AgentTask, PolicyDecision
from infra_agent.core.prompts import build_task_prompt
from infra_agent.core.settings import AppSettings
from infra_agent.tools.context import AgentContext


@dataclass(slots=True)
class InfraAgent:
    """基于 triage + subagent handoff 的 Infra Agent 运行时。"""

    settings: AppSettings
    _agents_dir: Path = field(default_factory=lambda: Path("agents"))
    _skills_dir: Path = field(default_factory=lambda: Path("skills"))
    _triage_agent: object | None = field(default=None, init=False, repr=False)

    def _ensure_triage_agent(self):
        """懒构建 triage agent。"""

        if self._triage_agent is not None:
            return self._triage_agent

        if self.settings.openai_api_key:
            set_default_openai_key(self.settings.openai_api_key)

        self._triage_agent = build_triage_agent(
            agents_dir=self._agents_dir,
            skills_dir=self._skills_dir,
            model=self.settings.runtime.model,
        )
        return self._triage_agent

    async def run(self, task: AgentTask) -> dict:
        """执行任务，由 triage agent 路由到合适的子代理。

        Args:
            task: 标准任务对象
        """

        triage = self._ensure_triage_agent()

        # 构建运行上下文（triage 层级使用默认策略，子代理策略由 AGENT.md 定义）
        context = AgentContext(
            workspace_root=Path(self.settings.git.workspace_root),
            policy=PolicyDecision(),
            task=task,
            skills_dir=self._skills_dir,
            allowed_skills=[],
        )

        # 构建用户输入
        user_input = build_task_prompt(task)

        # 执行（SDK 自动处理 handoff）
        result = await Runner.run(
            triage,
            input=user_input,
            context=context,
        )

        return {
            "task_prompt": user_input,
            "final_output": result.final_output,
        }


def create_infra_agent(settings: AppSettings | None = None) -> InfraAgent:
    """创建 Infra Agent。"""

    return InfraAgent(settings=settings or AppSettings.from_env())
