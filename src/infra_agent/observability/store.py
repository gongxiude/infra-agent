# -*- coding: utf-8 -*-

"""内存存储。"""

from __future__ import annotations

from infra_agent.core.models import TaskEvent, TaskRecord


class InMemoryStore:
    """最小内存存储。"""

    def __init__(self) -> None:
        """初始化存储。"""

        self.tasks: dict[str, TaskRecord] = {}
        self.events: dict[str, list[TaskEvent]] = {}

    async def save_task(self, record: TaskRecord) -> None:
        """保存任务。"""

        self.tasks[record.id] = record

    async def update_task_status(self, task_id: str, status: str) -> None:
        """更新任务状态。"""

        record = self.tasks[task_id]
        self.tasks[task_id] = record.model_copy(update={"status": status})

    async def get_task(self, task_id: str) -> TaskRecord | None:
        """读取任务。"""

        return self.tasks.get(task_id)

    async def list_tasks(self) -> list[TaskRecord]:
        """列出任务。"""

        return list(self.tasks.values())

    async def append_event(self, event: TaskEvent) -> None:
        """追加事件。"""

        self.events.setdefault(event.task_id, []).append(event)

    async def list_events(self, task_id: str) -> list[TaskEvent]:
        """列出事件。"""

        return self.events.get(task_id, [])
