# -*- coding: utf-8 -*-

"""CLI 配置持久化。"""

from __future__ import annotations

import json

from infra_agent.cli.configuration.models import CliConfig
from infra_agent.cli.mode.paths import cli_config_path


def load_config() -> CliConfig:
    """读取 CLI 配置。"""

    path = cli_config_path()
    if not path.exists():
        return CliConfig()
    return CliConfig.model_validate_json(path.read_text(encoding="utf-8"))


def save_config(config: CliConfig) -> None:
    """保存 CLI 配置。"""

    path = cli_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")
