"""任务状态机与运行上下文。

状态流转：
  idle → running → (paused ⇄ running) → awaiting_confirm / awaiting_credential → running
       → stopped / error / done
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from playwright.async_api import Page

    from ..browser.driver import BrowserDriver


@dataclass
class TaskContext:
    goal: str = ""
    target_tool: Optional[str] = None
    subtasks: list[str] = field(default_factory=list)
    verification: list[str] = field(default_factory=list)  # 与 subtasks 一一对应
    done: list[str] = field(default_factory=list)
    current: str = ""
    history: list[dict] = field(default_factory=list)  # 已执行动作摘要
    step: int = 0
    status: str = "idle"  # idle/running/paused/awaiting_confirm/awaiting_credential/stopped/error/done
    replan_count: int = 0

    def record(self, action: dict, result: str) -> None:
        self.history.append({"action": action, "result": result})
        self.step += 1

    def verification_for(self, subtask: str) -> list[str]:
        if subtask in self.subtasks:
            idx = self.subtasks.index(subtask)
            return [self.verification[idx]] if idx < len(self.verification) else []
        return []

    def advance_subtask(self, next_subtask: Optional[str] = None) -> None:
        """把 current 标记完成并推进到下一个未完成的子任务。"""
        if self.current and self.current not in self.done:
            self.done.append(self.current)
        if next_subtask and next_subtask in self.subtasks and next_subtask not in self.done:
            self.current = next_subtask
            return
        for s in self.subtasks:
            if s not in self.done:
                self.current = s
                return
        self.current = ""


def snapshot_url(page: Optional["Page"]) -> str:
    return page.url if page else ""
