"""Tests for memory persistence and retrieval blending (uses FakeLLM)."""

from __future__ import annotations

import numpy as np

from pueblo.config import DEFAULT
from pueblo.memory import (
    Memory,
    MemoryStore,
    MemoryStream,
    cosine,
    heuristic_importance,
    score_memories,
)


def test_store_roundtrip_with_embedding():
    store = MemoryStore(":memory:")
    emb = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    m = Memory("ana", "observation", "saw a cat", 0, 0, 5.0, embedding=emb)
    mid = store.add(m)
    got = store.get(mid)
    assert got is not None
    assert got.text == "saw a cat"
    assert got.agent_id == "ana"
    np.testing.assert_allclose(got.embedding, emb)


def test_all_for_filters_by_agent():
    store = MemoryStore(":memory:")
    store.add(Memory("ana", "observation", "a", 0, 0, 1.0))
    store.add(Memory("ben", "observation", "b", 0, 0, 1.0))
    assert len(store.all_for("ana")) == 1
    assert len(store.all_for("ben")) == 1


def test_cosine_basic():
    a = np.array([1.0, 0.0])
    b = np.array([1.0, 0.0])
    c = np.array([0.0, 1.0])
    assert cosine(a, b) == 1.0
    assert abs(cosine(a, c)) < 1e-6


def test_heuristic_importance_detects_salient_words():
    assert heuristic_importance("brushing teeth") < heuristic_importance(
        "there will be a party with a secret"
    )


def test_retrieval_prefers_relevant(fake_llm):
    store = MemoryStore(":memory:")
    stream = MemoryStream("ana", store, fake_llm)
    stream.add("the weather is sunny today", tick=0, importance=5)
    stream.add("Maria is throwing a party on Saturday", tick=0, importance=5)
    stream.add("the bread at the bakery was fresh", tick=0, importance=5)
    top = stream.retrieve("tell me about the party", tick=1, k=1)
    assert len(top) == 1
    assert "party" in top[0].text


def test_retrieval_rewards_recency_when_relevance_ties(fake_llm):
    store = MemoryStore(":memory:")
    stream = MemoryStream("ana", store, fake_llm)
    old = stream.add("I went to the plaza", tick=0, importance=5)
    new = stream.add("I went to the plaza", tick=50, importance=5)
    top = stream.retrieve("the plaza", tick=50, k=1)
    assert top[0].id == new.id != old.id


def test_score_memories_empty():
    assert score_memories([], np.ones(4), 0, DEFAULT) == []


def test_add_tracks_importance_for_reflection(fake_llm):
    store = MemoryStore(":memory:")
    stream = MemoryStream("ana", store, fake_llm)
    stream.add("x", tick=0, importance=4)
    stream.add("y", tick=0, importance=6)
    assert stream.importance_since_reflection == 10
