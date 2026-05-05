# -*- coding: utf-8 -*-

"""Skill meta-tools: load_skill 和 read_skill_file。"""

from __future__ import annotations

import json
from pathlib import Path

from agents import RunContextWrapper, function_tool

from infra_agent.tools.context import AgentContext


@function_tool
async def load_skill(
    ctx: RunContextWrapper[AgentContext],
    skill_name: str,
) -> str:
    """加载指定技能的完整指令内容。

    Args:
        skill_name: 技能名称（如 git-operations）
    """

    # 验证 skill 在允许范围内
    if skill_name not in ctx.context.allowed_skills:
        return json.dumps({"error": f"技能 '{skill_name}' 不在允许范围内"}, ensure_ascii=False)

    skill_file = ctx.context.skills_dir / skill_name / "SKILL.md"
    if not skill_file.is_file():
        return json.dumps({"error": f"技能 '{skill_name}' 未找到"}, ensure_ascii=False)

    from infra_agent.agents.parser import parse_frontmatter

    text = skill_file.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)

    # 列出支持文件
    skill_dir = ctx.context.skills_dir / skill_name
    supporting = [
        f.name for f in skill_dir.iterdir()
        if f.is_file() and f.name != "SKILL.md"
    ]

    return json.dumps({
        "skill_name": skill_name,
        "description": meta.get("description", ""),
        "instructions": body,
        "available_files": supporting,
    }, ensure_ascii=False)


@function_tool
async def read_skill_file(
    ctx: RunContextWrapper[AgentContext],
    skill_name: str,
    filename: str,
) -> str:
    """读取技能目录中的支持文件。

    Args:
        skill_name: 技能名称
        filename: 文件名（不含路径）
    """

    if skill_name not in ctx.context.allowed_skills:
        return json.dumps({"error": f"技能 '{skill_name}' 不在允许范围内"}, ensure_ascii=False)

    # 路径遍历防护
    if ".." in filename or filename.startswith("/"):
        return json.dumps({"error": f"非法文件名: {filename}"}, ensure_ascii=False)

    skill_dir = ctx.context.skills_dir / skill_name
    target = (skill_dir / filename).resolve()
    if not target.is_relative_to(skill_dir.resolve()):
        return json.dumps({"error": f"非法文件名: {filename}"}, ensure_ascii=False)

    if not target.is_file():
        return json.dumps({"error": f"文件不存在: {filename}"}, ensure_ascii=False)

    content = target.read_text(encoding="utf-8", errors="replace")
    return json.dumps({
        "skill_name": skill_name,
        "filename": filename,
        "content": content,
    }, ensure_ascii=False)
