# -*- coding: utf-8 -*-

"""Skill 加载器测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from infra_agent.agents.models import SkillMeta
from infra_agent.skills.loader import (
    build_skill_catalog_prompt,
    build_skills_prompt,
    discover_skill_catalog,
    discover_skills,
    load_skill_body,
)


@pytest.fixture()
def skills_dir(tmp_path: Path) -> Path:
    """创建临时 skills 目录结构。"""

    git_ops = tmp_path / "git-operations"
    git_ops.mkdir()
    (git_ops / "SKILL.md").write_text(
        "---\nname: git-operations\ndescription: Git 操作指南\n---\n\n# Git\n\n操作 git 仓库。",
        encoding="utf-8",
    )

    jenkins = tmp_path / "jenkins-pipeline-analysis"
    jenkins.mkdir()
    (jenkins / "SKILL.md").write_text(
        "---\nname: jenkins-pipeline-analysis\ndescription: 分析 pipeline\n---\n\n# Jenkins\n\n分析。",
        encoding="utf-8",
    )

    # 没有 SKILL.md 的目录
    empty = tmp_path / "empty-skill"
    empty.mkdir()

    return tmp_path


class TestDiscoverSkillCatalog:
    """discover_skill_catalog frontmatter 解析。"""

    def test_discovers_with_frontmatter(self, skills_dir: Path) -> None:
        """发现并解析 frontmatter。"""

        result = discover_skill_catalog(skills_dir)
        assert "git-operations" in result
        assert result["git-operations"].name == "git-operations"
        assert result["git-operations"].description == "Git 操作指南"

    def test_empty_dir(self, tmp_path: Path) -> None:
        """空目录返回空字典。"""

        assert discover_skill_catalog(tmp_path) == {}


class TestLoadSkillBody:
    """load_skill_body 按需加载。"""

    def test_loads_body(self, skills_dir: Path) -> None:
        """加载 body 内容（不含 frontmatter）。"""

        body = load_skill_body(skills_dir, "git-operations")
        assert body is not None
        assert "# Git" in body
        assert "---" not in body

    def test_missing_skill(self, skills_dir: Path) -> None:
        """不存在的 skill 返回 None。"""

        assert load_skill_body(skills_dir, "nonexistent") is None


class TestBuildSkillCatalogPrompt:
    """build_skill_catalog_prompt 目录生成。"""

    def test_generates_catalog(self, skills_dir: Path) -> None:
        """生成包含名称和描述的目录。"""

        prompt = build_skill_catalog_prompt(skills_dir, ["git-operations"])
        assert "git-operations" in prompt
        assert "Git 操作指南" in prompt
        assert "load_skill" in prompt

    def test_empty_slugs(self, skills_dir: Path) -> None:
        """空 slug 列表返回空字符串。"""

        assert build_skill_catalog_prompt(skills_dir, []) == ""


class TestDiscoverSkills:
    """discover_skills 兼容接口。"""

    def test_discovers_valid_skills(self, skills_dir: Path) -> None:
        """发现包含 SKILL.md 的目录。"""

        result = discover_skills(skills_dir)
        assert "git-operations" in result
        assert "jenkins-pipeline-analysis" in result
        assert "empty-skill" not in result


class TestBuildSkillsPrompt:
    """build_skills_prompt 兼容接口。"""

    def test_builds_prompt(self, skills_dir: Path) -> None:
        """生成技能提示词。"""

        prompt = build_skills_prompt(skills_dir, ["git-operations"])
        assert "## Skill: git-operations" in prompt

    def test_empty_slugs(self, skills_dir: Path) -> None:
        """空 slug 列表返回空字符串。"""

        assert build_skills_prompt(skills_dir, []) == ""
