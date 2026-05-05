# -*- coding: utf-8 -*-

"""CLI 环境加载。"""

from infra_agent.core.settings import AppSettings


def load_settings() -> AppSettings:
    """加载配置。"""

    return AppSettings.from_env()
