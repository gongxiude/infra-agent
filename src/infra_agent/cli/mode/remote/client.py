# -*- coding: utf-8 -*-

"""远端模式客户端。"""

from __future__ import annotations

import json
from urllib import request

from infra_agent.cli.configuration.models import CliConfig
from infra_agent.core.models import TaskContext


class RemoteClient:
    """远端 HTTP 客户端。"""

    def __init__(self, config: CliConfig) -> None:
        """初始化客户端。"""

        self._base_url = config.remote.base_url.rstrip("/")

    def submit_task(
        self,
        *,
        task_type: str,
        source_id: str,
        payload: dict,
        context: TaskContext,
    ) -> dict:
        """通过通用 API 提交任务。"""

        return self._post(
            "/api/tasks",
            {
                "task_type": task_type,
                "source_id": source_id,
                "payload": payload,
                "context": context.model_dump(mode="json"),
            },
        )

    def submit_chat(self, message: str, context: TaskContext) -> dict:
        """通过聊天入口提交自然语言。"""

        return self._post(
            "/chat",
            {
                "message": message,
                "repository_alias": context.repository_alias,
                "session_id": context.session_id,
            },
        )

    def list_tasks(self) -> list[dict]:
        """列出任务。"""

        with request.urlopen(f"{self._base_url}/api/tasks") as response:  # noqa: S310
            return json.loads(response.read().decode("utf-8"))

    def get_task(self, task_id: str) -> dict:
        """读取任务。"""

        with request.urlopen(f"{self._base_url}/api/tasks/{task_id}") as response:  # noqa: S310
            return json.loads(response.read().decode("utf-8"))

    def list_task_events(self, task_id: str) -> list[dict]:
        """读取任务事件。"""

        with request.urlopen(f"{self._base_url}/api/tasks/{task_id}/events") as response:  # noqa: S310
            return json.loads(response.read().decode("utf-8"))

    def _post(self, path: str, payload: dict) -> dict:
        """发送 POST 请求。"""

        req = request.Request(
            url=f"{self._base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req) as response:  # noqa: S310
            return json.loads(response.read().decode("utf-8"))
