# -*- coding: utf-8 -*-

"""Signal Router（入口信号统一处理）。"""

from __future__ import annotations

from typing import Any

from infra_agent.core.models import AgentTask, TaskContext, TaskTrigger, TriggerSource


class SignalRouter:
    """统一入口信号，将各种来源转换为标准 AgentTask。"""

    def from_webhook(
        self,
        *,
        source_id: str,
        task_type: str,
        payload: dict[str, Any],
        context: TaskContext,
    ) -> AgentTask:
        """处理 webhook 入口。"""

        return self._build_task(TriggerSource.WEBHOOK, source_id, task_type, payload, context)

    def from_schedule(
        self,
        *,
        source_id: str,
        task_type: str,
        payload: dict[str, Any],
        context: TaskContext,
    ) -> AgentTask:
        """处理 schedule 入口。"""

        return self._build_task(TriggerSource.SCHEDULE, source_id, task_type, payload, context)

    def from_api(
        self,
        *,
        source_id: str,
        task_type: str,
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

        return self._build_task(TriggerSource.ALERT, source_id, "alert_triage", payload, context)

    def from_user_chat(
        self,
        *,
        source_id: str,
        payload: dict[str, Any],
        context: TaskContext,
    ) -> AgentTask:
        """处理用户对话入口（路由由 LLM triage agent 决定）。"""

        return self._build_task(TriggerSource.USER, source_id, "chat", payload, context)

    def _build_task(
        self,
        source: TriggerSource,
        source_id: str,
        task_type: str,
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
