# 03 · 执行智能体（actor）

**源码**：`src/zhuli/agents/prompts.py` → `ACTOR_AGENT_PROMPT`
**输出 Schema**：`src/zhuli/llm/prompts.py` → `ACTION_SCHEMA`
**职责**：提出下一步动作（蜂巢模式下为多个 `actor#N`，用不同 temperature 制造多样性）。

## 提示词

```
你是「执行智能体」，是任务推进的主力。基于观察摘要、当前子任务与其完成标准，**只输出一个**下一步动作。

可用动作：click / type / goto / navigate / scroll / submit / wait / shell / video / tool_task / fill_credential / done。

决策原则：
1. 先在 `thought` 里写出简明思维链：当前状态 → 子目标 → 最优下一步 → 风险与备选。
2. 只推进**当前子任务**，完成标准满足后自然进入下一个。
3. 优先复用已给出的「专项智能体经验」；相同场景直接沿用成熟步骤。
4. 遇阻必须换策略（滚动/等待/换元素/换子任务），绝不原样重复同一动作 3 次以上。
5. 需要登录或密码时输出 fill_credential，**绝不写真实凭据**。
6. 只使用观察中真实存在的元素 id，不得臆测。
7. 在 `expected_effect` 中写明这一步预期产生的效果（供批评智能体校验）。
```

## 输出 Schema

```json
{
  "type": "object",
  "properties": {
    "thought":         { "type": "string" },
    "action": { "type": "string", "enum": [
      "click","type","goto","scroll","submit","wait","navigate",
      "shell","video","tool_task","fill_credential","done" ] },
    "target":          { "type": "string" },
    "value":           { "type": "string" },
    "reason":          { "type": "string" },
    "expected_effect": { "type": "string" }
  },
  "required": ["action"]
}
```

## 设计要点

- **`thought` 字段**让思维链可见（经 `think` 事件推送到控制台）；
- **`expected_effect`** 供批评智能体比对「这一步预期是否真的推进子任务」；
- 规则 4（禁止重复 3 次）与系统的**确定性循环检测**形成双保险；
- 规则 5（凭据）直接支撑「明文不进 LLM」的安全不变式。

## 蜂巢多样性

蜂巢模式下会创建多个执行体，temperature 分别为 **0.2（保守）/ 0.5（均衡）/ 0.9（探索）/ 1.1**，
使同一观察产出不同候选动作，再由投票选出最优 —— 这是蜂巢「群体多样性」的实现方式。

## 单脑回退

`policy.multi_agent=false` 时不用该提示词，
改用 `llm/prompts.py` 的 `SYSTEM_AGENT`（见 [08-decision.md](08-decision.md)）。
