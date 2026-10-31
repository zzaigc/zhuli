"""校准建议：只输出建议，绝不改写用户配置。

根据一次混沌运行的观察（失败次数、恢复路径、是否触顶）
给出参数范围建议，供运营者人工决定是否采纳。建议里不含
任何密钥、提示词或对话内容；函数不读、不写 settings.yaml，
调用方可用测试断言：建议前后配置文件内容不变。
"""
from __future__ import annotations

from .runner import ChaosRunResult


def suggest_parameters(results: list[ChaosRunResult]) -> list[dict]:
    failed = [r for r in results if not r.recovered]
    retries_exhausted = [r for r in results if r.recovery == "retry" and not r.recovered]
    replan_hits = [r for r in results if r.recovery == "replan"]
    fallback_hits = [r for r in results if r.recovery == "fallback"]
    suggestions: list[dict] = []
    if retries_exhausted:
        suggestions.append({
            "parameter": "policy.step_timeout_sec / 重试次数",
            "observed": f"{len(retries_exhausted)} 个可重试故障在重试后仍失败："
                        + ", ".join(r.fault for r in retries_exhausted),
            "suggested_range": "超时 120 秒起步评估，150~300 秒区间内人工试；重试次数 2~3 次",
            "rationale": "重试用尽说明不是偶发抖动，可能是超时太短或限流窗口太长；"
                         "先调超时再谈加重试，避免无限重试拖垮任务。",
            "apply": False,
        })
    if replan_hits:
        suggestions.append({
            "parameter": "policy.max_steps 与重规划上限（现为 3 次）",
            "observed": f"{len(replan_hits)} 次重规划："
                        + ", ".join(r.fault for r in replan_hits),
            "suggested_range": "重规划上限保持 3 次；若频繁触顶，优先修规划与页面选择器，"
                                "而不是直接放宽上限",
            "rationale": "频繁重规划通常是规划或观察问题，放宽上限只会让错误任务跑更久。",
            "apply": False,
        })
    if fallback_hits:
        suggestions.append({
            "parameter": "蜂巢降级与工具降级路径",
            "observed": f"{len(fallback_hits)} 次降级："
                        + ", ".join(r.fault for r in fallback_hits),
            "suggested_range": "保持蜂巢默认关闭；手动规模无上限但越大越费 token，自动模式 2~8；降级成功是正常表现，"
                                "不需要为此调大蜂群",
            "rationale": "降级是安全兜底，不是性能指标；降级频繁应查供应商稳定性。",
            "apply": False,
        })
    if failed:
        suggestions.append({
            "parameter": "循环检测阈值（连续相同动作 3 次）与升级处理",
            "observed": f"{len(failed)} 个故障未恢复："
                        + ", ".join(r.fault for r in failed),
            "suggested_range": "先修失败根因；循环阈值保持 3 次，升级处理保持人工确认",
            "rationale": "未恢复的故障必须先修，不能靠调阈值把它“调成成功”。",
            "apply": False,
        })
    if not suggestions:
        suggestions.append({
            "parameter": "（无）",
            "observed": "本次运行全部恢复",
            "suggested_range": "保持现有参数不变",
            "rationale": "全部恢复说明当前参数在本次故障组合下够用，不需要调参。",
            "apply": False,
        })
    return suggestions
