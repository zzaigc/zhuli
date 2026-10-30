"""配置加载与校验。

从项目根目录的 config/settings.yaml 读取（不存在则回退到 settings.yaml.example 的结构）。
API Key 通过环境变量或 keyring 解析，绝不落明文。
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml

from .schemas import ProviderConfig, Settings

_PROJECT_ROOT = Path(__file__).resolve().parents[3]  # src/zhuli/config -> 项目根
_CONFIG_PATH = _PROJECT_ROOT / "config" / "settings.yaml"


def _load_raw() -> dict:
    if _CONFIG_PATH.exists():
        with _CONFIG_PATH.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    raise FileNotFoundError(
        f"未找到配置文件：{_CONFIG_PATH}\n请复制 config/settings.yaml.example 为 config/settings.yaml 并填写。"
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    raw = _load_raw()
    return Settings.model_validate(raw)


def resolve_api_key(provider: ProviderConfig) -> str | None:
    """解析 provider 的 API Key：优先环境变量，其次 keyring。"""
    if provider.api_key_env:
        val = os.environ.get(provider.api_key_env)
        if val:
            return val
    if provider.api_key_service:
        try:
            import keyring

            return keyring.get_password(*provider.api_key_service.split(":", 1))  # type: ignore[arg-type]
        except Exception:
            return None
    return None
