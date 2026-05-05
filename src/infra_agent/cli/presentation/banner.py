# -*- coding: utf-8 -*-

"""CLI 横幅。"""

from infra_agent.cli.presentation.ascii_art import get_ascii_art
from infra_agent.cli.presentation.console import console


def print_global_banner(animated: bool = True) -> None:
    """打印全局横幅。"""

    del animated
    console.print(f"[bold cyan]{get_ascii_art()}[/bold cyan]")
    console.print("[dim]Jenkins pipeline / shared library / GitOps 客户端[/dim]\n")
