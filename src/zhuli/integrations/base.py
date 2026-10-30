"""外部工具连接器基类。

连接器是「薄适配层」：自身只负责「如何把任务交给目标工具、如何读回结果」，
底层能力完全复用 browser / computer 模块，不重复造轮子。

统一接口：
  - name / kind: 标识与类型（browser | computer）
  - run(task, **ctx): 执行一次任务并返回结果文本
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Callable, Awaitable, Optional

if TYPE_CHECKING:
    from playwright.async_api import Page

OnOutput = Optional[Callable[[str, str], Awaitable[None]]]


class BaseConnector(ABC):
    name: str = "base"
    kind: str = "browser"  # "browser" | "computer"

    def __init__(self, config: dict) -> None:
        self.config = config

    @abstractmethod
    async def run(self, task: str, *, page: "Optional[Page]" = None,
                  on_output: OnOutput = None) -> str:
        """执行任务并返回结果文本。"""
        raise NotImplementedError
