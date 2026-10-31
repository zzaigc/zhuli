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
# v0.2.0：强制指向项目内路径（不再是 setdefault），避免外部环境变量
# 把 Chromium 引回系统缓存或 C 盘。
_PROJECT_ROOT = Path(__file__).resolve().parents[2]  # main.py 在 src/zhuli/，上 2 层才是项目根（v0.2.0 修正：旧版 parents[3] 会误指父目录，导致找不到 config）
_RUNTIME_DIR = _PROJECT_ROOT / ".zhuli_runtime"
_BROWSERS_PATH = _RUNTIME_DIR / "browsers"
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(_BROWSERS_PATH)
_RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
_BROWSERS_PATH.mkdir(parents=True, exist_ok=True)

import uvicorn  # noqa: E402

from zhuli.console.server import create_app  # noqa: E402


def main() -> None:
    import argparse
    import json

    parser = argparse.ArgumentParser(prog="zhuli")
    parser.add_argument("--version", action="store_true", help="打印版本后退出")
    parser.add_argument("--check", action="store_true",
                        help="只检查配置与运行时目录，不启动服务")
    parser.add_argument("--no-parallel", action="store_true",
                        help="关闭并行子目标（v0.3.0）：所有子任务分组退化为顺序执行")
    parser.add_argument("--chaos-test", action="store_true",
                        help="开启混沌测试模式（v0.3.0，测试专用）：仅配合 --chaos-sample 或控制台测试接口使用，正常任务不会触发混沌")
    parser.add_argument("--chaos-sample", action="store_true",
                        help="在系统临时目录里跑一次混沌示例并输出报告后退出，不启动服务、不改用户配置")
    args = parser.parse_args()
    if args.chaos_sample:
        if not args.chaos_test:
            print("混沌示例需要同时带 --chaos-test（显式开启测试模式）。")
            return
        import tempfile
        from pathlib import Path as _Path

        from zhuli.chaos import build_report, run_scenario, write_report

        tmp = _Path(tempfile.mkdtemp(prefix="zhuli-chaos-sample-"))
        data = tmp / "data"
        data.mkdir(parents=True, exist_ok=True)
        (data / "probe.txt").write_text("chaos-sample", encoding="utf-8")

        def _step(name: str) -> str:
            if name == "tool_failure":
                return "fallback: 工具降级路径"
            return f"recovered step for {name}"

        results = run_scenario(
            ["llm_429", "browser_element_missing", "tool_failure", "llm_401"],
            lambda n: _step, isolated_dir=tmp, purpose="zhuli --chaos-sample 示例",
        )
        report_path = write_report(build_report(results, purpose="zhuli --chaos-sample 示例"), tmp)
        print(f"混沌示例完成：恢复 {sum(1 for r in results if r.recovered)}/{len(results)}，报告：{report_path}")
        return
    if args.chaos_test:
        from zhuli.chaos.guard import enable_test_mode

        enable_test_mode(purpose="CLI --chaos-test（测试专用）")
        print("警告：混沌测试模式已开启（仅本次运行，重启后关闭；正常任务请勿使用）。")
    if args.no_parallel:
        # 运行时覆盖（只在内存中，不改写配置文件），与 /api/parallel 同款。
        from zhuli.agents.runtime import set_parallel_enabled

        set_parallel_enabled(False)
    if args.version:
        from zhuli import __version__
        print(__version__)
        return
    if args.check:
        from zhuli import __version__

        config = _PROJECT_ROOT / "config" / "settings.yaml"
        print(json.dumps({
            "version": __version__,
            "project_root": str(_PROJECT_ROOT),
            "runtime_dir": str(_RUNTIME_DIR),
            "browsers_path": str(_BROWSERS_PATH),
            "config_exists": config.exists(),
            "config_path": str(config),
        }, ensure_ascii=False, indent=2))
        return
    app = create_app()
    # 监听本机回环，避免暴露到局域网；端口可在 settings 调整
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")


if __name__ == "__main__":
    main()
