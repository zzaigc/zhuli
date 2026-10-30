"""模型能力路由：按 capability（vision / reasoning / default）解析出 base_url / api_key / model。

路由逻辑来自配置：
  routing.<capability> -> provider 名称
  provider.models.<capability> 或 provider.default_model -> 模型 id
"""
from __future__ import annotations

from typing import Literal, Tuple

from ..config.settings import get_settings, resolve_api_key

Capability = Literal["vision", "reasoning", "default"]

# 运行期模型覆盖（控制台下拉切换后即时生效，不写回配置文件）
_OVERRIDES: dict[str, str] = {}


def set_override(capability: str, provider: str | None) -> None:
    """把某个 capability 的 provider 切换到指定供应商（空值表示恢复配置）。"""
    cap = capability or "default"
    if provider:
        _OVERRIDES[cap] = provider
    else:
        _OVERRIDES.pop(cap, None)


def overrides() -> dict[str, str]:
    return dict(_OVERRIDES)


def effective_provider(provider_name: str | None, capability: str) -> str | None:
    """解析「实际生效的 provider 名」：显式绑定 > 控制台覆盖 > 配置路由。"""
    if provider_name:
        return provider_name
    return _OVERRIDES.get(capability or "default")


def resolve_model(capability: Capability) -> Tuple[str, str | None, str]:
    """返回 (base_url, api_key, model_id)。"""
    s = get_settings()
    over = _OVERRIDES.get(capability)
    prov = s.provider(over) if over else None
    if prov is None:
        prov = s.provider_for(capability)
    if prov is None:
        raise ValueError(f"配置中未找到能力 '{capability}' 对应的 provider（检查 routing 配置）")
    model = prov.models.get(capability) or prov.default_model
    if not model:
        raise ValueError(f"provider '{prov.name}' 未配置模型（default_model 或 models.{capability}）")
    key = resolve_api_key(prov)
    return prov.base_url, key, model


def resolve_for(provider_name: str | None, capability: str = "reasoning") -> Tuple[str, str | None, str]:
    """按「显式 provider + capability」解析模型（多智能体可各自绑定不同模型/供应商）。

    provider_name 为空或找不到时，回退到该 capability 的 routing 配置。
    """
    s = get_settings()
    prov = s.provider(provider_name) if provider_name else None
    if prov is None:
        # 控制台可在运行期把某个能力切到别的供应商
        over = _OVERRIDES.get(capability)
        prov = s.provider(over) if over else None
    if prov is None:
        prov = s.provider_for(capability)  # type: ignore[arg-type]
    if prov is None:
        raise ValueError(f"未找到能力 '{capability}' 对应的 provider（检查 routing/agents 配置）")
    model = prov.models.get(capability) or prov.default_model
    if not model:
        raise ValueError(f"provider '{prov.name}' 未配置模型（default_model 或 models.{capability}）")
    return prov.base_url, resolve_api_key(prov), model


def resolve_embeddings() -> Tuple[str, str | None, str] | None:
    """返回用于技能语义检索的 embedding provider 配置；未配置则返回 None（回退关键词）。"""
    s = get_settings()
    name = s.routing.embeddings
    if not name:
        return None
    prov = s.provider(name)
    if prov is None:
        return None
    model = prov.embedding_model or prov.default_model
    if not model:
        return None
    key = resolve_api_key(prov)
    return prov.base_url, key, model
