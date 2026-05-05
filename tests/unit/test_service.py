# -*- coding: utf-8 -*-

"""服务闭环测试。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from unittest.mock import AsyncMock, patch

from infra_agent.core.agent import create_infra_agent
from infra_agent.core.models import TaskContext
from infra_agent.core.service import InfraAgentService
from infra_agent.core.settings import AppSettings
from infra_agent.execution.queue import InMemoryDispatchQueue
from infra_agent.ingestion.router import SignalRouter
from infra_agent.integrations.git.workspace import GitWorkspaceManager
from infra_agent.observability.store import InMemoryStore


@dataclass
class _MockRunResult:
    """模拟 Runner.run() 返回值。"""

    final_output: str = "测试输出: 分析完成。"


def test_service_submit_and_run_once() -> None:
    """服务应能完成一次提交和执行。"""

    settings = AppSettings.from_env()
    service = InfraAgentService(
        signal_router=SignalRouter(),
        queue=InMemoryDispatchQueue(),
        store=InMemoryStore(),
        agent=create_infra_agent(settings),
        workspace_manager=GitWorkspaceManager(settings.git),
    )

    async def _run() -> dict | None:
        task = service.signal_router.from_user_chat(
            source_id="cli-local",
            payload={"message": "请分析 shared library 的失败原因"},
            context=TaskContext(),
        )
        await service.submit_task(task)
        with patch("agents.Runner.run", new_callable=AsyncMock, return_value=_MockRunResult()):
            return await service.run_once()

    result = asyncio.run(_run())
    assert result is not None
    assert "final_output" in result
    assert result["final_output"] == "测试输出: 分析完成。"
