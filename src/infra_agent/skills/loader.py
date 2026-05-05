# -*- coding: utf-8 -*-

"""Skill 发现与加载，从 skills/*/SKILL.md 读取指令。"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def discover_skills(skills_dir: Path) -> dict[str, str]:
    """扫描 skills 目录，返回 {slug: content} 映射。

    Args:
        skills_dir: skills 根目录

    Returns:
        以目录名为 slug，SKILL.md 内容为 value 的字典。
    """

    result: dict[str, str] = {}
    if not skills_dir.is_dir():
        return result
    for entry in sorted(skills_dir.iterdir()):
        skill_file = entry / "SKILL.md"
        if entry.is_dir() and skill_file.is_file():
            result[entry.name] = skill_file.read_text(encoding="utf-8").strip()
    return result


def build_skills_prompt(skills_dir: Path, slugs: list[str]) -> str:
    """根据 slug 列表加载 SKILL.md 内容，拼接为提示词片段。

    Args:
        skills_dir: skills 根目录
        slugs: 要加载的 skill slug 列表

    Returns:
        拼接后的 skill 提示词文本，若无可用 skill 则返回空字符串。
    """

    if not slugs:
        return ""
    all_skills = discover_skills(skills_dir)
    parts: list[str] = []
    for slug in slugs:
        content = all_skills.get(slug)
        if content:
            parts.append(f"---\n## Skill: {slug}\n\n{content}")
        else:
            logger.warning("skill 未找到: %s", slug)
    return "\n\n".join(parts)
