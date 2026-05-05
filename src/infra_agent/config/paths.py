# -*- coding: utf-8 -*-

"""路径配置。"""

from __future__ import annotations

from pathlib import Path


def project_root() -> Path:
    """返回项目根目录。"""

    return Path(__file__).resolve().parents[3]


def data_dir() -> Path:
    """返回本地数据目录。"""

    path = project_root() / ".data"
    path.mkdir(parents=True, exist_ok=True)
    return path
