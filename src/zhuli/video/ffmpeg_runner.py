"""ffmpeg 命令构建与执行。

核心安全点：所有 ffmpeg 参数由白名单构建为**参数列表**（无 shell 拼接）。
LLM 只提供高层参数（文件名、时间戳、文本），本模块负责校验并装配命令。
复杂滤镜（watermark/subtitle）的文本经转义后作为单独参数传入。
"""
from __future__ import annotations

import asyncio
import shlex
from pathlib import Path

from ..computer.executor import run as run_command
from .planner import plan as plan_video

# 允许的输入/输出后缀白名单
_ALLOWED_EXT = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".mp3", ".wav", ".aac",
                ".m4a", ".srt", ".png", ".jpg", ".jpeg", ".gif", ".txt"}


def _safe_path(p: str, workdir: Path) -> str | None:
    path = Path(p)
    if not path.suffix.lower() in _ALLOWED_EXT:
        return None
    # 归一化到 workdir 内，禁止越界（如 ../）
    full = (workdir / path).resolve() if not path.is_absolute() else path.resolve()
    try:
        full.relative_to(workdir.resolve())
    except ValueError:
        return None
    return str(full)


def _esc(text: str) -> str:
    # 用于 drawtext 等滤镜链的文本转义（冒号/反斜杠/单引号）
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def build_command(step: dict, workdir: Path) -> list[str] | None:
    op = step.get("op")
    p = step.get("params", {})
    base = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]

    if op == "trim":
        inp = _safe_path(p.get("input", ""), workdir)
        out = _safe_path(p.get("output", "out_trim.mp4"), workdir)
        if not (inp and out):
            return None
        return [*base, "-i", inp, "-ss", str(p.get("start", "00:00:00")),
                "-to", str(p.get("end", "00:00:05")), out]

    if op == "concat":
        inputs = [i for i in (_safe_path(i, workdir) for i in p.get("inputs", [])) if i]
        out = _safe_path(p.get("output", "out_concat.mp4"), workdir)
        if not (inputs and out):
            return None
        return [*base, *sum((["-i", i] for i in inputs), []),
                "-filter_complex", f"concat=n={len(inputs)}:v=1:a=1[out]",
                "-map", "[out]", out]

    if op == "watermark":
        inp = _safe_path(p.get("input", ""), workdir)
        out = _safe_path(p.get("output", "out_wm.mp4"), workdir)
        if not (inp and out):
            return None
        if p.get("image"):
            wm = _safe_path(p["image"], workdir)
            if not wm:
                return None
            vf = f"movie={shlex.quote(wm)} [wm];[in][wm] overlay=10:10 [out]"
        else:
            text = _esc(p.get("text", "ZHULI"))
            vf = f"drawtext=text='{text}':x=10:y=10:fontsize=24:fontcolor=white"
        return [*base, "-i", inp, "-vf", vf, out]

    if op == "subtitle":
        inp = _safe_path(p.get("input", ""), workdir)
        out = _safe_path(p.get("output", "out_sub.mp4"), workdir)
        if not (inp and out):
            return None
        if p.get("srt"):
            sub = _safe_path(p["srt"], workdir)
            if not sub:
                return None
            vf = f"subtitles={shlex.quote(sub)}"
        else:
            text = _esc(p.get("text", ""))
            vf = f"drawtext=text='{text}':x=10:y=H-th-30:fontsize=28:fontcolor=white"
        return [*base, "-i", inp, "-vf", vf, out]

    if op == "convert":
        inp = _safe_path(p.get("input", ""), workdir)
        out = _safe_path(p.get("output", "out.mp4"), workdir)
        if not (inp and out):
            return None
        return [*base, "-i", inp, out]

    if op == "scale":
        inp = _safe_path(p.get("input", ""), workdir)
        out = _safe_path(p.get("output", "out_scale.mp4"), workdir)
        if not (inp and out):
            return None
        vf = f"scale={p.get('width', 1280)}:{p.get('height', 720)}"
        return [*base, "-i", inp, "-vf", vf, out]

    if op == "extract_audio":
        inp = _safe_path(p.get("input", ""), workdir)
        out = _safe_path(p.get("output", "out.aac"), workdir)
        if not (inp and out):
            return None
        return [*base, "-i", inp, "-vn", "-acodec", "copy", out]

    if op == "mute":
        inp = _safe_path(p.get("input", ""), workdir)
        out = _safe_path(p.get("output", "out_mute.mp4"), workdir)
        if not (inp and out):
            return None
        return [*base, "-i", inp, "-an", out]

    return None


async def run_plan(requirement: str, *, on_output=None, workdir: str | None = None,
                   max_chars: int = 20000, timeout: float = 300.0) -> dict:
    """规划并执行视频剪辑方案，逐命令回流输出。返回 {summary, results}。"""
    wd = Path(workdir or Path.cwd()).resolve()
    wd.mkdir(parents=True, exist_ok=True)
    video_plan = await plan_video(requirement)
    results = []
    for step in video_plan.get("steps", []):
        cmd = build_command(step, wd)
        if cmd is None:
            results.append({"op": step.get("op"), "ok": False, "error": "参数校验失败（非法路径/操作）"})
            continue
        res = await run_command(
            " ".join(shlex.quote(c) for c in cmd),  # 已为白名单参数，转义后以 shell 安全执行
            on_output=on_output, timeout=timeout, max_chars=max_chars, cwd=str(wd),
        )
        results.append({"op": step.get("op"), "cmd": cmd, **res})
    return {"summary": video_plan.get("summary", ""), "results": results}
