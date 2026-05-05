# -*- coding: utf-8 -*-

"""CLI 配置向导。"""

from infra_agent.cli.configuration.models import CliConfig
from infra_agent.cli.configuration.store import load_config, save_config


def ensure_required_config() -> None:
    """确保本地 CLI 配置存在。"""

    config = load_config()
    save_config(CliConfig.model_validate(config.model_dump()))
