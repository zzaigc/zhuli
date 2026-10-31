"""Runtime-only overrides for the agent coordinator (v0.2.0).

The console Hive button changes the mode for the current run only.
Overrides live in memory, are never written to config/settings.yaml,
and a restart returns to the config value. This mirrors the existing
/app/models runtime override style for provider routing.
"""
from __future__ import annotations

_OVERRIDE: dict[str, int | bool | None] = {"enabled": None, "size": None}


def set_hive_enabled(enabled: bool) -> None:
    _OVERRIDE["enabled"] = bool(enabled)


def set_hive_size(size: int) -> None:
    if not 1 <= int(size) <= 4:
        raise ValueError("hive_size must be 1 to 4")
    _OVERRIDE["size"] = int(size)


def hive_override() -> dict:
    return dict(_OVERRIDE)


def effective_hive(config_enabled: bool, config_size: int) -> tuple[bool, int]:
    """Return (enabled, size) with a runtime override winning over config."""
    enabled = _OVERRIDE["enabled"] if _OVERRIDE["enabled"] is not None else bool(config_enabled)
    size = _OVERRIDE["size"] if _OVERRIDE["size"] is not None else int(config_size)
    return enabled, max(1, min(size, 4))
