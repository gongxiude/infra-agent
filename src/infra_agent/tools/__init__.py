# -*- coding: utf-8 -*-

"""工具注册表与策略过滤。"""

from __future__ import annotations

from infra_agent.core.models import PolicyDecision
from infra_agent.tools.workspace_tools import (
    git_diff,
    git_status,
    inspect_workspace,
    read_file,
    write_file,
)

# 全部可用工具，键名与 PolicyEngine 输出的 allowed_tools 一致
ALL_TOOLS = {
    "inspect_workspace": inspect_workspace,
    "read_file": read_file,
    "write_file": write_file,
    "git_status": git_status,
    "git_diff": git_diff,
}


def get_tools_for_policy(policy: PolicyDecision) -> list:
    """根据策略决策过滤工具列表。

    Args:
        policy: 策略决策对象

    Returns:
        允许使用的工具列表。若 allowed_tools 为空则返回空列表（安全默认）。
    """

    if not policy.allowed_tools:
        return []
    tools = []
    for name in policy.allowed_tools:
        tool = ALL_TOOLS.get(name)
        if tool is not None and name not in policy.denied_tools:
            tools.append(tool)
    return tools
