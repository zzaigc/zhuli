"""Zhuli MCP server: JSON-RPC over stdio, standard library only.

Run: ``python -m zhuli.mcp.server`` (from the project root, with
``PYTHONPATH=src``). Each stdin line is one JSON-RPC request; each
response is one JSON line on stdout. No tool returns a secret.

Approval model (two steps, no interactive prompt over stdio):
  1. A tool that needs approval returns ``needs_approval: true`` plus a
     ``request_id`` and does NOT execute.
  2. The client calls ``zhuli_approve`` with that id, then re-calls the
     original tool with ``approved: true`` (or ``approval_id``).
A ``deny`` guardrail can never be overridden by approval.

Full orchestrator runs (``zhuli_run_task``) reuse the console
Orchestrator. They need a real config and a real provider key, and they
cannot answer interactive confirm or credential prompts over stdio:
a task that reaches such a prompt is reported as awaiting input when
the call timeout expires, and is not executed past that point.
Browser tools in MCP standalone mode have no page, so browser IDE
dispatch is reported as unavailable there; it works through the
console service, which owns the browser page.
"""
from __future__ import annotations

import asyncio
import json
import shutil
import sys
import uuid

VERSION = "0.3.0"

_APPROVALS: dict[str, bool] = {}


def _needs_approval(args: dict) -> str | None:
    """Return a request id if this call still needs approval, else None."""
    if args.get("approved") is True:
        return None
    aid = args.get("approval_id")
    if aid and _APPROVALS.get(str(aid)) is True:
        return None
    rid = str(uuid.uuid4())
    _APPROVALS[rid] = False
    return rid


def _approval_response(reason: str) -> dict:
    rid = _needs_approval({})
    return {"ok": False, "needs_approval": True, "request_id": rid, "reason": reason}


def _tool(name: str, description: str, properties: dict, required: list[str] | None = None) -> dict:
    return {
        "name": name,
        "description": description,
        "inputSchema": {"type": "object", "properties": properties, "required": required or []},
    }


def _tools() -> list[dict]:
    return [
        _tool("zhuli_status", "Zhuli service status: config presence and runtime dirs, no secrets.",
              {}),
        _tool("zhuli_config", "Configured provider names and routing, no keys.",
              {}),
        _tool("zhuli_skills", "List learned skills from the SQLite store.",
              {}),
        _tool("zhuli_shell", "Run one local command through the existing guardrail.",
              {"command": {"type": "string"}, "approved": {"type": "boolean"},
               "approval_id": {"type": "string"}}, ["command"]),
        _tool("zhuli_workflow_run", "Run a list of guarded shell steps in order; stops on first failure.",
              {"steps": {"type": "array", "items": {"type": "object"}},
               "approved": {"type": "boolean"}, "approval_id": {"type": "string"}}, ["steps"]),
        _tool("zhuli_tool_dispatch", "Dispatch a task to an external AI IDE tool (codebuddy, trae, opencode). Only when the console bidirectional switch is at IDE -> Zhuli; off or Zhuli -> IDE returns a clear mode error.",
              {"tool": {"type": "string"}, "task": {"type": "string"},
               "approved": {"type": "boolean"}, "approval_id": {"type": "string"}},
              ["tool", "task"]),
        _tool("zhuli_approve", "Approve a pending request returned by another tool.",
              {"request_id": {"type": "string"}, "approved": {"type": "boolean"}}, ["request_id"]),
        _tool("zhuli_run_task", "Best-effort full orchestrator run; needs config and a provider key.",
              {"goal": {"type": "string"}, "target_tool": {"type": "string"},
               "timeout_sec": {"type": "number"}}, ["goal"]),
    ]


def _status() -> dict:
    try:
        from ..config.settings import get_settings
        s = get_settings()
        return {"ok": True, "config": True, "providers": [p.name for p in s.providers],
                "integrations": list(s.integrations.keys())}
    except Exception as e:
        return {"ok": True, "config": False, "error": str(e)[:300]}


def _config() -> dict:
    try:
        from ..config.settings import get_settings
        s = get_settings()
        return {"ok": True, "providers": [p.name for p in s.providers],
                "routing": s.routing.model_dump(), "integrations": list(s.integrations.keys())}
    except Exception as e:
        return {"ok": False, "error": str(e)[:300]}


