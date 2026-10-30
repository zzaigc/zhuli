# 02 · 观察智能体（observer）

**源码**：`src/zhuli/agents/prompts.py` → `OBSERVER_AGENT_PROMPT` / `OBSERVER_SCHEMA`
**职责**：把原始页面观察蒸馏成对「当前子任务」真正有用的信息，降低决策噪声。
**开关**：`policy.observer_enabled`（关闭时不调用，直接用原始观察）。

## 提示词

```
你是「观察智能体」。职责：把原始页面观察（可交互元素列表 + 可访问性树）蒸馏成对「当前子任务」真正有用的信息，降低后续决策的噪声。

要求：
- 只保留与当前子任务相关的元素 id，剔除无关项（如广告、导航冗余项）。
- 用一句话总结当前页面状态：在哪个页面、是否已登录、是否已出现目标内容。
- 指出达成当前子任务的关键障碍（元素未加载 / 需要滚动 / 需要登录 / 需要等待）。
- 判断当前子任务看起来是否已经完成（progress）。
只输出结构化字段，不要解释。
```

## 输出 Schema

```json
{
  "type": "object",
  "properties": {
    "summary":      { "type": "string" },
    "relevant_ids": { "type": "array", "items": { "type": "string" } },
    "obstacles":    { "type": "string" },
    "progress":     { "type": "string", "enum": ["not_started", "in_progress", "done"] }
  },
  "required": ["summary"]
}
```

## 在决策链中的作用

蒸馏结果会被 `Orchestrator` 用来**重构给执行智能体的观察**：

```
页面状态: <summary>
障碍: <obstacles>
当前子任务: <current>
相关元素: [只保留 relevant_ids 对应的元素]
```

收益：
- **降噪**：剔除广告/无关导航，减少无关元素导致的误点；
- **省 token**：原始观察最多 60 个元素，蒸馏后通常只剩几个；
- **显式障碍**：让执行智能体知道「该滚动/等待/登录」，而不是盲动。

> 若 `relevant_ids` 为空，系统会回退保留前 30 个元素，保证不会因蒸馏过度而无元素可用。
