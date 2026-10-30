"""浏览器敏感操作识别。

- needs_confirm: 提交/支付/删除/跨域导航等敏感动作需用户确认（宁可多确认）
- has_login_form: 检测登录表单（含密码框），用于触发安全凭据卡片
"""
from __future__ import annotations

from urllib.parse import urlparse

from playwright.async_api import Page

from ..core.events import Action

_PAYMENT_KEYWORDS = ("pay", "checkout", "payment", "buy", "order", "subscribe", "购买", "支付", "结算", "下单")
_DELETE_KEYWORDS = ("delete", "remove", "trash", "删除", "移除")


async def needs_confirm(action: Action, page: Page) -> tuple[bool, str]:
    a = action.action
    if a in ("submit",):
        # 含密码框的提交（登录/注册）或支付/删除语义 -> 确认
        if await _page_has_password(page) or _has_keyword(action, _PAYMENT_KEYWORDS + _DELETE_KEYWORDS):
            return True, "检测到表单提交（可能含凭据或支付/删除），需你确认"
        return False, ""
    if a in ("goto", "navigate"):
        if _is_cross_domain(action.target, page.url):
            return True, f"将跳转到新域：{action.target}"
        return False, ""
    return False, ""


def _has_keyword(action: Action, keywords: tuple[str, ...]) -> bool:
    blob = f"{action.target or ''} {action.reason or ''}".lower()
    return any(k in blob for k in keywords)


def _is_cross_domain(target: str | None, current: str) -> bool:
    if not target:
        return False
    try:
        t = urlparse(target if target.startswith("http") else "https://" + target)
        c = urlparse(current)
        return bool(t.netloc) and t.netloc != c.netloc
    except Exception:
        return False


async def _page_has_password(page: Page) -> bool:
    try:
        return await page.locator('input[type="password"]').count() > 0
    except Exception:
        return False


async def has_login_form(page: Page) -> list[str] | None:
    """若页面存在可见登录表单（密码框），返回建议填写的字段名列表。"""
    if not await _page_has_password(page):
        return None
    fields: list[str] = []
    for name in ("username", "email", "phone", "account", "user"):
        if await page.locator(f'input[name*="{name}"], input[placeholder*="{name}"]').count() > 0:
            fields.append(name)
    fields.append("password")
    return fields
