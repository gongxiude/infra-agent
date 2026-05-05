# -*- coding: utf-8 -*-

"""CLI 交互壳。"""

from __future__ import annotations

import sys

from infra_agent.cli.configuration import ensure_required_config
from infra_agent.cli.presentation.banner import print_global_banner
from infra_agent.cli.presentation.console import console


def start_interactive_shell() -> None:
    """启动交互壳。"""

    print_global_banner()
    ensure_required_config()
    if not sys.stdin.isatty():
        from infra_agent.cli.mode.local import run_local_mode

        run_local_mode()
        return
    _refresh_screen()
    while True:
        choice = _select_mode()
        if choice in (None, "Exit"):
            console.print("已退出。")
            return
        if choice == "Local":
            from infra_agent.cli.mode.local import run_local_mode

            run_local_mode()
        else:
            from infra_agent.cli.mode.remote.menu import run_remote_mode

            run_remote_mode()
        _refresh_screen()


def _refresh_screen(message: str = "") -> None:
    """刷新屏幕。"""

    console.clear()
    print_global_banner(animated=False)
    if message:
        console.print(message)


def _select_mode() -> str | None:
    """选择运行模式。"""

    try:
        import questionary
    except ModuleNotFoundError:
        console.print("[yellow]未安装 questionary，默认进入 Local 模式。[/yellow]")
        return "Local"
    return questionary.select(
        "运行模式:",
        choices=["Local", "Remote", "Exit"],
    ).ask()
