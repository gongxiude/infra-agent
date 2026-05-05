# -*- coding: utf-8 -*-

"""核心数据模型。"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class TriggerSource(str, Enum):
    """任务入口来源。"""

    WEBHOOK = "webhook"
    SCHEDULE = "schedule"
    USER = "user"
    API = "api"
    ALERT = "alert"


class TaskType(str, Enum):
    """任务类型。"""

    CHAT = "chat"
    JENKINS_PIPELINE_ANALYSIS = "jenkins_pipeline_analysis"
    JENKINS_PIPELINE_CHANGE = "jenkins_pipeline_change"
    SHARED_LIBRARY_ANALYSIS = "shared_library_analysis"
    SHARED_LIBRARY_CHANGE = "shared_library_change"
    GITOPS_REPOSITORY_CHANGE = "gitops_repository_change"
    ALERT_TRIAGE = "alert_triage"


class TaskPriority(str, Enum):
    """任务优先级。"""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class TaskTrigger(BaseModel):
    """任务触发信息。"""

    source: TriggerSource
    source_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TaskContext(BaseModel):
    """任务上下文。"""

    organization_id: str = "default"
    repository_id: str | None = None
    repository_alias: str | None = None
    agent_slug: str = "infra-agent"
    priority: TaskPriority = TaskPriority.NORMAL
    session_id: str | None = None


class AgentTask(BaseModel):
    """标准任务对象。"""

    id: str = Field(default_factory=lambda: str(uuid4()))
    type: TaskType
    trigger: TaskTrigger
    context: TaskContext
    payload: dict[str, Any] = Field(default_factory=dict)


class PolicyDecision(BaseModel):
    """策略决策。"""

    allowed: bool = True
    tier: int = 2
    reason: str = "允许执行。"
    requires_pr: bool = True
    requires_validation: bool = True
    max_iterations: int = 10
    timeout_seconds: int = 900
    allowed_tools: list[str] = Field(default_factory=list)
    denied_tools: list[str] = Field(default_factory=list)
    skill_slugs: list[str] = Field(default_factory=list)
    credential_scopes: list[str] = Field(default_factory=list)


class TaskRecord(BaseModel):
    """任务记录。"""

    id: str
    type: str
    source: str
    status: str
    repository_alias: str | None = None
    priority: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TaskEvent(BaseModel):
    """任务事件。"""

    task_id: str
    event_type: str
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RouteResult(BaseModel):
    """自然语言路由结果。"""

    task_type: TaskType
    context: TaskContext
    payload: dict[str, Any]
