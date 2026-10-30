"""多智能体协调器（Coordinator）。

编排「规划 → 观察蒸馏 → 决策（执行）→ 批评 → 风险 → 反思 → 技能挖掘」流水线：

- **分布式**：每个智能体可绑定不同 provider / capability（配置 `agents` 段）；
- **并发**：批评智能体与风险智能体对同一动作**并行**推理，避免串行等待；
- **自我纠错**：批评结果为 revise 时，让执行智能体带批评重决策；abort 则触发重规划；
- **可降级**：`policy.multi_agent=false` 时回退为单脑模式（不启用观察蒸馏/批评/风险）。
"""
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Literal, Optional, TypeVar, cast

from ..config.schemas import Settings
from ..core.events import AgentEvent
from ..llm.prompts import ACTION_SCHEMA, SYSTEM_AGENT
from ..llm.provider import chat_structured
from ..memory.skills import Skill
from .base import BaseAgent
from .registry import AgentRegistry
from .roles import ActorAgent, CriticAgent, ObserverAgent, PlannerAgent, RiskAgent, SkillMinerAgent

Sink = Optional[Callable[[AgentEvent], Awaitable[None]]]


async def _none() -> None:
    return None


_T = TypeVar("_T", bound=BaseAgent)
AgentStage = Literal["plan", "observe", "decide", "critique", "risk", "reflect", "skill", "delegate"]


