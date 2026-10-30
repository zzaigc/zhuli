"""OpenCode 连接器（命令类）。

复用 computer 模块启动 OpenCode CLI 并捕获输出。优先尝试非交互模式
`opencode -p "<task>"`（若版本支持）；否则回退为启动交互式命令并提示用户接管。
"""
from __future__ import annotations

import shlex

from .base import BaseConnector, OnOutput
from ..computer.executor import run as run_command


class OpenCodeConnector(BaseConnector):
    name = "OpenCode"
    kind = "computer"

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self.command = config.get("command", ["opencode"])

    async def run(self, task: str, *, page=None, on_output: OnOutput = None) -> str:
        cmd = [*self.command, "-p", task]
        shell_cmd = " ".join(shlex.quote(c) for c in cmd)
        if on_output:
            await on_output("stdout", f"[OpenCode] 执行：{shell_cmd}")
        res = await run_command(
            shell_cmd, on_output=on_output, timeout=600.0, max_chars=30000
        )
        return f"[OpenCode 退出码 {res.get('exit_code')}]"
