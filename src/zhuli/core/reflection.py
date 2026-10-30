"""反思校验：每步后评估是否继续 / 重规划 / 完成 / 升级。

基于：当前子任务的完成标准、最近动作与结果、是否出现重复循环、是否超出最大步数。
"""
from __future__ import annotations

from ..llm.prompts import REFLECTION_SCHEMA, SYSTEM_REFLECTION
from ..llm.provider import chat_structured


async def reflect(
    goal: str,
    current_subtask: str,
    verification: list[str] | None,
    history: list[dict],
    max_steps: int,
) -> dict:
    """返回 {thought, status: continue|replan|done|escalate, reason, current_done, next}。

    除 LLM 判定外，orchestrator 还会叠加确定性的循环/卡死检测，二者取更保守结论。
    """
    recent = history[-6:]
    steps_desc = "\n".join(
        f"{i + 1}. 动作={h['action'].get('action')} 目标={h['action'].get('target')} "
        f"结果={str(h['result'])[:200]}"
        for i, h in enumerate(recent)
    )
    if not steps_desc:
        steps_desc = "(尚无执行记录)"
    verify_desc = "\n".join(f"- {v}" for v in (verification or [])) or "(无明确标准，按整体目标判断)"

    user_msg = (
        f"总体目标：{goal}\n"
        f"当前子任务：{current_subtask}\n"
        f"当前子任务的完成标准：\n{verify_desc}\n"
        f"已执行步数：{len(history)} / 上限 {max_steps}\n"
        f"最近执行记录：\n{steps_desc}\n\n"
        "请判断：当前子任务是否达成（current_done）？下一步走向（continue/replan/done/escalate）？"
    )
    messages = [
        {"role": "system", "content": SYSTEM_REFLECTION},
        {"role": "user", "content": user_msg},
    ]
    result = await chat_structured(
        "reasoning",
        messages,
        schema=REFLECTION_SCHEMA,
        schema_name="emit_reflection",
        schema_description="反思校验结果",
    )
    result.setdefault("current_done", False)
    result.setdefault("next", None)
    result.setdefault("thought", "")
    return result
