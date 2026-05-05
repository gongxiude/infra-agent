# -*- coding: utf-8 -*-

"""应用服务编排。"""

from __future__ import annotations

from infra_agent.core.agent import InfraAgent
from infra_agent.core.models import AgentTask, TaskEvent, TaskRecord
from infra_agent.execution.queue import InMemoryDispatchQueue
from infra_agent.ingestion.router import SignalRouter
from infra_agent.integrations.git.workspace import GitWorkspaceManager
from infra_agent.observability.store import InMemoryStore


class InfraAgentService:
    """最小闭环服务。"""

    def __init__(
        self,
        signal_router: SignalRouter,
        queue: InMemoryDispatchQueue,
        store: InMemoryStore,
        agent: InfraAgent,
        workspace_manager: GitWorkspaceManager,
    ) -> None:
        """初始化服务。"""

        self.signal_router = signal_router
        self.queue = queue
        self.store = store
        self.agent = agent
        self.workspace_manager = workspace_manager

    async def submit_task(self, task: AgentTask) -> None:
        """提交任务。"""

        record = TaskRecord(
            id=task.id,
            type=task.type,
            source=task.trigger.source.value,
            status="dispatched",
            repository_alias=task.context.repository_alias,
            priority=task.context.priority.value,
            payload=task.payload,
        )
        await self.store.save_task(record)
        await self.store.append_event(
            TaskEvent(task_id=task.id, event_type="task_dispatched", message="任务已入队。")
        )
        await self.queue.enqueue(task)

    async def run_once(self) -> dict | None:
        """执行单个任务。"""

        task = await self.queue.dequeue()
        if task is None:
            return None
        await self.store.update_task_status(task.id, "running")
        await self.store.append_event(
            TaskEvent(task_id=task.id, event_type="task_started", message="任务开始执行。")
        )
        # workspace 准备
        workspace = None
        if task.context.repository_alias:
            workspace = self.workspace_manager.ensure_workspace(task.context.repository_alias)
        # 由 triage agent + subagent handoff 执行
        result = await self.agent.run(task)
        payload = {
            **result,
            "workspace": workspace,
        }
        await self.store.update_task_status(task.id, "completed")
        await self.store.append_event(
            TaskEvent(task_id=task.id, event_type="task_completed", message="任务执行完成。", payload=payload)
        )
        return payload

    async def get_task(self, task_id: str) -> TaskRecord | None:
        """读取任务。"""

        return await self.store.get_task(task_id)

    async def list_tasks(self) -> list[TaskRecord]:
        """列出任务。"""

        return await self.store.list_tasks()

    async def list_task_events(self, task_id: str) -> list[TaskEvent]:
        """列出任务事件。"""

        return await self.store.list_events(task_id)
