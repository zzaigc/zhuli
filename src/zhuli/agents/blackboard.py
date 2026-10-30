"""蜂巢共享黑板（Blackboard）。

黑板架构是「分布式蜂巢思维」的核心：它不是某个智能体的私有记忆，
而是**本步内所有智能体共同读写的共享认知空间**：

    观察者写「页面状态/障碍」 → 多个执行体各自写「提案」 →
    评审者各自写「投票」 → 共识写入「决策」 → 执行结果回写黑板供反思

这样每个智能体只做自己擅长的一小块，整体却涌现出比单体更强的判断力；
任一成员失效，黑板上的其它成果依然可用（天然的容错性）。
"""
from __future__ import annotations

from threading import Lock
from typing import Any


class Blackboard:
    """线程/协程安全的共享黑板（每步重置，避免跨步污染）。"""

    def __init__(self) -> None:
        self._lock = Lock()
        self._fields: dict[str, Any] = {}
        self._authors: dict[str, str] = {}

    def write(self, author: str, key: str, value: Any) -> None:
        with self._lock:
            self._fields[key] = value
            self._authors[key] = author

    def read(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._fields.get(key, default)

    def reset(self) -> None:
        with self._lock:
            self._fields.clear()
            self._authors.clear()

    def snapshot(self) -> dict[str, Any]:
        """导出黑板内容（供事件/日志可观测，含作者归属）。"""
        with self._lock:
            return {
                "fields": dict(self._fields),
                "authors": dict(self._authors),
            }

    def digest(self, limit: int = 300) -> str:
        """生成人类可读摘要，用于在控制台展示「蜂巢此刻在想什么」。"""
        with self._lock:
            parts = [f"{k}: {str(v)[:limit]}" for k, v in self._fields.items()]
        return " | ".join(parts)
