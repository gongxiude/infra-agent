# -*- coding: utf-8 -*-

"""核心 Agent 封装，使用 triage + subagent handoff 架构。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from agents import Runner, set_default_openai_key, set_tracing_disabled
from openai import AsyncOpenAI

from infra_agent.agents.loader import build_triage_agent
from infra_agent.core.models import AgentTask, PolicyDecision
from infra_agent.core.prompts import build_task_prompt
from infra_agent.core.settings import AppSettings
from infra_agent.observability.hooks import LoggingHooks
from infra_agent.tools.context import AgentContext


@dataclass(slots=True)
class InfraAgent:
    """基于 triage + subagent handoff 的 Infra Agent 运行时。"""

    settings: AppSettings
    _agents_dir: Path = field(default_factory=lambda: Path("agents"))
    _skills_dir: Path = field(default_factory=lambda: Path("skills"))
    _triage_agent: object | None = field(default=None, init=False, repr=False)
    _model_provider: object | None = field(default=None, init=False, repr=False)

    def _ensure_triage_agent(self):
        """懒构建 triage agent。"""

        if self._triage_agent is not None:
            return self._triage_agent

        if self.settings.openai_api_key:
            set_default_openai_key(self.settings.openai_api_key)

        # 禁用 tracing（避免国内网络环境下 timeout 警告）
        set_tracing_disabled(True)

        # 如果配置了自定义 base_url，创建自定义 model provider
        if self.settings.openai_base_url:
            from agents import OpenAIResponsesModel

            client = AsyncOpenAI(
                api_key=self.settings.openai_api_key,
                base_url=self.settings.openai_base_url,
            )
            self._model_provider = OpenAIResponsesModel(
                model=self.settings.runtime.model,
                openai_client=client,
            )

        self._triage_agent = build_triage_agent(
            agents_dir=self._agents_dir,
            skills_dir=self._skills_dir,
            model=self._model_provider or self.settings.runtime.model,
        )
        return self._triage_agent

    async def run(self, task: AgentTask) -> dict:
        """执行任务，由 triage agent 路由到合适的子代理。

        Args:
            task: 标准任务对象
        """

        triage = self._ensure_triage_agent()

        # 构建运行上下文
        context = AgentContext(
            workspace_root=Path(self.settings.git.workspace_root),
            policy=PolicyDecision(),
            task=task,
            skills_dir=self._skills_dir,
            allowed_skills=[],
            remote_repositories=self.settings.git.remote_repositories,
        )

        # 构建用户输入
        user_input = build_task_prompt(task)

        # 执行（SDK 自动处理 handoff）
        result = await Runner.run(
            triage,
            input=user_input,
            context=context,
            hooks=LoggingHooks(),
        )

        return {
            "task_prompt": user_input,
            "final_output": result.final_output,
        }


def create_infra_agent(settings: AppSettings | None = None) -> InfraAgent:
    """创建 Infra Agent。"""

    return InfraAgent(settings=settings or AppSettings.from_env())
