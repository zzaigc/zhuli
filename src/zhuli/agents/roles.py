"""内置智能体角色。

每个角色 = 一个独立提示词 + 独立结构化输出，可绑定不同 provider/capability。
新增角色只需继承 StructuredAgent 并在 factory 中注册即可（模块化零侵入）。
"""
from __future__ import annotations

from typing import cast

from ..llm.prompts import (
    ACTION_SCHEMA, PLANNER_SCHEMA, REFLECTION_SCHEMA, SKILL_SCHEMA,
    SYSTEM_PLANNER, SYSTEM_REFLECTION, SYSTEM_SKILL,
)
from ..llm.provider import chat_structured, chat_text
from ..llm.router import Capability
from ..memory.skills import Skill
from .base import BaseAgent, StructuredAgent
from .prompts import (
    ACTOR_AGENT_PROMPT, CRITIC_AGENT_PROMPT, CRITIC_SCHEMA, OBSERVER_AGENT_PROMPT,
    OBSERVER_SCHEMA, RISK_AGENT_PROMPT, RISK_SCHEMA,
)


class PlannerAgent(StructuredAgent):
    """规划智能体：把目标拆成带完成标准的子任务，并支持反馈重规划。"""

    def __init__(self, capability: str = "reasoning", provider: str | None = None) -> None:
        super().__init__(
            "planner", SYSTEM_PLANNER, PLANNER_SCHEMA, "emit_plan",
            capability=capability, provider=provider,
            description="把目标拆解为有序、可验证的子任务",
        )

    async def run(self, goal: str, extra_context: str = "") -> dict:
        prompt = f"目标：{goal}"
        if extra_context:
            prompt += f"\n补充上下文：{extra_context}"
        return await self._call(prompt)

    async def replan(self, goal: str, feedback: str, history: list[dict],
                     previous: list[str]) -> dict:
        tried = "\n".join(
            f"- {h['action'].get('action')} {h['action'].get('target')} => {str(h.get('result'))[:200]}"
            for h in history[-6:]
        )
        prompt = (
            f"目标：{goal}\n上一版子任务：{previous}\n已尝试（含结果）：\n{tried}\n\n"
            f"反馈/问题：{feedback}\n\n请重新规划——保留有效部分、换掉无效/循环部分，并给出新的完成标准。"
        )
        return await self._call(prompt)


class ObserverAgent(StructuredAgent):
    """观察智能体：蒸馏原始观察，只留下与当前子任务相关的信息。"""

    def __init__(self, capability: str = "default", provider: str | None = None) -> None:
        super().__init__(
            "observer", OBSERVER_AGENT_PROMPT, OBSERVER_SCHEMA, "emit_observation",
            capability=capability, provider=provider,
            description="蒸馏页面观察，提炼与当前子任务相关的元素",
        )

    async def run(self, raw_observation: str, current_subtask: str,
                  verification: list[str] | None = None,
                  skill_hints: str = "") -> dict:
        prompt = (
            f"当前子任务：{current_subtask}\n"
            f"完成标准：{verification or ['无']}\n"
            f"{skill_hints}"
            f"原始观察：\n{raw_observation}"
        )
        return await self._call(prompt)


class ActorAgent(StructuredAgent):
    """执行智能体：提出下一步动作。"""

    def __init__(self, capability: str = "reasoning", provider: str | None = None,
                 temperature: float = 0.2, name: str = "actor") -> None:
        # name/temperature 可差异化 → 蜂巢模式下可组建多个「性格不同」的执行体
        super().__init__(
            name, ACTOR_AGENT_PROMPT, ACTION_SCHEMA, "emit_action",
            capability=capability, provider=provider,
            description="决策下一步具体动作", temperature=temperature,
        )

    async def run(self, observation: str, current_subtask: str, verification: list[str] | None,
                  history: list[dict], skills_text: str = "", feedback: str = "") -> dict:
        hist = "\n".join(
            f"- {h['action'].get('action')} {h['action'].get('target')} => {str(h.get('result'))[:80]}"
            for h in history[-5:]
        )
        prompt = (
            f"当前子任务：{current_subtask}\n"
            f"完成标准：{verification or ['无']}\n"
            f"{skills_text}"
            f"观察：\n{observation}\n\n"
            f"最近动作与结果：\n{hist}\n"
        )
        if feedback:
            prompt += f"\n批评智能体的意见（务必修正后再输出）：\n{feedback}\n"
        prompt += "\n请输出唯一下一步动作（务必填写 thought 与 expected_effect）。"
        return await self._call(prompt)


