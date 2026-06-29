"""Quick probe: what does the model return for a daily plan, and how many steps parse?"""

from __future__ import annotations

import json
import sys

from pueblo.config import Config, LLMConfig
from pueblo.llm import OllamaClient
from pueblo.planning import _PLAN_SYS
from pueblo.scenarios import build_village
from pueblo.simulation import Simulation
from pueblo.world import Clock, World


def main() -> int:
    model = sys.argv[1] if len(sys.argv) > 1 else None
    cfg = Config(llm=LLMConfig(chat_model=model)) if model else Config()
    llm = OllamaClient(cfg.llm)

    raw = llm.generate_json(
        "Allowed locations: plaza, tavern, bakery, market.\nThings on your mind:\n- (nothing)\n\nPlan your day.",
        system=_PLAN_SYS,
    )
    print("RAW PLAN JSON:", json.dumps(raw)[:600])

    sim = Simulation(world=World(clock=Clock(cfg.time)), llm=llm, cfg=cfg)
    build_village(sim, 3)
    sim.plan_day()
    for a in sim.agents.values():
        print(f"{a.name}: {len(a.plan)} steps -> {[(s.start_tick, s.activity, s.location) for s in a.plan]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
