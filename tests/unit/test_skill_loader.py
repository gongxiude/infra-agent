# -*- coding: utf-8 -*-

"""Skill 加载器测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from infra_agent.skills.loader import build_skills_prompt, discover_skills


@pytest.fixture()
def skills_dir(tmp_path: Path) -> Path:
    """创建临时 skills 目录结构。"""

    git_ops = tmp_path / "git-operations"
    git_ops.mkdir()
    (git_ops / "SKILL.md").write_text("# Git Operations\n\n操作 git 仓库。", encoding="utf-8")

    jenkins = tmp_path / "jenkins-pipeline-analysis"
    jenkins.mkdir()
    (jenkins / "SKILL.md").write_text("# Jenkins\n\n分析 pipeline。", encoding="utf-8")

    # 没有 SKILL.md 的目录应被忽略
    empty = tmp_path / "empty-skill"
    empty.mkdir()

    return tmp_path


class TestDiscoverSkills:
    """discover_skills 发现逻辑。"""

    def test_discovers_valid_skills(self, skills_dir: Path) -> None:
        """发现包含 SKILL.md 的目录。"""

        result = discover_skills(skills_dir)
        assert "git-operations" in result
        assert "jenkins-pipeline-analysis" in result
        assert "empty-skill" not in result

    def test_empty_dir(self, tmp_path: Path) -> None:
        """空目录返回空字典。"""

        assert discover_skills(tmp_path) == {}

    def test_nonexistent_dir(self) -> None:
        """不存在的目录返回空字典。"""

        assert discover_skills(Path("/nonexistent")) == {}


class TestBuildSkillsPrompt:
    """build_skills_prompt 拼接逻辑。"""

    def test_builds_prompt_for_existing_slugs(self, skills_dir: Path) -> None:
        """为存在的 slug 生成提示词。"""

        prompt = build_skills_prompt(skills_dir, ["git-operations"])
        assert "## Skill: git-operations" in prompt
        assert "操作 git 仓库" in prompt

    def test_multiple_slugs(self, skills_dir: Path) -> None:
        """多个 slug 拼接。"""

        prompt = build_skills_prompt(skills_dir, ["git-operations", "jenkins-pipeline-analysis"])
        assert "## Skill: git-operations" in prompt
        assert "## Skill: jenkins-pipeline-analysis" in prompt

    def test_missing_slug_skipped(self, skills_dir: Path) -> None:
        """不存在的 slug 被跳过。"""

        prompt = build_skills_prompt(skills_dir, ["nonexistent"])
        assert prompt == ""

    def test_empty_slugs(self, skills_dir: Path) -> None:
        """空 slug 列表返回空字符串。"""

        assert build_skills_prompt(skills_dir, []) == ""
