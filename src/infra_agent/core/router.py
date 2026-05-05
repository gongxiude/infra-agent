# -*- coding: utf-8 -*-

"""自然语言任务分配器。"""

from __future__ import annotations

from infra_agent.core.models import RouteResult, TaskContext, TaskPriority, TaskType


class NaturalLanguageRouter:
    """根据自然语言分配任务类型。"""

    def route(self, message: str, context: TaskContext) -> RouteResult:
        """路由用户输入。"""

        text = message.strip()
        lowered = text.casefold()
        route_context = context.model_copy(deep=True)
        task_type = TaskType.CHAT
        intent = "chat"

        if self._contains_any(lowered, ["pagerduty", "incident", "alarm", "alert", "cloudwatch", "告警", "报警"]):
            task_type = TaskType.ALERT_TRIAGE
            intent = "alert_triage"
            route_context.priority = TaskPriority.CRITICAL
        elif self._mentions_pipeline(lowered) and self._mentions_change(lowered):
            task_type = TaskType.JENKINS_PIPELINE_CHANGE
            intent = "jenkins_pipeline_change"
            route_context.repository_alias = route_context.repository_alias or "jenkins-pipeline"
        elif self._mentions_pipeline(lowered):
            task_type = TaskType.JENKINS_PIPELINE_ANALYSIS
            intent = "jenkins_pipeline_analysis"
            route_context.repository_alias = route_context.repository_alias or "jenkins-pipeline"
        elif self._mentions_shared_library(lowered) and self._mentions_change(lowered):
            task_type = TaskType.SHARED_LIBRARY_CHANGE
            intent = "shared_library_change"
            route_context.repository_alias = route_context.repository_alias or "jenkins-shared-library"
        elif self._mentions_shared_library(lowered):
            task_type = TaskType.SHARED_LIBRARY_ANALYSIS
            intent = "shared_library_analysis"
            route_context.repository_alias = route_context.repository_alias or "jenkins-shared-library"
        elif self._contains_any(lowered, ["gitops", "pull request", "merge request", "pr", "mr", "仓库"]) and self._mentions_change(lowered):
            task_type = TaskType.GITOPS_REPOSITORY_CHANGE
            intent = "gitops_repository_change"

        payload = {
            "message": text,
            "intent": intent,
            "classification": {
                "task_type": task_type.value,
                "repository_alias": route_context.repository_alias,
                "priority": route_context.priority.value,
            },
        }
        return RouteResult(task_type=task_type, context=route_context, payload=payload)

    def _mentions_pipeline(self, text: str) -> bool:
        """判断是否提到流水线。"""

        return self._contains_any(text, ["jenkinsfile", "pipeline", "流水线", "pipeline job"])

    def _mentions_shared_library(self, text: str) -> bool:
        """判断是否提到共享库。"""

        return self._contains_any(text, ["shared library", "vars/", "共享库", "groovy"])

    def _mentions_change(self, text: str) -> bool:
        """判断是否提到修改诉求。"""

        return self._contains_any(text, ["fix", "change", "update", "modify", "add", "修复", "修改", "更新", "新增"])

    def _contains_any(self, text: str, keywords: list[str]) -> bool:
        """判断是否包含任一关键词。"""

        return any(keyword in text for keyword in keywords)