def _skills() -> dict:
    try:
        from ..memory.store import store
        return {"ok": True, "skills": store.list_skills()}
    except Exception as e:
        return {"ok": False, "error": str(e)[:300]}


def _run_shell(command: str) -> dict:
    from ..computer import executor as computer_executor
    from ..computer.guard import classify

    level, reason = classify(command)
    if level == "deny":
        return {"ok": False, "error": f"command denied by guardrail: {reason}"}
    lines: list[str] = []

    async def on_output(stream: str, line: str) -> None:
        lines.append(f"{stream}: {line}")

    async def main() -> dict:
        return await computer_executor.run(command, on_output=on_output, timeout=120.0)

    res = asyncio.run(main())
    return {"ok": res.get("exit_code") == 0, "exit_code": res.get("exit_code"),
            "output": "\n".join(lines)[:8000]}


def _shell(args: dict) -> dict:
    command = str(args.get("command") or "")
    if not command.strip():
        return {"ok": False, "error": "empty command"}
    from ..computer.guard import classify
    level, reason = classify(command)
    if level == "deny":
        return {"ok": False, "error": f"command denied by guardrail: {reason}"}
    if level == "confirm":
        rid = _needs_approval(args)
        if rid is not None:
            return {"ok": False, "needs_approval": True, "request_id": rid, "reason": reason}
    try:
        return _run_shell(command)
    except Exception as e:
        return {"ok": False, "error": str(e)[:500]}


def _workflow(args: dict) -> dict:
    steps = args.get("steps") or []
    if not isinstance(steps, list) or not steps:
        return {"ok": False, "error": "steps must be a non-empty list"}
    commands = []
    for step in steps:
        cmd = step.get("command") if isinstance(step, dict) else None
        if not cmd:
            return {"ok": False, "error": "every step needs a command"}
        commands.append(str(cmd))
    from ..computer.guard import classify
    for cmd in commands:
        level, reason = classify(cmd)
        if level == "deny":
            return {"ok": False, "error": f"step denied by guardrail: {reason} ({cmd[:80]})"}
        if level == "confirm":
            rid = _needs_approval(args)
            if rid is not None:
                return {"ok": False, "needs_approval": True, "request_id": rid, "reason": reason}
    results = []
    for cmd in commands:
        try:
            r = _run_shell(cmd)
        except Exception as e:
            r = {"ok": False, "error": str(e)[:500]}
        results.append({"command": cmd, **r})
        if not r.get("ok"):
            return {"ok": False, "steps": results}
    return {"ok": True, "steps": results}


def _dispatch(args: dict) -> dict:
    tool = str(args.get("tool") or "").lower()
    task = str(args.get("task") or "")
    if tool not in ("codebuddy", "trae", "opencode"):
        return {"ok": False, "error": f"unknown IDE tool: {tool}"}
    if not task.strip():
        return {"ok": False, "error": "empty task"}
    # v0.3.0 双向开关：MCP 派发（IDE -> Zhuli 方向）只在开关切到
    # ide_to_zhuli 时允许；关闭或 Zhuli -> IDE 时直接返回明确错误，
    # 而不是 needs_approval（审批不能把一个被开关关掉的方向打开）。
    # 开关值读共享文件（控制台写入），无文件时默认 off，fail-closed。
    # 注意：MCP 独立进程不经过控制台 lifespan 的启动复位；控制台
    # 停服时会尽力删掉共享文件，独立 MCP 因此默认回 off。
    try:
        from ..agents.bidirectional import get_mode as _get_mode, mcp_block_reason as _mcp_reason
        _mode = _get_mode("off")
    except Exception:
        _mode, _mcp_reason = "off", None
    if _mode != "ide_to_zhuli":
        reason = _mcp_reason(_mode) if _mcp_reason else \
            "bidirectional mode is off: MCP dispatch is blocked"
        return {"ok": False, "error": reason}
    rid = _needs_approval(args)
    if rid is not None:
        return {"ok": False, "needs_approval": True, "request_id": rid,
                "reason": f"dispatch to external IDE tool {tool} requires approval"}
    if tool in ("codebuddy", "trae"):
        return {"ok": False, "unverified": True,
                "error": "browser IDE dispatch has no page in MCP standalone mode; "
                         "use the console service, which owns the browser page"}
    try:
        from ..config.settings import get_settings
        settings = get_settings()
        cfg = settings.integrations.get(tool)
        if cfg is None:
            return {"ok": False, "error": f"no integrations config for {tool}"}
        from ..integrations.opencode import OpenCodeConnector
        conn = OpenCodeConnector(cfg.model_dump())
        binary = conn.command[0] if conn.command else "opencode"
        if shutil.which(binary) is None:
            return {"ok": False, "unverified": True,
                    "error": f"opencode binary not found: {binary}"}
        result = asyncio.run(conn.run(task))
        return {"ok": True, "tool": tool, "result": result[:8000]}
    except Exception as e:
        return {"ok": False, "error": str(e)[:500]}


