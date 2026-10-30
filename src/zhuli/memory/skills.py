"""技能系统：从成功任务中沉淀可复用技能，并在新任务中检索复用，随使用自动迭代。

设计目标（对齐 Muse「越用越聪明」）：
- 每次成功任务后，用 LLM 把有效步骤压缩成「技能」（名称 / 触发条件 / 可复用步骤 / 标签）。
- 新任务开始时，按目标检索相关历史技能注入决策上下文，让 AI 直接复用成熟经验。
- 技能被复用时统计 usage / success；若同一目标已有技能，则把本次新经验合并精炼，实现「自动迭代」。
"""
from __future__ import annotations

import asyncio

from pydantic import BaseModel, Field

from ..llm.prompts import SKILL_SCHEMA, SYSTEM_SKILL
from ..llm.provider import chat_structured, embed_texts
from .store import store, _tokenize


async def _embed(text: str) -> list[float] | None:
    """文本向量化（语义检索用）；失败返回 None 并自动回退关键词。"""
    try:
        out = await embed_texts([text])
        return out[0] if out else None
    except Exception:
        return None


class Skill(BaseModel):
    id: int | None = None
    name: str
    description: str = ""
    trigger: str = ""
    procedure: str = ""
    tags: list[str] = Field(default_factory=list)
    usage_count: int = 0
    success_count: int = 0
    last_used: str | None = None

    @classmethod
    def from_row(cls, row: dict) -> "Skill":
        return cls(
            id=row.get("id"),
            name=row["name"],
            description=row.get("description") or "",
            trigger=row.get("trigger") or "",
            procedure=row.get("procedure") or "",
            tags=[t for t in (row.get("tags") or "").split(",") if t],
            usage_count=row.get("usage_count", 0),
            success_count=row.get("success_count", 0),
            last_used=row.get("last_used"),
        )


async def retrieve_skills(goal: str, limit: int = 3) -> list[Skill]:
    """按目标检索可复用的历史技能（供决策上下文注入）。
    优先语义检索（embedding），不可用或命中不足时回退关键词检索。
    """
    emb = await _embed(goal)
    if emb:
        rows = await asyncio.to_thread(store.search_skills_semantic, emb, limit)
    else:
        rows = await asyncio.to_thread(store.search_skills, goal, limit)
    return [Skill.from_row(r) for r in rows]


async def learn_from_task(
    goal: str,
    target_tool: str | None,
    success: bool,
    procedure_text: str,
    summary: str,
    *,
    miner=None,
) -> tuple[Skill | None, str | None]:
    """沉淀 / 迭代技能。返回 (skill, event_action)，event_action ∈ {'learned','updated'} 或 None。

    miner 为可选注入的「技能挖掘智能体」（提供 run(goal, procedure) 与 merge(skill, procedure)）；
    未提供时使用内置的单体提示词实现 —— 保证无协调器时也能独立工作。
    """
    task_id = await asyncio.to_thread(store.add_task, goal, target_tool, success, summary[:800])
    if not success or len(procedure_text.strip()) < 30:
        return None, None

    goal_emb = await _embed(goal)
    if goal_emb:
        existing = await asyncio.to_thread(store.search_skills_semantic, goal_emb, 5)
    else:
        existing = await asyncio.to_thread(store.search_skills, goal, 5)
    best = existing[0] if existing else None
    similar = False
    if best:
        similar = (best.get("score", 0) >= 0.35) if goal_emb else (_overlap(goal, best) >= 2)
    try:
        if best and similar:
            # 已有相似技能 -> 合并本次新经验，迭代更新（并刷新 embedding）
            if miner:
                merged = await miner.merge(Skill.from_row(best), procedure_text)
            else:
                merged = await _merge_procedure(best, procedure_text)
            emb = await _embed(f"{best['name']} {best['trigger']} {merged}")
            await asyncio.to_thread(store.refine_procedure, best["id"], merged, emb)
            await asyncio.to_thread(store.update_stats, best["id"], True)
            return Skill.from_row({**best, "procedure": merged}), "updated"

        extracted = await (miner.run(goal, procedure_text) if miner
                           else _extract_skill(goal, procedure_text))
        if not extracted:
            return None, None
        emb = await _embed(
            f"{extracted['name']} {extracted.get('trigger','')} {extracted['procedure']}"
        )
        sid = await asyncio.to_thread(
            store.add_skill,
            extracted["name"],
            extracted.get("description", ""),
            extracted.get("trigger", ""),
            extracted["procedure"],
            extracted.get("tags", []),
            emb,
        )
        row = await asyncio.to_thread(store.get_skill, sid)
        return Skill.from_row(row), "learned"
    except Exception:
        # 学习失败不影响主流程
        return None, None


def _overlap(goal: str, row: dict) -> int:
    qt = _tokenize(goal)
    blob = _tokenize(f"{row.get('name','')} {row.get('trigger','')} {row.get('procedure','')}")
    return len(qt & blob)


async def _extract_skill(goal: str, procedure_text: str) -> dict | None:
    messages = [
        {"role": "system", "content": SYSTEM_SKILL},
        {
            "role": "user",
            "content": f"目标：{goal}\n\n本次成功执行的步骤：\n{procedure_text}\n\n请提炼为一个可复用技能。",
        },
    ]
    return await chat_structured(
        "reasoning", messages, schema=SKILL_SCHEMA,
        schema_name="emit_skill", schema_description="可复用技能",
    )


async def _merge_procedure(existing: dict, new_procedure: str) -> str:
    messages = [
        {
            "role": "system",
            "content": "你是技能精炼器。把已有技能步骤与本次新经验合并为更通用、更准确的单一流程，去除冗余，保留关键顺序。",
        },
        {
            "role": "user",
            "content": f"已有技能步骤：\n{existing.get('procedure','')}\n\n本次新经验：\n{new_procedure}\n\n输出合并后的步骤（纯文本，分条）。",
        },
    ]
    merged = await chat_structured(
        "reasoning", messages,
        schema={"type": "object", "properties": {"procedure": {"type": "string"}}, "required": ["procedure"]},
        schema_name="emit_merge", schema_description="合并后的步骤",
    )
    return merged.get("procedure", existing.get("procedure", ""))
