"""SQLite 持久化存储：技能、任务历史、反思、键值记忆。

DB 文件位于项目内 `.zhuli_runtime/memory.db`（不进 C 盘）。
所有方法为同步阻塞，调用方用 `asyncio.to_thread` 包裹以避免阻塞事件循环。
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DB_PATH = _PROJECT_ROOT / ".zhuli_runtime" / "memory.db"


class MemoryStore:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or _DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # v0.2.0: callers use asyncio.to_thread for store methods, so the
        # connection must be usable from worker threads (v0.1.0 crashed
        # with "SQLite objects created in a thread..." on any task run).
        # Orchestrator skill calls are sequential, not concurrent writes.
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init()

    def _init(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS skills(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                trigger TEXT DEFAULT '',
                procedure TEXT DEFAULT '',
                tags TEXT DEFAULT '',
                usage_count INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                last_used TEXT,
                embedding TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS tasks(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal TEXT,
                target_tool TEXT,
                success INTEGER DEFAULT 0,
                summary TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS reflections(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER,
                status TEXT,
                reason TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS kv(
                key TEXT PRIMARY KEY,
                value TEXT
            );
            """
        )
        # 旧库兼容：补列（embedding 在后续版本新增）
        try:
            self._conn.execute("ALTER TABLE skills ADD COLUMN embedding TEXT")
            self._conn.commit()
        except sqlite3.OperationalError:
            pass
        self._conn.commit()

    # ---------- 技能 ----------
    def add_skill(self, name, description, trigger, procedure, tags, embedding=None) -> int:
        cur = self._conn.execute(
            "INSERT INTO skills(name,description,trigger,procedure,tags,embedding) VALUES(?,?,?,?,?,?)",
            (name, description, trigger, procedure, ",".join(tags), _enc_vec(embedding)),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_skill(self, skill_id: int) -> dict | None:
        row = self._conn.execute("SELECT * FROM skills WHERE id=?", (skill_id,)).fetchone()
        return dict(row) if row else None

    def list_skills(self, limit: int = 200) -> list[dict]:
        # 列表不返回 embedding（体积大），检索/编辑单独取
        rows = self._conn.execute(
            "SELECT id,name,description,trigger,procedure,tags,usage_count,success_count,last_used,created_at "
            "FROM skills ORDER BY usage_count DESC, id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def update_skill(self, skill_id: int, **fields) -> None:
        allowed = {"name", "description", "trigger", "procedure", "tags", "embedding"}
        sets, vals = [], []
        for k, v in fields.items():
            if k not in allowed or v is None:
                continue
            if k == "embedding":
                v = _enc_vec(v)
            sets.append(f"{k}=?")
            vals.append(v)
        if not sets:
            return
        vals.append(skill_id)
        self._conn.execute(f"UPDATE skills SET {','.join(sets)} WHERE id=?", vals)
        self._conn.commit()

    def delete_skill(self, skill_id: int) -> None:
        self._conn.execute("DELETE FROM skills WHERE id=?", (skill_id,))
        self._conn.commit()

    def update_stats(self, skill_id: int, success: bool) -> None:
        if success:
            self._conn.execute(
                "UPDATE skills SET usage_count=usage_count+1, success_count=success_count+1, last_used=datetime('now') WHERE id=?",
                (skill_id,),
            )
        else:
            self._conn.execute(
                "UPDATE skills SET usage_count=usage_count+1, last_used=datetime('now') WHERE id=?",
                (skill_id,),
            )
        self._conn.commit()

    def refine_procedure(self, skill_id: int, procedure: str, embedding=None) -> None:
        self._conn.execute(
            "UPDATE skills SET procedure=?, embedding=? WHERE id=?",
            (procedure, _enc_vec(embedding), skill_id),
        )
        self._conn.commit()

    def search_skills(self, query: str, limit: int = 5) -> list[dict]:
        """关键词检索（embedding 不可用时的回退）。"""
        qt = _tokenize(query)
        if not qt:
            return []
        rows = self._conn.execute(
            "SELECT id,name,description,trigger,procedure,tags,usage_count,success_count FROM skills"
        ).fetchall()
        scored = []
        for r in rows:
            d = dict(r)
            blob = _tokenize(f"{d['name']} {d['description']} {d['trigger']} {d['procedure']} {d['tags']}")
            score = len(qt & blob)
            if score > 0:
                scored.append((score, d))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [d for _, d in scored[:limit]]

    def search_skills_semantic(self, query_emb: list[float], limit: int = 5) -> list[dict]:
        """语义检索：与已存技能 embedding 做余弦相似度排序。"""
        rows = self._conn.execute(
            "SELECT id,name,description,trigger,procedure,tags,usage_count,success_count,embedding FROM skills"
        ).fetchall()
        scored = []
        for r in rows:
            d = dict(r)
            vec = _dec_vec(d.get("embedding"))
            if not vec or len(vec) != len(query_emb):
                continue
            sim = _cosine(query_emb, vec)
            if sim > 0:
                d["score"] = round(sim, 4)
                scored.append((sim, d))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [d for _, d in scored[:limit]]


def _enc_vec(vec: list[float] | None) -> str | None:
    return None if vec is None else json.dumps(vec, separators=(",", ":"))


def _dec_vec(s: str | None) -> list[float] | None:
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        return None


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def _tokenize(text: str) -> set[str]:
    """混合分词：拉丁词（>=2 字母/数字）+ 中文二元组，兼顾中英文检索。"""
    text = (text or "").lower()
    latin = set(re.findall(r"[a-z0-9]{2,}", text))
    cjk = re.findall(r"[一-鿿]", text)
    bigrams = {cjk[i] + cjk[i + 1] for i in range(len(cjk) - 1)}
    return latin | bigrams

    # ---------- 任务 / 反思 ----------
    def add_task(self, goal, target_tool, success, summary) -> int:
        cur = self._conn.execute(
            "INSERT INTO tasks(goal,target_tool,success,summary) VALUES(?,?,?,?)",
            (goal, target_tool, 1 if success else 0, summary),
        )
        self._conn.commit()
        return cur.lastrowid

    def add_reflection(self, task_id, status, reason) -> None:
        self._conn.execute(
            "INSERT INTO reflections(task_id,status,reason) VALUES(?,?,?)",
            (task_id, status, reason),
        )
        self._conn.commit()

    def recent_tasks(self, limit: int = 10) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM tasks ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    # ---------- 键值记忆 ----------
    def set_kv(self, key, value) -> None:
        self._conn.execute(
            "INSERT INTO kv(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        self._conn.commit()

    def get_kv(self, key) -> str | None:
        row = self._conn.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

    def close(self) -> None:
        self._conn.close()


store = MemoryStore()
