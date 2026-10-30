# 07 · 反思（reflection）

**源码**：`src/zhuli/llm/prompts.py` → `SYSTEM_REFLECTION` / `REFLECTION_SCHEMA`
**执行者**：批评智能体（critic）在执行后承担反思校验。
**职责**：判定当前子任务是否达成，并决定下一步走向。

## 提示词

```
你是反思校验器（Muse 式自我纠错）。基于最近执行结果、目标完成度与历史动作，判断下一步走向。

步骤：
1. 先对照「当前子任务的完成标准」判断它是否已达成（current_done）。
2. 检测异常：连续无进展 / 动作明显重复循环 / 超出最大步数 / 已无可行动作 → 倾向 replan 或 escalate。
3. 给出简洁的反思思路（thought）与判定理由（reason）。

状态含义：
- continue: 当前子任务未达成，继续推进
- replan: 偏离/卡死/循环，需要换策略重新规划（在 reason 说明问题）
- done: **所有**子任务均已达成，目标完成
- escalate: 需要用户介入（信息不足 / 超出能力 / 不确定风险）

注意：只有「当前子任务」达成时置 current_done=true（哪怕后面还有子任务）；全部达成才置 done。
```

## 输出 Schema

```json
{
  "type": "object",
  "properties": {
    "thought":      { "type": "string" },
    "status":       { "type": "string", "enum": ["continue","replan","done","escalate"] },
    "reason":       { "type": "string" },
    "current_done": { "type": "boolean" },
    "next":         { "type": "string" }
  },
  "required": ["status", "reason"]
}
```

## `current_done` vs `done`（易混淆点）

| 字段 | 含义 | 系统行为 |
|---|---|---|
| `current_done=true` | 当前子任务完成，**后面还有** | 勾选进度并推进到下一子任务，继续循环 |
| `status=done` | **全部**子任务完成 | 结束任务并沉淀技能 |

## 系统行为

```python
if status == "done":        # 全部完成
    结束 → 沉淀技能
elif current_done:          # 当前子任务完成
    推进下一子任务 → 推送 plan 事件
elif status == "replan":    # 卡死/偏离
    触发重规划（保留已完成部分）
elif status == "escalate":  # 需要人介入
    置 error 状态并提示用户
```

## 与确定性检测的双保险

反思是 **LLM 判断**（语义强），此外系统还有 **确定性循环检测**（连续 3 步动作指纹相同即判定死循环）。
两者任一触发都会导致重规划 —— 既不漏判也不误判过度。

## 校验依据

反思的输入包含「当前子任务的完成标准（verification）」，
因此判定依据是**可验证的标准**而非模糊印象 —— 这是规划阶段产出 `verification` 的价值所在。
