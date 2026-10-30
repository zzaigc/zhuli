"""浏览器驱动：启动独立的 headed Chromium（隔离 profile）。

关键点：
  - 使用 launch_persistent_context + 独立 user_data_dir，与日常浏览器完全隔离
  - headless=False 让用户能看到 AI 实时操作
  - 仅暴露 page 级别的薄封装，不承载任何 AI 决策逻辑
"""
from __future__ import annotations

from pathlib import Path

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

# 项目根目录（src/zhuli/browser/driver.py -> 3 层上）
_PROJECT_ROOT = Path(__file__).resolve().parents[3]


class BrowserDriver:
    def __init__(
        self,
        *,
        headless: bool = False,
        user_data_dir: str = ".zhuli_runtime/profile",
        viewport: dict | None = None,
    ) -> None:
        self.headless = headless
        # 相对路径一律解析到「项目根目录」，确保用户 profile 落在 E 盘当前目录，绝不进 C 盘
        p = Path(user_data_dir)
        self.user_data_dir = str(
            p if p.is_absolute() else (_PROJECT_ROOT / p).resolve()
        )
        self.viewport = viewport or {"width": 1280, "height": 800}
        self._pw = None
        self.context: BrowserContext | None = None
        self.browser: Browser | None = None

    async def __aenter__(self) -> "BrowserDriver":
        self._pw = await async_playwright().start()
        self.context = await self._pw.chromium.launch_persistent_context(
            user_data_dir=self.user_data_dir,
            headless=self.headless,
            viewport=self.viewport,
            args=["--no-first-run", "--no-default-browser-check"],
        )
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self.context is not None:
            await self.context.close()
        if self._pw is not None:
            await self._pw.stop()

    async def new_page(self) -> Page:
        assert self.context is not None
        return await self.context.new_page()

    @property
    def page(self) -> Page:
        assert self.context is not None
        pages = self.context.pages
        return pages[-1] if pages else self.context.pages[0]
