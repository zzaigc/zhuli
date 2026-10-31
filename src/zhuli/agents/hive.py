"""蜂巢思维协调器（HiveCoordinator）。

与常规多智能体流水线（串行审批）不同，蜂巢模式是**群体并行 + 共识择优**：

```
        ┌─ 执行体#1（低温·保守）─┐
观察 → 黑板 ─┼─ 执行体#2（中温·均衡）─┼─→ 并行提案
        └─ 执行体#3（高温·探索）─┘
                     │
            （每个提案并行送审）
        ┌────────────┴────────────┐
    批评智能体                 风险智能体     → 并行评审
        └────────────┬────────────┘
                  共识（加权投票）
                     │
              择优执行 / 全体否决→重规划
```

关键特性：
- **群体多样性**：多个执行体使用不同 temperature（也可配不同 provider），避免单一思路。
- **并行**：提案与评审全部并发，不因增加成员而线性变慢。
- **共识**：批评与风险加权打分选出最优动作，而非听任某一个体。
- **容错**：个别成员失效（LLM 报错）不影响整体；全部失效则自动降级为单体决策。
- **共享黑板**：所有认知沉淀在 Blackboard 上，可观测、可复盘。
"""
from __future__ import annotations

import asyncio

from ..config.schemas import Settings
from .blackboard import Blackboard
from .coordinator import Coordinator
from .registry import AgentRegistry
from .roles import ActorAgent, CriticAgent, RiskAgent

# 加权打分：批评结论 与 风险等级 共同决定一个提案的得分
_CRITIC_SCORE = {"accept": 2, "revise": 1, "abort": -2}
_RISK_SCORE = {"safe": 2, "confirm": 0, "danger": -2}
# 多样性温度：保守 / 均衡 / 探索
_TEMPERATURES = (0.2, 0.5, 0.9, 1.1)
_AUTO_MIN, _AUTO_MAX = 2, 8
_RISK_WORDS = ("风险", "危险", "确认", "敏感", "支付", "删除", "risk", "danger", "confirm", "sensitive")


def temperatures_for_size(size: int) -> list[float]:
    """Temperatures for a swarm of the given size.

    Size <= 4 keeps the original order (0.2, 0.5, 0.9, 1.1) exactly.
    Size > 4 spreads evenly across roughly 0.2 to 1.2 instead of
    repeating the same four values, so a large swarm is actually
    diverse rather than the same four minds in the same order.
    """
    if size <= len(_TEMPERATURES):
        return list(_TEMPERATURES[:size])
    if size == 1:
        return [0.2]
    return [round(0.2 + (1.2 - 0.2) * i / (size - 1), 2) for i in range(size)]


def auto_decide_size(subtask: str = "", verification: list[str] | None = None,
                     total_subtasks: int | None = None,
                     history: list[dict] | None = None) -> tuple[int, str]:
    """Heuristic auto hive size (2-8). Documented, not a guaranteed optimum.

    Base 3. +1 per extra subtask beyond 2. +1 when verification
    criteria are many (>= 3). +1 when the subtask/verification
    mentions risk/danger/confirmation. +1 for a long or multi-part
    subtask. -1 for a very simple single-step goal. Clamped to 2-8,
    so auto never silently uses a huge swarm.
    """
    reasons: list[str] = []
    size = 3
    reasons.append("基础3")
    if total_subtasks is not None and total_subtasks > 2:
        extra = total_subtasks - 2
        size += extra
        reasons.append(f"多子任务+{extra}（共{total_subtasks}个）")
    ver = list(verification or [])
    if len(ver) >= 3:
        size += 1
        reasons.append("验证标准多+1")
    hay = (subtask or "") + " " + " ".join(str(v) for v in ver)
    hay_low = hay.lower()
    if any(w in hay or w in hay_low for w in _RISK_WORDS):
        size += 1
        reasons.append("含风险/确认+1")
    if len(subtask or "") > 80 or "；" in (subtask or "") or (subtask or "").count("、") >= 2:
        size += 1
        reasons.append("长/多段任务+1")
    if (len(subtask or "") < 20 and not ver and not history
            and total_subtasks in (None, 1)):
        size -= 1
        reasons.append("简单单步-1")
    clamped = max(_AUTO_MIN, min(size, _AUTO_MAX))
    if clamped != size:
        reasons.append(f"自动范围限制到{_AUTO_MIN}~{_AUTO_MAX}")
    reason = " + ".join(reasons) + f" = {clamped}"
    return clamped, reason


def _score(criticism: dict | None, risk: dict | None) -> int:
    s = 0
    if criticism:
        s += _CRITIC_SCORE.get(criticism.get("verdict"), 0)
    if risk:
        s += _RISK_SCORE.get(risk.get("level"), 0)
    return s


