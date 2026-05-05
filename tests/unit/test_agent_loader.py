# -*- coding: utf-8 -*-

"""Agent Loader 测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from infra_agent.agents.loader import build_triage_agent, discover_agents
from infra_agent.agents.models import AgentDefinition


@pytest.fixture()
def agents_dir(tmp_path: Path) -> Path:
    """创建临时 agents 目录结构。"""

    # jenkins-pipeline agent
    jenkins = tmp_path / "jenkins-pipeline"
    jenkins.mkdir()
    (jenkins / "AGENT.md").write_text(
        "---\nname: jenkins-pipeline\ndescription: Jenkins 流水线\n"
        "tools: [inspect_workspace, read_file]\nskills: [git-operations]\n"
        "tier: 2\n---\n\n你是 Jenkins 专家。",
        encoding="utf-8",
    )

    # general agent
    general = tmp_path / "general"
    general.mkdir()
    (general / "AGENT.md").write_text(
        "---\nname: general\ndescription: 通用对话\ntools: []\n---\n\n你是通用助手。",
        encoding="utf-8",
    )

    # 没有 AGENT.md 的目录
    empty = tmp_path / "empty"
    empty.mkdir()

    return tmp_path


@pytest.fixture()
def skills_dir(tmp_path: Path) -> Path:
    """创建临时 skills 目录。"""

    skills = tmp_path / "skills"
    skills.mkdir()
    git_ops = skills / "git-operations"
    git_ops.mkdir()
    (git_ops / "SKILL.md").write_text(
        "---\nname: git-operations\ndescription: Git 操作\n---\n\n# Git\n\n操作指南。",
        encoding="utf-8",
    )
    return skills


class TestDiscoverAgents:
    """discover_agents 发现逻辑。"""

    def test_discovers_valid_agents(self, agents_dir: Path) -> None:
        """发现包含 AGENT.md 的目录。"""

        result = discover_agents(agents_dir)
        assert "jenkins-pipeline" in result
        assert "general" in result
        assert "empty" not in result

    def test_agent_definition_fields(self, agents_dir: Path) -> None:
        """解析后字段正确。"""

        result = discover_agents(agents_dir)
        jenkins = result["jenkins-pipeline"]
        assert jenkins.name == "jenkins-pipeline"
        assert jenkins.description == "Jenkins 流水线"
        assert jenkins.tools == ["inspect_workspace", "read_file"]
        assert jenkins.skills == ["git-operations"]
        assert jenkins.tier == 2
        assert "Jenkins 专家" in jenkins.instructions

    def test_nonexistent_dir(self) -> None:
        """不存在的目录返回空字典。"""

        assert discover_agents(Path("/nonexistent")) == {}


class TestBuildTriageAgent:
    """build_triage_agent 构建逻辑。"""

    def test_builds_triage_with_handoffs(self, agents_dir: Path, skills_dir: Path) -> None:
        """triage agent 包含所有子代理作为 handoffs。"""

        triage = build_triage_agent(agents_dir, skills_dir, "gpt-4o")
        assert triage.name == "infra-agent-triage"
        assert len(triage.handoffs) == 2
        handoff_names = {h.name for h in triage.handoffs}
        assert "jenkins-pipeline" in handoff_names
        assert "general" in handoff_names

    def test_triage_instructions_contain_catalog(self, agents_dir: Path, skills_dir: Path) -> None:
        """triage 指令包含子代理目录。"""

        triage = build_triage_agent(agents_dir, skills_dir, "gpt-4o")
        assert "jenkins-pipeline" in triage.instructions
        assert "通用对话" in triage.instructions
