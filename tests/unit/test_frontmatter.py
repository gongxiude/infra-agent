# -*- coding: utf-8 -*-

"""Frontmatter 解析器测试。"""

from __future__ import annotations

from infra_agent.agents.parser import parse_frontmatter


class TestParseFrontmatter:
    """parse_frontmatter 解析逻辑。"""

    def test_valid_frontmatter(self) -> None:
        """正常 frontmatter 解析。"""

        text = "---\nname: test\ndescription: hello\n---\n\n# Body\n\nContent."
        meta, body = parse_frontmatter(text)
        assert meta == {"name": "test", "description": "hello"}
        assert body == "# Body\n\nContent."

    def test_no_frontmatter(self) -> None:
        """无 frontmatter 返回空 dict。"""

        text = "# Just a markdown file\n\nNo frontmatter here."
        meta, body = parse_frontmatter(text)
        assert meta == {}
        assert "Just a markdown file" in body

    def test_complex_frontmatter(self) -> None:
        """复杂 YAML frontmatter。"""

        text = "---\nname: agent\ntools: [read_file, write_file]\ntier: 2\n---\n\nInstructions."
        meta, body = parse_frontmatter(text)
        assert meta["name"] == "agent"
        assert meta["tools"] == ["read_file", "write_file"]
        assert meta["tier"] == 2
        assert body == "Instructions."

    def test_malformed_yaml(self) -> None:
        """畸形 YAML 返回空 dict。"""

        text = "---\n: invalid yaml [[\n---\n\nBody."
        meta, body = parse_frontmatter(text)
        assert meta == {}

    def test_no_closing_delimiter(self) -> None:
        """缺少结束分隔符。"""

        text = "---\nname: test\nNo closing delimiter"
        meta, body = parse_frontmatter(text)
        assert meta == {}
