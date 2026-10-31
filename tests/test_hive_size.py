"""蜂巢自定义规模与自动模式测试（v0.3.0，标准库 unittest，无真实 LLM/浏览器/网络）。

- 手动规模 1、5、8、12 都建出对应数量的执行体，温度对大蜂群均匀铺开；
- 规模 0 与非整数被拒绝，且不改动当前值；
- 自动模式对复杂多子任务的规模大于简单任务，自动范围恒在 2~8；
- 切回手动恢复手动规模；批评/风险加权投票与否决规则不变。
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from zhuli.agents.hive import (
    HiveCoordinator, auto_decide_size, temperatures_for_size,
    _CRITIC_SCORE, _RISK_SCORE,
)
from zhuli.agents.registry import AgentRegistry
from zhuli.agents.roles import ActorAgent
from zhuli.agents import runtime as hive_runtime


def make_coord(size=3, mode="manual"):
    reg = AgentRegistry()
    reg.register(ActorAgent(capability="reasoning", provider=None))
    return HiveCoordinator(reg, sink=None, settings=None, hive_size=size, hive_size_mode=mode)


class TestTemperatures(unittest.TestCase):
    def test_small_swarm_keeps_original_order(self):
        self.assertEqual(temperatures_for_size(3), [0.2, 0.5, 0.9])
        self.assertEqual(temperatures_for_size(4), [0.2, 0.5, 0.9, 1.1])

    def test_large_swarm_spreads_evenly_not_repeated(self):
        temps = temperatures_for_size(8)
        self.assertEqual(len(temps), 8)
        self.assertAlmostEqual(temps[0], 0.2)
        self.assertAlmostEqual(temps[-1], 1.2)
        # 均匀铺开：相邻差基本相等，且不是 0.2,0.5,0.9,1.1,0.2… 的重复
        diffs = [round(temps[i + 1] - temps[i], 2) for i in range(len(temps) - 1)]
        self.assertTrue(max(diffs) - min(diffs) <= 0.02)
        self.assertNotEqual(temps[4], 0.2)

    def test_manual_sizes_build_that_many_proposers(self):
        for size in (1, 5, 8, 12):
            coord = make_coord(size=size)
            self.assertEqual(len(coord._proposers), size)
            self.assertEqual(coord.hive_size, size)
            temps = [p._temperature for p in coord._proposers]
            self.assertEqual(len(temps), size)
            if size > 4:
                self.assertEqual(temps, temperatures_for_size(size))


class TestSizeValidation(unittest.TestCase):
    def test_zero_and_non_integer_rejected(self):
        for bad in (0, -1, 2.5, "abc", True, None):
            with self.assertRaises(ValueError):
                hive_runtime.set_hive_size(bad)
        with self.assertRaises(ValueError):
            make_coord(size=0)

    def test_valid_sizes_accepted_no_upper_limit(self):
        for good in (1, 5, 8, 12, 20):
            hive_runtime.set_hive_size(good)
            self.assertEqual(hive_runtime.hive_override()["size"], good)


class TestAutoMode(unittest.TestCase):
    def test_complex_larger_than_simple(self):
        simple_size, _ = auto_decide_size("打开网页", [], total_subtasks=1, history=[])
        complex_size, reason = auto_decide_size(
            "先收集数据、再分析风险、确认后删除旧文件并生成报告；涉及敏感操作与确认",
            ["数据完整", "风险已评估", "已确认", "报告已生成"],
            total_subtasks=5, history=[{"action": "x"}])
        self.assertGreater(complex_size, simple_size)
        self.assertIn("基础", reason)

    def test_auto_stays_within_2_to_8(self):
        huge, _ = auto_decide_size("做很多很多事情；涉及风险；确认；验证标准很多；" * 20,
                                   ["a", "b", "c", "d", "e"], total_subtasks=20)
        tiny, _ = auto_decide_size("好", [], total_subtasks=1, history=[])
        self.assertTrue(2 <= huge <= 8)
        self.assertTrue(2 <= tiny <= 8)

    def test_switch_back_to_manual_restores_manual_size(self):
        hive_runtime.set_hive_size(5)
        hive_runtime.set_hive_size_mode("auto")
        _, size_auto, mode_auto = hive_runtime.effective_hive(False, 3, "manual")
        self.assertEqual(mode_auto, "auto")
        self.assertEqual(size_auto, 5)
        hive_runtime.set_last_auto(8, "测试自动结果")
        hive_runtime.set_hive_size_mode("manual")
        _, size_manual, mode_manual = hive_runtime.effective_hive(False, 3, "manual")
        self.assertEqual(mode_manual, "manual")
        self.assertEqual(size_manual, 5)

    def test_auto_coordinator_keeps_manual_size(self):
        coord = make_coord(size=5, mode="auto")
        self.assertEqual(coord.manual_size, 5)
        self.assertEqual(coord.hive_size_mode, "auto")


class TestVotingUnchanged(unittest.TestCase):
    def test_weighted_scores_unchanged(self):
        self.assertEqual(_CRITIC_SCORE, {"accept": 2, "revise": 1, "abort": -2})
        self.assertEqual(_RISK_SCORE, {"safe": 2, "confirm": 0, "danger": -2})


if __name__ == "__main__":
    unittest.main()
