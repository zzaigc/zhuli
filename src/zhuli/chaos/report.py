"""混沌运行报告：只写隔离目录，含注入、恢复、失败与建议。"""
from __future__ import annotations

import json
from pathlib import Path

from .calibration import suggest_parameters
from .guard import ensure_isolated_dir
from .runner import ChaosRunResult


def build_report(results: list[ChaosRunResult], *, purpose: str) -> dict:
    recovered = [r for r in results if r.recovered]
    failed = [r for r in results if not r.recovered]
    return {
        "purpose": purpose,
        "test_only": True,
        "chaos_enabled": False,  # 报告生成时测试模式已关闭（见 runner 上下文退出）
        "total": len(results),
        "recovered": len(recovered),
        "failed": len(failed),
        "events": [
            {"fault": r.fault, "expected_recovery": r.expected_recovery,
             "status": r.status, "recovery": r.recovery,
             "attempts": r.attempts, "notes": r.notes}
            for r in results
        ],
        "failures": [r.fault for r in failed],
        "suggestions": suggest_parameters(results),
        "disclaimer": "本报告是测试建议，不是自动调参；是否改配置由运营者人工决定。",
    }


def write_report(report: dict, output_dir: str | Path) -> Path:
    out = ensure_isolated_dir(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    md_lines = ["# 混沌测试报告（测试专用）", "",
                f"目的：{report['purpose']}", "",
                f"总计 {report['total']} 个故障，恢复 {report['recovered']} 个，"
                f"未恢复 {report['failed']} 个。", ""]
    for ev in report["events"]:
        md_lines.append(f"- {ev['fault']}：期望 {ev['expected_recovery']}，"
                        f"结果 {ev['status']}，恢复路径 {ev['recovery']}，"
                        f"尝试 {ev['attempts']} 次")
    md_lines += ["", "## 校准建议（仅建议，不自动改配置）", ""]
    for s in report["suggestions"]:
        md_lines.append(f"- {s['parameter']}：{s['observed']}；"
                        f"建议范围：{s['suggested_range']}；理由：{s['rationale']}")
    md_lines += ["", "注意：未恢复的故障必须先修根因，不能靠调阈值记为成功。", ""]
    (out / "chaos-report.md").write_text("\n".join(md_lines), encoding="utf-8")
    (out / "chaos-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return out / "chaos-report.md"