class HiveCoordinator(Coordinator):
    """蜂巢协调器：继承常规协调能力（规划/观察/反思/技能），仅把「决策」升级为群体共识。"""

    def __init__(self, registry: AgentRegistry, sink=None, settings: Settings | None = None,
                 hive_size: int = 3, hive_size_mode: str = "manual") -> None:
        super().__init__(registry, sink, settings)
        if isinstance(hive_size, bool) or not isinstance(hive_size, int) or hive_size < 1:
            raise ValueError("hive_size must be an integer >= 1")
        if hive_size_mode not in ("manual", "auto"):
            raise ValueError("hive_size_mode must be 'manual' or 'auto'")
        self.hive_size = hive_size
        self.manual_size = hive_size
        self.hive_size_mode = hive_size_mode
        self.last_auto: dict | None = None
        self.blackboard = Blackboard()
        self._proposers: list[ActorAgent] = self._build_swarm()

    def _build_swarm(self, size: int | None = None) -> list[ActorAgent]:
        """组建执行体蜂群（同一 provider 下用不同 temperature 制造多样性）。"""
        n = self.hive_size if size is None else size
        temps = temperatures_for_size(n)
        # 注册表可容纳异构智能体（外部工具/专项/自定义），故安全取值
        base = self._get("actor", ActorAgent)
        cap = str(getattr(base, "capability", "reasoning") or "reasoning")
        prov = getattr(base, "provider", None)
        return [
            ActorAgent(
                capability=cap, provider=prov,
                temperature=temps[i],
                name=f"actor#{i + 1}",
            )
            for i in range(n)
        ]

    # ---------- 蜂巢决策 ----------
    async def decide(self, *, observation: str, subtask: str,
                     verification: list[str] | None, history: list[dict],
                     skills_text: str = "", known_ids: list[str] | None = None,
                     url: str = "", total_subtasks: int | None = None) -> dict:
        if self._single_brain():
            return await self._fallback_decide(
                observation=observation, subtask=subtask, verification=verification,
                history=history, skills_text=skills_text, url=url,
            )

        # 自动模式：在每一步蜂巢决策前按任务启发式选规模（2-8），
        # 手动规模保存在 manual_size，绝不被自动结果覆盖。
        auto_info: dict | None = None
        if self.hive_size_mode == "auto":
            auto_size, auto_reason = auto_decide_size(
                subtask, verification, total_subtasks, history)
            auto_info = {"size": auto_size, "reason": auto_reason}
            self.last_auto = dict(auto_info)
            try:
                from .runtime import set_last_auto
                set_last_auto(auto_size, auto_reason)
            except Exception:
                pass
            if auto_size != len(self._proposers):
                self.hive_size = auto_size
                self._proposers = self._build_swarm(auto_size)

        # 每步重置黑板，写入共享上下文
        self.blackboard.reset()
        self.blackboard.write("ctx", "subtask", subtask)
        self.blackboard.write("ctx", "verification", verification or [])

        # 1) 群体并行提案
        results = await asyncio.gather(
            *[p.run(observation, subtask, verification, history, skills_text)
              for p in self._proposers],
            return_exceptions=True,
        )
        proposals: list[tuple[str, dict]] = []
        for p, r in zip(self._proposers, results):
            if isinstance(r, BaseException):
                await self._emit(p.name, "decide", summary=f"提案失败：{r}")
                continue
            if isinstance(r, dict) and r.get("action"):
                proposals.append((p.name, r))
                self.blackboard.write(p.name, "proposal", r.get("action"))
                await self._emit(p.name, "decide", summary=str(r.get("thought") or "")[:200])

        if not proposals:
            # 蜂群全部失效 → 优雅降级为单体决策
            await self._emit("hive", "consensus", summary="蜂群全部失效，降级为单体决策")
            return await super().decide(
                observation=observation, subtask=subtask, verification=verification,
                history=history, skills_text=skills_text, known_ids=known_ids, url=url,
            )

        # 2) 每个提案并行送审（批评 + 风险）
        critiques = await asyncio.gather(
            *[self._review(prop, subtask, verification, known_ids or [], url)
              for _, prop in proposals]
        )

        scored = []
        for (name, prop), (criticism, risk) in zip(proposals, critiques):
            score = _score(criticism, risk)
            scored.append({"name": name, "proposal": prop, "criticism": criticism,
                           "risk": risk, "score": score})
            self.blackboard.write(name, "vote", score)
        scored.sort(key=lambda x: x["score"], reverse=True)

        best = scored[0]
        self.blackboard.write("hive", "decision", best["proposal"].get("action"))
        votes = [
            {"agent": s["name"], "action": s["proposal"].get("action"), "score": s["score"],
             "verdict": (s["criticism"] or {}).get("verdict"),
             "risk": (s["risk"] or {}).get("level")}
            for s in scored
        ]
        await self._emit(
            "hive", "consensus",
            summary=" / ".join(f"{v['agent']}:{v['action']}({v['score']})" for v in votes),
            verdict=f"选中 {best['name']} → {best['proposal'].get('action')}",
        )

        winner_verdict = (best["criticism"] or {}).get("verdict")
        winner_risk = (best["risk"] or {}).get("level")
        out = {
            "proposal": best["proposal"],
            "criticism": best["criticism"],
            "risk": best["risk"],
            # 最优动作仍被判「不可行」或「高危」→ 否决，交回上层触发重规划
            "abort": winner_verdict == "abort" or winner_risk == "danger",
            "votes": votes,
            "blackboard": self.blackboard.snapshot(),
        }
        if auto_info is not None:
            out["auto"] = auto_info
        return out

    async def _review(self, proposal: dict, subtask: str, verification: list[str] | None,
                      known_ids: list[str], url: str) -> tuple[dict | None, dict | None]:
        """对单个提案并行征询批评与风险意见。"""
        critic = self._get("critic", CriticAgent)
        risk = self._get("risk", RiskAgent)
        c_task = critic.run(proposal, subtask, verification, known_ids) if critic else _none()
        r_task = risk.run(proposal, url) if risk else _none()
        return await asyncio.gather(c_task, r_task)


async def _none() -> None:
    return None
