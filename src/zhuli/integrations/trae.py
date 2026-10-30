"""Trae 连接器（浏览器类）。

与 CodeBuddy 同构，复用 browser 模块操作 Trae 网页/对话界面。选择器为 best-effort 探测。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from .base import BaseConnector, OnOutput

if TYPE_CHECKING:
    from playwright.async_api import Page


class TraeConnector(BaseConnector):
    name = "Trae"
    kind = "browser"

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self.url = config.get("url", "https://www.trae.ai")

    async def run(self, task: str, *, page: Optional["Page"] = None,
                  on_output: OnOutput = None) -> str:
        if page is None:
            raise RuntimeError("浏览器类连接器需要 orchestrator 提供 page 实例")
        if page.url.rstrip("/") != self.url.rstrip("/"):
            await page.goto(self.url, wait_until="domcontentloaded")
        if on_output:
            await on_output("stdout", f"[Trae] 已在页面 {self.url} 就绪")
        box = page.locator("textarea, input[type=text], [contenteditable=true]").first
        await box.wait_for(state="visible", timeout=15000)
        await box.click()
        await box.fill(task)
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(4000)
        text = (await page.inner_text("body")) or ""
        return text[:8000]
