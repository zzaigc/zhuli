"""编排器主循环：观察 → 决策 → 执行 → 反思。

把各能力模块（browser / computer / video / integrations）与决策核心
（planner / reflection / llm）串成闭环。对外只暴露：
  - submit(goal, target_tool) : 提交任务
  - pause / resume / stop      : 人在回路控制
  - resolve_confirm / resolve_credential : 处理确认/凭据卡片回传
  - sink                       : 事件推送回调（由 console 注入）
"""
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Optional, Union

from ..browser import actions as browser_actions
from ..browser import annotator
from ..browser.driver import BrowserDriver
from ..browser.guard import has_login_form, needs_confirm
from ..computer import executor as computer_executor
from ..computer.guard import classify as classify_command
from ..config.settings import get_settings
from ..credential.card import build_request, redact
from ..integrations.base import BaseConnector
from ..integrations.codebuddy import CodeBuddyConnector
from ..integrations.opencode import OpenCodeConnector
from ..integrations.trae import TraeConnector
from ..agents import Coordinator, build_coordinator, build_registry
from ..memory.skills import Skill, learn_from_task, retrieve_skills
from ..memory.store import store
from ..security.secure_string import SecureString
from ..video.ffmpeg_runner import run_plan as run_video
from .events import (
    Action, ChatEvent, CommandEvent, ConfirmRequestEvent, CredentialRequestEvent,
    ErrorEvent, PlanEvent, ReflectionEvent, ScreenshotEvent, StatusEvent, StepLogEvent,
    SkillEvent, ThinkEvent,
)
from .state import TaskContext

Event = Union[
    PlanEvent, ReflectionEvent, StepLogEvent, ScreenshotEvent, CommandEvent,
    ConfirmRequestEvent, CredentialRequestEvent, ChatEvent, StatusEvent, SkillEvent, ErrorEvent,
]
Sink = Callable[[Event], Awaitable[None]]

_CONNECTOR_REGISTRY = {
    "codebuddy": CodeBuddyConnector,
    "trae": TraeConnector,
    "opencode": OpenCodeConnector,
}


