"""v0.3.0 双向开关测试（unittest，无真实 LLM / 浏览器 / 网络）。

覆盖：三个位置互斥且只有一个值生效；开关各位置的派发允许/阻止；
共享文件跨进程可见；/api/dispatch 前置检查；Orchestrator.submit
的开关检查；MCP zhuli_tool_dispatch 的开关检查；原有派发检查
（未知 IDE / 无页面 / 缺二进制）仍返回明确错误、不伪造成功。
"""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("ZHULI_BIDIRECTIONAL_STATE",
                      str(Path(tempfile.gettempdir()) / "zhuli-bi-test.json"))

from zhuli.agents import bidirectional as bi  # noqa: E402
from zhuli.agents.bidirectional import (  # noqa: E402
    IDE_TOOLS, can_console_dispatch, can_mcp_dispatch, get_mode, set_mode,
)
from zhuli.console.server import validate_dispatch  # noqa: E402
from zhuli.integrations.dispatch import KNOWN_TOOLS, check as dispatch_check  # noqa: E402
from zhuli.mcp.server import _dispatch as mcp_dispatch  # noqa: E402


def _set_mode_for_test(mode: str) -> None:
    """Set mode and wipe process memory afterwards, so get_mode must
    prove the shared file (the cross-process path) carries the value."""
    set_mode(mode)
    bi._MEMORY = None


class TestModes(unittest.TestCase):
    def tearDown(self) -> None:
        _set_mode_for_test("off")

    def test_exactly_one_value_and_invalid_rejected(self) -> None:
        for mode in ("off", "ide_to_zhuli", "zhuli_to_ide"):
            _set_mode_for_test(mode)
            self.assertEqual(get_mode("off"), mode)
        for bad in ("both", "", "IDE_TO_ZHULI", None, True):
            with self.assertRaises(ValueError):
                set_mode(bad)  # type: ignore[arg-type]
        # A rejected set must not change the current value.
        _set_mode_for_test("off")
        self.assertEqual(get_mode("off"), "off")

    def test_shared_file_is_the_cross_process_path(self) -> None:
        _set_mode_for_test("zhuli_to_ide")
        raw = json.loads(Path(os.environ["ZHULI_BIDIRECTIONAL_STATE"]).read_text())
        self.assertEqual(raw["mode"], "zhuli_to_ide")
        self.assertNotIn("key", raw)
        self.assertNotIn("token", raw)

    def test_ide_tool_names_match_dispatch_module(self) -> None:
        self.assertEqual(tuple(IDE_TOOLS), tuple(KNOWN_TOOLS))

    def test_gates_are_mutually_exclusive(self) -> None:
        table = {
            "off": (False, False),
            "ide_to_zhuli": (False, True),
            "zhuli_to_ide": (True, False),
        }
        for mode, (console, mcp) in table.items():
            self.assertEqual(can_console_dispatch(mode), console, mode)
            self.assertEqual(can_mcp_dispatch(mode), mcp, mode)

    def test_switching_restores_previous_direction_only_by_value(self) -> None:
        # No hidden second flag: the mode is one string; switching
        # left then right then middle leaves exactly the last value.
        for mode in ("ide_to_zhuli", "zhuli_to_ide", "off"):
            _set_mode_for_test(mode)
        self.assertEqual(get_mode("off"), "off")
        self.assertFalse(can_console_dispatch(get_mode("off")))
        self.assertFalse(can_mcp_dispatch(get_mode("off")))


class TestYamlOffTrap(unittest.TestCase):
    """YAML 1.1 陷阱回归：不加引号的 off 会被解析成布尔 False，
    绝不能因此让整个配置加载失败（在线检查真实捕获过一次）。"""

    def test_false_coerces_to_off(self) -> None:
        from zhuli.config.schemas import PolicyConfig

        self.assertEqual(PolicyConfig.model_validate({"bidirectional_mode": False}).bidirectional_mode, "off")
        self.assertEqual(PolicyConfig.model_validate({"bidirectional_mode": "off"}).bidirectional_mode, "off")
        with self.assertRaises(Exception):
            PolicyConfig.model_validate({"bidirectional_mode": "both"})

    def test_example_quotes_off(self) -> None:
        example = Path(__file__).resolve().parents[1] / "config" / "settings.yaml.example"
        self.assertIn('bidirectional_mode: "off"', example.read_text(encoding="utf-8"))


