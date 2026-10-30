"""外部工具智能体：把 CodeBuddy / Trae / OpenCode 等外部 AI 编码工具当作「远程智能体」。

它们复用 browser / computer 能力（连接器内部实现），对 Coordinator 呈现为
与其他智能体一致的 `run()` 接口 —— 因此任务可以直接「派给」它们执行。
"""
from __future__ import annotations

from ..integrations.base import BaseConnector
from .base import BaseAgent


class ToolAgent(BaseAgent):
    """外部工具智能体：对外表现为智能体，对内复用连接器（browser/computer）。"""

    kind = "tool"

    def __init__(self, name: str, connector: BaseConnector) -> None:
        self.name = f"tool:{name}"
        self.tool_name = name
        self.connector = connector
        self.description = f"外部 AI 编码工具（{connector.kind} 型）：{name}"

    async def run(self, task: str, page=None, on_output=None) -> dict:
        try:
            result = await self.connector.run(task, page=page, on_output=on_output)
        except Exception as e:  # 外部工具失败不应中断整体决策链
            return {"ok": False, "tool": self.tool_name, "result": f"外部工具执行失败：{e}"}
        return {"ok": True, "tool": self.tool_name, "result": (result or "")[:2000]}

    def info(self) -> dict:
        info = super().info()
        info.update({"tool": self.tool_name, "connector_kind": self.connector.kind})
        return info
