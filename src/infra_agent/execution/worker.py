# -*- coding: utf-8 -*-

"""常驻 worker。"""

from __future__ import annotations

import asyncio
import logging

from infra_agent.cli.api import build_service
from infra_agent.core.settings import AppSettings

LOGGER = logging.getLogger(__name__)


async def run_worker_loop(poll_interval_seconds: float = 1.0) -> None:
    """运行 worker 循环。"""

    service = build_service(AppSettings.from_env())
    LOGGER.info("worker started")
    while True:
        result = await service.run_once()
        if result is None:
            await asyncio.sleep(poll_interval_seconds)


def main() -> None:
    """运行 worker 入口。"""

    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_worker_loop())
