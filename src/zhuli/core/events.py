"""WebSocket 事件契约（前后端共用语义）。

所有事件均为 Pydantic 模型；orchestrator / 各模块产生事件后，由 console 通过 WebSocket
推送给前端，前端按 `type` 字段分发处理。新增事件类型时务必同步前端 ws.ts 的分发逻辑。
"""
from __future__ import annotations

import json
from typing import Literal, Union

from pydantic import BaseModel, Field


class Action(BaseModel):
    """LLM 决策产生的结构化动作（也是各能力模块执行的统一输入）。"""

    action: Literal[
        "click", "type", "goto", "scroll", "submit", "wait", "navigate",
        "shell", "video", "tool_task", "fill_credential", "done",
    ]
    target: str | None = None  # selector / 命令 / 视频或工具任务描述 / 字段名
    value: str | None = None   # 敏感值仅脱敏后入日志，不进 LLM
    reason: str | None = None
    thought: str | None = None  # 模型的一步思考（对外可见，体现「思维链」）


class PlanEvent(BaseModel):
    type: Literal["plan"]
    subtasks: list[str]
    current: str
    done: list[str]
    verification: list[str] = Field(default_factory=list)  # 每子任务的完成判定标准


class ReflectionEvent(BaseModel):
    type: Literal["reflection"]
    status: Literal["continue", "replan", "done", "escalate"]
    reason: str


class StepLogEvent(BaseModel):
    type: Literal["step_log"]
    step: int
    action: Action
    observation_summary: str


class ScreenshotEvent(BaseModel):
    type: Literal["screenshot"]
    image_b64: str
    highlights: list[dict] = Field(default_factory=list)  # [{selector,x,y,w,h}]


class CommandEvent(BaseModel):
    type: Literal["command"]
    cmd: str
    stream: str = "stdout"  # "stdout" | "stderr"
    line: str
    exit_code: int | None = None


class ConfirmRequestEvent(BaseModel):
    type: Literal["confirm_request"]
    reason: str
    pending_action: Action


class CredentialRequestEvent(BaseModel):
    type: Literal["credential_request"]
    fields: list[str]  # 需要用户填写的字段名，不含值


class ChatEvent(BaseModel):
    type: Literal["chat"]
    role: Literal["user", "assistant", "system"]
    text: str


class StatusEvent(BaseModel):
    type: Literal["status"]
    state: Literal["idle", "running", "paused", "awaiting_confirm",
                   "awaiting_credential", "stopped", "error"]
    message: str | None = None


class SkillEvent(BaseModel):
    """技能沉淀/复用事件（前端可在日志或提示区展示「越用越聪明」的痕迹）。"""
    type: Literal["skill"]
    name: str
    description: str = ""
    action: Literal["learned", "updated", "matched", "promoted"]
    reason: str | None = None


class ThinkEvent(BaseModel):
    """思维链事件：把决策大脑在「规划 / 决策 / 反思」各阶段的思考可见化。"""
    type: Literal["think"]
    stage: Literal["plan", "decide", "reflect"]
    text: str


class AgentEvent(BaseModel):
    """多智能体活动事件：让「哪个智能体做了什么、结论如何」在控制台可见。"""
    type: Literal["agent"]
    agent: str
    stage: Literal["plan", "observe", "decide", "critique", "risk", "reflect",
                   "skill", "delegate", "consensus"]
    summary: str = ""
    verdict: str | None = None  # accept/revise/abort/safe/confirm/danger


class ErrorEvent(BaseModel):
    type: Literal["error"]
    message: str


Event = Union[
    PlanEvent, ReflectionEvent, StepLogEvent, ScreenshotEvent, CommandEvent,
    ConfirmRequestEvent, CredentialRequestEvent, ChatEvent, StatusEvent,
    SkillEvent, ThinkEvent, AgentEvent, ErrorEvent,
]


def to_ws(event: Event) -> str:
    """将事件序列化为 WebSocket 文本帧（JSON）。"""
    return json.dumps(event.model_dump(mode="json"), ensure_ascii=False)
