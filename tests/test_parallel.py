"""并行子目标测试（v0.3.0，标准库 unittest，无第三方依赖）。

用假智能体/桩步骤验证规则，不依赖真实 LLM、浏览器或网络：
- 独立步骤在组内并发思考、结果按组内顺序合并；
- 浏览器步骤永远不分组（含第二道防线拆组）；
- 依赖步骤与共享文件/工具的步骤不分组；
- 规划失败回退为单步顺序；并行组失败回退为顺序重跑；
- 工具执行永远不并发；Hive 模式与开关关闭时强制顺序。
"""
import asyncio
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from zhuli.core.parallel import (  # noqa: E402
    ParallelRunner,
    effective_parallel,
    plan_groups,
    run_parallel_groups,
    sanitize_groups,
)


def _concurrency_tracker():
    """返回 (think, execute, state)：记录思考与执行的并发峰值。"""
    state = {"think_active": 0, "think_max": 0, "exec_active": 0, "exec_max": 0}

    async def think(subtask):
        state["think_active"] += 1
        state["think_max"] = max(state["think_max"], state["think_active"])
        try:
            await asyncio.sleep(0.02)
            return f"action:{subtask}"
        finally:
            state["think_active"] -= 1

    async def execute(action):
        state["exec_active"] += 1
        state["exec_max"] = max(state["exec_max"], state["exec_active"])
        try:
            await asyncio.sleep(0.01)
            return f"done:{action}"
        finally:
            state["exec_active"] -= 1

    return think, execute, state


class TestPlanGroups(unittest.TestCase):
    def test_independent_steps_group_together(self):
        groups = plan_groups(["整理会议纪要", "生成本周摘要", "列出待办清单"])
        self.assertEqual(groups, [["整理会议纪要", "生成本周摘要", "列出待办清单"]])

    def test_browser_steps_are_never_grouped(self):
        groups = plan_groups(["整理会议纪要", "打开网页并点击提交按钮", "生成本周摘要"])
        self.assertEqual(groups, [["整理会议纪要"], ["打开网页并点击提交按钮"], ["生成本周摘要"]])

    def test_browser_tool_is_never_grouped(self):
        groups = plan_groups(
            ["整理会议纪要", "提交表单"], tools=[None, "browser"])
        self.assertIn(["提交表单"], groups)
        self.assertTrue(all(len(g) == 1 for g in groups if "提交表单" in g))

    def test_dependency_steps_are_not_grouped_with_predecessor(self):
        groups = plan_groups(["起草报告", "然后把报告发给团队"])
        self.assertEqual(groups, [["起草报告"], ["然后把报告发给团队"]])

    def test_shared_file_steps_are_not_grouped(self):
        groups = plan_groups(["把结果写入 report.md", "把附录追加到 report.md"])
        self.assertEqual(groups, [["把结果写入 report.md"], ["把附录追加到 report.md"]])

    def test_sanitize_splits_browser_group(self):
        # 即使规划器错误地把浏览器步骤分进了组，执行前也要拆回单步。
        groups = sanitize_groups([["整理会议纪要", "打开网页并点击提交按钮"]])
        self.assertEqual(groups, [["整理会议纪要"], ["打开网页并点击提交按钮"]])

    def test_planner_failure_falls_back_to_singletons(self):
        class Broken:
            def __iter__(self):
                raise RuntimeError("planner broken")

        # 不可遍历的输入：分组返回空（不抛错），调用方可安全地顺序处理。
        self.assertEqual(plan_groups(Broken()), [])
        # 非法分组输入：清洗后仍为单步，不原样放行。
        self.assertEqual(sanitize_groups([["a", ""], []]), [["a"]])


class TestEffectiveParallel(unittest.TestCase):
    def test_hive_forces_sequential(self):
        self.assertFalse(effective_parallel(True, hive_enabled=True))
        self.assertFalse(effective_parallel(True, runtime_override=True, hive_enabled=True))

    def test_runtime_override_wins_over_config(self):
        self.assertTrue(effective_parallel(False, runtime_override=True))
        self.assertFalse(effective_parallel(True, runtime_override=False))

    def test_config_default_on(self):
        self.assertTrue(effective_parallel(True))


class TestParallelRunner(unittest.IsolatedAsyncioTestCase):
    async def test_independent_steps_think_concurrently_results_in_order(self):
        think, execute, state = _concurrency_tracker()
        results = await run_parallel_groups(
            [["整理会议纪要", "生成本周摘要", "列出待办清单"]], think, execute)
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].fell_back_to_sequential)
        self.assertEqual(results[0].results, [
            "done:action:整理会议纪要",
            "done:action:生成本周摘要",
            "done:action:列出待办清单",
        ])
        self.assertGreater(state["think_max"], 1, "思考应当并发")
        self.assertEqual(state["exec_max"], 1, "工具执行永远不并发")

    async def test_groups_run_in_order(self):
        seen = []

        async def think(s):
            return s

        async def execute(a):
            seen.append(a)
            return a

        results = await run_parallel_groups(
            [["第一组A", "第一组B"], ["第二组A"]], think, execute)
        self.assertEqual(seen, ["第一组A", "第一组B", "第二组A"])
        self.assertEqual([r.group_index for r in results], [0, 1])

    async def test_failed_group_falls_back_to_sequential(self):
        active = {"n": 0}

        async def think(s):
            active["n"] += 1
            try:
                # 并发思考时失败，顺序重跑时成功：模拟并行链路故障。
                if active["n"] > 1:
                    raise RuntimeError("parallel think failed")
                await asyncio.sleep(0.01)
                return s
            finally:
                active["n"] -= 1

        async def execute(a):
            return f"done:{a}"

        results = await run_parallel_groups([["A", "B"]], think, execute)
        self.assertTrue(results[0].fell_back_to_sequential)
        self.assertEqual(results[0].results, ["done:A", "done:B"])

    async def test_switch_off_runs_sequentially(self):
        think, execute, state = _concurrency_tracker()
        results = await run_parallel_groups(
            [["A", "B", "C"]], think, execute, parallel=False)
        self.assertTrue(results[0].sequential)
        self.assertEqual(state["think_max"], 1)
        self.assertEqual(results[0].results, ["done:action:A", "done:action:B", "done:action:C"])

    async def test_sequential_retry_failure_propagates(self):
        async def think(s):
            raise RuntimeError("always broken")

        async def execute(a):
            return a

        with self.assertRaises(RuntimeError):
            await run_parallel_groups([["A", "B"]], think, execute)

    async def test_runner_sanitizes_browser_group_before_execution(self):
        think, execute, _ = _concurrency_tracker()
        runner = ParallelRunner()
        results = await runner.run_groups(
            [["整理会议纪要", "打开网页并点击提交按钮"]], think, execute)
        # 第二道防线已拆组：浏览器步骤单独成组，思考不与他人并发。
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r.sequential for r in results))


if __name__ == "__main__":
    unittest.main()
