# 智能体系统提示词集

> **唯一真源是代码**：`src/zhuli/agents/prompts.py` 与 `src/zhuli/llm/prompts.py`。
> 本目录是它们的**可读副本**，用于评审、版本对比与交接；**改代码后请同步更新此处**。

## 为什么把提示词单独成册

- **多提示词**是本项目的核心设计：每个智能体有独立提示词与输出 Schema，互不影响；
- 改行为时优先改提示词，而不是硬编码进逻辑；
- 副本便于 AI 快速理解「每个角色被要求做什么」，无需翻代码。

## 清单

| 文件 | 角色 | 源码位置 |
|---|---|---|
| [01-planner.md](01-planner.md) | 规划智能体 | `llm/prompts.py` |
| [02-observer.md](02-observer.md) | 观察智能体 | `agents/prompts.py` |
| [03-actor.md](03-actor.md) | 执行智能体 | `agents/prompts.py` |
| [04-critic.md](04-critic.md) | 批评智能体 | `agents/prompts.py` |
| [05-risk.md](05-risk.md) | 风险智能体 | `agents/prompts.py` |
| [06-skill-miner.md](06-skill-miner.md) | 技能挖掘智能体 | `llm/prompts.py` |
| [07-reflection.md](07-reflection.md) | 反思（由批评智能体承担） | `llm/prompts.py` |
| [08-decision.md](08-decision.md) | 单脑模式决策大脑 | `llm/prompts.py` |

## 通用约定

1. 全部提示词都要求 **只输出结构化字段，不要解释**（由 JSON Schema 约束）；
2. 涉及凭据时一律要求输出 `fill_credential`，**绝不写真实凭据**；
3. 涉及元素时一律要求「只使用观察中真实存在的 id，不得臆测」；
4. 强调「遇阻必须换策略，绝不原样重复同一动作 3 次以上」（防死循环）。

## 调优建议

| 症状 | 优先改谁 |
|---|---|
| 计划不切实际 | `01-planner`（让 verification 更具体） |
| 决策噪声大 | `02-observer`（收紧 relevant_ids）+ 开 `observer_enabled` |
| 动作总点错元素 | `03-actor`（强化「不得臆测 id」）+ `04-critic`（严格判 revise） |
| 陷入死循环 | `04-critic`（abort 判据）+ 循环检测阈值 |
| 高危操作没拦住 | `05-risk` |
| 技能不够通用 | `06-skill-miner` |
| 过早/过晚认为完成 | `07-reflection` |