class Orchestrator:
    def __init__(self, sink: Sink) -> None:
        self.sink = sink
        self.ctx = TaskContext()
        self.browser: Optional[BrowserDriver] = None
        self.page = None
        self.connectors: dict[str, BaseConnector] = {}
        self._confirm_future: Optional[asyncio.Future] = None
        self._cred_future: Optional[asyncio.Future] = None
        self._resume_event = asyncio.Event()
        self._resume_event.set()
        self._stop = False
        self._loop: Optional[asyncio.Task] = None
        self._matched_skills: list[Skill] = []
        self.registry = None
        self.coord: Optional[Coordinator] = None
        self._pre_confirmed = False  # 风险智能体已确认过，避免规则护栏重复弹窗

    # ---------- 生命周期 ----------
    async def start(self) -> None:
        try:
            settings = get_settings()
        except Exception as e:
            await self.sink(
                ErrorEvent(
                    type="error",
                    message=f"配置加载失败：{e}（请复制 config/settings.yaml.example 为 config/settings.yaml 并填写）",
                )
            )
            return
        try:
            self.browser = await BrowserDriver(
                headless=settings.browser.headless,
                user_data_dir=settings.browser.user_data_dir,
                viewport=settings.browser.viewport.model_dump(),
            ).__aenter__()
            self.page = await self.browser.new_page()
        except Exception as e:
            await self.sink(
                ErrorEvent(
                    type="error",
                    message=f"浏览器启动失败（确认已安装 Chromium 且 user_data_dir 可写）：{e}",
                )
            )
            self.browser = None
            self.page = None

        for name, cfg in settings.integrations.items():
            cls = _CONNECTOR_REGISTRY.get(name)
            if cls:
                self.connectors[name] = cls(cfg.model_dump())

        # 构建多智能体团队（内置角色 + 外部工具智能体），供协调器调度
        self.registry = build_registry(settings, self.connectors)
        # 蜂巢模式（群体并行提案 + 共识择优）或常规多智能体流水线
        self.coord = build_coordinator(settings, self.registry, self._agent_sink)

    def rebuild_coordinator(self):
        """v0.2.0：用当前运行时覆盖重建协调器（Hive 开关用），不改写配置文件。

        返回新协调器；注册表未就绪时返回 None。正在运行的任务不受影响，
        新协调器只用于后续任务的决策。
        """
        if self.registry is None:
            return None
        settings = get_settings()
        self.coord = build_coordinator(settings, self.registry, self._agent_sink)
        return self.coord

    async def _agent_sink(self, event) -> None:
        """把多智能体活动事件转发给控制台（让「哪个智能体做了什么」可见）。"""
        await self.sink(event)

    async def shutdown(self) -> None:
        self._stop = True
        self._resume_event.set()
        if self.browser is not None:
            await self.browser.__aexit__(None, None, None)

    # ---------- 人在回路控制 ----------
    async def submit(self, goal: str, target_tool: Optional[str] = None) -> None:
        self.ctx = TaskContext(goal=goal, target_tool=target_tool)
        self._stop = False
        self._resume_event.set()
        self._loop = asyncio.create_task(self._run())

    def pause(self) -> None:
        if self.ctx.status == "running":
            self.ctx.status = "paused"
            asyncio.create_task(self.sink(StatusEvent(type="status", state="paused")))

    def resume(self) -> None:
        if self.ctx.status == "paused":
            self.ctx.status = "running"
            self._resume_event.set()
            asyncio.create_task(self.sink(StatusEvent(type="status", state="running")))

    def takeover(self) -> None:
        """交还控制权：AI 停手，用户直接操作弹出的 Chromium 窗口，之后点「继续」交回。"""
        if self.ctx.status not in ("running", "awaiting_confirm", "awaiting_credential"):
            return
        self.ctx.status = "paused"
        asyncio.create_task(self.sink(StatusEvent(type="status", state="paused", message=None)))
        asyncio.create_task(
            self.sink(ChatEvent(
                type="chat", role="system",
                text="已交还控制权：你现在可以直接操作弹出的 Chromium 窗口，完成后点「继续」让 AI 重新接管。",
            ))
        )

    def stop(self) -> None:
        self._stop = True
        self._resume_event.set()
        self.ctx.status = "stopped"
        asyncio.create_task(self.sink(StatusEvent(type="status", state="stopped")))

    def resolve_confirm(self, approved: bool) -> None:
        if self._confirm_future and not self._confirm_future.done():
            self._confirm_future.set_result(approved)

    def resolve_credential(self, values: dict) -> None:
        if self._cred_future and not self._cred_future.done():
            self._cred_future.set_result(values)

    # ---------- 主循环 ----------
    async def _run(self) -> None:
        settings = get_settings()
        if self.coord is None:
            await self.sink(ErrorEvent(
                type="error",
                message="智能体团队未就绪：配置加载失败，请检查 config/settings.yaml",
            ))
            return
        self.ctx.status = "running"
        await self.sink(ChatEvent(type="chat", role="assistant", text=f"收到任务：{self.ctx.goal}"))

        # 检索可复用的历史技能，注入规划与决策上下文（Muse 式「越用越聪明」）
        self._matched_skills = await retrieve_skills(self.ctx.goal)
        for s in self._matched_skills:
            await self.sink(SkillEvent(type="skill", name=s.name, description=s.description,
                                       action="matched", reason=s.trigger))

        # 经验上下文：检索到的技能 + 已升格的专项智能体
        extra = self.coord.skills_context(self._matched_skills)
        plan = await self.coord.plan(self.ctx.goal, extra_context=extra)
        self.ctx.subtasks = plan.get("subtasks", [self.ctx.goal])
        self.ctx.verification = plan.get("verification", [])
        self.ctx.current = plan.get("current", self.ctx.goal)
        await self.sink(ThinkEvent(type="think", stage="plan",
                                   text=plan.get("thought") or "已生成初始计划"))
        await self._emit_plan()

        if self.ctx.target_tool and self.ctx.target_tool in self.connectors:
            conn = self.connectors[self.ctx.target_tool]
            if conn.kind == "browser" and self.page is not None:
                await self.page.goto(conn.config.get("url", "about:blank"))

        max_steps = settings.policy.max_steps
        while self.ctx.step < max_steps and not self._stop:
            await self._resume_event.wait()
            if self._stop:
                break
            try:
                await self._step(settings)
            except Exception as e:  # 单步异常兜底
                await self.sink(ErrorEvent(type="error", message=f"执行异常：{e}"))
                # 快照回滚（浏览器场景）后重试一次
                await self._rollback()
                try:
                    await self._step(settings)
                except Exception as e2:
                    await self.sink(ErrorEvent(type="error", message=f"重试仍失败：{e2}"))
                    self.ctx.status = "error"
                    await self.sink(StatusEvent(type="status", state="error",
                                                message="需要你介入：连续执行失败，已停止"))
                    break
            # 终止条件：反思判定完成或升级
            if self.ctx.status in ("done", "error"):
                break
            # 确定性循环/卡死检测：连续重复相同动作则强制重规划
            if self._detect_loop(threshold=3):
                await self.sink(ThinkEvent(type="think", stage="reflect",
                                           text="检测到连续重复动作（疑似死循环），强制重规划"))
                await self._do_replan(feedback="连续重复相同动作且未产生进展，请换策略或换子任务")
                if self.ctx.status in ("done", "error"):
                    break
        if not self._stop and self.ctx.status != "error":
            self.ctx.status = "done"
            await self.sink(StatusEvent(type="status", state="done", message="任务结束"))
        # 任务结束后沉淀/迭代技能（成功才学习）
        await self._learn()

    # ---------- 计划/重规划辅助 ----------
    async def _emit_plan(self) -> None:
        await self.sink(PlanEvent(type="plan", subtasks=self.ctx.subtasks,
                                  current=self.ctx.current, done=self.ctx.done,
                                  verification=self.ctx.verification))

    async def _do_replan(self, feedback: str) -> None:
        self.ctx.replan_count += 1
        if self.ctx.replan_count > 3:
            self.ctx.status = "error"
            await self.sink(StatusEvent(type="status", state="error",
                                        message="需要你介入：多次重规划仍无效，请调整目标或配置"))
            return
        plan = await self.coord.replan(self.ctx.goal, feedback, self.ctx.history, self.ctx.subtasks)
        # 保留已完成的子任务，只更新未完成部分
        new_subs = plan.get("subtasks", self.ctx.subtasks)
        kept = [s for s in self.ctx.done]
        self.ctx.subtasks = kept + [s for s in new_subs if s not in kept]
        self.ctx.verification = plan.get("verification", self.ctx.verification)
        if self.ctx.current not in self.ctx.subtasks or self.ctx.current in self.ctx.done:
            self.ctx.advance_subtask(plan.get("current"))
        await self.sink(ThinkEvent(type="think", stage="plan",
                                   text=plan.get("thought") or "已重规划"))
        await self._emit_plan()

    def _detect_loop(self, threshold: int = 3) -> bool:
        """确定性循环检测：最近 N 个动作的指纹完全相同 => 疑似死循环。"""
        recent = [h["action"] for h in self.ctx.history[-threshold:]]
        if len(recent) < threshold:
            return False
        fps = [f"{a.get('action')}:{a.get('target')}" for a in recent]
        return len(set(fps)) == 1

    async def _rollback(self) -> None:
        """单步失败后的最佳努力回滚：浏览器回到上一步 URL。"""
        if self.page is not None and getattr(self, "_last_url", None):
            try:
                await self.page.goto(self._last_url)
            except Exception:
                pass

    async def _step(self, settings) -> None:
        # 0) 记录快照 URL（用于失败回滚）
        if self.page is not None:
            self._last_url = self.page.url

        # 1) 观察（原始）
        elements: list[dict] = []
        if self.page is not None:
            elements = await annotator.annotate(self.page)
            a11y = await annotator.accessibility_summary(self.page)
            raw = (
                f"当前URL: {self.page.url}\n"
                f"目标工具: {self.ctx.target_tool or '本助理'}\n"
                f"当前子任务: {self.ctx.current or '(未规划)'}\n"
                f"当前子任务完成标准: {self.ctx.verification_for(self.ctx.current) or '无'}\n"
                f"子任务进度: 已完成 {len(self.ctx.done)}/{len(self.ctx.subtasks)}\n"
                f"可交互元素:\n"
                + "\n".join(
                    f"[{e.get('id')}] <{e.get('tag')}> {e.get('text','')} {e.get('name','')}".strip()
                    for e in elements[:60]
                )
                + f"\n可访问性树摘要:\n{a11y}"
            )
        else:
            raw = "(无浏览器上下文，仅命令/视频能力可用)"

        known_ids = [str(e.get("id")) for e in elements]
        skills_text = self.coord.skills_context(self._matched_skills)

        # 2) 观察蒸馏（Observer 智能体）→ 聚焦当前子任务，降低噪声
        distilled = await self.coord.observe(
            raw, self.ctx.current, self.ctx.verification_for(self.ctx.current),
            skill_hints=skills_text,
        )
        if distilled:
            relevant = set(str(i) for i in (distilled.get("relevant_ids") or []))
            kept = [e for e in elements if str(e.get("id")) in relevant] or elements[:30]
            obs = (
                f"当前URL: {self.page.url if self.page else '-'}\n"
                f"页面状态: {distilled.get('summary', '')}\n"
                f"障碍: {distilled.get('obstacles') or '无'}\n"
                f"当前子任务: {self.ctx.current or '(未规划)'}\n"
                f"相关元素:\n"
                + "\n".join(
                    f"[{e.get('id')}] <{e.get('tag')}> {e.get('text','')}".strip() for e in kept
                )
            )
        else:
            obs = raw

        # 3) 多智能体决策：执行智能体提议 → 批评+风险并发审查 → 必要时带批评重决策
        res = await self.coord.decide(
            observation=obs,
            subtask=self.ctx.current,
            verification=self.ctx.verification_for(self.ctx.current),
            history=self.ctx.history,
            skills_text=skills_text,
            known_ids=known_ids,
            url=self.page.url if self.page else "",
        )
        if res.get("abort"):
            await self.sink(ThinkEvent(type="think", stage="reflect",
                                       text="批评智能体判定当前路线不可行，触发重规划"))
            await self._do_replan(feedback="批评智能体判定此路不通，请换策略或换子任务")
            return

        # 蜂巢模式：把群体投票过程可见化（看得见「蜂巢在怎么想」）
        if res.get("votes"):
            summary = "，".join(
                f"{v['agent']} 提议 {v['action']}（得分 {v['score']}"
                f"｜批评 {v.get('verdict') or '-'}｜风险 {v.get('risk') or '-'}）"
                for v in res["votes"]
            )
            await self.sink(ThinkEvent(type="think", stage="decide", text="🐝 蜂巢共识：" + summary))

        decision = res["proposal"]
        action = Action(**{k: v for k, v in decision.items() if k in Action.model_fields})
        await self.sink(ThinkEvent(type="think", stage="decide",
                                   text=action.thought or action.reason or "（无思考内容）"))
        await self.sink(ChatEvent(type="chat", role="assistant",
                                  text=action.reason or f"动作：{action.action}"))

        if action.action == "done":
            self.ctx.status = "done"
            return

        # 4) 风险智能体判定需确认时，先走人在回路（并避免与规则护栏重复弹窗）
        risk = res.get("risk") or {}
        self._pre_confirmed = False
        if risk.get("level") in ("confirm", "danger") and settings.policy.confirm_dangerous:
            if not await self._await_confirm(action, risk.get("reason") or "风险智能体判定需用户确认"):
                self.ctx.record(decision, "用户取消了高风险操作")
                return
            self._pre_confirmed = True

        # 5) 执行（含规则护栏/凭据）
        result = await self._execute(action, settings)

        # 6) 日志 + 截图
        log_action = action.model_copy(update={"value": redact(action.value)})
        await self.sink(StepLogEvent(type="step_log", step=self.ctx.step,
                                     action=log_action, observation_summary=obs[:300]))
        if self.page is not None and action.action not in ("shell", "video", "tool_task"):
            img = await annotator.get_screenshot(self.page)
            hl = await annotator.highlight(self.page, action.target)
            await self.sink(ScreenshotEvent(type="screenshot", image_b64=img, highlights=hl))

        self.ctx.record(decision, str(result))

        # 7) 反思（批评智能体校验当前子任务是否达成）
        refl = await self.coord.reflect(
            self.ctx.goal, self.ctx.current,
            self.ctx.verification_for(self.ctx.current),
            self.ctx.history, settings.policy.max_steps,
        )
        await self.sink(ThinkEvent(type="think", stage="reflect",
                                   text=refl.get("thought") or refl.get("reason") or ""))
        await self.sink(ReflectionEvent(type="reflection", status=refl["status"], reason=refl["reason"]))

        if refl["status"] == "done":
            self.ctx.status = "done"
        elif refl.get("current_done"):
            # 当前子任务达成，推进到下一子任务
            self.ctx.advance_subtask(refl.get("next"))
            await self._emit_plan()
        elif refl["status"] == "replan":
            await self._do_replan(feedback=refl["reason"])
        elif refl["status"] == "escalate":
            self.ctx.status = "error"
            await self.sink(StatusEvent(type="status", state="error",
                                        message="需要你介入：" + refl["reason"]))

    # ---------- 技能沉淀（Muse 式自进化）----------
    async def _learn(self) -> None:
        if not self.ctx.history:
            return
        success = self.ctx.status == "done" and not self._stop
        procedure = "\n".join(
            f"{i + 1}. {h['action'].get('action')} {h['action'].get('target')} — {(h.get('observation') or '')[:120]}"
            for i, h in enumerate(self.ctx.history)
        )
        summary = procedure[:800]
        # 技能挖掘交给「技能挖掘智能体」（未就绪时回退内置实现）
        miner = self.coord.registry.get("skill_miner") if self.coord else None
        try:
            skill, action = await learn_from_task(
                self.ctx.goal, self.ctx.target_tool, success, procedure, summary, miner=miner
            )
        except Exception as e:
            await self.sink(ErrorEvent(type="error", message=f"技能沉淀失败（不影响主流程）：{e}"))
            return
        # 标记本次命中的技能为已使用
        if success:
            for s in self._matched_skills:
                if s.id:
                    try:
                        await asyncio.to_thread(store.update_stats, s.id, True)
                    except Exception:
                        pass
        if skill and action:
            await self.sink(SkillEvent(type="skill", name=skill.name, description=skill.description,
                                       action=action, reason=skill.trigger))
        # 技能成熟后升格为专项智能体 → 系统模块随使用增长（越用越智能）
        if skill and self.coord:
            try:
                promoted = self.coord.promote(skill)
            except Exception:
                promoted = None
            if promoted:
                await self.sink(SkillEvent(
                    type="skill", name=skill.name, description=skill.description,
                    action="promoted",
                    reason=f"已升格为专项智能体（团队现有 {len(self.coord.registry)} 个模块）",
                ))

    async def _execute(self, action: Action, settings) -> str:
        a = action.action
        # ---- 浏览器类 ----
        if a in ("click", "type", "goto", "scroll", "submit", "wait", "navigate"):
            if self.page is None:
                return "错误：无浏览器上下文"
            need, reason = await needs_confirm(action, self.page)
            if need and settings.policy.confirm_dangerous and not self._pre_confirmed:
                if not await self._await_confirm(action, reason):
                    return "用户取消了该操作"
            res = await browser_actions.execute(self.page, action)
            return "ok" if res["ok"] else f"失败：{res.get('error')}"

        # ---- 凭据填写 ----
        if a == "fill_credential":
            fields = [action.target or "password"]
            # 若页面有登录表单，补全所需字段
            login = await has_login_form(self.page) if self.page else None
            if login:
                fields = login
            await self.sink(build_request(fields))
            self.ctx.status = "awaiting_credential"
            values = await self._await_credential()
            self.ctx.status = "running"
            injected: list[str] = []
            # 凭据在内存中仅以密文持有，只在注入瞬间解密，用完立即销毁
            for f, v in values.items():
                if not v:
                    continue
                sec = SecureString(v, label=f"cred:{f}")
                try:
                    await browser_actions.fill_credential(self.page, f, sec.reveal())
                finally:
                    sec.wipe()
                injected.append(f)
            return f"已注入凭据字段：{', '.join(injected)}"

        # ---- 本地命令 ----
        if a == "shell":
            cmd = action.target or ""
            level, reason = classify_command(cmd)
            if level == "deny":
                await self.sink(ErrorEvent(type="error", message=f"命令被禁止：{reason}"))
                return "命令被禁止"
            if level == "confirm" and settings.policy.confirm_dangerous and not self._pre_confirmed:
                if not await self._await_confirm(action, reason):
                    return "用户取消了命令执行"
            res = await computer_executor.run(
                cmd, timeout=settings.computer.timeout_sec,
                max_chars=settings.computer.max_output_chars,
                on_output=self._cmd_out,
            )
            return f"exit={res.get('exit_code')}"

        # ---- 视频剪辑 ----
        if a == "video":
            out = await run_video(
                action.value or action.target or "",
                on_output=self._cmd_out,
            )
            return out.get("summary", "视频任务完成")

        # ---- 外部工具（派发给外部工具智能体）----
        if a == "tool_task":
            name = action.target or self.ctx.target_tool
            if not name:
                return "未指定外部工具"
            # v0.2.0：派发前先做显式检查（未知工具 / 缺页面 / 缺二进制），
            # 失败直接返回，不让异常进入决策循环；再走一次派发确认。
            from ..integrations.dispatch import check as dispatch_check
            _conn = self.connectors.get(str(name).lower())
            _cmd = getattr(_conn, "command", None) if _conn else None
            _chk = dispatch_check(str(name), action.value or action.target or "",
                                  page=self.page, command=_cmd)
            if not _chk.get("ok"):
                return str(_chk.get("error"))
            if settings.policy.confirm_dangerous and not self._pre_confirmed:
                if not await self._await_confirm(
                        action, f"派发给外部 IDE 工具 {name}：它可能读写文件，确认后执行"):
                    return "用户取消了外部工具派发"
            res = await self.coord.delegate(
                name,
                action.value or action.target or "",
                page=self.page,
                on_output=self._cmd_out,
            )
            if not res.get("ok"):
                await self.sink(ErrorEvent(type="error", message=str(res.get("result"))))
            return str(res.get("result", ""))[:500]

        return f"未知动作：{a}"

    # ---------- 等待用户交互 ----------
    async def _await_confirm(self, action: Action, reason: str) -> bool:
        self.ctx.status = "awaiting_confirm"
        await self.sink(ConfirmRequestEvent(type="confirm_request", reason=reason, pending_action=action))
        self._confirm_future = asyncio.get_event_loop().create_future()
        approved = await self._confirm_future
        self._confirm_future = None
        self.ctx.status = "running"
        return bool(approved)

    async def _await_credential(self) -> dict:
        self._cred_future = asyncio.get_event_loop().create_future()
        values = await self._cred_future
        self._cred_future = None
        return values or {}

    async def _cmd_out(self, stream: str, line: str) -> None:
        await self.sink(CommandEvent(type="command", cmd="", stream=stream, line=line))
