"""任务规划器：把高层目标拆成有序、可验证的子任务清单。

结果由 orchestrator 维护进度；当 Reflection 判定卡死/偏离时由 orchestrator 触发重规划（replan）。
"""
from __future__ import annotations

from ..llm.prompts import PLANNER_SCHEMA, SYSTEM_PLANNER
from ..llm.provider import chat_structured


async def decompose(goal: str, *, extra_context: str = "") -> dict:
    """返回 {thought, subtasks, verification, tools, current, needs_replan}。"""
    user_msg = f"目标：{goal}"
    if extra_context:
        user_msg += f"\n补充上下文：{extra_context}"
    messages = [
        {"role": "system", "content": SYSTEM_PLANNER},
        {"role": "user", "content": user_msg},
    ]
    return await chat_structured(
        "reasoning",
        messages,
        schema=PLANNER_SCHEMA,
        schema_name="emit_plan",
        schema_description="任务分解结果",
    )


async def replan(
    goal: str,
    feedback: str,
    history: list[dict],
    previous_subtasks: list[str],
) -> dict:
    """基于失败反馈重新规划。返回结构与 decompose 一致。"""
    tried = "\n".join(
        f"- {h['action'].get('action')} {h['action'].get('target')} => {str(h.get('result'))[:200]}"
        for h in history[-6:]
    )
    user_msg = (
        f"目标：{goal}\n"
        f"上一版子任务：{previous_subtasks}\n"
        f"已尝试（含结果）：\n{tried}\n\n"
        f"反馈/问题：{feedback}\n\n"
        "请重新规划——保留有效的部分、换掉无效/循环的部分，并给出新的完成标准。"
    )
    messages = [
        {"role": "system", "content": SYSTEM_PLANNER},
        {"role": "user", "content": user_msg},
    ]
    return await chat_structured(
        "reasoning",
        messages,
        schema=PLANNER_SCHEMA,
        schema_name="emit_plan",
        schema_description="重规划结果",
    )
