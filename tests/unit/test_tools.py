# -*- coding: utf-8 -*-

"""工具函数与策略过滤测试。"""

from __future__ import annotations

from infra_agent.core.models import PolicyDecision
from infra_agent.tools import ALL_TOOLS, get_tools_for_policy


class TestGetToolsForPolicy:
    """get_tools_for_policy 过滤逻辑。"""

    def test_empty_allowed_returns_empty(self) -> None:
        """allowed_tools 为空时返回空列表。"""

        policy = PolicyDecision(allowed_tools=[])
        assert get_tools_for_policy(policy) == []

    def test_read_only_policy(self) -> None:
        """分析类任务只返回只读工具。"""

        policy = PolicyDecision(allowed_tools=["inspect_workspace", "read_file"])
        tools = get_tools_for_policy(policy)
        names = {t.name for t in tools}
        assert names == {"inspect_workspace", "read_file"}

    def test_change_policy(self) -> None:
        """变更类任务返回读写工具。"""

        policy = PolicyDecision(
            allowed_tools=["inspect_workspace", "read_file", "write_file", "git_status", "git_diff"]
        )
        tools = get_tools_for_policy(policy)
        names = {t.name for t in tools}
        assert names == {"inspect_workspace", "read_file", "write_file", "git_status", "git_diff"}

    def test_denied_tools_excluded(self) -> None:
        """denied_tools 中的工具应被排除。"""

        policy = PolicyDecision(
            allowed_tools=["inspect_workspace", "read_file", "write_file"],
            denied_tools=["write_file"],
        )
        tools = get_tools_for_policy(policy)
        names = {t.name for t in tools}
        assert "write_file" not in names
        assert names == {"inspect_workspace", "read_file"}

    def test_unknown_tool_ignored(self) -> None:
        """allowed_tools 中不存在的工具名被跳过。"""

        policy = PolicyDecision(allowed_tools=["inspect_workspace", "nonexistent_tool"])
        tools = get_tools_for_policy(policy)
        names = {t.name for t in tools}
        assert names == {"inspect_workspace"}

    def test_all_tools_registered(self) -> None:
        """ALL_TOOLS 包含 7 个预期工具。"""

        expected = {
            "inspect_workspace", "read_file", "write_file",
            "git_status", "git_diff", "load_skill", "read_skill_file",
        }
        assert set(ALL_TOOLS.keys()) == expected
