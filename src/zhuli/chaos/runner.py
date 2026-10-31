"""混沌运行器：注入故障，观察并记录恢复路径，失败记为失败。

恢复映射与 orchestrator 现有机制对应，不发明新机制：
- retry：可重试故障（429、超时、跳转超时）先重试，指定次数内
  成功记 recovered=retry；次数用尽记 failed。
- rollback：服务中途重启类故障，先从快照恢复再重跑一次。
- replan：页面崩溃/元素缺失类故障，记一次重规划（replan 回调）。
- fallback：供应商中断/工具失败，记一次降级（fallback 回调，
  例如蜂巢降级回单脑、工具降级路径）。
- escalate：401 这类不可重试故障，不重试，直接升级处理。
- graceful_degradation：浏览器不可用时服务仍可运行（降级标记）。
步骤函数（step）是测试用的桩：它可以成功、返回恢复标记，
或再次抛出异常。恢复失败时结果 recovered=False、status=failed，
绝不记为成功。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .faults import FAULTS, ChaosFault, inject
from .guard import ChaosGuard, is_test_mode_enabled

log = logging.getLogger("zhuli.chaos")


@dataclass
class ChaosRunResult:
    fault: str
    expected_recovery: str
    status: str  # recovered | failed | skipped
    recovery: str = ""
    attempts: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def recovered(self) -> bool:
        return self.status == "recovered"


def simulate_recovery(fault_name: str, step, *, retries: int = 2,
                      rollback=None, replan=None, fallback=None,
                      escalate=None) -> ChaosRunResult:
    """对一个已注入的故障做一次恢复模拟。

    step: 可调用对象，接受 fault_name，返回 recovery 标记字符串
    或抛出异常。rollback/replan/fallback/escalate 是可选回调，
    被调用即记一次对应恢复动作。retries 只用于 retry 类故障。
    """
    fault = FAULTS.get(fault_name)
    if fault is None:
        raise ValueError(f"unknown chaos fault: {fault_name}")
    if not is_test_mode_enabled():
        raise RuntimeError("chaos is off: enable test mode explicitly before running a scenario")
    expected = fault.expected_recovery
    attempts = 0
    notes: list[str] = []
    try:
        if expected == "retry":
            for attempt in range(retries + 1):
                attempts += 1
                try:
                    result = step(fault_name)
                    notes.append(f"attempt {attempts}: {result}")
                    return ChaosRunResult(fault_name, expected, "recovered", "retry", attempts, notes)
                except Exception as exc:  # noqa: BLE001 - 记录后继续重试
                    notes.append(f"attempt {attempts} failed: {exc}")
            return ChaosRunResult(fault_name, expected, "failed", "retry", attempts, notes)
        # 非重试类：先执行一次恢复回调，再跑一步；任何异常都记失败。
        callbacks = {"rollback": rollback, "replan": replan, "fallback": fallback,
                     "escalate": escalate, "graceful_degradation": None}
        cb = callbacks.get(expected)
        if cb is not None:
            cb(fault_name)
            notes.append(f"{expected} callback executed")
        attempts = 1
        result = step(fault_name)
        notes.append(f"step after {expected}: {result}")
        return ChaosRunResult(fault_name, expected, "recovered", expected, attempts, notes)
    except Exception as exc:  # noqa: BLE001 - 失败必须如实记录
        notes.append(f"recovery failed: {exc}")
        return ChaosRunResult(fault_name, expected, "failed", expected, attempts, notes)


def run_scenario(fault_names, step_factory, *, isolated_dir, purpose,
                 retries: int = 2) -> list[ChaosRunResult]:
    """在隔离目录里按顺序注入一组故障并记录结果。

    step_factory(fault_name) 返回该故障对应的步骤函数；
    注入本身用 inject() 校验测试模式已开启。每个故障先注入
    （记录），再用 simulate_recovery 观察恢复。
    """
    results: list[ChaosRunResult] = []
    with ChaosGuard(isolated_dir, purpose=purpose):
        for name in fault_names:
            try:
                inject(name, test_mode=True)
            except ChaosFault as exc:
                log.warning("chaos scenario injected %s", exc.kind)
            step = step_factory(name)
            results.append(simulate_recovery(
                name, step, retries=retries,
                rollback=lambda n: log.info("chaos rollback %s", n),
                replan=lambda n: log.info("chaos replan %s", n),
                fallback=lambda n: log.info("chaos fallback %s", n),
                escalate=lambda n: log.info("chaos escalate %s", n),
            ))
    return results
