# -*- coding: utf-8 -*-

"""CLI 远端模式。"""

from __future__ import annotations

import json

from rich.panel import Panel

from infra_agent.cli.configuration.store import load_config
from infra_agent.cli.mode.remote.client import RemoteClient
from infra_agent.cli.presentation.console import console
from infra_agent.core.models import TaskContext


def run_remote_mode() -> None:
    """运行远端模式。"""

    console.print("[cyan]Remote Mode[/cyan]")
    console.print("[dim]通过 HTTP 调用远端 infra-agent API。[/dim]")
    client = RemoteClient(load_config())
    _print_banner()
    while True:
        try:
            command = input("infra-agent (remote)> ").strip()
        except EOFError:
            console.print()
            return
        if not command:
            continue
        if command in {"exit", "quit"}:
            console.print("[dim]退出远端模式。[/dim]")
            return
        if command == "help":
            _print_help()
            continue
        if command == "list":
            console.print(client.list_tasks())
            continue
        if command.startswith("get "):
            console.print(client.get_task(command.removeprefix("get ").strip()))
            continue
        if command.startswith("events "):
            console.print(client.list_task_events(command.removeprefix("events ").strip()))
            continue
        if command.startswith("submit-jenkins-change "):
            payload = _parse_json(command.removeprefix("submit-jenkins-change ").strip())
            if payload is None:
                console.print("[yellow]payload 必须是 JSON。[/yellow]")
                continue
            console.print(
                client.submit_task(
                    task_type="jenkins_pipeline_change",
                    source_id="cli-remote",
                    payload=payload,
                    context=TaskContext(repository_alias=str(payload.get("repository_alias", "jenkins-pipeline"))),
                )
            )
            continue
        result = client.submit_chat(command, TaskContext())
        output = result.get("result", {}).get("final_output", "") if isinstance(result, dict) else str(result)
        console.print(f"\n[green]{output}[/green]\n")


def _parse_json(raw: str) -> dict | None:
    """解析 JSON。"""

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def _print_banner() -> None:
    """打印横幅。"""

    console.print(
        Panel(
            "远端模式已启动。\n直接输入自然语言即可调用远端 /chat。\n输入 help 查看命令，输入 exit 返回上一级菜单。",
            title="Remote Mode",
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
