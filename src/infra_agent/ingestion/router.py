# -*- coding: utf-8 -*-

"""Signal Router。"""

from __future__ import annotations

from typing import Any

from infra_agent.core.models import AgentTask, TaskContext, TaskTrigger, TaskType, TriggerSource
from infra_agent.core.router import NaturalLanguageRouter


class SignalRouter:
    """统一入口信号。"""

    def __init__(self) -> None:
        """初始化路由器。"""

        self._nl_router = NaturalLanguageRouter()

    def from_webhook(
        self,
        *,
        source_id: str,
        task_type: TaskType,
        payload: dict[str, Any],
        context: TaskContext,
    ) -> AgentTask:
        """处理 webhook 入口。"""

        return self._build_task(TriggerSource.WEBHOOK, source_id, task_type, payload, context)

    def from_schedule(
        self,
        *,
        source_id: str,
        task_type: TaskType,
        payload: dict[str, Any],
        context: TaskContext,
    ) -> AgentTask:
        """处理 schedule 入口。"""

        return self._build_task(TriggerSource.SCHEDULE, source_id, task_type, payload, context)

    def from_api(
        self,
        *,
        source_id: str,
        task_type: TaskType,
        payload: dict[str, Any],
        context: TaskContext,
    ) -> AgentTask:
        """处理 API 入口。"""

        return self._build_task(TriggerSource.API, source_id, task_type, payload, context)

    def from_alert(
        self,
        *,
        source_id: str,
        payload: dict[str, Any],
        context: TaskContext,
    ) -> AgentTask:
        """处理 alert 入口。"""

        return self._build_task(TriggerSource.ALERT, source_id, TaskType.ALERT_TRIAGE, payload, context)

    def from_user_chat(
        self,
        *,
        source_id: str,
        payload: dict[str, Any],
        context: TaskContext,
    ) -> AgentTask:
        """处理用户对话入口。"""

        message = str(payload.get("message", "")).strip()
        route = self._nl_router.route(message, context)
        merged_payload = {**payload, **route.payload}
        return self._build_task(TriggerSource.USER, source_id, route.task_type, merged_payload, route.context)

    def _build_task(
        self,
        source: TriggerSource,
        source_id: str,
        task_type: TaskType,
        payload: dict[str, Any],
        context: TaskContext,
    ) -> AgentTask:
        """构建标准任务。"""

        return AgentTask(
            type=task_type,
            trigger=TaskTrigger(source=source, source_id=source_id),
            context=context,
            payload=payload,
        )
