# -*- coding: utf-8 -*-

"""CLI 路径。"""

from __future__ import annotations

from pathlib import Path

from infra_agent.config.paths import project_root


def cli_config_path() -> Path:
    """返回 CLI 配置文件路径。"""

    return project_root() / ".data" / "cli-config.json"
