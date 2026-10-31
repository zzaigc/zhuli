"""Runtime-only overrides for the agent coordinator (v0.2.0).

The console Hive button changes the mode for the current run only.
Overrides live in memory, are never written to config/settings.yaml,
and a restart returns to the config value. This mirrors the existing
/app/models runtime override style for provider routing.
"""
from __future__ import annotations

_OVERRIDE: dict = {"enabled": None, "size": None, "mode": None, "last_auto": None}


def _coerce_hive_size(size) -> int:
    """Validate a manual hive size: integer >= 1, no upper limit.

    Booleans, fractional floats and non-integer strings are rejected;
    a valid integer string is accepted (the API layer already int()s
    JSON numbers, this keeps direct callers honest too).
    """
    if isinstance(size, bool):
        raise ValueError("hive_size must be an integer >= 1")
    if isinstance(size, float):
        if not size.is_integer():
            raise ValueError("hive_size must be an integer >= 1")
        size = int(size)
    elif isinstance(size, str):
        s = size.strip()
        if not s.lstrip("-").isdigit():
            raise ValueError("hive_size must be an integer >= 1")
        size = int(s)
    elif isinstance(size, int):
        pass
    else:
        try:
            size = int(size)
        except (TypeError, ValueError):
            raise ValueError("hive_size must be an integer >= 1")
    if size < 1:
        raise ValueError("hive_size must be an integer >= 1")
    return size


def set_hive_enabled(enabled: bool) -> None:
    _OVERRIDE["enabled"] = bool(enabled)


def set_hive_size(size) -> None:
    # Manual size only: auto decisions are stored separately in
    # last_auto and never overwrite the manual size, so switching
    # back to manual restores exactly this value.
    _OVERRIDE["size"] = _coerce_hive_size(size)


def set_hive_size_mode(mode: str) -> None:
    if mode not in ("manual", "auto"):
        raise ValueError("hive_size_mode must be 'manual' or 'auto'")
    _OVERRIDE["mode"] = mode


def set_last_auto(size: int, reason: str) -> None:
    _OVERRIDE["last_auto"] = {"size": int(size), "reason": str(reason)}


def hive_override() -> dict:
    return dict(_OVERRIDE)


def effective_hive(config_enabled: bool, config_size: int,
                   config_mode: str = "manual") -> tuple[bool, int, str]:
    """Return (enabled, manual size, mode), runtime override winning over config.

    Size is the manual size only (override or config, >= 1, no upper
    limit). In auto mode the per-step size is decided separately by
    HiveCoordinator and reported via last_auto; it never overwrites
    this manual size.
    """
    enabled = _OVERRIDE["enabled"] if _OVERRIDE["enabled"] is not None else bool(config_enabled)
    size = _OVERRIDE["size"] if _OVERRIDE["size"] is not None else _coerce_hive_size(config_size)
    mode = _OVERRIDE["mode"] if _OVERRIDE["mode"] is not None else (config_mode or "manual")
    if mode not in ("manual", "auto"):
        mode = "manual"
    return enabled, size, mode


# ---- v0.3.0 并行开关运行时覆盖（与 Hive 覆盖同款：只在内存中，重启恢复配置值） ----
_PARALLEL_OVERRIDE: dict[str, bool | None] = {"enabled": None}


def set_parallel_enabled(enabled: bool) -> None:
    _PARALLEL_OVERRIDE["enabled"] = bool(enabled)


def parallel_override() -> dict:
    return dict(_PARALLEL_OVERRIDE)


def effective_parallel(config_enabled: bool, hive_enabled: bool) -> bool:
    """并行是否真正生效：Hive 开启时强制关闭；运行时覆盖优先于配置。"""
    if hive_enabled:
        return False
    if _PARALLEL_OVERRIDE["enabled"] is not None:
        return bool(_PARALLEL_OVERRIDE["enabled"])
    return bool(config_enabled)
