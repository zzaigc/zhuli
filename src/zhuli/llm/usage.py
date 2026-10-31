"""Token usage recording for Zhuli v0.3.0.

Rules, kept deliberately honest:
- Only real provider calls are counted in user-facing totals. A caller
  that is a test, stub or mock must pass source="test"; summary() then
  excludes it from totals, by-model, by-day and recent records.
- If a provider returns no usage, the call is recorded as
  usage_known=0 with all token counts NULL, never as zero. Totals sum
  only known calls; unknown calls are counted separately.
- No price is invented. Cost is computed only when the operator has
  placed a prices file in the runtime directory (see _load_prices);
  otherwise cost is None and the console shows token counts only.
- Storage is in the project-local runtime directory
  (.zhuli_runtime/usage.db, gitignored), never in repo source, and
  never contains any key, secret or prompt text. Only provider name,
  model, capability, kind, session id, hive flag and counts are stored.
- Session id and hive flag are best-effort context: the console
  sets them for a task at submit time (see orchestrator.submit);
  calls made outside a task, for example from MCP standalone mode,
  are recorded with session_id NULL and hive NULL.
"""
from __future__ import annotations

import contextvars
import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SESSION_CTX: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "zhuli_usage_session", default=None)
_HIVE_CTX: contextvars.ContextVar[bool | None] = contextvars.ContextVar(
    "zhuli_usage_hive", default=None)

_LOCK = threading.Lock()
_DB: sqlite3.Connection | None = None
_DB_PATH: Path | None = None


def set_usage_context(session_id: str | None, hive: bool | None):
    """Set session/hive context for the current task; returns a token
    the caller should reset after spawning the task, so the new task
    inherits the values but the submitting task does not leak them."""
    t1 = _SESSION_CTX.set(session_id)
    t2 = _HIVE_CTX.set(hive)
    return (t1, t2)


def reset_usage_context(tokens) -> None:
    _SESSION_CTX.reset(tokens[0])
    _HIVE_CTX.reset(tokens[1])


def current_session_id() -> str | None:
    return _SESSION_CTX.get()


def current_hive() -> bool | None:
    return _HIVE_CTX.get()


def db_path() -> Path:
    override = os.environ.get("ZHULI_USAGE_DB")
    if override:
        return Path(override)
    root = Path(__file__).resolve().parents[3]
    return root / ".zhuli_runtime" / "usage.db"


def _connect() -> sqlite3.Connection:
    global _DB, _DB_PATH
    path = db_path()
    if _DB is not None and _DB_PATH == path:
        return _DB
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS usage_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            date TEXT NOT NULL,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            capability TEXT NOT NULL,
            kind TEXT NOT NULL,
            session_id TEXT,
            hive INTEGER,
            source TEXT NOT NULL DEFAULT 'real',
            usage_known INTEGER NOT NULL DEFAULT 0,
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            total_tokens INTEGER,
            cached_tokens INTEGER
        )"""
    )
    conn.commit()
    _DB = conn
    _DB_PATH = path
    return conn


def parse_usage(resp: Any) -> dict[str, int | None] | None:
    """Extract token counts from an OpenAI-style response, or None
    when the provider returned no usable usage object."""
    try:
        usage = getattr(resp, "usage", None)
        if usage is None and isinstance(resp, dict):
            usage = resp.get("usage")
        if usage is None:
            return None
        if isinstance(usage, dict):
            prompt = usage.get("prompt_tokens")
            completion = usage.get("completion_tokens")
            total = usage.get("total_tokens")
            cached = usage.get("cached_tokens")
            details = usage.get("prompt_tokens_details") or {}
            if cached is None and isinstance(details, dict):
                cached = details.get("cached_tokens")
        else:
            prompt = getattr(usage, "prompt_tokens", None)
            completion = getattr(usage, "completion_tokens", None)
            total = getattr(usage, "total_tokens", None)
            cached = getattr(usage, "cached_tokens", None)
            details = getattr(usage, "prompt_tokens_details", None)
            if cached is None and details is not None:
                cached = getattr(details, "cached_tokens", None)
        if prompt is None and completion is None and total is None:
            return None
        if total is None and prompt is not None and completion is not None:
            total = int(prompt) + int(completion)
        return {
            "prompt_tokens": int(prompt) if prompt is not None else None,
            "completion_tokens": int(completion) if completion is not None else None,
            "total_tokens": int(total) if total is not None else None,
            "cached_tokens": int(cached) if cached is not None else None,
        }
    except Exception:
        return None


def record(
    *,
    provider: str,
    model: str,
    capability: str,
    kind: str = "chat",
    usage: dict[str, int | None] | None = None,
    session_id: str | None = None,
    hive: bool | None = None,
    source: str = "real",
) -> None:
    """Record one provider call. Never raises: a usage failure must
    never break the LLM call it is measuring."""
    try:
        if session_id is None:
            session_id = current_session_id()
        if hive is None:
            hive = current_hive()
        now = datetime.now(timezone.utc)
        conn = _connect()
        with _LOCK:
            conn.execute(
                """INSERT INTO usage_records
                (ts, date, provider, model, capability, kind, session_id,
                 hive, source, usage_known, prompt_tokens,
                 completion_tokens, total_tokens, cached_tokens)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    now.isoformat(),
                    now.date().isoformat(),
                    str(provider or "unknown"),
                    str(model or "unknown"),
                    str(capability or "default"),
                    str(kind),
                    session_id,
                    None if hive is None else (1 if hive else 0),
                    str(source),
                    1 if usage else 0,
                    usage.get("prompt_tokens") if usage else None,
                    usage.get("completion_tokens") if usage else None,
                    usage.get("total_tokens") if usage else None,
                    usage.get("cached_tokens") if usage else None,
                ),
            )
            conn.commit()
    except Exception:
        pass


