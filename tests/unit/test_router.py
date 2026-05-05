# -*- coding: utf-8 -*-

"""自然语言路由测试。"""

from infra_agent.core.models import TaskContext, TaskPriority, TaskType
from infra_agent.core.router import NaturalLanguageRouter


def test_pipeline_change_route() -> None:
    """应识别流水线变更任务。"""

    result = NaturalLanguageRouter().route("请修改 Jenkinsfile 增加扫描阶段", TaskContext())
    assert result.task_type is TaskType.JENKINS_PIPELINE_CHANGE
    assert result.context.repository_alias == "jenkins-pipeline"


def test_shared_library_analysis_route() -> None:
    """应识别共享库分析任务。"""

    result = NaturalLanguageRouter().route("分析 shared library 的 vars/deploy.groovy", TaskContext())
    assert result.task_type is TaskType.SHARED_LIBRARY_ANALYSIS
    assert result.context.repository_alias == "jenkins-shared-library"


def test_alert_route() -> None:
    """应识别告警任务。"""

    result = NaturalLanguageRouter().route("PagerDuty incident 正在报警", TaskContext())
    assert result.task_type is TaskType.ALERT_TRIAGE
    assert result.context.priority is TaskPriority.CRITICAL
