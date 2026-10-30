"""CodeBuddy 连接器（浏览器类）。

复用 browser 模块操作 CodeBuddy 网页对话界面：打开页面 → 在输入框填入需求 →
发送 → 等待并读回结果。选择器为 best-effort 探测，若目标站点改版请在集成配置中调整。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from .base import BaseConnector, OnOutput

if TYPE_CHECKING:
    from playwright.async_api import Page


class CodeBuddyConnector(BaseConnector):
    name = "CodeBuddy"
    kind = "browser"

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self.url = config.get("url", "https://copilot.tencent.com/chat")

    async def run(self, task: str, *, page: Optional["Page"] = None,
                  on_output: OnOutput = None) -> str:
        if page is None:
            raise RuntimeError("浏览器类连接器需要 orchestrator 提供 page 实例")
        if page.url.rstrip("/") != self.url.rstrip("/"):
            await page.goto(self.url, wait_until="domcontentloaded")
        if on_output:
            await on_output("stdout", f"[CodeBuddy] 已在页面 {self.url} 就绪")
        # best-effort 定位输入框（textarea / 文本输入 / 可编辑区）
        box = page.locator("textarea, input[type=text], [contenteditable=true]").first
        await box.wait_for(state="visible", timeout=15000)
        await box.click()
        await box.fill(task)
        # 优先按 Enter 发送；若无响应再尝试点击「发送」按钮
        await page.keyboard.press("Enter")
        # 等待结果生成（简单等待 + 读取页面文本）
        await page.wait_for_timeout(4000)
        text = (await page.inner_text("body")) or ""
        return text[:8000]
