# -*- coding: utf-8 -*-

"""服务端启动入口。"""

from __future__ import annotations

import argparse
import logging


def _setup_logging() -> None:
    """配置日志格式。"""

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )


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

    _setup_logging()
    args = build_parser().parse_args(argv)
    if args.command == "worker":
        run_worker()
        return
    run_api()
