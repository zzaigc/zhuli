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
                 hive_size: int = 3) -> None:
        super().__init__(registry, sink, settings)
        self.hive_size = max(1, min(hive_size, 4))
        self.blackboard = Blackboard()
        self._proposers: list[ActorAgent] = self._build_swarm()

    def _build_swarm(self) -> list[ActorAgent]:
        """组建执行体蜂群（同一 provider 下用不同 temperature 制造多样性）。"""
        # 注册表可容纳异构智能体（外部工具/专项/自定义），故安全取值
        base = self._get("actor", ActorAgent)
        cap = str(getattr(base, "capability", "reasoning") or "reasoning")
        prov = getattr(base, "provider", None)
        return [
            ActorAgent(
                capability=cap, provider=prov,
                temperature=_TEMPERATURES[i % len(_TEMPERATURES)],
                name=f"actor#{i + 1}",
            )
            for i in range(self.hive_size)
        ]

    # ---------- 蜂巢决策 ----------
    async def decide(self, *, observation: str, subtask: str,
                     verification: list[str] | None, history: list[dict],
                     skills_text: str = "", known_ids: list[str] | None = None,
                     url: str = "") -> dict:
        if self._single_brain():
            return await self._fallback_decide(
                observation=observation, subtask=subtask, verification=verification,
                history=history, skills_text=skills_text, url=url,
            )

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
        return {
            "proposal": best["proposal"],
            "criticism": best["criticism"],
            "risk": best["risk"],
            # 最优动作仍被判「不可行」或「高危」→ 否决，交回上层触发重规划
            "abort": winner_verdict == "abort" or winner_risk == "danger",
            "votes": votes,
            "blackboard": self.blackboard.snapshot(),
        }

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
