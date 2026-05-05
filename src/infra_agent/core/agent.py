# -*- coding: utf-8 -*-

"""核心 Agent 封装，使用 OpenAI Agents SDK。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from agents import Agent, ModelSettings, Runner, set_default_openai_key

from infra_agent.core.models import AgentTask, PolicyDecision
from infra_agent.core.prompts import SYSTEM_PROMPT, build_task_prompt
from infra_agent.core.settings import AppSettings
from infra_agent.guardrails.policy_guardrail import policy_input_guardrail
from infra_agent.skills.loader import build_skills_prompt
from infra_agent.tools import get_tools_for_policy
from infra_agent.tools.context import AgentContext


@dataclass(slots=True)
class InfraAgent:
    """基于 OpenAI Agents SDK 的 Infra Agent 运行时。"""

    settings: AppSettings
    system_prompt: str = SYSTEM_PROMPT
    _skills_dir: Path = field(default_factory=lambda: Path("skills"))

    async def run(self, task: AgentTask, policy: PolicyDecision | None = None) -> dict:
        """执行单个任务。

        Args:
            task: 标准任务对象
            policy: 策略决策，为 None 时使用默认值（无工具）
        """

        policy = policy or PolicyDecision()

        # 设置 API key
        if self.settings.openai_api_key:
            set_default_openai_key(self.settings.openai_api_key)

        # 构建工具列表（根据策略过滤）
        tools = get_tools_for_policy(policy)

        # 构建 skills 指令
        skills_prompt = build_skills_prompt(self._skills_dir, policy.skill_slugs)

        # 拼接完整 instructions
        instructions = self.system_prompt
        if skills_prompt:
            instructions += "\n\n" + skills_prompt

        # 构建运行上下文
        context = AgentContext(
            workspace_root=Path(self.settings.git.workspace_root),
            policy=policy,
            task=task,
        )

        # 构建 SDK Agent
        agent = Agent[AgentContext](
            name="infra-agent",
            instructions=instructions,
            tools=tools,
            model=self.settings.runtime.model,
            model_settings=ModelSettings(temperature=0.1),
            input_guardrails=[policy_input_guardrail],
        )

        # 构建用户输入
        user_input = build_task_prompt(task)

        # 执行
        result = await Runner.run(
            agent,
            input=user_input,
            context=context,
            max_turns=policy.max_iterations,
        )

        return {
            "system_prompt": instructions,
            "task_prompt": user_input,
            "final_output": result.final_output,
        }


def create_infra_agent(settings: AppSettings | None = None) -> InfraAgent:
    """创建 Infra Agent。"""

    return InfraAgent(settings=settings or AppSettings.from_env())
