"""The party experiment — the acceptance test for Pueblo Vivo.

Seed ONE agent (the host) with the fact that they are throwing a party, then run a
simulated day. Measure how the news spreads by word of mouth and how many villagers
re-plan to attend.

Run (from brain/, with the venv active and Ollama up):
    python -m experiments.party --agents 5 --ticks 72
    python -m experiments.party --model qwen2.5:7b      # higher quality
"""

from __future__ import annotations

import argparse
import sys

from pueblo.config import Config, LLMConfig
from pueblo.llm import OllamaClient
from pueblo.scenarios import (
    HOST_ID,
    PARTY_FACT,
    PARTY_HOUR,
    PARTY_LOCATION,
    attendees,
    build_village,
)
from pueblo.simulation import Simulation, format_event
from pueblo.world import Clock, World


def run(args) -> int:
    cfg = Config(llm=LLMConfig(chat_model=args.model)) if args.model else Config()
    llm = OllamaClient(cfg.llm)
    if not llm.is_up():
        print("ERROR: Ollama is not reachable at", cfg.llm.host, file=sys.stderr)
        return 2
    print(f"Ollama up. chat={cfg.llm.chat_model} embed={cfg.llm.embed_model}")
    print(f"Available models: {llm.available_models()}")

    world = World(clock=Clock(cfg.time))
    sim = Simulation(world=world, llm=llm, cfg=cfg, seed=args.seed)
    build_village(sim, args.agents)
    names = {a.id: a.name for a in sim.agents.values()}
    sim.on_event = lambda ev: print(format_event(ev, names))

    print("\n=== Planning the day ===")
    sim.plan_day()

    print(f"\n=== {sim.agents[HOST_ID].name} decides to throw a party ===")
    sim.seed_fact(HOST_ID, PARTY_FACT)

    print(f"\n=== Running {args.ticks} ticks ({world.clock.cfg.minutes_per_tick} min each) ===")
    sim.run(args.ticks)

    informed = sim.informed_agents()
    by_chain = [a for a in informed if a != HOST_ID]
    going = attendees(sim)
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Villagers: {len(sim.agents)}")
    print(f"Informed about the party: {len(informed)}/{len(sim.agents)} -> {sorted(informed)}")
    print(f"  ...by word of mouth (not the host): {len(by_chain)} -> {sorted(by_chain)}")
    print(f"Plan to attend (at {PARTY_LOCATION} ~{PARTY_HOUR}:00): {len(going)} -> {sorted(going)}")
    print("\nPropagation path (who told whom):")
    for e in sim.gossip_edges:
        print(f"  {names[e.src]} -> {names[e.dst]}  (tick {e.tick})")
    print(f"\nConversations held: {len(sim.conversations)}")

    need_informed = max(2, (len(sim.agents) - 1) // 2)
    need_going = max(1, (len(sim.agents) - 1) // 3)
    ok = len(by_chain) >= need_informed and len(going) >= need_going
    print("\nACCEPTANCE:",
          f"chain>={need_informed} (got {len(by_chain)}),",
          f"attend>={need_going} (got {len(going)}) ->",
          "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    p = argparse.ArgumentParser(description="Pueblo Vivo party (gossip) experiment")
    p.add_argument("--agents", type=int, default=5)
    p.add_argument("--ticks", type=int, default=72)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--model", type=str, default=None, help="override chat model (e.g. qwen2.5:7b)")
    return run(p.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
