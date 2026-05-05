# -*- coding: utf-8 -*-

"""入口路由测试。"""

from infra_agent.core.models import TaskContext, TaskType, TriggerSource
from infra_agent.ingestion.router import SignalRouter


def test_user_chat_routes_to_classified_task() -> None:
    """用户对话应走自然语言分配。"""

    task = SignalRouter().from_user_chat(
        source_id="chat-1",
        payload={"message": "请修改 Jenkins pipeline 增加测试"},
        context=TaskContext(),
    )
    assert task.type is TaskType.JENKINS_PIPELINE_CHANGE
    assert task.trigger.source is TriggerSource.USER
    assert task.payload["intent"] == "jenkins_pipeline_change"
