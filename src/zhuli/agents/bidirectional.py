"""Single shared value for the console IDE bidirectional switch (v0.3.0).

The switch has exactly three positions, held in ONE value by
construction, so the two directions can never be on at the same time:

  - ``off``          -- middle, default: only 本助理, no IDE dispatch
                        in either direction.
  - ``ide_to_zhuli`` -- left: an external IDE operates Zhuli through
                        MCP tools (including ``zhuli_tool_dispatch``).
                        Zhuli must NOT dispatch back, or an
                        IDE <-> Zhuli ping-pong loop could form.
  - ``zhuli_to_ide`` -- right: Zhuli dispatches to an external IDE
                        (codebuddy / trae / opencode) from the console.
                        Incoming MCP dispatch to Zhuli is blocked.

Why a shared file, not just a UI flag: the console server and the MCP
server are separate processes. The console switch writes this value to
both process memory and a small JSON file under ``.zhuli_runtime/``
(never committed, contains no secret, only the mode string); the MCP
dispatch path reads that file on EVERY call, so a console switch
takes effect for MCP without an MCP restart. If the file cannot be
read (no console session has written one), the mode falls back to
``off``: fail-closed, both directions blocked, never silently open.

Restart behaviour (same pattern as the Hive runtime toggle): the
console resets this value to the config value
(``policy.bidirectional_mode``, default ``off``) when it starts, and
best-effort removes the shared file when it stops, so a later
standalone MCP run without a console session also defaults to off.
Within one console run, the value is live-shared, not restart-gated.

The console UI additionally remembers the last position in browser
localStorage (``zhuli-bidirectional-mode``) for display only; the
server value always wins on load, so a stale browser value can never
re-enable a direction the server has turned off.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

MODES = ("off", "ide_to_zhuli", "zhuli_to_ide")
DEFAULT_MODE = "off"

# IDE tool names, mirroring integrations.dispatch.KNOWN_TOOLS. Kept as a
# plain tuple here so this module stays importable without pulling in
# the integrations package (the console server and the MCP server both
# import it early); tests assert the two stay in sync.
IDE_TOOLS = ("codebuddy", "trae", "opencode")

LABELS = {
    "off": "关闭（仅本助理）",
    "ide_to_zhuli": "IDE -> Zhuli",
    "zhuli_to_ide": "Zhuli -> IDE",
}

_MEMORY: str | None = None


def _project_root() -> Path:
    # This file lives at src/zhuli/agents/, so parents[3] is the
    # project root (same layout rule as main.py's parents[2] from
    # src/zhuli/).
    return Path(__file__).resolve().parents[3]


def state_path() -> Path:
    """Shared state file path. Tests override it with the
    ZHULI_BIDIRECTIONAL_STATE environment variable."""
    override = os.environ.get("ZHULI_BIDIRECTIONAL_STATE")
    if override:
        return Path(override)
    return _project_root() / ".zhuli_runtime" / "bidirectional.json"


def _read_file() -> str | None:
    try:
        raw = json.loads(state_path().read_text(encoding="utf-8"))
        mode = raw.get("mode") if isinstance(raw, dict) else None
        return mode if mode in MODES else None
    except Exception:
        return None


def _write_file(mode: str) -> bool:
    try:
        path = state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"mode": mode}, ensure_ascii=False),
                        encoding="utf-8")
        return True
    except Exception:
        return False


def validate_mode(mode) -> str:
    if mode not in MODES:
        raise ValueError("bidirectional mode must be one of: off, ide_to_zhuli, zhuli_to_ide")
    return mode  # type: ignore[return-value]


def get_mode(config_default: str = DEFAULT_MODE) -> str:
    """Current mode. The shared file wins when present (live sharing
    across processes); otherwise process memory, otherwise the config
    default, otherwise off. Never returns an invalid value."""
    from_file = _read_file()
    if from_file is not None:
        return from_file
    if _MEMORY is not None:
        return _MEMORY
    return config_default if config_default in MODES else DEFAULT_MODE


def set_mode(mode: str) -> str:
    """Set the mode in memory AND in the shared file. The file write
    is best-effort (a failed write still leaves the in-process value
    correct, and a foreign process without a file fails closed to
    off); the return value is always the validated mode."""
    mode = validate_mode(mode)
    global _MEMORY
    _MEMORY = mode
    _write_file(mode)
    return mode


def clear_shared_file() -> None:
    """Best-effort removal of the shared file (console shutdown)."""
    try:
        state_path().unlink(missing_ok=True)
    except Exception:
        pass


def can_console_dispatch(mode: str) -> bool:
    """Zhuli -> IDE allowed only in the right position."""
    return mode == "zhuli_to_ide"


def can_mcp_dispatch(mode: str) -> bool:
    """IDE -> Zhuli (MCP) allowed only in the left position."""
    return mode == "ide_to_zhuli"


def console_block_reason(mode: str) -> str:
    if mode == "off":
        return ("双向开关处于关闭位置：Zhuli 不能派发到 IDE；"
                "如需派发，请把开关切到 Zhuli -> IDE")
    if mode == "ide_to_zhuli":
        return ("双向开关处于 IDE -> Zhuli 位置：Zhuli 不能反向派发，"
                "否则会形成 IDE <-> Zhuli 来回循环；"
                "如需派发，请把开关切到 Zhuli -> IDE")
    return ""


def mcp_block_reason(mode: str) -> str:
    if mode == "off":
        return ("双向开关处于关闭位置：MCP 派发已关闭；"
                "如需 IDE 操作 Zhuli，请把控制台双向开关切到 IDE -> Zhuli")
    if mode == "zhuli_to_ide":
        return ("双向开关处于 Zhuli -> IDE 位置：为防止 IDE <-> Zhuli "
                "来回循环，来自 IDE 的 MCP 派发已被阻止；"
                "如需 IDE 操作 Zhuli，请把开关切到 IDE -> Zhuli")
    return ""


def is_ide_tool(tool) -> bool:
    return str(tool or "").lower() in IDE_TOOLS
