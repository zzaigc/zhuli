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
from ..config.settings import get_settings
from ..core.events import to_ws, Event
from ..core.orchestrator import Orchestrator
from ..credential.vault import configure_security, security_info
from ..llm import router as llm_router
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_security()  # 配置就绪后再初始化军事级加密（缺配置也不影响启动）
    await hub.orch.start()
    yield
    await hub.orch.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(title="ZHULI", version="0.1.0", lifespan=lifespan)

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
            await hub.orch.submit(data.get("goal", ""), data.get("target_tool"))
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
