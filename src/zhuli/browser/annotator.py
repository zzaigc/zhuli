"""页面标注与观察：注入稳定 id、抽取可交互元素、可访问性树摘要、元素高亮坐标。

观察表示（Observation）= 可交互元素列表 + Accessibility Tree 摘要 + （可选）截图。
不把整页 DOM 上送，避免 token 爆炸。元素用 `data-zhuli-id` 稳定标识，供 LLM 引用。
"""
from __future__ import annotations

import json

from playwright.async_api import Page

_MAX_ELEMENTS = 200

# 在页面内执行的标注脚本：为可交互元素分配 data-zhuli-id 并返回摘要
_ANNOTATE_JS = """
() => {
  const SEL = 'a,button,input,select,textarea,[role="button"],[role="link"],'
            + '[contenteditable="true"],summary,label';
  const els = Array.from(document.querySelectorAll(SEL))
    .filter(e => e.offsetParent !== null || e.tagName === 'INPUT' && e.type === 'hidden' ? false : true)
    .slice(0, %d);
  const out = [];
  els.forEach((el, i) => {
    if (el.hasAttribute('data-zhuli-id')) return;
    el.setAttribute('data-zhuli-id', 'z' + i);
    const tag = el.tagName.toLowerCase();
    let text = (el.innerText || el.value || el.getAttribute('aria-label') || '').trim().slice(0, 80);
    const info = { id: 'z' + i, tag };
    if (text) info.text = text;
    const name = el.getAttribute('name') || el.getAttribute('aria-label');
    if (name) info.name = name.slice(0, 60);
    if (el.placeholder) info.placeholder = el.placeholder.slice(0, 60);
    if (el.type) info.type = el.type;
    const role = el.getAttribute('role');
    if (role) info.role = role;
    if (el.href) info.href = el.href.slice(0, 120);
    out.push(info);
  });
  return out;
}
""" % _MAX_ELEMENTS


async def annotate(page: Page) -> list[dict]:
    """为页面可交互元素注入 data-zhuli-id，返回元素摘要列表。"""
    return await page.evaluate(_ANNOTATE_JS)


async def accessibility_summary(page: Page, max_chars: int = 4000) -> str:
    """生成可访问性树紧凑摘要（角色/名称/值/状态），截断以省 token。"""
    try:
        snap = await page.accessibility.snapshot()
    except Exception:
        return ""
    text = _flatten_a11y(snap)
    return text[:max_chars]


def _flatten_a11y(node: dict | None, depth: int = 0, lines: list[str] | None = None) -> str:
    if node is None:
        return ""
    lines = lines if lines is not None else []
    role = node.get("role", "?")
    name = (node.get("name") or "").strip().replace("\n", " ")
    value = node.get("value")
    checked = node.get("checked")
    prefix = "  " * depth
    line = f"{prefix}- {role}"
    if name:
        line += f" '{name[:60]}'"
    if value not in (None, ""):
        line += f" ={str(value)[:40]}"
    if checked is not None:
        line += f" [checked={checked}]"
    lines.append(line)
    for child in node.get("children", []) or []:
        _flatten_a11y(child, depth + 1, lines)
    return "\n".join(lines)


async def highlight(page: Page, zhuli_id: str | None) -> list[dict]:
    """返回指定元素（或全部已标注元素）的边框坐标，用于前端高亮覆盖层。"""
    if not zhuli_id:
        return []
    box = await page.evaluate(
        """(id) => {
            const el = document.querySelector(`[data-zhuli-id="${id}"]`);
            if (!el) return null;
            const r = el.getBoundingClientRect();
            return {x: r.x, y: r.y, w: r.width, h: r.height};
        }""",
        zhuli_id,
    )
    if not box:
        return []
    return [{"selector": zhuli_id, **box}]


async def get_screenshot(page: Page) -> str:
    """返回 JPEG base64 截图（压缩以节流）。"""
    data = await page.screenshot(type="jpeg", quality=60, full_page=False)
    import base64

    return base64.b64encode(data).decode("ascii")
