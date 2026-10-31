"""OpenAI 兼容多 provider 异步客户端。

统一封装：
  - 按 capability 选择 provider+model（见 router）
  - 支持「函数调用」式结构化输出（强制 tool_choice）以约束 LLM 返回 JSON
  - 兼容 OpenAI / DeepSeek / Kimi / GLM 等 OpenAI 格式接口
"""
from __future__ import annotations

from typing import Any, Literal

from openai import AsyncOpenAI

from .router import Capability, effective_provider, resolve_for, resolve_model
from .usage import parse_usage, record as record_usage

_client_cache: dict[str, AsyncOpenAI] = {}


def _get_client(base_url: str, api_key: str | None) -> AsyncOpenAI:
    key = f"{base_url}:{api_key}"
    client = _client_cache.get(key)
    if client is None:
        client = AsyncOpenAI(base_url=base_url, api_key=api_key or "EMPTY")
        _client_cache[key] = client
    return client


def _tool_from_schema(name: str, description: str, schema: dict) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": schema,
        },
    }


async def chat_structured(
    capability: Capability,
    messages: list[dict],
    *,
    schema: dict,
    schema_name: str = "emit_result",
    schema_description: str = "按约束返回结构化结果",
    temperature: float = 0.2,
    provider: str | None = None,
    session_id: str | None = None,
    hive: bool | None = None,
) -> dict:
    """以函数调用方式强制 LLM 返回符合 schema 的 JSON，返回解析后的 dict。

    provider 显式指定时使用「该 provider + capability」的绑定（多智能体分布式）；
    否则按 capability 走默认路由。
    """
    if provider:
        base_url, api_key, model = resolve_for(provider, capability)
    else:
        base_url, api_key, model = resolve_model(capability)
    client = _get_client(base_url, api_key)
    tool = _tool_from_schema(schema_name, schema_description, schema)

    resp = await client.chat.completions.create(
        model=model,
        messages=messages,  # type: ignore[arg-type]
        tools=[tool],  # type: ignore[list-item]
        tool_choice={"type": "function", "function": {"name": schema_name}},
        temperature=temperature,
    )
    record_usage(
        provider=effective_provider(provider, capability) or "unknown",
        model=model, capability=capability, kind="chat",
        usage=parse_usage(resp), session_id=session_id, hive=hive,
    )
    msg = resp.choices[0].message
    if msg.tool_calls:
        import json

        return json.loads(msg.tool_calls[0].function.arguments)
    # 兜底：部分 provider 不支持 tool_choice 时，尝试从 content 解析
    if msg.content:
        import json

        return json.loads(msg.content)
    raise ValueError("LLM 未返回结构化结果")


async def chat_text(
    capability: Capability,
    messages: list[dict],
    *,
    temperature: float = 0.3,
    max_tokens: int | None = None,
    provider: str | None = None,
    session_id: str | None = None,
    hive: bool | None = None,
) -> str:
    """普通文本补全（用于 Planner / Reflection 的自然语言输出）。"""
    if provider:
        base_url, api_key, model = resolve_for(provider, capability)
    else:
        base_url, api_key, model = resolve_model(capability)
    client = _get_client(base_url, api_key)
    kwargs: dict[str, Any] = {"model": model, "messages": messages, "temperature": temperature}  # type: ignore[arg-type]
    if max_tokens:
        kwargs["max_tokens"] = max_tokens
    resp = await client.chat.completions.create(**kwargs)
    record_usage(
        provider=effective_provider(provider, capability) or "unknown",
        model=model, capability=capability, kind="chat",
        usage=parse_usage(resp), session_id=session_id, hive=hive,
    )
    return resp.choices[0].message.content or ""


async def embed_texts(texts: list[str]) -> list[list[float]] | None:
    """批量文本向量化，用于技能语义检索。未配置 embedding provider 或失败则返回 None。"""
    from .router import resolve_embeddings

    cfg = resolve_embeddings()
    if not cfg:
        return None
    base_url, api_key, model = cfg
    try:
        from ..config.settings import get_settings

        emb_provider = get_settings().routing.embeddings or "unknown"
        client = _get_client(base_url, api_key)
        resp = await client.embeddings.create(model=model, input=texts)
        record_usage(
            provider=emb_provider, model=model, capability="embedding",
            kind="embedding", usage=parse_usage(resp),
        )
        return [d.embedding for d in resp.data]
    except Exception:
        return None