class Coordinator:
    def __init__(self, registry: AgentRegistry, sink: Sink = None,
                 settings: Optional[Settings] = None) -> None:
        self.registry = registry
        self.sink = sink
        self._settings = settings

    @property
    def settings(self) -> Settings:
        if self._settings is None:
            from ..config.settings import get_settings

            self._settings = get_settings()
        return self._settings

    def _get(self, name: str, cls: type[_T]) -> Optional[_T]:
        """按类型取出已注册智能体（便于调用各角色的专有方法）。"""
        return cast(Optional[_T], self.registry.get(name))

    async def _emit(self, agent: str, stage: AgentStage, summary: str = "",
                    verdict: str | None = None) -> None:
        if self.sink:
            await self.sink(
                AgentEvent(type="agent", agent=agent, stage=stage, summary=summary[:400], verdict=verdict)
            )

    def _single_brain(self) -> bool:
        """单脑模式：不启用多智能体协作（回退为传统单一决策大脑）。"""
        return not self.settings.policy.multi_agent

    # ---------- 规划 ----------
    async def plan(self, goal: str, extra_context: str = "") -> dict:
        if self._single_brain():
            from ..core.planner import decompose

            return await decompose(goal, extra_context=extra_context)
        agent = self._get("planner", PlannerAgent)
        if agent is None:
            raise RuntimeError("未注册规划智能体 planner")
        result = await agent.run(goal, extra_context)
        await self._emit("planner", "plan", summary=result.get("thought") or "已生成计划")
        return result

    async def replan(self, goal: str, feedback: str, history: list[dict], previous: list[str]) -> dict:
        if self._single_brain():
            from ..core.planner import replan as core_replan

            return await core_replan(goal, feedback, history, previous)
        agent = self._get("planner", PlannerAgent)
        if agent is None:
            raise RuntimeError("未注册规划智能体 planner")
        result = await agent.replan(goal, feedback, history, previous)
        await self._emit("planner", "plan", summary=result.get("thought") or "已重规划")
        return result

    # ---------- 观察蒸馏 ----------
    async def observe(self, raw_observation: str, subtask: str,
                      verification: list[str] | None, skill_hints: str = "") -> dict:
        """返回 {} 表示未启用（调用方直接使用原始观察）。"""
        if not (self.settings.policy.multi_agent and self.settings.policy.observer_enabled):
            return {}
        agent = self._get("observer", ObserverAgent)
        if agent is None:
            return {}
        result = await agent.run(raw_observation, subtask, verification, skill_hints)
        await self._emit("observer", "observe", summary=result.get("summary", ""))
        return result

    # ---------- 决策（执行 + 批评 + 风险 并发）----------
    async def decide(self, *, observation: str, subtask: str, verification: list[str] | None,
                     history: list[dict], skills_text: str = "",
                     known_ids: list[str] | None = None, url: str = "") -> dict:
        if self._single_brain():
            return await self._fallback_decide(
                observation=observation, subtask=subtask, verification=verification,
                history=history, skills_text=skills_text, url=url,
            )
        actor = self._get("actor", ActorAgent)
        if actor is None:
            raise RuntimeError("未注册执行智能体 actor")

        proposal = await actor.run(observation, subtask, verification, history, skills_text)
        await self._emit("actor", "decide", summary=str(proposal.get("thought") or "")[:300])

        out = {"proposal": proposal, "criticism": None, "risk": None, "abort": False}
        if not self.settings.policy.multi_agent:
            return out

        critic = self._get("critic", CriticAgent)
        risk = self._get("risk", RiskAgent)

        if self.settings.policy.self_critique and critic:
            # 批评与风险「并行」推理（分布式协作的核心加速点）
            criticism, risk_result = await asyncio.gather(
                critic.run(proposal, subtask, verification, known_ids or []),
                risk.run(proposal, url) if risk else _none(),
            )
            out["criticism"] = criticism
            out["risk"] = risk_result
            verdict = criticism.get("verdict")
            await self._emit("critic", "critique",
                             summary=criticism.get("criticism") or criticism.get("thought") or "",
                             verdict=verdict)

            if verdict == "revise":
                better = criticism.get("better_action") or {}
                if better.get("action"):
                    proposal = {**proposal, **{k: v for k, v in better.items() if v}}
                else:
                    proposal = await actor.run(
                        observation, subtask, verification, history, skills_text,
                        feedback=criticism.get("criticism", ""),
                    )
                out["proposal"] = proposal
                # 修正后的动作重新评估风险
                if risk:
                    out["risk"] = await risk.run(proposal, url)
            elif verdict == "abort":
                out["abort"] = True
        elif risk:
            out["risk"] = await risk.run(proposal, url)

        risk_out = out.get("risk")
        if isinstance(risk_out, dict):
            await self._emit("risk", "risk", summary=str(risk_out.get("reason", "")),
                             verdict=risk_out.get("level"))
        return out

    # ---------- 单脑回退：直接以单一决策大脑产出动作（行为等同旧版）----------
    async def _fallback_decide(self, *, observation: str, subtask: str,
                               verification: list[str] | None, history: list[dict],
                               skills_text: str = "", url: str = "") -> dict:
        sys = SYSTEM_AGENT
        if skills_text:
            sys += f"\n\n已掌握的可复用技能（可参考沿用）：\n{skills_text}"
        hist = "\n".join(
            f"- {h['action'].get('action')} {h['action'].get('target')} => {str(h.get('result'))[:80]}"
            for h in history[-5:]
        )
        messages = [
            {"role": "system", "content": sys},
            {"role": "user", "content": (
                f"当前子任务：{subtask}\n完成标准：{verification or ['无']}\n"
                f"{observation}\n\n最近动作与结果:\n{hist}\n\n请输出下一步动作。"
            )},
        ]
        proposal = await chat_structured(
            "reasoning", messages, schema=ACTION_SCHEMA,
            schema_name="emit_action", schema_description="下一步结构化动作",
        )
        return {"proposal": proposal, "criticism": None, "risk": None, "abort": False}

    # ---------- 反思 ----------
    async def reflect(self, goal: str, subtask: str, verification: list[str] | None,
                      history: list[dict], max_steps: int) -> dict:
        if self._single_brain():
            from ..core.reflection import reflect as core_reflect

            return await core_reflect(goal, subtask, verification, history, max_steps)
        critic = self._get("critic", CriticAgent)
        if critic is None:
            raise RuntimeError("未注册批评智能体 critic")
        result = await critic.reflect(goal, subtask, verification, history, max_steps)
        await self._emit("critic", "reflect", summary=result.get("reason", ""), verdict=result.get("status"))
        return result

    # ---------- 技能挖掘 ----------
    async def mine_skill(self, goal: str, procedure: str) -> dict:
        agent = self._get("skill_miner", SkillMinerAgent)
        if agent is None:
            return {}
        result = await agent.run(goal, procedure)
        await self._emit("skill_miner", "skill", summary=result.get("name", ""))
        return result

    async def merge_skill(self, skill: Skill, new_procedure: str) -> str:
        agent = self._get("skill_miner", SkillMinerAgent)
        if agent is None:
            return new_procedure
        merged = await agent.merge(skill, new_procedure)
        await self._emit("skill_miner", "skill", summary=f"迭代技能：{skill.name}")
        return merged or new_procedure

    # ---------- 派发给外部工具 ----------
    async def delegate(self, tool_name: str, task: str, page=None, on_output=None) -> dict:
        agent = self.registry.get(f"tool:{tool_name}")
        if agent is None:
            return {"ok": False, "tool": tool_name, "result": f"未注册外部工具智能体：{tool_name}"}
        result = await agent.run(task, page=page, on_output=on_output)  # type: ignore[arg-type]
        await self._emit(f"tool:{tool_name}", "delegate", summary=task[:200])
        return result

    # ---------- 经验上下文（检索技能 + 已升格专项智能体）----------
    def skills_context(self, skills: Optional[list[Skill]] = None) -> str:
        """把「本次检索到的技能」与「已升格的专项智能体」合成为可复用经验上下文。"""
        parts: list[str] = []
        names = set()
        for s in skills or []:
            parts.append(f"- 【{s.name}】触发: {s.trigger}\n  步骤: {s.procedure}")
            names.add(s.name)
        for a in self.registry.skill_agents():
            if a.skill.name not in names:
                parts.append(f"- 【{a.skill.name}】触发: {a.skill.trigger}\n  步骤: {a.skill.procedure}")
        if not parts:
            return ""
        return "可复用的成熟经验（相同或相似场景优先沿用，也可视情况调整）：\n" + "\n".join(parts)

    # ---------- 技能升格（用得越多，模块越多）----------
    def promote(self, skill: Skill) -> BaseAgent | None:
        if not skill:
            return None
        promoted = self.registry.promote_skill(skill, self.settings.policy.skill_promote_threshold)
        return promoted
