"""Memory stream + retrieval — the heart of a generative agent.

Each agent owns a `MemoryStream`: an append-only log of `Memory` objects backed by
SQLite. Retrieval blends recency, importance and relevance (cosine over
embeddings) exactly in the spirit of the Generative Agents paper, with each
component min-max normalised over the candidate set before a weighted sum.

The module is dependency-light: it needs an object with `.embed(text)->np.ndarray`
and (optionally) `.generate_json(...)` for importance scoring. Tests inject a fake.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field

import numpy as np

from .config import DEFAULT, Config

KINDS = ("observation", "conversation", "reflection", "plan")


@dataclass
class Memory:
    agent_id: str
    kind: str
    text: str
    created_tick: int
    last_access_tick: int
    importance: float  # 1..10
    embedding: np.ndarray | None = None
    citations: list[int] = field(default_factory=list)
    id: int | None = None

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"unknown memory kind {self.kind!r}; expected one of {KINDS}")


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #
def _emb_to_blob(emb: np.ndarray | None) -> bytes | None:
    if emb is None:
        return None
    return np.asarray(emb, dtype=np.float32).tobytes()


def _blob_to_emb(blob: bytes | None) -> np.ndarray | None:
    if blob is None:
        return None
    return np.frombuffer(blob, dtype=np.float32)


class MemoryStore:
    """SQLite-backed store shared by all agents (rows filtered by agent_id)."""

    def __init__(self, db_path: str = ":memory:"):
        # check_same_thread=False so the server's worker thread can use it.
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                text TEXT NOT NULL,
                created_tick INTEGER NOT NULL,
                last_access_tick INTEGER NOT NULL,
                importance REAL NOT NULL,
                embedding BLOB,
                citations TEXT NOT NULL DEFAULT '[]'
            )
            """
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_mem_agent ON memories(agent_id)"
        )
        self.conn.commit()

    def add(self, m: Memory) -> int:
        cur = self.conn.execute(
            """INSERT INTO memories
               (agent_id, kind, text, created_tick, last_access_tick, importance, embedding, citations)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                m.agent_id,
                m.kind,
                m.text,
                m.created_tick,
                m.last_access_tick,
                float(m.importance),
                _emb_to_blob(m.embedding),
                json.dumps(m.citations),
            ),
        )
        self.conn.commit()
        m.id = int(cur.lastrowid)
        return m.id

    def _row_to_memory(self, r: sqlite3.Row) -> Memory:
        return Memory(
            id=r["id"],
            agent_id=r["agent_id"],
            kind=r["kind"],
            text=r["text"],
            created_tick=r["created_tick"],
            last_access_tick=r["last_access_tick"],
            importance=r["importance"],
            embedding=_blob_to_emb(r["embedding"]),
            citations=json.loads(r["citations"]),
        )

    def all_for(self, agent_id: str) -> list[Memory]:
        rows = self.conn.execute(
            "SELECT * FROM memories WHERE agent_id=? ORDER BY id", (agent_id,)
        ).fetchall()
        return [self._row_to_memory(r) for r in rows]

    def get(self, mem_id: int) -> Memory | None:
        r = self.conn.execute("SELECT * FROM memories WHERE id=?", (mem_id,)).fetchone()
        return self._row_to_memory(r) if r else None

    def touch(self, ids: list[int], tick: int) -> None:
        if not ids:
            return
        self.conn.executemany(
            "UPDATE memories SET last_access_tick=? WHERE id=?",
            [(tick, i) for i in ids],
        )
        self.conn.commit()


# --------------------------------------------------------------------------- #
# Retrieval (pure functions)
# --------------------------------------------------------------------------- #
def cosine(a: np.ndarray, b: np.ndarray) -> float:
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def _minmax(xs: list[float]) -> list[float]:
    lo, hi = min(xs), max(xs)
    if hi - lo < 1e-9:
        return [1.0 for _ in xs]  # all equal -> treat as fully present
    return [(x - lo) / (hi - lo) for x in xs]


def score_memories(
    memories: list[Memory],
    query_emb: np.ndarray,
    now_tick: int,
    cfg: Config = DEFAULT,
) -> list[tuple[Memory, float]]:
    """Return (memory, score) pairs sorted by descending blended score."""
    if not memories:
        return []
    rc = cfg.retrieval
    recency = [rc.recency_decay ** max(0, now_tick - m.last_access_tick) for m in memories]
    importance = [m.importance / 10.0 for m in memories]
    relevance = [
        cosine(query_emb, m.embedding) if m.embedding is not None else 0.0
        for m in memories
    ]
    rec_n = _minmax(recency)
    imp_n = _minmax(importance)
    rel_n = _minmax(relevance)
    scored = []
    for m, r, i, v in zip(memories, rec_n, imp_n, rel_n):
        s = rc.w_recency * r + rc.w_importance * i + rc.w_relevance * v
        scored.append((m, s))
    scored.sort(key=lambda t: t[1], reverse=True)
    return scored


# --------------------------------------------------------------------------- #
# Importance scoring
# --------------------------------------------------------------------------- #
_IMPORTANCE_SYS = (
    "Rate how poignant or important a memory is to a person, on a scale of 1 to 10. "
    "Guidance: 1-2 = purely mundane routine (brushing teeth, tying shoes); "
    "4-6 = notable social news, plans, or invitations (a party, meeting someone new); "
    "8-10 = life-changing or emotional (a wedding, a breakup, learning of a death). "
    "Anything about an upcoming event or invitation is at least 6. "
    "Respond as JSON: {\"rating\": <int 1-10>}."
)


def heuristic_importance(text: str) -> float:
    """Cheap deterministic fallback used when no LLM is available (and in tests)."""
    cues = (
        "party", "fiesta", "wedding", "boda", "death", "muerte", "love", "amor",
        "fight", "pelea", "secret", "secreto", "fire", "incendio", "invite", "invita",
    )
    t = text.lower()
    base = 3.0
    base += sum(1.5 for c in cues if c in t)
    return float(min(10.0, max(1.0, base)))


def score_importance(text: str, llm=None) -> float:
    if llm is None or not hasattr(llm, "generate_json"):
        return heuristic_importance(text)
    try:
        data = llm.generate_json(
            f"Memory: {text}\nHow important (1-10)?", system=_IMPORTANCE_SYS
        )
        rating = float(data.get("rating", heuristic_importance(text)))
        return float(min(10.0, max(1.0, rating)))
    except Exception:  # noqa: BLE001 - never let scoring crash ingestion
        return heuristic_importance(text)


# --------------------------------------------------------------------------- #
# Per-agent memory stream
# --------------------------------------------------------------------------- #
class MemoryStream:
    def __init__(self, agent_id: str, store: MemoryStore, llm, cfg: Config = DEFAULT):
        self.agent_id = agent_id
        self.store = store
        self.llm = llm
        self.cfg = cfg
        # Tracks importance accumulated since the last reflection (trigger).
        self.importance_since_reflection: float = 0.0

    def add(
        self,
        text: str,
        tick: int,
        *,
        kind: str = "observation",
        importance: float | None = None,
        citations: list[int] | None = None,
    ) -> Memory:
        if importance is None:
            importance = score_importance(text, self.llm)
        emb = self.llm.embed(text) if self.llm is not None else None
        m = Memory(
            agent_id=self.agent_id,
            kind=kind,
            text=text,
            created_tick=tick,
            last_access_tick=tick,
            importance=importance,
            embedding=emb,
            citations=citations or [],
        )
        self.store.add(m)
        self.importance_since_reflection += importance
        return m

    def all(self) -> list[Memory]:
        return self.store.all_for(self.agent_id)

    def retrieve(self, query: str, tick: int, k: int | None = None) -> list[Memory]:
        mems = self.all()
        if not mems:
            return []
        q_emb = self.llm.embed(query)
        scored = score_memories(mems, q_emb, tick, self.cfg)
        k = k or self.cfg.retrieval.top_k
        top = [m for m, _ in scored[:k]]
        self.store.touch([m.id for m in top if m.id is not None], tick)
        return top