def _approve(args: dict) -> dict:
    rid = str(args.get("request_id") or "")
    if rid not in _APPROVALS:
        return {"ok": False, "error": "unknown request_id"}
    _APPROVALS[rid] = bool(args.get("approved", True))
    return {"ok": True, "request_id": rid, "approved": _APPROVALS[rid]}


def _run_task(args: dict) -> dict:
    goal = str(args.get("goal") or "")
    if not goal.strip():
        return {"ok": False, "error": "empty goal"}
    timeout = float(args.get("timeout_sec") or 30)

    async def main() -> dict:
        from ..core.orchestrator import Orchestrator
        events: list[str] = []

        async def sink(event) -> None:
            try:
                events.append(str(event.type))
            except Exception:
                events.append("event")

        orch = Orchestrator(sink)
        await orch.start()
        if orch.coord is None:
            await orch.shutdown()
            return {"ok": False, "error": "agent team not ready: check config/settings.yaml",
                    "events": events}
        await orch.submit(goal, args.get("target_tool"))
        try:
            if orch._loop is not None:
                await asyncio.wait_for(orch._loop, timeout=timeout)
        except asyncio.TimeoutError:
            status = orch.ctx.status
            await orch.shutdown()
            return {"ok": False, "timeout": True, "status": status,
                    "note": "task reached a prompt or long run over stdio; "
                            "interactive confirm/credential is not supported in MCP mode",
                    "events": events[-20:]}
        except Exception as e:
            await orch.shutdown()
            return {"ok": False, "error": str(e)[:500], "events": events[-20:]}
        status = orch.ctx.status
        await orch.shutdown()
        return {"ok": status == "done", "status": status, "events": events[-20:]}

    try:
        return asyncio.run(main())
    except Exception as e:
        return {"ok": False, "error": str(e)[:500]}


def _call(name: str, args: dict) -> dict:
    handlers = {
        "zhuli_status": lambda: _status(),
        "zhuli_config": lambda: _config(),
        "zhuli_skills": lambda: _skills(),
        "zhuli_shell": lambda: _shell(args),
        "zhuli_workflow_run": lambda: _workflow(args),
        "zhuli_tool_dispatch": lambda: _dispatch(args),
        "zhuli_approve": lambda: _approve(args),
        "zhuli_run_task": lambda: _run_task(args),
    }
    fn = handlers.get(name)
    if fn is None:
        return {"ok": False, "error": f"unknown tool: {name}"}
    return fn()


def handle(request: dict) -> dict | None:
    method = request.get("method", "")
    req_id = request.get("id")
    if method.startswith("notifications/"):
        return None
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": req_id,
                "result": {"protocolVersion": "2024-11-05",
                           "capabilities": {"tools": {}},
                           "serverInfo": {"name": "zhuli", "version": VERSION}}}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": _tools()}}
    if method == "tools/call":
        params = request.get("params") or {}
        result = _call(str(params.get("name") or ""), params.get("arguments") or {})
        return {"jsonrpc": "2.0", "id": req_id,
                "result": {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
                           "isError": not result.get("ok", True)}}
    return {"jsonrpc": "2.0", "id": req_id,
            "error": {"code": -32601, "message": f"method not found: {method}"}}


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except Exception:
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": None,
                                         "error": {"code": -32700, "message": "parse error"}}) + "\n")
            sys.stdout.flush()
            continue
        try:
            response = handle(request)
        except Exception as e:
            response = {"jsonrpc": "2.0", "id": request.get("id"),
                        "error": {"code": -32603, "message": str(e)[:500]}}
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
