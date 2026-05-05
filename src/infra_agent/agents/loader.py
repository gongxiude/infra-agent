# -*- coding: utf-8 -*-

"""从 AGENT.md 文件发现和构建 SDK Agent 对象。"""

from __future__ import annotations

import logging
from pathlib import Path

from agents import Agent, ModelSettings

from infra_agent.agents.models import AgentDefinition
from infra_agent.agents.parser import parse_frontmatter
from infra_agent.skills.loader import build_skill_catalog_prompt
from infra_agent.tools import ALL_TOOLS
from infra_agent.tools.context import AgentContext

logger = logging.getLogger(__name__)


def discover_agents(agents_dir: Path) -> dict[str, AgentDefinition]:
    """扫描 agents 目录，返回 {slug: AgentDefinition} 映射。

    Args:
        agents_dir: agents 根目录

    Returns:
        以目录名为 slug 的 AgentDefinition 字典。
    """

    result: dict[str, AgentDefinition] = {}
    if not agents_dir.is_dir():
        return result
    for entry in sorted(agents_dir.iterdir()):
        agent_file = entry / "AGENT.md"
        if entry.is_dir() and agent_file.is_file():
            text = agent_file.read_text(encoding="utf-8")
            meta, body = parse_frontmatter(text)
            if not meta.get("name"):
                logger.warning("AGENT.md 缺少 name 字段: %s", agent_file)
                continue
            defn = AgentDefinition(**meta, instructions=body)
            result[entry.name] = defn
    return result


def build_subagent(
    defn: AgentDefinition,
    skills_dir: Path,
    model: str,
) -> Agent[AgentContext]:
    """从 AgentDefinition 构建一个 SDK Agent 对象。

    Args:
        defn: 子代理定义
        skills_dir: skills 根目录
        model: LLM 模型名称
    """

    # 根据定义过滤工具
    tools = [ALL_TOOLS[name] for name in defn.tools if name in ALL_TOOLS]

    # 添加 skill meta-tools（load_skill, read_skill_file）
    for meta_name in ("load_skill", "read_skill_file"):
        if meta_name in ALL_TOOLS:
            tools.append(ALL_TOOLS[meta_name])

    # 构建 instructions：body + skill 目录
    instructions = defn.instructions
    if defn.skills:
        catalog = build_skill_catalog_prompt(skills_dir, defn.skills)
        if catalog:
            instructions += "\n\n" + catalog

    return Agent[AgentContext](
        name=defn.name,
        handoff_description=defn.description,
        instructions=instructions,
        tools=tools,
        model=model,
        model_settings=ModelSettings(temperature=0.1),
    )


def build_triage_agent(
    agents_dir: Path,
    skills_dir: Path,
    model: str,
) -> Agent[AgentContext]:
    """构建 triage agent，所有子代理作为 handoffs。

    Args:
        agents_dir: agents 根目录
        skills_dir: skills 根目录
        model: LLM 模型名称
    """

    definitions = discover_agents(agents_dir)
    if not definitions:
        logger.warning("未发现任何 AGENT.md 定义，triage agent 将没有 handoff 目标")

    # 构建子代理
    subagents: list[Agent[AgentContext]] = []
    for slug, defn in definitions.items():
        sub = build_subagent(defn, skills_dir, model)
        subagents.append(sub)
        logger.info("已加载子代理: %s (%s)", defn.name, defn.description)

    # 构建 triage 指令（动态生成子代理目录）
    agent_catalog = "\n".join(
        f"- **{defn.name}**: {defn.description}"
        for defn in definitions.values()
    )
    triage_instructions = _TRIAGE_TEMPLATE.format(agent_catalog=agent_catalog)

    return Agent[AgentContext](
        name="infra-agent-triage",
        instructions=triage_instructions,
        handoffs=subagents,
        model=model,
        model_settings=ModelSettings(temperature=0.0),
    )


_TRIAGE_TEMPLATE = """\
你是 infra-agent 分流路由器。根据用户请求，判断应该交给哪个专家代理处理，然后执行 handoff。

## 可用专家

{agent_catalog}

## 路由规则

1. 仔细阅读用户请求，判断最匹配的专家代理。
2. 如果请求明确属于某个专家领域，直接 handoff 到该代理。
3. 如果无法确定，handoff 到 general 代理。
4. 不要自己回答用户问题，始终交给专家代理处理。
"""
