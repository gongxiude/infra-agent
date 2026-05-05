# -*- coding: utf-8 -*-

"""Skill 发现与加载，支持 progressive disclosure。"""

from __future__ import annotations

import logging
from pathlib import Path

from infra_agent.agents.models import SkillMeta
from infra_agent.agents.parser import parse_frontmatter

logger = logging.getLogger(__name__)


def discover_skill_catalog(skills_dir: Path) -> dict[str, SkillMeta]:
    """扫描 skills 目录，只解析 frontmatter 元数据。

    Args:
        skills_dir: skills 根目录

    Returns:
        以目录名为 slug 的 SkillMeta 字典。
    """

    result: dict[str, SkillMeta] = {}
    if not skills_dir.is_dir():
        return result
    for entry in sorted(skills_dir.iterdir()):
        skill_file = entry / "SKILL.md"
        if entry.is_dir() and skill_file.is_file():
            text = skill_file.read_text(encoding="utf-8")
            meta, _ = parse_frontmatter(text)
            name = meta.get("name", entry.name)
            description = meta.get("description", "")
            result[entry.name] = SkillMeta(name=name, description=description)
    return result


def load_skill_body(skills_dir: Path, slug: str) -> str | None:
    """按需加载指定 skill 的完整 body 内容。

    Args:
        skills_dir: skills 根目录
        slug: skill 目录名

    Returns:
        SKILL.md 的 body 部分，未找到时返回 None。
    """

    skill_file = skills_dir / slug / "SKILL.md"
    if not skill_file.is_file():
        return None
    text = skill_file.read_text(encoding="utf-8")
    _, body = parse_frontmatter(text)
    return body


def build_skill_catalog_prompt(skills_dir: Path, allowed_slugs: list[str]) -> str:
    """生成紧凑的 skill 目录提示词（只含名称和描述）。

    Args:
        skills_dir: skills 根目录
        allowed_slugs: 允许使用的 skill slug 列表

    Returns:
        Markdown 格式的 skill 目录文本。
    """

    if not allowed_slugs:
        return ""
    catalog = discover_skill_catalog(skills_dir)
    lines: list[str] = ["## 可用技能", "", "使用 `load_skill` 工具加载完整技能指令。", ""]
    for slug in allowed_slugs:
        meta = catalog.get(slug)
        if meta:
            lines.append(f"- **{meta.name}**: {meta.description}")
        else:
            logger.warning("skill 未找到: %s", slug)
    return "\n".join(lines) if len(lines) > 4 else ""


# --- 兼容旧接口 ---


def discover_skills(skills_dir: Path) -> dict[str, str]:
    """扫描 skills 目录，返回 {slug: content} 映射（兼容旧接口）。"""

    result: dict[str, str] = {}
    if not skills_dir.is_dir():
        return result
    for entry in sorted(skills_dir.iterdir()):
        skill_file = entry / "SKILL.md"
        if entry.is_dir() and skill_file.is_file():
            result[entry.name] = skill_file.read_text(encoding="utf-8").strip()
    return result


def build_skills_prompt(skills_dir: Path, slugs: list[str]) -> str:
    """根据 slug 列表加载 SKILL.md 全部内容（兼容旧接口）。"""

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
