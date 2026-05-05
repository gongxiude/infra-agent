# -*- coding: utf-8 -*-

"""服务端启动入口。"""

from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    """构建参数解析器。"""

    parser = argparse.ArgumentParser(description="infra-agent runtime")
    parser.add_argument("command", nargs="?", default="api", choices=["api", "worker"])
    return parser


def run_api() -> None:
    """启动 API。"""

    from infra_agent.cli.api import run_api_server

    run_api_server()


def run_worker() -> None:
    """启动 worker。"""

    from infra_agent.execution.worker import main as worker_main

    worker_main()


def main(argv: list[str] | None = None) -> None:
    """运行启动入口。"""

    args = build_parser().parse_args(argv)
    if args.command == "worker":
        run_worker()
        return
    run_api()
