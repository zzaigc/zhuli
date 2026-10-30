"""安全卡片逻辑辅助：构建凭据请求、日志脱敏。

真正的「弹出卡片 → 用户填写 → 注入页面」由前端 CredentialCard 组件与
orchestrator 协同完成；本模块只负责构造请求事件与脱敏，确保明文绝不进入日志/LLM。
"""
from __future__ import annotations

from ..core.events import CredentialRequestEvent


def build_request(fields: list[str]) -> CredentialRequestEvent:
    """构造凭据请求事件（只含字段名，不含值）。"""
    return CredentialRequestEvent(type="credential_request", fields=fields)


def redact(value: str | None) -> str:
    """把敏感值替换为脱敏占位符，用于日志/事件展示。"""
    if not value:
        return ""
    return "***"
