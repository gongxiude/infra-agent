# -*- coding: utf-8 -*-

"""FastAPI 与服务装配。"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from infra_agent.core.agent import create_infra_agent
from infra_agent.core.models import TaskContext, TaskType
from infra_agent.core.service import InfraAgentService
from infra_agent.core.settings import AppSettings
from infra_agent.execution.queue import InMemoryDispatchQueue
from infra_agent.ingestion.router import SignalRouter
from infra_agent.integrations.git.workspace import GitWorkspaceManager
from infra_agent.observability.store import InMemoryStore
from infra_agent.policy.engine import PolicyEngine

SERVICE: InfraAgentService | None = None


class SubmitTaskRequest(BaseModel):
    """任务提交请求。"""

    task_type: TaskType
    source_id: str
    payload: dict[str, Any]
    context: TaskContext


def build_service(settings: AppSettings) -> InfraAgentService:
    """构建服务对象。"""

    global SERVICE
    if SERVICE is None:
        SERVICE = InfraAgentService(
            signal_router=SignalRouter(),
            policy_engine=PolicyEngine(settings),
            queue=InMemoryDispatchQueue(),
            store=InMemoryStore(),
            agent=create_infra_agent(settings),
            workspace_manager=GitWorkspaceManager(settings.git),
        )
    return SERVICE


def create_app(settings: AppSettings | None = None) -> FastAPI:
    """创建应用。"""

    app_settings = settings or AppSettings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """管理生命周期。"""

        app.state.settings = app_settings
        app.state.service = build_service(app_settings)
        yield

    app = FastAPI(title=app_settings.app_name, lifespan=lifespan)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        """健康检查。"""

        return {"status": "ok"}

    @app.post("/api/tasks")
    async def submit_task(request: SubmitTaskRequest) -> dict[str, Any]:
        """提交显式任务。"""

        service: InfraAgentService = app.state.service
        task = service.signal_router.from_api(
            source_id=request.source_id,
            task_type=request.task_type,
            payload=request.payload,
            context=request.context,
        )
        decision = await service.submit_task(task)
        result = await service.run_once()
        return {
            "task_id": task.id,
            "task_type": task.type.value,
            "policy": decision.model_dump(mode="json"),
            "result": result,
        }

    @app.post("/chat")
    async def chat(payload: dict[str, Any]) -> dict[str, Any]:
        """提交用户对话。"""

        service: InfraAgentService = app.state.service
        context = TaskContext(
            repository_alias=payload.get("repository_alias"),
            session_id=payload.get("session_id"),
        )
        task = service.signal_router.from_user_chat(
            source_id=str(payload.get("message_id", "chat")),
            payload=payload,
            context=context,
        )
        decision = await service.submit_task(task)
        result = await service.run_once()
        return {
            "task_id": task.id,
            "task_type": task.type.value,
            "context": task.context.model_dump(mode="json"),
            "policy": decision.model_dump(mode="json"),
            "result": result,
        }

    @app.post("/webhooks/jenkins")
    async def jenkins_webhook(payload: dict[str, Any]) -> dict[str, Any]:
        """提交 Jenkins webhook。"""

        service: InfraAgentService = app.state.service
        task = service.signal_router.from_webhook(
            source_id=str(payload.get("build_id", "jenkins-webhook")),
            task_type=TaskType.JENKINS_PIPELINE_CHANGE,
            payload=payload,
            context=TaskContext(repository_alias=str(payload.get("repository_alias", "jenkins-pipeline"))),
        )
        decision = await service.submit_task(task)
        result = await service.run_once()
        return {"task_id": task.id, "policy": decision.model_dump(mode="json"), "result": result}

    @app.post("/alerts")
    async def alerts(payload: dict[str, Any]) -> dict[str, Any]:
        """提交告警。"""

        service: InfraAgentService = app.state.service
        task = service.signal_router.from_alert(
            source_id=str(payload.get("alert_id", "alert")),
            payload=payload,
            context=TaskContext(),
        )
        decision = await service.submit_task(task)
        result = await service.run_once()
        return {"task_id": task.id, "policy": decision.model_dump(mode="json"), "result": result}

    @app.get("/api/tasks")
    async def list_tasks() -> list[dict[str, Any]]:
        """列出任务。"""

        service: InfraAgentService = app.state.service
        return [record.model_dump(mode="json") for record in await service.list_tasks()]

    @app.get("/api/tasks/{task_id}")
    async def get_task(task_id: str) -> dict[str, Any]:
        """读取任务。"""

        service: InfraAgentService = app.state.service
        record = await service.get_task(task_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Task not found")
        return record.model_dump(mode="json")

    @app.get("/api/tasks/{task_id}/events")
    async def list_task_events(task_id: str) -> list[dict[str, Any]]:
        """读取任务事件。"""

        service: InfraAgentService = app.state.service
        return [record.model_dump(mode="json") for record in await service.list_task_events(task_id)]

    return app


def run_api_server(settings: AppSettings | None = None) -> None:
    """运行 API 服务。"""

    app_settings = settings or AppSettings.from_env()
    uvicorn.run(
        create_app(app_settings),
        host=app_settings.runtime.api_host,
        port=app_settings.runtime.api_port,
    )
