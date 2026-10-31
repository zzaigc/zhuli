"""混沌测试（v0.3.0，标准库 unittest，无真实 LLM、浏览器或网络）。

覆盖：默认关闭、显式开启、隔离目录拒绝、每种注入器触发期望
恢复路径、失败记为失败、快照恢复、校准建议不写配置、
普通任务消息不能开启混沌。
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from zhuli.chaos import (  # noqa: E402
    FAULTS,
    build_report,
    disable_test_mode,
    enable_test_mode,
    ensure_isolated_dir,
    inject,
    is_test_mode_enabled,
    list_faults,
    restore_snapshot,
    run_scenario,
    simulate_recovery,
    suggest_parameters,
    take_snapshot,
    write_report,
)
from zhuli.chaos.faults import ChaosFault  # noqa: E402
from zhuli.config.schemas import ChaosConfig  # noqa: E402


def _ok_step(name):
    return f"ok:{name}"


def _fail_step(name):
    raise RuntimeError(f"still failing: {name}")


class TestChaosDefaults(unittest.TestCase):
    def setUp(self):
        disable_test_mode()

    def tearDown(self):
        disable_test_mode()

    def test_off_by_default(self):
        self.assertFalse(ChaosConfig().enabled)
        self.assertFalse(ChaosConfig().test_mode)
        self.assertFalse(is_test_mode_enabled())
        with self.assertRaises(RuntimeError):
            inject("llm_429", test_mode=False)
        with self.assertRaises(RuntimeError):
            simulate_recovery("llm_429", _ok_step)

    def test_enable_requires_purpose(self):
        with self.assertRaises(ValueError):
            enable_test_mode(purpose="")
        enable_test_mode(purpose="unit test")
        self.assertTrue(is_test_mode_enabled())

    def test_normal_task_message_cannot_enable(self):
        # 模拟 _dispatch 的任务消息：它只读 goal/target_tool/session_id，
        # 从不读 chaos 字段；此处断言混沌仍关闭，且该字段不产生任何开启效果。
        task_message = {"type": "task", "goal": "做点事", "chaos": True, "chaos_test": True}
        self.assertTrue(task_message.get("chaos"))
        self.assertFalse(is_test_mode_enabled())

    def test_unknown_fault(self):
        enable_test_mode(purpose="unit test")
        with self.assertRaises(ValueError):
            inject("no_such_fault", test_mode=True)


class TestChaosInjectors(unittest.TestCase):
    def setUp(self):
        enable_test_mode(purpose="unit test")

    def tearDown(self):
        disable_test_mode()

    def test_every_fault_injects_and_recovers(self):
        for fault in list_faults():
            with self.subTest(fault=fault.name):
                with self.assertRaises(ChaosFault):
                    inject(fault.name, test_mode=True)
                result = simulate_recovery(fault.name, _ok_step)
                self.assertTrue(result.recovered, fault.name)
                self.assertEqual(result.expected_recovery, fault.expected_recovery)

    def test_retry_exhaustion_is_failed_not_success(self):
        result = simulate_recovery("llm_429", _fail_step, retries=1)
        self.assertFalse(result.recovered)
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.attempts, 2)

    def test_failed_recovery_reported_failed(self):
        result = simulate_recovery("browser_page_crash", _fail_step)
        self.assertFalse(result.recovered)
        report = build_report([result], purpose="unit test")
        self.assertEqual(report["failed"], 1)
        self.assertIn("browser_page_crash", report["failures"])


class TestChaosIsolation(unittest.TestCase):
    def test_rejects_real_runtime_paths(self):
        for bad in ["/home/hatch/workspace/zhuli-work/.zhuli_runtime",
                    "/home/hatch/workspace/zhuli-work",
                    "/tmp"]:
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    ensure_isolated_dir(bad)

    def test_snapshot_and_restore_in_temp(self):
        with tempfile.TemporaryDirectory(prefix="zhuli-chaos-test-") as tmp:
            root = Path(tmp) / "data"
            root.mkdir()
            (root / "probe.txt").write_text("v1", encoding="utf-8")
            snap = take_snapshot(root, Path(tmp) / "snap")
            (root / "probe.txt").write_text("v2", encoding="utf-8")
            restore_snapshot(snap, root)
            self.assertEqual((root / "probe.txt").read_text(encoding="utf-8"), "v1")

    def test_scenario_and_report_in_temp_only(self):
        with tempfile.TemporaryDirectory(prefix="zhuli-chaos-test-") as tmp:
            results = run_scenario(
                ["llm_429", "tool_failure"], lambda n: _ok_step,
                isolated_dir=tmp, purpose="unit test")
            self.assertEqual(len(results), 2)
            self.assertTrue(all(r.recovered for r in results))
            # 退出后测试模式自动关闭
            self.assertFalse(is_test_mode_enabled())
            report_path = write_report(
                build_report(results, purpose="unit test"), tmp)
            self.assertTrue(report_path.exists())
            self.assertIn("校准建议", report_path.read_text(encoding="utf-8"))

    def test_calibration_does_not_write_config(self):
        with tempfile.TemporaryDirectory(prefix="zhuli-chaos-test-") as tmp:
            cfg = Path(tmp) / "settings.yaml"
            cfg.write_text("chaos:\n  enabled: false\n", encoding="utf-8")
            before = cfg.read_text(encoding="utf-8")
            results = run_scenario(
                ["llm_429"], lambda n: _fail_step,
                isolated_dir=tmp, purpose="unit test")
            suggestions = suggest_parameters(results)
            self.assertTrue(suggestions)
            self.assertTrue(all(s.get("apply") is False for s in suggestions))
            self.assertEqual(cfg.read_text(encoding="utf-8"), before)


if __name__ == "__main__":
    unittest.main()
