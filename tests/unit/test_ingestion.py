# -*- coding: utf-8 -*-

"""Ingestion SignalRouter 测试。"""

from __future__ import annotations

from infra_agent.core.models import TaskContext, TriggerSource
from infra_agent.ingestion.router import SignalRouter


def test_user_chat_creates_chat_task() -> None:
    """from_user_chat 应创建 chat 类型任务。"""

    router = SignalRouter()
    task = router.from_user_chat(
        source_id="cli-local",
        payload={"message": "请修改 Jenkins pipeline 增加测试"},
        context=TaskContext(),
    )
    # 路由现在由 LLM triage agent 决定，ingestion 层始终创建 chat 类型
    assert task.type == "chat"
    assert task.trigger.source == TriggerSource.USER
    assert task.payload["message"] == "请修改 Jenkins pipeline 增加测试"


def test_alert_creates_alert_triage_task() -> None:
    """from_alert 应创建 alert_triage 类型任务。"""

    router = SignalRouter()
    task = router.from_alert(
        source_id="alert-123",
        payload={"alert_id": "123", "severity": "critical"},
        context=TaskContext(),
    )
    assert task.type == "alert_triage"
    assert task.trigger.source == TriggerSource.ALERT


def test_webhook_creates_explicit_type() -> None:
    """from_webhook 使用显式 task_type。"""

    router = SignalRouter()
    task = router.from_webhook(
        source_id="jenkins-build-1",
        task_type="jenkins_pipeline_change",
        payload={"build_id": "1"},
        context=TaskContext(repository_alias="my-repo"),
    )
    assert task.type == "jenkins_pipeline_change"
    assert task.trigger.source == TriggerSource.WEBHOOK
    assert task.context.repository_alias == "my-repo"
