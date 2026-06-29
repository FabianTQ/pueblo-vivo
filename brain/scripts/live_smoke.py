"""Minimal live check against a real Ollama: does a fact carry through one
conversation (utterance -> summary -> listener's memory)?

Run from brain/ with the venv and Ollama up:
    python -m scripts.live_smoke
    python -m scripts.live_smoke qwen2.5:7b
"""

from __future__ import annotations

import sys

from pueblo.agent import Agent
from pueblo.config import Config, LLMConfig
from pueblo.conversation import converse
from pueblo.llm import OllamaClient
from pueblo.memory import MemoryStore, score_importance
from pueblo.scenarios import FACT_KEYWORDS
from pueblo.world import World


def main() -> int:
    model = sys.argv[1] if len(sys.argv) > 1 else None
    cfg = Config(llm=LLMConfig(chat_model=model)) if model else Config()
    llm = OllamaClient(cfg.llm)
    print(f"chat={cfg.llm.chat_model} embed={cfg.llm.embed_model}")
    if not llm.is_up():
        print("Ollama not reachable", file=sys.stderr)
        return 2

    # 1) embeddings + importance sanity
    emb = llm.embed("a party at the plaza")
    print(f"embedding dim = {emb.shape[0]}")
    imp_party = score_importance("There is a big party tonight!", llm)
    imp_mundane = score_importance("I tied my shoes.", llm)
    print(f"importance: party={imp_party:.1f}  mundane={imp_mundane:.1f}")

    # 2) one conversation transmits a seeded fact
    world = World()
    world.add_location("tavern", "the lively tavern")
    store = MemoryStore(":memory:")
    maria = Agent("maria", "Maria", "warm, sociable", "innkeeper", "Runs the inn.", home="tavern")
    diego = Agent("diego", "Diego", "talkative, curious", "bartender", "Pours drinks.", home="tavern")
    for a in (maria, diego):
        a.attach_memory(store, llm, cfg)
        world.place(a.id, "tavern")
    maria.memory.add(
        "I am throwing a party at the plaza tonight at 5pm and want to invite everyone.",
        tick=0, kind="observation", importance=9,
    )

    print("\n--- conversation ---")
    res = converse(maria, diego, world, tick=1, llm=llm, max_turns=4)
    for sid, line in res.transcript:
        print(f"  {sid}: {line}")
    print("\n--- summaries ---")
    for aid, s in res.summaries.items():
        print(f"  {aid}: {s}")

    diego_knows = any(
        any(w in m.text.lower() for w in FACT_KEYWORDS) for m in diego.memory.all()
    )
    print(f"\nDiego learned about the party: {diego_knows}")
    return 0 if (diego_knows and imp_party > imp_mundane) else 1


if __name__ == "__main__":
    raise SystemExit(main())
