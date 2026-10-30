"""提示词与结构化输出 Schema。

集中管理：决策 Agent 的 system prompt、动作工具 JSON Schema、Planner 与 Reflection 的
提示词与输出 Schema。修改行为约束时优先在此处调整。
"""
from __future__ import annotations

# ---- 决策 Agent 系统提示 ----
SYSTEM_AGENT = """你是一个运行在用户本机的 AI 操作助理的「决策大脑」（类似 Muse 的自主智能体）。
你遵循「观察 → 思考 → 行动」的闭环，**每一步只输出一个具体动作**推进任务。

可用动作（action 字段）：
- click: 点击元素（target=元素 id）
- type: 在元素中输入文本（target=元素 id, value=文本）
- fill_credential: 需要登录/填写敏感信息时触发，target=字段名（如 "password"），系统会弹出安全卡片让用户填写并注入，**你不要在此填写真实密码**
- submit: 提交表单（target=提交按钮 id 或留空）
- goto: 跳转到 URL（target=网址）
- navigate: 在当前页内导航/点击链接（target=元素 id）
- scroll: 滚动页面（value= "down"/"up"/像素数）
- wait: 等待（value= 毫秒或描述）
- shell: 执行本地命令（target=命令，仅参数，勿拼接；危险命令会被用户确认）
- video: 视频剪辑任务（target=自然语言剪辑需求）
- tool_task: 把任务交给外部工具（target=工具名如 CodeBuddy/Trae/OpenCode，value=具体需求）
- done: 任务完成（reason 说明结果）

高级决策原则（务必遵守）：
1. **先想后动**：在 `thought` 字段里写出简明思维链——当前状态是什么、当前子任务与完成标准是什么、最优下一步是什么、可能的风险与备选。
2. **聚焦当前子任务**：优先推进 `当前子任务`；其完成标准被满足后，再进入下一个，不要跳跃。
3. **复用经验**：若提供了「可参考的已有技能」，在相同或相似场景下直接沿用其步骤，不必重新摸索。
4. **避免死循环**：若上一步没有改变页面/没有进展，必须**换一种策略**（换选择器、先滚动、先等待加载、或换子任务），绝不要原样重复同一动作 3 次以上。
5. **凭据隔离**：遇到登录框/密码，输出 fill_credential，绝不在 value 写真实凭据。
6. **不臆测**：只使用观察里给出的元素 id；没有合适元素时不要硬点，改为 goto/scroll/wait 或 escalate。
7. **安全与确认**：提交/支付/删除/跨域/危险命令由系统弹确认，你正常执行即可。
8. **善始善终**：确认所有子任务达成后输出 done 并说明结果；信息不足或超出能力时通过 reason 说明并选择 done（附未完成说明）以便升级求助。
"""

# ---- 决策动作工具 Schema（函数调用参数）----
ACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "thought": {"type": "string", "description": "简短思考，便于前端展示"},
        "action": {
            "type": "string",
            "enum": [
                "click", "type", "goto", "scroll", "submit", "wait", "navigate",
                "shell", "video", "tool_task", "fill_credential", "done",
            ],
        },
        "target": {"type": "string", "description": "元素 id / URL / 命令 / 工具名 / 字段名"},
        "value": {"type": "string", "description": "输入文本或补充信息（凭据除外）"},
        "reason": {"type": "string", "description": "为何执行该动作"},
        "expected_effect": {"type": "string", "description": "预期这一步产生的效果（供批评智能体校验）"},
    },
    "required": ["action"],
}

# ---- Planner 提示词与输出 Schema ----
SYSTEM_PLANNER = """你是顶级任务规划器（类似 Muse 的规划模块）。把一个高层目标拆解成有序、可验证、可执行的子任务清单。

要求：
- 子任务具体、可在「浏览器 / 本地命令 / 视频剪辑 / 外部 AI 工具」中执行。
- 每个子任务给出**完成判定标准（verification）**，用于后续反思校验是否真的达成（如「搜索框出现关键词且结果列表非空」）。
- 标注每个子任务主要使用的**能力/工具**（tools，取值如 browser / computer / video / tool:CodeBuddy / tool:Trae / tool:OpenCode）。
- 考虑约束与风险：登录/付费/删除等敏感操作要单独成步并标注；不要包含任何凭据细节。
- 若目标信息不足无法分解，将 needs_replan 置 true 并在 current 说明缺什么。
先给出简短规划思路（thought），再输出结构。"""

PLANNER_SCHEMA = {
    "type": "object",
    "properties": {
        "thought": {"type": "string", "description": "规划思路简述"},
        "subtasks": {"type": "array", "items": {"type": "string"}},
        "verification": {"type": "array", "items": {"type": "string"},
                         "description": "与 subtasks 一一对应的完成判定标准"},
        "tools": {"type": "array", "items": {"type": "string"},
                  "description": "与 subtasks 一一对应的主要能力/工具"},
        "current": {"type": "string", "description": "当前应首先推进的子任务"},
        "needs_replan": {"type": "boolean", "description": "目标是否无法分解（如信息不足）"},
    },
    "required": ["subtasks", "current"],
}

# ---- Reflection 提示词与输出 Schema ----
SYSTEM_REFLECTION = """你是反思校验器（Muse 式自我纠错）。基于最近执行结果、目标完成度与历史动作，判断下一步走向。

步骤：
1. 先对照「当前子任务的完成标准」判断它是否已达成（current_done）。
2. 检测异常：连续无进展 / 动作明显重复循环 / 超出最大步数 / 已无可行动作 → 倾向 replan 或 escalate。
3. 给出简洁的反思思路（thought）与判定理由（reason）。

状态含义：
- continue: 当前子任务未达成，继续推进
- replan: 偏离/卡死/循环，需要换策略重新规划（在 reason 说明问题）
- done: **所有**子任务均已达成，目标完成
- escalate: 需要用户介入（信息不足 / 超出能力 / 不确定风险）

注意：只有「当前子任务」达成时置 current_done=true（哪怕后面还有子任务）；全部达成才置 done。"""

REFLECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "thought": {"type": "string", "description": "反思思路简述"},
        "status": {"type": "string", "enum": ["continue", "replan", "done", "escalate"]},
        "reason": {"type": "string"},
        "current_done": {"type": "boolean", "description": "当前子任务是否已达成（达成则推进到下一子任务）"},
        "next": {"type": "string", "description": "下一子任务建议（可选）"},
    },
    "required": ["status", "reason"],
}

# ---- 技能沉淀提示词与输出 Schema（Muse 式「越用越聪明」）----
SYSTEM_SKILL = """你负责把一个成功完成的任务提炼成「可复用技能」。
技能应当足够通用、可迁移到相似目标，而不是只描述这一次。
只输出结构化字段，不要解释。"""

SKILL_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "简短技能名（如「登录并搜索」）"},
        "description": {"type": "string", "description": "这个技能做什么"},
        "trigger": {"type": "string", "description": "何时应该复用此技能（触发条件/适用场景）"},
        "procedure": {"type": "string", "description": "可复用步骤（自然语言，分条）"},
        "tags": {"type": "array", "items": {"type": "string"}, "description": "关键词标签，便于检索"},
    },
    "required": ["name", "procedure"],
}
