# -*- coding: utf-8 -*-

"""策略输入 Guardrail，在 Agent 执行前验证任务是否被策略允许。"""

from __future__ import annotations

from agents import (
    Agent,
    GuardrailFunctionOutput,
    InputGuardrail,
    RunContextWrapper,
)

from infra_agent.tools.context import AgentContext


async def _check_policy(
    ctx: RunContextWrapper[AgentContext],
    agent: Agent,
    input: str | list,
) -> GuardrailFunctionOutput:
    """检查策略是否允许执行。"""

    policy = ctx.context.policy
    if not policy.allowed:
        return GuardrailFunctionOutput(
            output_info={"reason": policy.reason, "tier": policy.tier},
            tripwire_triggered=True,
        )
    return GuardrailFunctionOutput(
        output_info={"status": "allowed", "tier": policy.tier},
        tripwire_triggered=False,
    )


policy_input_guardrail = InputGuardrail(guardrail_function=_check_policy)
