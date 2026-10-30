"""视频剪辑规划器：把自然语言需求转为结构化剪辑方案。

LLM 只负责生成「高层操作 + 参数」（如 trim 的起止时间、concat 的文件列表），
不直接拼 ffmpeg 命令；真正的命令由 ffmpeg_runner 按白名单构建，杜绝注入。
"""
from __future__ import annotations

from ..llm.provider import chat_structured
from ..llm.prompts import SYSTEM_AGENT  # 复用基础约束语气（可选）

VIDEO_PLANNER_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string", "description": "方案概述"},
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "op": {
                        "type": "string",
                        "enum": [
                            "trim", "concat", "watermark", "subtitle",
                            "convert", "scale", "extract_audio", "mute",
                        ],
                    },
                    "params": {"type": "object", "description": "该操作所需参数"},
                },
                "required": ["op", "params"],
            },
        },
    },
    "required": ["summary", "steps"],
}

SYSTEM_VIDEO = """你是视频剪辑规划器。把用户需求拆成若干 ffmpeg 高层操作步骤。
可用操作：trim(裁剪), concat(拼接), watermark(水印), subtitle(字幕),
convert(转格式), scale(缩放分辨率), extract_audio(提取音频), mute(静音)。
参数示例：
- trim: {input, output, start("00:00:03"), end("00:00:10")}
- concat: {inputs:[a.mp4,b.mp4], output, ...}  (inputs 为本地文件列表)
- watermark: {input, output, text 或 image, position}
- subtitle: {input, output, text 或 srt, lang}
- convert: {input, output, format}
- scale: {input, output, width, height}
- extract_audio: {input, output}
- mute: {input, output}
只使用用户给出的文件名（不要臆造路径）；不要输出完整 ffmpeg 命令。"""


async def plan(requirement: str) -> dict:
    """返回 {summary, steps:[{op, params}]}。"""
    messages = [
        {"role": "system", "content": SYSTEM_VIDEO},
        {"role": "user", "content": requirement},
    ]
    return await chat_structured(
        "reasoning",
        messages,
        schema=VIDEO_PLANNER_SCHEMA,
        schema_name="emit_video_plan",
        schema_description="视频剪辑方案：高层操作步骤与参数",
    )
