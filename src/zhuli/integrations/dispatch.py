"""IDE dispatch checks shared by the orchestrator and the MCP server.

This module does not execute a task itself. It answers, before any
browser page or shell command is touched: is this tool known, is its
required runtime present, and does it need approval first? The caller
owns the actual execution and the user-facing approval prompt, so the
existing orchestrator confirm flow stays unchanged.

Verified in v0.2.0:
  - computer dispatch (opencode) with a stub binary: output is returned.
  - unknown tool, empty task, missing page and missing binary: clean
    failures, no exception leaks into the decision loop.
Not verified in v0.2.0 (no real login, no real IDE session):
  - CodeBuddy and Trae against their live web pages. Their selectors
    are best-effort and their pages may require login or change layout.
"""
from __future__ import annotations

import shutil

KNOWN_TOOLS = ("codebuddy", "trae", "opencode")


def check(tool: str, task: str, *, page=None, command: list[str] | None = None) -> dict:
    """Return {ok, error} for a dispatch request, without executing it."""
    name = (tool or "").lower()
    if name not in KNOWN_TOOLS:
        return {"ok": False, "error": f"unknown IDE tool: {tool}"}
    if not (task or "").strip():
        return {"ok": False, "error": "empty IDE task"}
    if name in ("codebuddy", "trae") and page is None:
        return {"ok": False, "error": f"browser IDE tool {name} needs a browser page"}
    if name == "opencode":
        binary = (command or ["opencode"])[0]
        if shutil.which(binary) is None:
            return {"ok": False, "error": f"opencode binary not found: {binary}"}
    return {"ok": True, "tool": name}