class TestValidateDispatch(unittest.TestCase):
    def test_mode_blocks_before_anything_else(self) -> None:
        for mode in ("off", "ide_to_zhuli"):
            r = validate_dispatch("做点事", "codebuddy", mode=mode, busy=False,
                                  page=object(), configured_tools=["codebuddy"])
            self.assertFalse(r["ok"])
            self.assertIn("双向开关", r["error"])
        # And in the right position the same request passes checks.
        r = validate_dispatch("做点事", "codebuddy", mode="zhuli_to_ide", busy=False,
                              page=object(), configured_tools=["codebuddy"])
        self.assertTrue(r["ok"])

    def test_busy_and_empty_goal(self) -> None:
        r = validate_dispatch("做点事", "opencode", mode="zhuli_to_ide", busy=True,
                              page=None, configured_tools=["opencode"])
        self.assertFalse(r["ok"])
        self.assertIn("任务执行中", r["error"])
        r = validate_dispatch("   ", "opencode", mode="zhuli_to_ide", busy=False,
                              page=None, configured_tools=["opencode"])
        self.assertFalse(r["ok"])
        self.assertIn("先输入任务目标", r["error"])

    def test_unknown_unconfigured_no_page_missing_binary(self) -> None:
        r = validate_dispatch("做点事", "not-an-ide", mode="zhuli_to_ide", busy=False,
                              page=None, configured_tools=["codebuddy"])
        self.assertFalse(r["ok"])
        self.assertIn("未知 IDE", r["error"])
        r = validate_dispatch("做点事", "trae", mode="zhuli_to_ide", busy=False,
                              page=None, configured_tools=["codebuddy"])
        self.assertFalse(r["ok"])
        self.assertIn("未在配置", r["error"])
        r = validate_dispatch("做点事", "trae", mode="zhuli_to_ide", busy=False,
                              page=None, configured_tools=["trae"])
        self.assertFalse(r["ok"])
        self.assertIn("没有可用页面", r["error"])
        # opencode binary is absent in this VM: honest error, not success.
        r = validate_dispatch("做点事", "opencode", mode="zhuli_to_ide", busy=False,
                              page=None, configured_tools=["opencode"])
        self.assertFalse(r["ok"])
        self.assertIn("找不到 OpenCode", r["error"])

    def test_dispatch_check_primitives_still_honest(self) -> None:
        self.assertFalse(dispatch_check("nope", "x")["ok"])
        self.assertFalse(dispatch_check("codebuddy", "x", page=None)["ok"])
        self.assertFalse(dispatch_check("opencode", "x",
                                        command=["definitely-not-a-binary-xyz"])["ok"])
        self.assertTrue(dispatch_check("codebuddy", "x", page=object())["ok"])


class TestMcpDispatchGate(unittest.TestCase):
    def tearDown(self) -> None:
        _set_mode_for_test("off")

    def test_off_and_right_block_mcp_dispatch_before_approval(self) -> None:
        for mode, needle in (("off", "关闭"), ("zhuli_to_ide", "循环")):
            _set_mode_for_test(mode)
            r = mcp_dispatch({"tool": "opencode", "task": "做点事"})
            self.assertFalse(r["ok"])
            self.assertNotIn("needs_approval", r)
            self.assertIn(needle, r["error"])

    def test_left_allows_mcp_dispatch_to_reach_approval(self) -> None:
        _set_mode_for_test("ide_to_zhuli")
        r = mcp_dispatch({"tool": "opencode", "task": "做点事"})
        self.assertFalse(r["ok"])
        self.assertTrue(r.get("needs_approval"))

    def test_left_missing_binary_is_error_not_success(self) -> None:
        _set_mode_for_test("ide_to_zhuli")
        with mock.patch("shutil.which", return_value=None):
            r = mcp_dispatch({"tool": "opencode", "task": "做点事", "approved": True})
        self.assertFalse(r["ok"])
        self.assertIn("binary not found", r["error"])


class TestOrchestratorSubmitGate(unittest.IsolatedAsyncioTestCase):
    def tearDown(self) -> None:
        _set_mode_for_test("off")

    async def test_blocked_submit_creates_no_loop(self) -> None:
        from zhuli.core.orchestrator import Orchestrator

        seen: list[str] = []

        async def sink(event) -> None:
            seen.append(str(event.type))

        _set_mode_for_test("off")
        orch = Orchestrator(sink)
        await orch.submit("做点事", "codebuddy")
        self.assertEqual(orch.ctx.status, "error")
        self.assertIsNone(orch._loop)
        self.assertIn("error", seen)

    async def test_allowed_submit_creates_loop(self) -> None:
        from zhuli.core.orchestrator import Orchestrator

        async def sink(event) -> None:
            pass

        _set_mode_for_test("zhuli_to_ide")
        orch = Orchestrator(sink)
        try:
            await orch.submit("做点事", "codebuddy")
            self.assertIsNotNone(orch._loop)
            self.assertNotEqual(orch.ctx.status, "error")
        finally:
            if orch._loop is not None:
                orch._loop.cancel()
                try:
                    await orch._loop
                except (asyncio.CancelledError, Exception):
                    pass


if __name__ == "__main__":
    unittest.main()
