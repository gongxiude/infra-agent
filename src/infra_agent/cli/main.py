# -*- coding: utf-8 -*-

"""CLI 入口。"""

from __future__ import annotations

import click

from infra_agent.cli.interactive_shell import start_interactive_shell
from infra_agent.cli.presentation.styles import apply_questionary_style


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx: click.Context) -> None:
    """运行 CLI 入口。"""

    apply_questionary_style()
    if ctx.invoked_subcommand is None:
        start_interactive_shell()


def main() -> None:
    """运行 CLI。"""

    cli()
