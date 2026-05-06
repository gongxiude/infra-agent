# -*- coding: utf-8 -*-

"""Agent 运行时日志 hooks。"""

from __future__ import annotations

import logging
import time
from typing import Any

from agents import Agent, RunContextWrapper, RunHooks, Tool

from infra_agent.tools.context import AgentContext

logger = logging.getLogger("infra_agent.runtime")


class LoggingHooks(RunHooks[AgentContext]):
    """记录 agent 执行过程的关键事件。"""

    def __init__(self) -> None:
        self._start_time: float = 0

    async def on_agent_start(
        self, context: RunContextWrapper[AgentContext], agent: Agent[AgentContext]
    ) -> None:
        """agent 开始执行。"""
        self._start_time = time.time()
        logger.info("[agent:start] %s", agent.name)

    async def on_agent_end(
        self, context: RunContextWrapper[AgentContext], agent: Agent[AgentContext], output: Any
    ) -> None:
        """agent 执行结束。"""
        elapsed = time.time() - self._start_time
        output_preview = str(output)[:100] if output else "(empty)"
        logger.info("[agent:end] %s (%.1fs) output=%s", agent.name, elapsed, output_preview)

    async def on_handoff(
        self,
        context: RunContextWrapper[AgentContext],
        from_agent: Agent[AgentContext],
        to_agent: Agent[AgentContext],
    ) -> None:
        """agent 之间的 handoff。"""
        logger.info("[handoff] %s → %s", from_agent.name, to_agent.name)

    async def on_tool_start(
        self,
        context: RunContextWrapper[AgentContext],
        agent: Agent[AgentContext],
        tool: Tool,
    ) -> None:
        """工具调用开始。"""
        logger.info("[tool:start] %s.%s", agent.name, tool.name)

    async def on_tool_end(
        self,
        context: RunContextWrapper[AgentContext],
        agent: Agent[AgentContext],
        tool: Tool,
        result: str,
    ) -> None:
        """工具调用结束。"""
        result_preview = result[:150] if result else "(empty)"
        logger.info("[tool:end] %s.%s → %s", agent.name, tool.name, result_preview)
