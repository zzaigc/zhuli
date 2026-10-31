"""并行子目标执行（v0.3.0，Nova 式规则的 Zhuli 改写，非复制代码）。

适用范围与诚实边界
----------------
- 本模块只处理「子任务描述」级别的分组与执行：把一次规划得到的
  子任务清单分成若干组，组按顺序执行，组内子任务的「思考」并发、
  「工具执行」加锁串行，最后按组内顺序合并结果。
- 它不改动实时浏览器主循环：主循环每一步的观察都依赖上一步的
  结果、且多个浏览器步骤共用同一个页面，所以主循环仍顺序执行
  （见 orchestrator.plan_groups 的说明）。并行执行器用于独立的、
  非浏览器子任务单元；浏览器步骤永远不会被并行。
- Hive 模式已有自己的并行提案与投票：开启 Hive 时，分组一律强制
  为单步（顺序），避免「双重并行」打乱投票。

分组规则（Planner 分组，只分独立子任务）
---------------------------------------
1. 浏览器步骤永远单组：工具为 browser，或文本含浏览器关键词。
2. 依赖步骤不与被依赖者同组：文本含「然后/接着/基于上一步/用上
   一步的结果/previous」等依赖词时，另起一组。
3. 共享可变资源的步骤不与同组：同一文件路径、同一工具目标、同一
   引用字符串出现在组内已有成员时，另起一组。
4. 其余步骤可同组。

第二道防线（执行前再校验，sanitize_groups）
------------------------------------------
即使上游规划已经给出了分组，执行前也会重新检查：任何含浏览器
步骤或浏览器关键词的组都会被拆回单步；组内出现共享资源时也会
重新分组。误判（false positive）只损失速度，不损失正确性。

执行规则（run_parallel_groups / ParallelRunner）
-----------------------------------------------
- 组按顺序执行；组内「思考」（think，可并发的 LLM 推理）用
  asyncio.gather 并发，思考结果按组内顺序保存。
- 「工具执行」（execute）始终在同一把 asyncio.Lock 下串行执行，
  工具调用永远不会在同一瞬间发生；共享状态的更新也在锁下进行。
- 兜底：规划失败、分组非法、或并行组执行失败时，先回退到
  「一组成员逐个顺序重跑」（思考+执行各一步）；顺序重跑也失败
  时，异常向上传递，由调用方决定重规划或停机，绝不静默丢弃。
- 开关：配置 policy.parallel_enabled（默认开）+ 运行时覆盖
  （/api/parallel、CLI --no-parallel）。关闭时所有组退化为单步。
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional, Sequence

# ---- 浏览器关键词：命中即视为浏览器步骤，永远单步 ----
BROWSER_KEYWORDS = (
    "browser", "playwright", "chromium", "浏览器", "网页", "页面",
    "点击", "click", "打开网页", "打开页面", "跳转", "navigate",
    "截屏", "screenshot", "滚动页面", "scroll", "表单", "登录网页",
    "搜索网页", "web page", "open page", "open website",
)

# ---- 依赖关键词：命中即视为依赖前一步，不能与前一步同组 ----
DEPENDENCY_KEYWORDS = (
    "然后", "接着", "之后", "基于上一步", "用上一步", "上一步",
    "前一步", "的结果", "previous step", "previous subtask",
    "based on the previous", "after the previous", "using the previous",
)

# ---- 工具目标名：同组内出现同一工具名即视为共享可变状态 ----
TOOL_NAMES = (
    "codebuddy", "trae", "opencode", "browser", "shell", "video", "ffmpeg",
)

_FILE_RE = re.compile(r"[\w\-./\\]+\.(?:txt|md|py|json|yaml|yml|html|css|js|ts|png|jpg|mp4|csv)\b", re.I)
_QUOTED_RE = re.compile(r"[\"'「『]([^\"'」』]{2,80})[\"'」』]")


def is_browser_step(text: str, tool: Optional[str] = None) -> bool:
    """是否为浏览器步骤：工具名是 browser，或文本含浏览器关键词。"""
    if tool and str(tool).strip().lower() == "browser":
        return True
    lowered = (text or "").lower()
    return any(kw.lower() in lowered for kw in BROWSER_KEYWORDS)


def _has_dependency(text: str) -> bool:
    lowered = (text or "").lower()
    return any(kw.lower() in lowered for kw in DEPENDENCY_KEYWORDS)


def extract_resources(text: str) -> set[str]:
    """提取步骤共享的可变资源：文件路径、工具名、引用字符串。"""
    lowered = (text or "").lower()
    resources = {m.group(0).lower() for m in _FILE_RE.finditer(lowered)}
    resources |= {t for t in TOOL_NAMES if t in lowered}
    resources |= {m.group(1).strip().lower() for m in _QUOTED_RE.finditer(text or "")}
    return resources


def plan_groups(
    subtasks: Sequence[str],
    tools: Optional[Sequence[Optional[str]]] = None,
) -> list[list[str]]:
    """把子任务清单分组。任何输入异常都回退为单步分组，绝不抛错。

    tools 与 subtasks 一一对应时可用工具名辅助判定浏览器步骤；
    未提供时只按文本关键词判定。
    """
    try:
        items = [str(s) for s in (subtasks or []) if str(s or "").strip()]
        if not items:
            return []
        tool_list: list[Optional[str]] = list(tools or []) + [None] * len(items)
        groups: list[list[str]] = []
        current: list[str] = []
        current_resources: set[str] = set()
        for idx, subtask in enumerate(items):
            tool = tool_list[idx] if idx < len(tool_list) else None
            if is_browser_step(subtask, tool) or _has_dependency(subtask):
                # 浏览器步骤与依赖步骤：先收起当前组，自己单独成组。
                if current:
                    groups.append(current)
                    current, current_resources = [], set()
                groups.append([subtask])
                continue
            resources = extract_resources(subtask)
            if current and (resources & current_resources):
                groups.append(current)
                current, current_resources = [], set()
            current.append(subtask)
            current_resources |= resources
        if current:
            groups.append(current)
        return groups
    except Exception:
        # 规划失败兜底：全部单步，顺序执行（见模块说明）。
        # 输入本身不可遍历时，连单步清单也建不出来，返回空分组。
        try:
            return [[str(s)] for s in (subtasks or []) if str(s or "").strip()]
        except Exception:
            return []


def sanitize_groups(
    groups: Sequence[Sequence[str]],
    tools: Optional[dict[str, Optional[str]]] = None,
) -> list[list[str]]:
    """执行前第二道防线：把任何含浏览器步骤的组拆回单步。

    tools 可按子任务文本给出工具名；未给出时只按文本判定。
    非法分组（空组、非字符串）会被清洗，绝不原样放行。
    """
    sanitized: list[list[str]] = []
    try:
        flat_tools = tools or {}
        for group in groups or []:
            members = [str(s) for s in (group or []) if str(s or "").strip()]
            if not members:
                continue
            if len(members) == 1:
                sanitized.append(members)
                continue
            if any(is_browser_step(m, flat_tools.get(m)) for m in members):
                # 含浏览器步骤的组：一律拆回单步，哪怕是规划器分错了组。
                sanitized.extend([[m] for m in members])
            else:
                # 组内共享资源也重新分组（复用 plan_groups 的规则）。
                sanitized.extend(plan_groups(members, [flat_tools.get(m) for m in members]))
        return sanitized
    except Exception:
        flat: list[str] = []
        for group in groups or []:
            flat.extend(str(s) for s in (group or []) if str(s or "").strip())
        return [[s] for s in flat]


def effective_parallel(
    config_enabled: bool,
    *,
    runtime_override: Optional[bool] = None,
    hive_enabled: bool = False,
) -> bool:
    """并行是否真正生效：Hive 开启时强制关闭；运行时覆盖优先于配置。"""
    if hive_enabled:
        return False
    if runtime_override is not None:
        return bool(runtime_override)
    return bool(config_enabled)


@dataclass
class GroupResult:
    """一组子任务的执行结果（按组内顺序合并）。"""

    group_index: int
    group: list[str]
    results: list = field(default_factory=list)
    fell_back_to_sequential: bool = False
    sequential: bool = False


class ParallelRunner:
    """并行执行器：思考并发、工具串行、失败回退顺序重跑。

    think(subtask) -> action：可并发的推理/准备阶段。
    execute(action) -> result：工具执行阶段，始终在工具锁下串行。
    共享状态更新请放在 execute 内（锁内），或由调用方在锁外按
    GroupResult 的顺序合并（本模块按组内顺序返回结果）。
    """

    def __init__(self) -> None:
        self.tool_lock = asyncio.Lock()
        self.state_lock = asyncio.Lock()

    async def _run_one_sequentially(
        self, subtask: str, think: Callable, execute: Callable
    ):
        action = await think(subtask)
        async with self.tool_lock:
            result = await execute(action)
        async with self.state_lock:
            pass  # 状态合并点：调用方按返回顺序合并，此处保留锁语义
        return result

    async def run_group(
        self, group: Sequence[str], group_index: int, think: Callable, execute: Callable,
        *, parallel: bool = True,
    ) -> GroupResult:
        members = list(group)
        if not parallel or len(members) == 1:
            results = [await self._run_one_sequentially(s, think, execute) for s in members]
            return GroupResult(group_index, members, results, sequential=True)
        try:
            # 思考并发（gather），结果天然按组内顺序；工具执行随后串行。
            # 失败时必须先取消残留的思考任务，否则它们会在顺序重跑时
            # 继续运行，污染重跑（测试曾因此捕获到该问题）。
            tasks = [asyncio.create_task(think(s)) for s in members]
            try:
                actions = await asyncio.gather(*tasks)
            except Exception:
                for t in tasks:
                    t.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                raise
            results = []
            for action in actions:
                async with self.tool_lock:
                    results.append(await execute(action))
            return GroupResult(group_index, members, results)
        except Exception:
            # 并行组失败兜底：整组顺序重跑（思考+执行各一步）。
            results = [await self._run_one_sequentially(s, think, execute) for s in members]
            return GroupResult(group_index, members, results, fell_back_to_sequential=True)

    async def run_groups(
        self, groups: Sequence[Sequence[str]], think: Callable, execute: Callable,
        *, parallel: bool = True,
    ) -> list[GroupResult]:
        """组按顺序执行；执行前先过第二道防线（sanitize_groups）。"""
        safe_groups = sanitize_groups(groups)
        return [
            await self.run_group(g, idx, think, execute, parallel=parallel)
            for idx, g in enumerate(safe_groups)
        ]


async def run_parallel_groups(
    groups: Sequence[Sequence[str]], think: Callable, execute: Callable,
    *, parallel: bool = True,
) -> list[GroupResult]:
    """便捷入口：新建一个 ParallelRunner 并按组顺序执行。"""
    return await ParallelRunner().run_groups(groups, think, execute, parallel=parallel)
