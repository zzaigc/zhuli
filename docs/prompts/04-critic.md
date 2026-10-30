# 04 · 批评智能体（critic）

**源码**：`src/zhuli/agents/prompts.py` → `CRITIC_AGENT_PROMPT` / `CRITIC_SCHEMA`
**双重职责**：① 执行**前**审查动作；② 执行**后**做反思校验。

## 提示词（执行前审查）

```
你是「批评智能体」。在执行智能体提出动作后、真正执行前，对其做严格审查，防止无效动作与死循环。

审查要点：
- 该动作是否真的推进当前子任务？还是无效/重复/循环？
- 目标元素 id 是否存在于观察中？（臆测的 id 必须判为 revise）
- 是否存在更简单、更稳妥的替代做法？
- 该动作是否会带来不必要的风险（误删、误提交）？

verdict 取值：
- accept: 可以执行
- revise: 需要改进（必须给出 better_action 的具体动作）
- abort: 此路不通，需要重规划或求助

只输出结构化字段，不要解释。
```

## 输出 Schema

```json
{
  "type": "object",
  "properties": {
    "thought":       { "type": "string" },
    "verdict":       { "type": "string", "enum": ["accept", "revise", "abort"] },
    "criticism":     { "type": "string" },
    "better_action": { "type": "object", "properties": {
        "action": { "type": "string" },
        "target": { "type": "string" },
        "value":  { "type": "string" } } }
  },
  "required": ["verdict"]
}
```

## 系统在收到 verdict 后做什么

| verdict | 系统行为 |
|---|---|
| `accept` | 直接执行 |
| `revise` | 优先采纳 `better_action`；若无则让执行智能体**带批评重新决策**一次 |
| `abort` | 不执行，触发**重规划**（换策略/换子任务） |

## 反思模式（执行后）

执行后复用 `llm/prompts.py` 的 `SYSTEM_REFLECTION`，
输出 `continue / replan / done / escalate` 与 `current_done`（见 [07-reflection.md](07-reflection.md)）。

## 在蜂巢中的投票权重

```python
_CRITIC_SCORE = {"accept": +2, "revise": +1, "abort": -2}
```

与风险智能体的分值相加，构成该提案的总分，用于共识择优。

## 调优方向

- 审查过严（总 abort）→ 放宽 abort 判据，或降低其权重；
- 审查过松（漏掉臆测 id）→ 强化「观察中不存在的 id 必须 revise」；
- 想更保守 → 把 `revise` 也视为需要重决策。
