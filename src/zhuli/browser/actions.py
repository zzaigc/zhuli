"""浏览器动作执行器。

纯执行层：把结构化 Action 应用到 Playwright page。不做任何 AI 决策。
包含：单步失败重试一次、返回 URL 快照供上层回滚、敏感动作由上层（guard）先行判定。
"""
from __future__ import annotations

from playwright.async_api import Locator, Page

from ..core.events import Action


def _locator(page: Page, target: str | None) -> Locator:
    if not target:
        raise ValueError("动作缺少 target（元素 id）")
    return page.locator(f'[data-zhuli-id="{target}"]')


async def fill_credential(page: Page, field_name: str, value: str) -> None:
    """把凭据值填入与 field_name 匹配的输入框（凭据明文不进 LLM）。"""
    locator = await _find_input_by_name(page, field_name)
    await locator.fill(value)


async def _find_input_by_name(page: Page, field_name: str) -> Locator:
    # 按 name/placeholder/type/aria-label 模糊匹配输入框
    candidates = page.locator(
        f'input[name*="{field_name}"], input[placeholder*="{field_name}"], '
        f'input[type="{field_name}"], input[aria-label*="{field_name}"]'
    )
    if await candidates.count() > 0:
        return candidates.first
    # 兜底：当前页面第一个可见密码框/输入框
    pw = page.locator('input[type="password"]')
    if field_name.lower() in ("password", "passwd", "pwd") and await pw.count() > 0:
        return pw.first
    return page.locator("input").first


async def execute(page: Page, action: Action, *, credential_value: str | None = None) -> dict:
    """执行浏览器动作，返回 {ok, error?, snapshot(url)}。"""
    snapshot = page.url
    try:
        if action.action == "click" or action.action == "navigate":
            await _locator(page, action.target).click()
        elif action.action == "type":
            await _locator(page, action.target).fill(action.value or "")
        elif action.action == "fill_credential":
            if credential_value is None:
                raise ValueError("fill_credential 缺少凭据值（应由上层在用户填卡后注入）")
            await fill_credential(page, action.target or "password", credential_value)
        elif action.action == "submit":
            if action.target:
                await _locator(page, action.target).click()
            else:
                await page.keyboard.press("Enter")
        elif action.action == "goto":
            await page.goto(action.target or "")
        elif action.action == "scroll":
            delta = _parse_scroll(action.value)
            await page.mouse.wheel(0, delta)
        elif action.action == "wait":
            ms = _parse_wait(action.value)
            await page.wait_for_timeout(ms)
        elif action.action == "done":
            pass
        else:
            raise ValueError(f"浏览器模块不支持动作：{action.action}")
        return {"ok": True, "snapshot": snapshot}
    except Exception as e:  # 重试一次
        try:
            if action.action in ("click", "type", "submit", "navigate") and action.target:
                await _locator(page, action.target).wait_for(state="attached", timeout=2000)
        except Exception:
            pass
        return {"ok": False, "error": str(e), "snapshot": snapshot}


def _parse_scroll(value: str | None) -> int:
    if not value:
        return 400
    v = value.strip().lower()
    if v == "up":
        return -400
    if v == "down":
        return 400
    try:
        return int(float(v))
    except ValueError:
        return 400


def _parse_wait(value: str | None) -> int:
    if not value:
        return 500
    try:
        return max(0, int(float(value)))
    except ValueError:
        return 500
