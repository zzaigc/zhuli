"""多智能体基座。

设计要点（对应「多智能体 + 多提示词 + 分布式模块化」）：
  - 每个智能体拥有**独立 system prompt** 与**独立结构化输出 Schema**（多提示词）；
  - 每个智能体可绑定**不同 provider / capability** → 可跑在不同模型或不同供应商上（分布式）；
  - 统一 `run()` 接口 → 注册到 Registry 后由 Coordinator 编排，新增智能体零侵入。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal, cast

from ..llm.provider import chat_structured
from ..llm.router import Capability


class BaseAgent(ABC):
    """智能体统一接口。"""

    name: str = "agent"
    description: str = ""
    kind: Literal["llm", "tool", "skill"] = "llm"

    @abstractmethod
    async def run(self, *args: Any, **kwargs: Any) -> dict:
        """统一执行入口（各子类可收窄为具名参数，故基类用 *args 保持兼容）。"""

    def info(self) -> dict:
        return {"name": self.name, "kind": self.kind, "description": self.description}


class StructuredAgent(BaseAgent, ABC):
    """基于 LLM 结构化输出（JSON Schema 约束）的智能体（由子类实现 run）。"""

    kind = "llm"

    def __init__(
        self,
        name: str,
        system_prompt: str,
        schema: dict,
        schema_name: str,
        *,
        capability: str = "reasoning",
        provider: str | None = None,
        description: str = "",
        schema_description: str = "",
        temperature: float = 0.2,
    ) -> None:
        self.name = name
        self.description = description
        self.capability = capability
        self.provider = provider
        self._system = system_prompt
        self._schema = schema
        self._schema_name = schema_name
        self._schema_desc = schema_description or f"{name} 的结构化输出"
        self._temperature = temperature

    def info(self) -> dict:
        """对外描述：只暴露模型与供应商名称，绝不外泄 base_url / api_key。"""
        info = super().info()
        info.update({
            "capability": self.capability,
            "provider": self.provider or "",
            "model": self._model_id(),
        })
        return info

    def _model_id(self) -> str:
        try:
            from ..llm.router import resolve_for

            return resolve_for(self.provider, self.capability)[2]
        except Exception:
            return ""

    async def _call(self, user_prompt: str) -> dict:
        messages = [
            {"role": "system", "content": self._system},
            {"role": "user", "content": user_prompt},
        ]
        return await chat_structured(
            cast(Capability, self.capability),
            messages,
            schema=self._schema,
            schema_name=self._schema_name,
            schema_description=self._schema_desc,
            temperature=self._temperature,
            provider=self.provider,
        )
