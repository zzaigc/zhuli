"""本地命令执行器。

安全约定：
  - 无 shell 语法的命令用参数列表（create_subprocess_exec）执行，杜绝拼接注入
  - 含管道/重定向等 shell 特性的命令，仅在护栏判定为 confirm 且用户批准后，才以
    create_subprocess_shell 执行（此时安全边界来自 command guard，而非 shell 规避）
  - stdout/stderr 逐行回流，受 max_chars 限长，避免 WS 拥塞
"""
from __future__ import annotations

import asyncio
import re
import shlex

_SHELL_META = re.compile(r"[|&;><$\n`]")


async def run(
    cmd: str,
    *,
    on_output=None,
    timeout: float = 60.0,
    max_chars: int = 20000,
    cwd: str | None = None,
    allowed_dirs: list[str] | None = None,
) -> dict:
    """执行命令并返回 {exit_code, truncated, stdout_chars}。"""
    use_shell = bool(_SHELL_META.search(cmd))
    if use_shell:
        proc = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=cwd
        )
    else:
        try:
            args = shlex.split(cmd, posix=False)
        except ValueError:
            args = cmd.split()
        proc = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=cwd
        )

    emitted = 0
    truncated = False

    async def _pump(stream, stream_name: str):
        nonlocal emitted, truncated
        if stream is None:
            return
        async for raw in stream:
            if truncated:
                continue
            line = raw.decode("utf-8", errors="replace").rstrip("\n")
            if on_output:
                await on_output(stream_name, line)
            emitted += len(line)
            if emitted >= max_chars:
                truncated = True
                if on_output:
                    await on_output(stream_name, "… [输出已超过上限，已截断]")

    try:
        await asyncio.wait_for(
            asyncio.gather(_pump(proc.stdout, "stdout"), _pump(proc.stderr, "stderr")),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        proc.kill()
        if on_output:
            await on_output("stderr", f"[命令超时 {timeout}s 已被终止]")

    exit_code = await proc.wait()
    return {
        "exit_code": exit_code,
        "truncated": truncated,
        "stdout_chars": emitted,
    }
