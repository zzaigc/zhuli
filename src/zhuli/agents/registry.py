"""智能体注册表：系统的「模块仓库」。

- 内置智能体在启动时注册；外部工具作为远程智能体注册；
- **学到的技能达到使用阈值后会自动升格为专项智能体并注册进来**
  → 系统「越用越多模块、越用越聪明」；
- 新增智能体只需 `register()`，Coordinator 自动可用（模块化零侵入）。
"""
from __future__ import annotations

from typing import Literal, cast

from ..memory.skills import Skill
from .base import BaseAgent
from .roles import SkillAgent


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    # ---------- 注册/注销 ----------
    def register(self, agent: BaseAgent) -> BaseAgent:
        self._agents[agent.name] = agent
        return agent

    def unregister(self, name: str) -> None:
        self._agents.pop(name, None)

    def get(self, name: str) -> BaseAgent | None:
        return self._agents.get(name)

    def all(self) -> list[BaseAgent]:
        return list(self._agents.values())

    def by_kind(self, kind: Literal["llm", "tool", "skill"]) -> list[BaseAgent]:
        return [a for a in self._agents.values() if a.kind == kind]

    def tool_agents(self) -> list[BaseAgent]:
        return self.by_kind("tool")

    def skill_agents(self) -> list[SkillAgent]:
        return [cast(SkillAgent, a) for a in self._agents.values() if a.kind == "skill"]

    # ---------- 技能升格 ----------
    def has_skill_agent(self, skill_name: str) -> bool:
        return f"skill:{skill_name}" in self._agents

    def promote_skill(self, skill: Skill, threshold: int = 2) -> SkillAgent | None:
        """技能成功复用达到阈值即升格为专项智能体（系统模块随使用增长）。"""
        if not skill.name or skill.success_count < threshold:
            return None
        if self.has_skill_agent(skill.name):
            return cast(SkillAgent, self._agents[f"skill:{skill.name}"])
        return cast(SkillAgent, self.register(SkillAgent(skill)))

    # ---------- 对外描述 ----------
    def describe(self) -> list[dict]:
        """对外描述（供控制台展示团队名册），字段名稳定：name/role/..."""
        out = []
        for a in self._agents.values():
            info = a.info()
            info.setdefault("role", info.get("description", ""))
            out.append(info)
        return out

    def __len__(self) -> int:
        return len(self._agents)