def _load_prices() -> dict[str, float]:
    """Optional prices file: .zhuli_runtime/prices.json mapping a model
    name to a price per 1,000,000 tokens, in the operator's currency.
    Absent or invalid means cost is not shown at all."""
    try:
        path = db_path().parent / "prices.json"
        if not path.exists():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}
        return {str(k): float(v) for k, v in data.items() if v is not None}
    except Exception:
        return {}


def summary(limit: int = 50) -> dict[str, Any]:
    """User-facing totals. Only source='real' and usage_known=1 calls
    contribute to token sums; unknown calls are counted separately
    and test/stub/mock calls are excluded entirely."""
    conn = _connect()
    with _LOCK:
        cur = conn.cursor()
        totals = cur.execute(
            """SELECT COUNT(*), COALESCE(SUM(prompt_tokens),0),
                      COALESCE(SUM(completion_tokens),0),
                      COALESCE(SUM(total_tokens),0),
                      COALESCE(SUM(cached_tokens),0)
               FROM usage_records WHERE source='real' AND usage_known=1"""
        ).fetchone()
        unknown = cur.execute(
            """SELECT COUNT(*) FROM usage_records
               WHERE source='real' AND usage_known=0"""
        ).fetchone()[0]
        total_calls = cur.execute(
            "SELECT COUNT(*) FROM usage_records WHERE source='real'"
        ).fetchone()[0]
        by_model_rows = cur.execute(
            """SELECT model, COUNT(*), COALESCE(SUM(total_tokens),0)
               FROM usage_records WHERE source='real' AND usage_known=1
               GROUP BY model ORDER BY 3 DESC"""
        ).fetchall()
        by_day_rows = cur.execute(
            """SELECT date, COUNT(*), COALESCE(SUM(total_tokens),0)
               FROM usage_records WHERE source='real' AND usage_known=1
               GROUP BY date ORDER BY date DESC LIMIT 30"""
        ).fetchall()
        hive_rows = cur.execute(
            """SELECT hive, COUNT(*), COALESCE(SUM(total_tokens),0)
               FROM usage_records WHERE source='real' AND usage_known=1
               GROUP BY hive"""
        ).fetchall()
        recent_rows = cur.execute(
            """SELECT ts, provider, model, capability, kind, session_id,
                      hive, usage_known, prompt_tokens, completion_tokens,
                      total_tokens, cached_tokens
               FROM usage_records WHERE source='real'
               ORDER BY id DESC LIMIT ?""",
            (int(limit),),
        ).fetchall()
    hive_map = {row[0]: {"calls": row[1], "total_tokens": row[2]} for row in hive_rows}
    prices = _load_prices()
    cost = None
    if prices:
        total_cost = 0.0
        for model, _calls, tokens in by_model_rows:
            price = prices.get(model)
            if price is not None:
                total_cost += tokens * price / 1_000_000
        cost = round(total_cost, 6)
    return {
        "calls": int(total_calls),
        "known_calls": int(totals[0]),
        "unknown_calls": int(unknown),
        "prompt_tokens": int(totals[1]),
        "completion_tokens": int(totals[2]),
        "total_tokens": int(totals[3]),
        "cached_tokens": int(totals[4]),
        "cost": cost,
        "cost_note": (
            "Cost is shown only when the operator placed a prices.json "
            "in .zhuli_runtime; otherwise token counts only, no price invented."
            if cost is None
            else "Cost from operator-supplied .zhuli_runtime/prices.json (per 1M tokens)."
        ),
        "by_model": [
            {"model": m, "calls": c, "total_tokens": t} for m, c, t in by_model_rows
        ],
        "by_day": [
            {"date": d, "calls": c, "total_tokens": t} for d, c, t in by_day_rows
        ],
        "hive": {
            "hive": hive_map.get(1, {"calls": 0, "total_tokens": 0}),
            "non_hive": hive_map.get(0, {"calls": 0, "total_tokens": 0}),
            "unknown_mode": hive_map.get(None, {"calls": 0, "total_tokens": 0}),
        },
        "recent": [
            {
                "ts": r[0], "provider": r[1], "model": r[2], "capability": r[3],
                "kind": r[4], "session_id": r[5],
                "hive": (None if r[6] is None else bool(r[6])),
                "usage_known": bool(r[7]),
                "prompt_tokens": r[8], "completion_tokens": r[9],
                "total_tokens": r[10], "cached_tokens": r[11],
            }
            for r in recent_rows
        ],
        "notes": [
            "Test, stub and mock calls are excluded from all totals above.",
            "Calls with no usage from the provider are counted as unknown, not zero.",
            "Session persistence in v0.3.0 is browser-local; session ids here are best-effort context from console tasks.",
        ],
    }
