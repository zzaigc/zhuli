"""混沌测试（v0.3.0，测试专用，默认关闭）。

本包只做故障注入的弹性测试，不做生产功能，不改动用户配置，
不削弱任何护栏、批准或安全检查。正常任务永远不会触发混沌：
只有显式开启测试模式（配置 chaos.enabled 为 false 是默认值；
运行时开启还必须用 CLI --chaos-test 或控制台测试接口，并带
确认串）后，测试运行器才会在隔离的临时目录里注入故障。

导出：ChaosFault、FAULTS、inject、guard、runner、calibration、
snapshot/restore 与报告。详见 docs/13-混沌测试.md。
"""
from __future__ import annotations

from .calibration import suggest_parameters
from .faults import FAULTS, ChaosFault, Fault, inject, list_faults
from .guard import (
    ChaosGuard,
    disable_test_mode,
    enable_test_mode,
    ensure_isolated_dir,
    is_test_mode_enabled,
)
from .report import build_report, write_report
from .runner import ChaosRunResult, run_scenario, simulate_recovery
from .snapshot import restore_snapshot, take_snapshot

__all__ = [
    "FAULTS",
    "ChaosFault",
    "ChaosGuard",
    "ChaosRunResult",
    "Fault",
    "build_report",
    "disable_test_mode",
    "enable_test_mode",
    "ensure_isolated_dir",
    "inject",
    "is_test_mode_enabled",
    "list_faults",
    "restore_snapshot",
    "run_scenario",
    "simulate_recovery",
    "suggest_parameters",
    "take_snapshot",
    "write_report",
]
