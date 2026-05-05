# -*- coding: utf-8 -*-

"""内存队列。"""

from __future__ import annotations

from collections import deque

from infra_agent.core.models import AgentTask


class InMemoryDispatchQueue:
    """最小派发队列。"""

    def __init__(self) -> None:
        """初始化队列。"""

        self._queue: deque[AgentTask] = deque()

    async def enqueue(self, task: AgentTask) -> None:
        """入队。"""

        self._queue.append(task)

    async def dequeue(self) -> AgentTask | None:
        """出队。"""

        if not self._queue:
            return None
        return self._queue.popleft()
