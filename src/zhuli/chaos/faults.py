"""故障注入器（显式、具名、可记录）。

每一种故障都是一个具名 Fault：注入时只做一件事——记录并抛出
ChaosFault，或返回一个延迟标记，绝不静默修改数据、删除文件、
绕过护栏或调用真实网络/浏览器/模型。真实故障的恢复路径
（重试、回滚、重规划、降级、升级）由 runner.simulate_recovery
按 orchestrator 现有规则模拟与记录。
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

log = logging.getLogger("zhuli.chaos")


class ChaosFault(Exception):
    """一次被注入的故障。kind 是故障名，detail 说明模拟的场景。"""

    def __init__(self, kind: str, detail: str = "") -> None:
        super().__init__(f"chaos fault {kind}: {detail}")
        self.kind = kind
        self.detail = detail


@dataclass(frozen=True)
class Fault:
    name: str
    category: str  # llm | browser | provider | tool | service
    description: str
    # 注入后期望的恢复路径（与 orchestrator 现有机制对应）
    expected_recovery: str  # retry | rollback | replan | fallback | escalate | graceful_degradation
    delay_sec: float = 0.0


FAULTS: dict[str, Fault] = {
    "llm_401": Fault("llm_401", "llm", "模型调用返回 401（无有效密钥）", "escalate"),
    "llm_429": Fault("llm_429", "llm", "模型调用返回 429（限流）", "retry"),
    "llm_timeout": Fault("llm_timeout", "llm", "模型调用超时", "retry"),
    "browser_page_crash": Fault("browser_page_crash", "browser", "浏览器页面崩溃", "replan"),
    "browser_element_missing": Fault("browser_element_missing", "browser", "页面元素不存在", "replan"),
    "browser_nav_timeout": Fault("browser_nav_timeout", "browser", "页面跳转超时", "retry"),
    "provider_network_delay": Fault("provider_network_delay", "provider", "供应商网络延迟（模拟，不发真实请求）", "retry", delay_sec=0.2),
    "provider_network_loss": Fault("provider_network_loss", "provider", "供应商网络中断（模拟）", "fallback"),
    "tool_slow": Fault("tool_slow", "tool", "工具调用变慢（模拟延迟）", "retry", delay_sec=0.2),
    "tool_failure": Fault("tool_failure", "tool", "工具调用失败", "fallback"),
    "service_restart_mid_task": Fault("service_restart_mid_task", "service", "任务中途服务重启（模拟：中断标记，需从快照恢复）", "rollback"),
}


def list_faults() -> list[Fault]:
    return list(FAULTS.values())


def inject(name: str, *, test_mode: bool) -> Fault:
    """注入故障。test_mode 为 False 时拒绝，避免正常任务误触发。

    延迟类故障先做一次短暂模拟延迟再抛出，仍以异常结束，
    不会返回“假成功”。未知故障名直接报 ValueError。
    """
    fault = FAULTS.get(name)
    if fault is None:
        raise ValueError(f"unknown chaos fault: {name}")
    if not test_mode:
        raise RuntimeError("chaos is off: enable test mode explicitly before injecting a fault")
    log.warning("chaos inject %s: %s", fault.name, fault.description)
    if fault.delay_sec:
        time.sleep(fault.delay_sec)
    raise ChaosFault(fault.name, fault.description)
