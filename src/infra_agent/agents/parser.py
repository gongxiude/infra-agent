# -*- coding: utf-8 -*-

"""YAML frontmatter 解析。"""

from __future__ import annotations

import yaml


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """解析 Markdown 文件中的 YAML frontmatter 和 body。

    Args:
        text: 完整 Markdown 文本

    Returns:
        (frontmatter_dict, body_text) 元组。无 frontmatter 时返回空 dict。
    """

    stripped = text.strip()
    if not stripped.startswith("---"):
        return {}, stripped

    # 找到第二个 --- 分隔符
    end = stripped.find("---", 3)
    if end == -1:
        return {}, stripped

    yaml_block = stripped[3:end].strip()
    body = stripped[end + 3:].strip()

    try:
        meta = yaml.safe_load(yaml_block)
    except yaml.YAMLError:
        return {}, stripped

    if not isinstance(meta, dict):
        return {}, stripped

    return meta, body
