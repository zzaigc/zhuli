"""命令护栏：把命令分级为 allow / confirm / deny。

设计原则：宁可多确认。破坏性命令直接 deny；涉及写系统目录、网络外发、安装卸载等需 confirm。
仅做启发式关键词/正则匹配，不解析 shell 语义，因此危险命令务必经用户确认后再执行。
"""
from __future__ import annotations

import re

# 直接禁止（破坏性 / 不可逆）
_DENY = [
    r"\brm\s+-rf\s+/", r"\brm\s+-rf\s+~", r"\brm\s+-fr\s+/",
    r"\bformat\b", r"\bdiskpart\b", r"\bmkfs\b", r"\bdd\s+if=",
    r":\(\)\s*\{", r"\bshutdown\b", r"\bhalt\b", r"\breboot\b",
    r"\bchmod\s+-R\s+777\s+/", r"\bmv\s+.*\s+/\b", r">\s*/dev/sd",
]

# 需要确认（敏感但可能合法）
_CONFIRM = [
    r"\bsudo\b", r"\bsu\b", r"\bapt\b", r"\byum\b", r"\bbrew\b",
    r"\bpip\s+install", r"\bnpm\s+install", r"\bgit\s+push",
    r"\bcurl\b", r"\bwget\b", r"\bssh\b", r"\bscp\b", r"\bftp\b",
    r"\breg\b", r"\bnetsh\b", r"\bformat\b", r">\s*/", r">>/",
    r"\buseradd\b", r"\buserdel\b", r"\bcrontab\b",
]


def classify(cmd: str) -> tuple[str, str]:
    """返回 (level, reason)，level ∈ {allow, confirm, deny}。"""
    c = cmd.lower()
    for pat in _DENY:
        if re.search(pat, c):
            return "deny", f"命中禁止规则：{pat}"
    for pat in _CONFIRM:
        if re.search(pat, c):
            return "confirm", f"命中需确认规则：{pat}"
    return "allow", ""
