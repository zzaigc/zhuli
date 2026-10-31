"""OpenCode 连接器（命令类）。

v0.2.0 修正：旧版把命令拼成 shell 字符串并只返回退出码，实际输出被丢弃。
新版用参数列表执行（不拼 shell 字符串），并把捕获的输出连同退出码一起返回，
这样 orchestrator 的 tool_task 结果里才有可用的内容。找不到 opencode 二进制时
返回清晰的错误，而不是让调用方猜测。

注意：真实 OpenCode CLI 在本机未安装时仍未验证；见 integrations/dispatch.py。
"""
from __future__ import annotations

import asyncio
import shutil

from .base import BaseConnector, OnOutput


class OpenCodeConnector(BaseConnector):
    name = "OpenCode"
    kind = "computer"

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self.command = config.get("command", ["opencode"])

    async def run(self, task: str, *, page=None, on_output: OnOutput = None) -> str:
        binary = self.command[0] if self.command else "opencode"
        if shutil.which(binary) is None:
            raise RuntimeError(f"找不到 OpenCode 可执行文件：{binary}")
        proc = await asyncio.create_subprocess_exec(
            *self.command, "-p", task,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=600.0)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise RuntimeError("OpenCode 执行超时（600s）")
        text = (out or b"").decode("utf-8", errors="replace")
        err_text = (err or b"").decode("utf-8", errors="replace")
        if on_output:
            for line in text.splitlines():
                await on_output("stdout", line)
            for line in err_text.splitlines():
                await on_output("stderr", line)
        body = text.strip() or err_text.strip() or "(无输出)"
        return f"[OpenCode 退出码 {proc.returncode}]\n{body[:30000]}"
