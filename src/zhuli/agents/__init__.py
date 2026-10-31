"""多智能体包：模块化、可插拔、随使用增长。

- `base` / `registry`：智能体统一接口与注册表（动态注册 = 系统模块可增长）
- `roles`          ：内置角色（规划 / 观察 / 执行 / 批评 / 风险 / 技能挖掘 + 技能专项）
- `tool`           ：外部工具智能体（CodeBuddy / Trae / OpenCode 作为远程智能体）
- `coordinator`    ：多智能体协调器（并发批评+风险、自我纠错、可降级单脑）
"""
from __future__ import annotations

from ..config.schemas import Settings
from ..integrations.base import BaseConnector
from .base import BaseAgent, StructuredAgent
from .blackboard import Blackboard
from .coordinator import Coordinator
from .hive import HiveCoordinator
from .registry import AgentRegistry
from .roles import (
    ActorAgent, CriticAgent, ObserverAgent, PlannerAgent,
    RiskAgent, SkillAgent, SkillMinerAgent,
)
from .tool import ToolAgent

__all__ = [
    "BaseAgent", "StructuredAgent", "AgentRegistry", "Coordinator", "HiveCoordinator",
    "Blackboard",
    "PlannerAgent", "ObserverAgent", "ActorAgent", "CriticAgent",
    "RiskAgent", "SkillMinerAgent", "SkillAgent", "ToolAgent",
    "build_registry", "build_coordinator",
]

# 智能体名 -> (默认能力, 类)；配置 agents 段可覆盖 provider 与 capability
_DEFAULT_AGENTS: dict[str, tuple] = {
    "planner": ("reasoning", PlannerAgent),
    "observer": ("default", ObserverAgent),
    "actor": ("reasoning", ActorAgent),
    "critic": ("reasoning", CriticAgent),
    "risk": ("default", RiskAgent),
    "skill_miner": ("reasoning", SkillMinerAgent),
}


def build_registry(settings: Settings,
                   connectors: dict[str, BaseConnector] | None = None) -> AgentRegistry:
    """按配置构建并注册智能体团队（内置角色 + 外部工具）。

    每个角色可绑定不同的 provider/capability —— 即「不同智能体跑在不同模型上」。
    """
    reg = AgentRegistry()
    cfg = getattr(settings, "agents", {}) or {}
    for name, (default_cap, cls) in _DEFAULT_AGENTS.items():
        ac = cfg.get(name)
        provider = ac.provider if ac else None
        capability = ac.capability if ac else default_cap
        reg.register(cls(capability=capability, provider=provider))
    for name, conn in (connectors or {}).items():
        reg.register(ToolAgent(name, conn))
    return reg


def build_coordinator(settings: Settings, registry: AgentRegistry, sink=None
                      ) -> Coordinator | HiveCoordinator:
    """按配置构建协调器：蜂巢模式（群体共识）或常规多智能体流水线。

    v0.2.0：运行时覆盖（agents.runtime）优先于配置文件，但不改写文件；
    重启后恢复为配置值。
    """
    from .runtime import effective_hive

    hive_enabled, hive_size, hive_mode = effective_hive(
        settings.policy.hive_mode, settings.policy.hive_size,
        getattr(settings.policy, "hive_size_mode", "manual"))
    if hive_enabled and settings.policy.multi_agent:
        return HiveCoordinator(registry, sink, settings, hive_size, hive_mode)
    return Coordinator(registry, sink, settings)
