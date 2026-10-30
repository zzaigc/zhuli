"""ZHULI 启动入口。

启动本地服务（FastAPI + Uvicorn）。控制台页面与 WebSocket 由 console.server 提供。
关键约束：Playwright 的 Chromium 二进制与用户 profile 一律放在「项目目录内」，
绝不放 C 盘（见 PLAYWRIGHT_BROWSERS_PATH 与 browser.driver 的 user_data_dir 解析）。
"""
from __future__ import annotations

import os
from pathlib import Path

# 必须在导入 playwright 之前设定，否则浏览器会被装到 C 盘用户目录。
# 所有运行时产物统一放在项目内特定子目录 .zhuli_runtime/ 下。
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_RUNTIME_DIR = _PROJECT_ROOT / ".zhuli_runtime"
_BROWSERS_PATH = _RUNTIME_DIR / "browsers"
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(_BROWSERS_PATH))
_RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
_BROWSERS_PATH.mkdir(parents=True, exist_ok=True)

import uvicorn  # noqa: E402

from zhuli.console.server import create_app  # noqa: E402


def main() -> None:
    app = create_app()
    # 监听本机回环，避免暴露到局域网；端口可在 settings 调整
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")


if __name__ == "__main__":
    main()
