"""Shared test fixtures, incl. a deterministic FakeLLM so the cognitive core can be
tested without a running Ollama server.

FakeLLM.embed gives words stable random vectors and sums them, so texts that share
vocabulary get higher cosine similarity — enough to exercise relevance ranking.
FakeLLM.chat / generate_json can be scripted with queued responses.
"""

from __future__ import annotations

import hashlib
import re

import numpy as np
import pytest


class FakeLLM:
    def __init__(self, dim: int = 64, chat_script=None, json_script=None):
        self.dim = dim
        self.chat_script = list(chat_script or [])
        self.json_script = list(json_script or [])
        self.calls: list[tuple[str, str]] = []

    # deterministic semantic-ish embedding
    def _word_vec(self, word: str) -> np.ndarray:
        h = hashlib.sha256(word.encode()).digest()
        seed = int.from_bytes(h[:8], "little")
        rng = np.random.default_rng(seed)
        return rng.standard_normal(self.dim).astype(np.float32)

    # Common English/Spanish function words are dropped so that the fake
    # embedding reflects *content* similarity (a stand-in for real semantics).
    STOPWORDS = frozenset(
        "the a an is are was were on at in of to me about tell today and or i you it "
        "this that with for there will be el la los las un una es en de y o sobre hoy "
        "se va al".split()
    )

    def embed(self, text: str, **kw) -> np.ndarray:
        words = [
            w for w in re.findall(r"[a-záéíóúñ]+", text.lower()) if w not in self.STOPWORDS
        ]
        if not words:
            return np.ones(self.dim, dtype=np.float32)
        v = np.sum([self._word_vec(w) for w in words], axis=0)
        n = np.linalg.norm(v)
        return (v / n).astype(np.float32) if n else v

    def chat(self, messages, *, system=None, fmt=None, temperature=None, model=None) -> str:
        self.calls.append(("chat", messages[-1]["content"] if messages else ""))
        if self.chat_script:
            return self.chat_script.pop(0)
        return "ok"

    def complete(self, prompt, *, system=None, **kw) -> str:
        return self.chat([{"role": "user", "content": prompt}], system=system, **kw)

    def generate_json(self, prompt, *, system=None, temperature=None, model=None):
        self.calls.append(("json", prompt))
        if self.json_script:
            return self.json_script.pop(0)
        # default: an importance rating
        return {"rating": 5}


class RouterLLM(FakeLLM):
    """Routes JSON/text responses by inspecting the system prompt.

    Deterministic stand-in for a real model that makes the simulation mechanics
    exercisable: plans put agents at the plaza, conversations mention the party, and
    summaries transmit it.
    """

    def complete(self, prompt, *, system=None, **kw):
        return "Hey, did you hear there's a party at the plaza on Saturday?"

    def generate_json(self, prompt, *, system=None, **kw):
        s = (system or "").lower()
        if "scale of 1 to 10" in s:
            return {"rating": 5}
        if "planning their day" in s:
            return [{"time": "09:00", "activity": "hang out", "location": "plaza"}]
        if "changes their day plan" in s:
            return {
                "change": True,
                "new_steps": [{"time": "17:00", "activity": "go to the party", "location": "plaza"}],
                "reason": "there is a party",
            }
        if "summarise a conversation" in s:
            return {"learned": ["there is a party at the plaza on Saturday"], "summary": "We chatted."}
        if "salient high-level" in s:
            return {"questions": []}
        if "synthesise high-level" in s:
            return {"insights": []}
        return {}


@pytest.fixture
def fake_llm():
    return FakeLLM()


@pytest.fixture
def router_llm():
    return RouterLLM()
