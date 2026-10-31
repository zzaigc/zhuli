"""控制台后端：FastAPI + WebSocket 事件推送 + 静态托管。

职责：
  - 持有 Orchestrator 单例，并把其事件广播给所有连接的 WebSocket 客户端
  - 接收前端指令（提交任务 / 确认 / 填卡 / 暂停恢复停止）并转交 orchestrator
  - 提供静态文件托管（前端构建产物）
"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ..agents import HiveCoordinator
from ..agents.bidirectional import (
    IDE_TOOLS as _IDE_TOOLS,
    can_console_dispatch as _can_console_dispatch,
    can_mcp_dispatch as _can_mcp_dispatch,
    clear_shared_file as _clear_bidirectional_file,
    console_block_reason as _console_block_reason,
    get_mode as _bidirectional_mode,
    set_mode as _set_bidirectional_mode,
)
from ..agents.runtime import (
    effective_parallel as _runtime_effective_parallel,
    hive_override, parallel_override, set_hive_enabled, set_hive_size,
    set_hive_size_mode, set_parallel_enabled,
)
from ..config.settings import get_settings
from ..core.events import to_ws, ErrorEvent, Event
from ..core.orchestrator import Orchestrator
from ..credential.vault import configure_security, security_info
from ..llm import router as llm_router
from ..llm.usage import summary as usage_summary
from ..memory.store import store

_STATIC_DIR = Path(__file__).resolve().parent / "static"


class Hub:
    def __init__(self) -> None:
        self.clients: Set[WebSocket] = set()
        self.recent: list[str] = []  # 缓冲历史事件，供新连接客户端回放（如启动期错误）
        self.orch = Orchestrator(self._sink)

    async def _sink(self, event: Event) -> None:
        msg = to_ws(event)
        self.recent.append(msg)
        if len(self.recent) > 100:
            self.recent = self.recent[-100:]
        for ws in list(self.clients):
            try:
                await ws.send_text(msg)
            except Exception:
                self.clients.discard(ws)

    async def connect(self, ws: WebSocket) -> None:
        self.clients.add(ws)
        # 回放历史事件，确保启动期（如浏览器缺失）的错误可见
        for msg in self.recent:
            try:
                await ws.send_text(msg)
            except Exception:
                self.clients.discard(ws)
                break

    async def disconnect(self, ws: WebSocket) -> None:
        self.clients.discard(ws)


hub = Hub()

# v0.3.0 派发确认（两步式，与 MCP 的 zhuli_approve 同款思路）：
# 第一次 POST /api/dispatch 只做全部检查并返回 needs_approval +
# request_id，不提交、不执行；第二次带 approval_id + approved=true
# 才重新检查并提交。确认 id 只存在内存里，重启即失效。
_DISPATCH_APPROVALS: dict[str, bool] = {}

_BUSY_STATES = ("running", "awaiting_confirm", "awaiting_credential")


def _config_bidirectional_mode() -> str:
    """配置里的双向开关默认值（读不到配置时为 off， fail-closed）。"""
    try:
        mode = get_settings().policy.bidirectional_mode
    except Exception:
        return "off"
    return mode if mode in ("off", "ide_to_zhuli", "zhuli_to_ide") else "off"


def _bidirectional_status() -> dict:
    mode = _bidirectional_mode(_config_bidirectional_mode())
    return {
        "mode": mode,
        "config_mode": _config_bidirectional_mode(),
        "can_console_dispatch": _can_console_dispatch(mode),
        "can_mcp_dispatch": _can_mcp_dispatch(mode),
        "note": ("三段开关，同一时刻只有一个位置生效：off = 仅本助理；"
                 "ide_to_zhuli = IDE 经 MCP 操作 Zhuli，Zhuli 不可反向派发；"
                 "zhuli_to_ide = Zhuli 派发到 IDE，MCP 派发被阻止。"
                 "两方向绝不同时开启，避免 IDE <-> Zhuli 来回循环。"
                 "开关是运行时覆盖，重启恢复为配置值。"),
    }


def validate_dispatch(goal: str, tool: str, *, mode: str, busy: bool,
                      page, configured_tools) -> dict:
    """派发到 IDE 之前的全部前置检查（不提交、不执行）。

    顺序即报错优先级：开关位置 -> 任务是否在跑 -> 目标是否为空 ->
    IDE 是否已知 -> 是否在配置里 -> 复用 integrations/dispatch.check
    的运行时检查（浏览器类 IDE 有无页面、opencode 二进制在不在）。
    返回 {ok: True} 或 {ok: False, error: 中文原因}。本函数是纯检查，
    供单元测试直接调用；路由层在此之后再走两步确认并提交。
    """
    if not _can_console_dispatch(mode):
        return {"ok": False, "error": _console_block_reason(mode)}
    if busy:
        return {"ok": False, "error": "任务执行中，结束后可派发"}
    if not (goal or "").strip():
        return {"ok": False, "error": "先输入任务目标"}
    name = (tool or "").lower()
    if name not in _IDE_TOOLS:
        return {"ok": False, "error": f"未知 IDE：{tool}（可选：codebuddy、trae、opencode）"}
    if name not in (configured_tools or []):
        return {"ok": False, "error": f"未在配置 integrations 里找到 {name}，请先在配置里添加该 IDE"}
    from ..integrations.dispatch import check as _dispatch_check
    res = _dispatch_check(name, goal, page=page)
    if not res.get("ok"):
        err = str(res.get("error") or "")
        if err.startswith("browser IDE"):
            return {"ok": False, "error": f"浏览器类 IDE {name} 需要浏览器页面，当前控制台没有可用页面"}
        if err.startswith("opencode binary"):
            return {"ok": False, "error": "找不到 OpenCode 可执行文件：opencode（请先安装 OpenCode CLI，再派发）"}
        return {"ok": False, "error": err}
    return {"ok": True, "tool": name}


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_security()  # 配置就绪后再初始化军事级加密（缺配置也不影响启动）
    # v0.3.0 双向开关：启动时把共享值复位为配置值（运行时覆盖不跨重启），
    # 这样控制台与独立 MCP 进程在同一次运行里共享的都是本次的值。
    try:
        _set_bidirectional_mode(_config_bidirectional_mode())
    except Exception:
        pass
    await hub.orch.start()
    yield
    await hub.orch.shutdown()
    try:
        _clear_bidirectional_file()  # 停服后独立 MCP 默认回 off，fail-closed
    except Exception:
        pass


def create_app() -> FastAPI:
    app = FastAPI(title="ZHULI", version="0.3.0", lifespan=lifespan)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "service": "zhuli"}

    @app.get("/api/config")
    async def api_config() -> dict:
        s = get_settings()
        return {
            "providers": [p.name for p in s.providers],
            "routing": s.routing.model_dump(),
            "integrations": list(s.integrations.keys()),
        }

    @app.get("/api/skills")
    async def api_skills() -> list:
        return store.list_skills()

    @app.get("/api/agents")
    async def api_agents() -> dict:
        """返回当前智能体团队（内置角色 / 外部工具 / 已升格的专项智能体）与协作模式。"""
        reg = hub.orch.registry
        if reg is None:
            return {"agents": [], "total": 0, "mode": "single"}
        try:
            multi = get_settings().policy.multi_agent
        except Exception:
            multi = True
        if isinstance(hub.orch.coord, HiveCoordinator):
            mode = "hive"
        elif multi:
            mode = "multi"
        else:
            mode = "single"
        return {"agents": reg.describe(), "total": len(reg), "mode": mode}

    @app.get("/api/models")
    async def api_models() -> dict:
        """可切换的模型清单：供应商 + 各能力当前生效供应商 + 运行期覆盖。"""
        s = get_settings()
        caps = ["default", "reasoning", "vision"]
        over = llm_router.overrides()
        routing = s.routing.model_dump() if hasattr(s.routing, "model_dump") else {}
        return {
            "providers": [p.name for p in s.providers],
            # 展示「实际生效」的供应商（覆盖优先于配置），控制台下拉据此回显
            "routing": {c: over.get(c) or routing.get(c, "") for c in caps},
            "overrides": over,
            "capabilities": caps,
        }

    @app.post("/api/models")
    async def api_set_model(body: dict) -> dict:
        """运行期切换某个能力所用的供应商（不写回配置文件，重启后回到配置值）。"""
        cap = str(body.get("capability") or "default")
        prov = str(body.get("provider") or "")
        if prov and prov not in [p.name for p in get_settings().providers]:
            return {"ok": False, "error": f"未知供应商：{prov}"}
        llm_router.set_override(cap, prov)
        return {"ok": True, "overrides": llm_router.overrides()}

    def _hive_status() -> dict:
        """v0.2.0：当前蜂巢状态。运行时覆盖只存在内存中，重启后恢复配置值。"""
        s = get_settings()
        over = hive_override()
        size_mode = over.get("mode") or getattr(s.policy, "hive_size_mode", "manual")
        manual_size = over.get("size") or int(s.policy.hive_size)
        coord = hub.orch.coord
        if isinstance(coord, HiveCoordinator):
            mode, enabled, size = "hive", True, int(coord.hive_size)
            last_auto = getattr(coord, "last_auto", None) or over.get("last_auto")
            size_mode = getattr(coord, "hive_size_mode", size_mode)
        elif s.policy.multi_agent:
            mode, enabled, size = "multi", False, int(manual_size)
            last_auto = over.get("last_auto")
        else:
            mode, enabled, size = "single", False, int(manual_size)
            last_auto = over.get("last_auto")
        return {
            "mode": mode,
            "hive_mode": enabled,
            "hive_size": size,
            "hive_size_mode": size_mode,
            "manual_hive_size": int(manual_size),
            "last_auto": last_auto if size_mode == "auto" else None,
            "config_hive_mode": bool(s.policy.hive_mode),
            "config_hive_size": int(s.policy.hive_size),
            "config_hive_size_mode": getattr(s.policy, "hive_size_mode", "manual"),
            "runtime_override": over,
            "note": "运行时覆盖，不写回配置文件；重启后恢复为配置值。手动规模无上限（>=1），自动模式范围 2~8。",
        }

    @app.get("/api/hive")
    async def api_hive() -> dict:
        return _hive_status()

    @app.post("/api/hive")
    async def api_set_hive(body: dict) -> dict:
        """运行时切换蜂巢模式（与 /api/models 覆盖同款：不写回配置文件）。

        body 可含 hive_mode（bool）、hive_size（>= 1 的整数，无上限）
        与 hive_size_mode（manual/auto）；只给其中一项时其余保持当前值。
        hive_size 小于 1 或非整数时返回错误且不做任何改动；切回手动时
        恢复之前的手动规模（自动结果保存在 last_auto，绝不覆盖手动规模）。
        """
        if "hive_size" in body and body["hive_size"] is not None:
            try:
                from ..agents.runtime import _coerce_hive_size
                size = _coerce_hive_size(body["hive_size"])
            except (TypeError, ValueError):
                return {"ok": False, "error": "hive_size 必须是大于等于 1 的整数"}
            set_hive_size(size)
        if "hive_size_mode" in body and body["hive_size_mode"] is not None:
            if body["hive_size_mode"] not in ("manual", "auto"):
                return {"ok": False, "error": "hive_size_mode 必须是 manual 或 auto"}
            set_hive_size_mode(body["hive_size_mode"])
        if "hive_mode" in body and body["hive_mode"] is not None:
            set_hive_enabled(bool(body["hive_mode"]))
        if hub.orch.rebuild_coordinator() is None:
            return {"ok": False, "error": "智能体团队未就绪，无法重建协调器"}
        return {"ok": True, **_hive_status()}

    def _parallel_status() -> dict:
        """v0.3.0：并行子目标状态。运行时覆盖只在内存中，重启恢复配置值。

        Hive 开启时 effective 恒为 False：蜂巢已有自己的并行提案与
        投票，子任务分组不再叠加并行，避免打乱投票。
        """
        try:
            s = get_settings()
            config_enabled = bool(s.policy.parallel_enabled)
        except Exception:
            config_enabled = True
        hive = isinstance(hub.orch.coord, HiveCoordinator)
        return {
            "parallel_enabled": _runtime_effective_parallel(config_enabled, hive),
            "config_parallel_enabled": config_enabled,
            "runtime_override": parallel_override(),
            "hive_mode": hive,
            "groups": list(hub.orch._parallel_groups),
            "note": "运行时覆盖，不写回配置文件；重启后恢复为配置值。Hive 模式下强制顺序执行。",
        }

    @app.get("/api/parallel")
    async def api_parallel() -> dict:
        return _parallel_status()

    @app.post("/api/parallel")
    async def api_set_parallel(body: dict) -> dict:
        """运行时开关并行子目标（不写回配置文件）。body: {parallel_enabled: bool}。"""
        if "parallel_enabled" in body and body["parallel_enabled"] is not None:
            set_parallel_enabled(bool(body["parallel_enabled"]))
        return {"ok": True, **_parallel_status()}

    @app.get("/api/bidirectional")
    async def api_bidirectional() -> dict:
        """v0.3.0：当前双向开关位置（单个值，三选一，绝不同时开启两方向）。"""
        return _bidirectional_status()

    @app.post("/api/bidirectional")
    async def api_set_bidirectional(body: dict) -> dict:
        """运行时切换双向开关（不写回配置文件，重启恢复为配置值）。

        只接受 off / ide_to_zhuli / zhuli_to_ide 三个值；其它值返回
        错误且不做任何改动。切换只影响后续派发，正在运行的任务不受影响。
        """
        mode = body.get("mode")
        if mode not in ("off", "ide_to_zhuli", "zhuli_to_ide"):
            return {"ok": False, "error": "mode 必须是 off、ide_to_zhuli 或 zhuli_to_ide 之一"}
        _set_bidirectional_mode(mode)
        return {"ok": True, **_bidirectional_status()}

    @app.post("/api/dispatch")
    async def api_dispatch(body: dict) -> dict:
        """v0.3.0：控制台「派发到 IDE」按钮的后端路由。

        路径选择说明：不用「直接发 WebSocket 任务」是因为按钮需要
        在提交前就给出诚实结果（开关位置、任务在跑、IDE 未知、
        未配置、无页面、缺二进制），而不是把失败埋进执行循环里。
        本路由只做检查 + 两步确认 + 提交：提交走的仍是
        hub.orch.submit(goal, target_tool) 这条普通任务路径，所以
        执行中若遇到需要确认的步骤，仍会走原有的右侧确认流程，
        普通任务消息也绕不过 Orchestrator.submit 里的开关检查。
        两步确认：第一次不带 approval_id 时只返回 needs_approval +
        request_id，不提交；第二次带 approval_id + approved=true 时
        重新做全部检查，通过后才提交。
        """
        import uuid as _uuid

        goal = str(body.get("goal") or "")
        tool = str(body.get("tool") or "")
        try:
            configured = list(get_settings().integrations.keys())
        except Exception:
            configured = []
        busy = getattr(hub.orch.ctx, "status", "idle") in _BUSY_STATES
        checked = validate_dispatch(goal, tool, mode=_bidirectional_mode(_config_bidirectional_mode()),
                                    busy=busy, page=hub.orch.page,
                                    configured_tools=configured)
        if not checked.get("ok"):
            return checked
        approval_id = body.get("approval_id")
        if not (body.get("approved") is True and approval_id
                and str(approval_id) in _DISPATCH_APPROVALS):
            rid = str(_uuid.uuid4())
            _DISPATCH_APPROVALS[rid] = False  # 待确认；只有带 approved=true 的第二次调用才放行
            return {"ok": False, "needs_approval": True, "request_id": rid,
                    "reason": f"派发到外部 IDE（{checked['tool']}）需要确认",
                    "tool": checked["tool"], "mode": _bidirectional_mode(_config_bidirectional_mode())}
        _DISPATCH_APPROVALS.pop(str(approval_id), None)
        await hub.orch.submit(goal, checked["tool"])
        return {"ok": True, "submitted": True, "tool": checked["tool"],
                "mode": _bidirectional_mode(_config_bidirectional_mode()),
                "note": "已提交为普通任务；执行中若遇到需要确认的步骤，仍会走右侧确认流程。"}

    @app.get("/api/chaos")
    async def api_chaos() -> dict:
        """混沌测试状态（测试专用，默认关闭；正常控制台没有混沌按钮）。

        开启只能走 POST /api/chaos 且带确认串，运行时覆盖、不写回配置。
        """
        from ..chaos.guard import CONFIRM_STRING, is_test_mode_enabled

        try:
            config_enabled = bool(get_settings().chaos.enabled)
        except Exception:
            config_enabled = False
        return {
            "test_only": True,
            "enabled": is_test_mode_enabled(),
            "config_enabled": config_enabled,
            "confirm_string_hint": "POST 时需带 confirm=CHAOS-TEST-ONLY（接口返回不重复完整确认串的用法以外内容）",
            "note": "混沌是测试专用故障注入，默认关闭；正常任务不会触发混沌；"
                    "本接口不接受普通任务消息里的 chaos 字段。",
        }

    @app.post("/api/chaos")
    async def api_set_chaos(body: dict) -> dict:
        """运行时开启/关闭混沌测试模式（测试专用，不写回配置文件）。

        开启条件：body.test_mode 为 true 且 body.confirm 等于确认串。
        关闭不需要确认串。任何其它组合一律拒绝开启。
        """
        from ..chaos.guard import CONFIRM_STRING, disable_test_mode, enable_test_mode

        if body.get("test_mode") is True and body.get("confirm") == CONFIRM_STRING:
            enable_test_mode(purpose="控制台测试接口（测试专用）")
            enabled = True
        elif body.get("test_mode") is False:
            disable_test_mode()
            enabled = False
        else:
            return {"ok": False, "error": "chaos test mode requires test_mode=true and the test-only confirm string"}
        status = await api_chaos()
        return {"ok": True, "enabled": enabled, **status}

    @app.get("/api/usage")
    async def api_usage() -> dict:
        """v0.3.0: Token usage totals. Only real provider calls with
        usage returned by the provider contribute to token sums;
        calls with no usage are counted as unknown, not zero, and
        test/stub/mock calls are excluded. Cost is shown only when
        the operator placed prices.json in .zhuli_runtime."""
        return usage_summary()

    @app.get("/api/security")
    async def api_security() -> dict:
        """返回加密与安全状态（不含任何秘密，仅指纹与来源）。"""
        return security_info()

    @app.put("/api/skills/{skill_id}")
    async def api_skill_update(skill_id: int, body: dict) -> dict:
        store.update_skill(skill_id, **body)
        return {"ok": True, "id": skill_id}

    @app.delete("/api/skills/{skill_id}")
    async def api_skill_delete(skill_id: int) -> dict:
        store.delete_skill(skill_id)
        return {"ok": True, "id": skill_id}

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket) -> None:
        await ws.accept()
        await hub.connect(ws)
        try:
            while True:
                data = await ws.receive_json()
                await _dispatch(data)
        except WebSocketDisconnect:
            await hub.disconnect(ws)
        except Exception:
            await hub.disconnect(ws)

    async def _dispatch(data: dict) -> None:
        t = data.get("type")
        if t == "task":
            # v0.3.0 双向开关同样约束普通任务消息：目标工具是 IDE 时，
            # 只有开关在 Zhuli -> IDE 位置才提交；否则只广播一条错误，
            # 不提交、不执行。Orchestrator.submit 里还有第二道检查。
            _tool = data.get("target_tool")
            if _tool and str(_tool).lower() in _IDE_TOOLS:
                _mode = _bidirectional_mode(_config_bidirectional_mode())
                if not _can_console_dispatch(_mode):
                    await hub._sink(ErrorEvent(type="error", message=_console_block_reason(_mode)))
                    return
            # session_id is optional and backward compatible: old
            # clients that omit it still work, with usage recorded
            # without a session id.
            await hub.orch.submit(
                data.get("goal", ""), data.get("target_tool"),
                session_id=data.get("session_id"),
            )
        elif t == "confirm":
            hub.orch.resolve_confirm(bool(data.get("approved", False)))
        elif t == "credential":
            hub.orch.resolve_credential(data.get("values", {}))
        elif t == "control":
            act = data.get("action")
            if act == "pause":
                hub.orch.pause()
            elif act == "resume":
                hub.orch.resume()
            elif act == "takeover":
                hub.orch.takeover()
            elif act == "stop":
                hub.orch.stop()

    # 静态托管（前端构建产物）
    if _STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

        @app.get("/")
        async def index() -> FileResponse:
            return FileResponse(str(_STATIC_DIR / "index.html"))

    return app
