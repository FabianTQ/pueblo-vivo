"""Live regression tests against a real Ollama (skipped by default).

Run with:  pytest -m live
Requires Ollama running with a chat model + nomic-embed-text.
"""

from __future__ import annotations

import pytest

from pueblo.agent import Agent
from pueblo.conversation import converse
from pueblo.llm import OllamaClient
from pueblo.memory import MemoryStore, score_importance
from pueblo.scenarios import FACT_KEYWORDS
from pueblo.world import World

pytestmark = pytest.mark.live


def _llm() -> OllamaClient:
    llm = OllamaClient()
    if not llm.is_up():
        pytest.skip("Ollama not reachable")
    return llm


def test_embeddings_and_importance_differentiate():
    llm = _llm()
    assert llm.embed("a party at the plaza").shape[0] > 0
    assert score_importance("There is a big party tonight!", llm) > score_importance(
        "I tied my shoes.", llm
    )


def test_fact_propagates_through_one_conversation():
    llm = _llm()
    world = World()
    world.add_location("tavern")
    store = MemoryStore(":memory:")
    a = Agent("maria", "Maria", "warm, sociable", "innkeeper", "Runs the inn.", home="tavern")
    b = Agent("diego", "Diego", "curious", "bartender", "Pours drinks.", home="tavern")
    for ag in (a, b):
        ag.attach_memory(store, llm)
        world.place(ag.id, "tavern")
    a.memory.add(
        "I am throwing a party at the plaza tonight at 5pm and want to invite everyone.",
        0, importance=9,
    )
    converse(a, b, world, 1, llm, max_turns=4)
    learned = any(
        any(k in m.text.lower() for k in FACT_KEYWORDS) for m in b.memory.all()
    )
    assert learned, "Diego should have learned about the party"
