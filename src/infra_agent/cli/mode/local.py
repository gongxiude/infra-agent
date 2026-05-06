# -*- coding: utf-8 -*-

"""CLI 本地模式。"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from rich.panel import Panel

from infra_agent.cli.env import load_settings
from infra_agent.cli.presentation.console import console
from infra_agent.core.agent import create_infra_agent
from infra_agent.core.models import TaskContext
from infra_agent.core.service import InfraAgentService
from infra_agent.execution.queue import InMemoryDispatchQueue
from infra_agent.ingestion.router import SignalRouter
from infra_agent.integrations.git.workspace import GitWorkspaceManager
from infra_agent.observability.store import InMemoryStore


def build_local_service() -> InfraAgentService:
    """构建本地服务实例。"""

    settings = load_settings()
    return InfraAgentService(
        signal_router=SignalRouter(),
        queue=InMemoryDispatchQueue(),
        store=InMemoryStore(),
        agent=create_infra_agent(settings),
        workspace_manager=GitWorkspaceManager(settings.git),
    )


def run_local_mode() -> None:
    """运行本地模式。"""

    console.print("[cyan]Local Mode[/cyan]")
    console.print("[dim]直接调用本地 infra-agent 代码。[/dim]")
    asyncio.run(_run_local_shell())


async def _run_local_shell() -> None:
    """启动本地交互壳。"""

    service = build_local_service()
    _print_banner()
    while True:
        try:
            command = input("infra-agent (local)> ").strip()
        except EOFError:
            console.print()
            return
        if not command:
            continue
        if command in {"exit", "quit"}:
            console.print("[dim]退出本地模式。[/dim]")
            return
        if command == "help":
            _print_help()
            continue
        if command == "list":
            console.print([record.model_dump(mode="json") for record in await service.list_tasks()])
            continue
        if command.startswith("get "):
            record = await service.get_task(command.removeprefix("get ").strip())
            console.print(record.model_dump(mode="json") if record else "任务不存在。")
            continue
        if command.startswith("events "):
            records = await service.list_task_events(command.removeprefix("events ").strip())
            console.print([record.model_dump(mode="json") for record in records])
            continue
        if command.startswith("submit-jenkins-change "):
            payload = _parse_json(command.removeprefix("submit-jenkins-change ").strip())
            if payload is None:
                console.print("[yellow]payload 必须是 JSON。[/yellow]")
                continue
            result = await _submit_typed_task(
                service,
                task_type="jenkins_pipeline_change",
                payload=payload,
                context=TaskContext(repository_alias=str(payload.get("repository_alias", "jenkins-pipeline"))),
            )
            console.print(result)
            continue
        result = await _submit_chat(service, command)
        console.print(f"\n[green]{result}[/green]\n")


async def _submit_chat(service: InfraAgentService, message: str) -> str:
    """提交自然语言消息，返回 agent 输出文本。"""

    task = service.signal_router.from_user_chat(
        source_id="cli-local",
        payload={"message": message},
        context=TaskContext(),
    )
    await service.submit_task(task)
    result = await service.run_once()
    return result.get("final_output", "") if result else "（无响应）"


async def _submit_typed_task(
    service: InfraAgentService,
    task_type: str,
    payload: dict[str, Any],
    context: TaskContext,
) -> dict[str, Any]:
    """提交显式任务。"""

    task = service.signal_router.from_api(
        source_id="cli-local",
        task_type=task_type,
        payload=payload,
        context=context,
    )
    await service.submit_task(task)
    result = await service.run_once()
    return {
        "task_id": task.id,
        "task_type": task.type,
        "result": result,
    }


def _parse_json(raw: str) -> dict[str, Any] | None:
    """解析 JSON。"""

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def _print_banner() -> None:
    """打印本地模式横幅。"""

    console.print(
        Panel(
            "本地模式已启动。\n直接输入自然语言即可提交用户任务。\n输入 help 查看命令，输入 exit 返回上一级菜单。",
            title="Local Mode",
            border_style="cyan",
        )
    )


def _print_help() -> None:
    """打印帮助。"""

    console.print("[bold]Commands:[/bold]")
    console.print("- 直接输入自然语言")
    console.print("- submit-jenkins-change <json_payload>")
    console.print("- list")
    console.print("- get <task_id>")
    console.print("- events <task_id>")
    console.print("- help")
    console.print("- exit")