class CriticAgent(StructuredAgent):
    """批评智能体：执行前审查动作；同时承担执行后的反思校验。"""

    def __init__(self, capability: str = "reasoning", provider: str | None = None) -> None:
        super().__init__(
            "critic", CRITIC_AGENT_PROMPT, CRITIC_SCHEMA, "emit_critique",
            capability=capability, provider=provider,
            description="执行前审查动作，执行后反思校验",
        )

    async def run(self, proposal: dict, current_subtask: str,
                  verification: list[str] | None, known_ids: list[str]) -> dict:
        prompt = (
            f"当前子任务：{current_subtask}\n完成标准：{verification or ['无']}\n"
            f"观察中真实存在的元素 id：{known_ids[:60]}\n"
            f"待审查动作：{proposal}\n\n请给出审查结论。"
        )
        return await self._call(prompt)

    async def reflect(self, goal: str, current_subtask: str, verification: list[str] | None,
                      history: list[dict], max_steps: int) -> dict:
        """执行后的反思校验（复用 llm/prompts 的 REFLECTION_SCHEMA）。"""
        recent = history[-6:]
        steps_desc = "\n".join(
            f"{i + 1}. 动作={h['action'].get('action')} 目标={h['action'].get('target')} "
            f"结果={str(h['result'])[:200]}"
            for i, h in enumerate(recent)
        ) or "(尚无执行记录)"
        verify_desc = "\n".join(f"- {v}" for v in (verification or [])) or "(无明确标准，按整体目标判断)"
        prompt = (
            f"总体目标：{goal}\n当前子任务：{current_subtask}\n"
            f"当前子任务的完成标准：\n{verify_desc}\n"
            f"已执行步数：{len(history)} / 上限 {max_steps}\n"
            f"最近执行记录：\n{steps_desc}\n\n"
            "请判断：当前子任务是否达成（current_done）？下一步走向（continue/replan/done/escalate）？"
        )
        messages = [
            {"role": "system", "content": SYSTEM_REFLECTION},
            {"role": "user", "content": prompt},
        ]
        result = await chat_structured(
            cast(Capability, self.capability), messages, schema=REFLECTION_SCHEMA,
            schema_name="emit_reflection", schema_description="反思校验结果",
            provider=self.provider,
        )
        result.setdefault("current_done", False)
        result.setdefault("next", None)
        result.setdefault("thought", "")
        return result


class RiskAgent(StructuredAgent):
    """风险智能体：给待执行动作做敏感度分级（与规则护栏互补）。"""

    def __init__(self, capability: str = "default", provider: str | None = None) -> None:
        super().__init__(
            "risk", RISK_AGENT_PROMPT, RISK_SCHEMA, "emit_risk",
            capability=capability, provider=provider,
            description="评估动作风险等级（safe/confirm/danger）",
        )

    async def run(self, proposal: dict, url: str = "") -> dict:
        prompt = f"当前页面：{url or '未知'}\n待评估动作：{proposal}\n\n请给出风险等级。"
        return await self._call(prompt)


class SkillMinerAgent(StructuredAgent):
    """技能挖掘智能体：把成功任务沉淀为可复用技能。"""

    def __init__(self, capability: str = "reasoning", provider: str | None = None) -> None:
        super().__init__(
            "skill_miner", SYSTEM_SKILL, SKILL_SCHEMA, "emit_skill",
            capability=capability, provider=provider,
            description="从成功任务中提炼可复用技能",
        )

    async def run(self, goal: str, procedure: str) -> dict:
        prompt = f"本次任务目标：{goal}\n\n执行过程：\n{procedure}\n\n请提炼成可复用技能。"
        return await self._call(prompt)

    async def merge(self, skill: Skill, new_procedure: str) -> str:
        """把新经验合并进既有技能，返回精炼后的步骤文本。"""
        messages = [
            {"role": "system", "content": (
                "你负责把「已有技能步骤」与「本次新经验」合并成更通用、更精简的可复用步骤。"
                "只输出合并后的步骤文本，分条列出，不要解释。"
            )},
            {"role": "user", "content": (
                f"技能名：{skill.name}\n触发条件：{skill.trigger}\n已有步骤：\n{skill.procedure}\n\n"
                f"本次新经验：\n{new_procedure}\n\n请输出合并后的步骤（保留通用的、去掉本次特有的细节）。"
            )},
        ]
        text = await chat_text(cast(Capability, self.capability), messages, provider=self.provider)
        return (text or "").strip()


class SkillAgent(BaseAgent):
    """专项智能体：由「学到的技能」升格而成（用得越多，系统模块越多）。

    它本身不调用 LLM，而是把成熟经验作为上下文提供给执行智能体；
    注册进 Registry 后即成为系统里的一个新模块。
    """

    kind = "skill"

    def __init__(self, skill: Skill) -> None:
        self.name = f"skill:{skill.name}"
        self.description = f"专项经验：{skill.trigger}"
        self.skill = skill

    async def run(self, **kwargs) -> dict:
        return {"name": self.skill.name, "trigger": self.skill.trigger,
                "procedure": self.skill.procedure}

    def info(self) -> dict:
        info = super().info()
        info.update({
            "usage_count": self.skill.usage_count,
            "success_count": self.skill.success_count,
            "procedure": self.skill.procedure[:200],
        })
        return info
