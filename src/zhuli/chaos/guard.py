"""混沌安全护栏：默认关闭，测试模式显式开启，隔离目录强制检查。

规则（代码强制，不是文档约定）：
1. 默认关闭：配置 chaos.enabled 默认 False；运行时默认也关闭。
2. 开启必须显式：enable_test_mode(purpose=...) 要求非空 purpose，
   且调用方必须声明 test_mode=True；普通任务消息里带 chaos 字段
   也不会开启（见 tests：_dispatch 从不解析 chaos 字段）。
3. 控制台接口开启还必须带确认串 CHAOS-TEST-ONLY（见 server）。
4. 隔离目录：只允许系统临时目录下的路径；拒绝项目根、
   项目 .zhuli_runtime、用户主目录、以及任何非临时目录路径，
   防止快照/恢复触碰真实运行时数据。快照只复制、不删除。
"""
from __future__ import annotations

import tempfile
from pathlib import Path

CONFIRM_STRING = "CHAOS-TEST-ONLY"

_TEST_MODE = {"enabled": False, "purpose": ""}


def is_test_mode_enabled() -> bool:
    return bool(_TEST_MODE["enabled"])


def enable_test_mode(*, purpose: str) -> None:
    if not purpose or not str(purpose).strip():
        raise ValueError("chaos test mode requires a non-empty purpose")
    _TEST_MODE["enabled"] = True
    _TEST_MODE["purpose"] = str(purpose)


def disable_test_mode() -> None:
    _TEST_MODE["enabled"] = False
    _TEST_MODE["purpose"] = ""


def ensure_isolated_dir(path: str | Path) -> Path:
    """校验并返回隔离目录。不是临时目录下的路径一律拒绝。"""
    p = Path(path).resolve()
    tmp = Path(tempfile.gettempdir()).resolve()
    if p == tmp or tmp not in p.parents:
        raise ValueError(f"chaos isolated dir must be inside the system temp dir: {p}")
    # 绝不允许指向真实运行时目录名（即使它恰好在临时目录外也已拒绝；
    # 这里再防一层同名误用）。
    if p.name in {".zhuli_runtime", ".zhuli_browser_profile"}:
        raise ValueError("chaos isolated dir must not be a real runtime directory name")
    return p


class ChaosGuard:
    """一次测试运行的护栏：持有隔离目录与开启状态，退出即关闭。"""

    def __init__(self, isolated_dir: str | Path, *, purpose: str) -> None:
        self.isolated_dir = ensure_isolated_dir(isolated_dir)
        self.purpose = purpose

    def __enter__(self) -> "ChaosGuard":
        enable_test_mode(purpose=self.purpose)
        self.isolated_dir.mkdir(parents=True, exist_ok=True)
        return self

    def __exit__(self, *exc: object) -> bool:
        disable_test_mode()
        return False
