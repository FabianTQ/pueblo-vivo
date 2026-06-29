"""The tick-based simulation loop — the serial "reasoning queue" of the headless brain.

Each tick: agents move to where their plan says they should be, co-located agents may
converse (this is where gossip flows), agents who learn something important may
reconsider their plans, and reflection fires when warranted. LLM work happens
serially, which mirrors the single-GPU reality (one inference at a time).

The simulation can optionally *track a fact* (by keyword): it records the
propagation graph (who told whom) and nudges newly-informed agents to reconsider
their plans — giving the gossip experiment its measurable edges and attendance.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .agent import Agent
from .config import DEFAULT, Config
from .conversation import ConversationResult, converse
from .memory import MemoryStore, cosine
from .planning import generate_daily_plan, reconsider_plan
from .reflection import maybe_reflect
from .world import World


@dataclass
class GossipEdge:
    src: str
    dst: str
    tick: int


@dataclass
class Simulation:
    world: World
    llm: object
    cfg: Config = DEFAULT
    seed: int = 0
    store: MemoryStore | None = None

    agents: dict[str, Agent] = field(default_factory=dict)
    fact_keywords: list[str] = field(default_factory=list)
    fact_text: str = ""
    gossip_edges: list[GossipEdge] = field(default_factory=list)
    conversations: list[ConversationResult] = field(default_factory=list)

    cooldown_ticks: int = 6
    max_convos_per_tick: int = 3
    convo_turns: int = 4  # turns per conversation (lower = faster, still transmits)
    fact_sim_threshold: float = 0.68  # semantic backup for fact detection
    on_event: object = None  # optional callable(dict) for event streaming

    def __post_init__(self) -> None:
        self.rng = random.Random(self.seed)
        if self.store is None:
            self.store = MemoryStore(self.cfg.db_path)
        self._last_talk: dict[tuple[str, str], int] = {}
        self._fact_emb = None

    # -- setup -------------------------------------------------------------
    def add_agent(self, agent: Agent, location: str) -> Agent:
        agent.attach_memory(self.store, self.llm, self.cfg)
        self.agents[agent.id] = agent
        self.world.place(agent.id, location)
        return agent

    def track_fact(self, keywords: list[str], text: str) -> None:
        self.fact_keywords = [k.lower() for k in keywords]
        self.fact_text = text
        try:
            self._fact_emb = self.llm.embed(text)
        except Exception:  # noqa: BLE001 - semantic backup is optional
            self._fact_emb = None

    def knows_fact(self, agent: Agent) -> bool:
        """True if any memory mentions the fact (keyword) or is semantically close.

        The semantic backup catches paraphrases (e.g. the model says "soiree" or
        "gathering" instead of "party") that keyword matching would miss.
        """
        if agent.memory is None:
            return False
        mems = agent.memory.all()
        if self.fact_keywords:
            for m in mems:
                low = m.text.lower()
                if any(kw in low for kw in self.fact_keywords):
                    return True
        if self._fact_emb is not None:
            for m in mems:
                if m.embedding is not None and cosine(self._fact_emb, m.embedding) >= self.fact_sim_threshold:
                    return True
        return False

    def seed_fact(self, agent_id: str, text: str, *, importance: float = 9.0) -> None:
        """Inject a fact straight into one agent's mind and let them reconsider."""
        a = self.agents[agent_id]
        assert a.memory is not None
        a.memory.add(text, self.world.clock.tick, kind="observation", importance=importance)
        reconsider_plan(a, self.world, self.world.clock.tick, text, self.llm)
        self.emit({"type": "seed", "agent": agent_id, "text": text, "tick": self.world.clock.tick})

    # -- daily planning ----------------------------------------------------
    def plan_day(self) -> None:
        for a in self.agents.values():
            generate_daily_plan(a, self.world, self.world.clock.tick, self.llm)
            self.emit({"type": "plan", "agent": a.id, "steps": len(a.plan)})

    # -- per-tick phases ---------------------------------------------------
    def _move(self) -> None:
        tick = self.world.clock.tick
        for a in self.agents.values():
            step = a.current_step(tick)
            loc = step.location if step else a.home
            if loc not in self.world.locations:
                continue
            a.current_action = step.activity if step else "at home"
            if self.world.location_of(a.id) != loc:
                self.world.place(a.id, loc)
                self.emit({"type": "move", "agent": a.id, "to": loc, "tick": tick})

    def _converse_round(self) -> None:
        tick = self.world.clock.tick
        pairs = self.world.co_located_pairs()
        eligible = [
            p for p in pairs if tick - self._last_talk.get(p, -9999) >= self.cooldown_ticks
        ]
        self.rng.shuffle(eligible)
        for (x, y) in eligible[: self.max_convos_per_tick]:
            a, b = self.agents[x], self.agents[y]
            knew = {x: self.knows_fact(a), y: self.knows_fact(b)}
            self.emit({"type": "talk_start", "a": x, "b": y, "loc": self.world.location_of(x), "tick": tick})
            res = converse(
                a, b, self.world, tick, self.llm,
                max_turns=self.convo_turns,
                on_utterance=lambda sid, oid, line: self.emit(
                    {"type": "say", "agent": sid, "to": oid, "text": line, "tick": tick}
                ),
            )
            self.conversations.append(res)
            self._last_talk[(x, y)] = tick
            self.emit({"type": "talk_end", "a": x, "b": y, "tick": tick})
            # detect propagation and let newly-informed agents reconsider
            for src, dst in ((x, y), (y, x)):
                if knew[src] and not knew[dst] and self.knows_fact(self.agents[dst]):
                    self.gossip_edges.append(GossipEdge(src, dst, tick))
                    self.emit({"type": "gossip", "src": src, "dst": dst, "tick": tick})
                    if self.fact_text:
                        changed = reconsider_plan(self.agents[dst], self.world, tick, self.fact_text, self.llm)
                        if changed:
                            self.emit({"type": "replan", "agent": dst, "tick": tick})

    def _reflect_round(self) -> None:
        tick = self.world.clock.tick
        for a in self.agents.values():
            new = maybe_reflect(a, tick, self.llm, self.cfg)
            if new:
                self.emit({"type": "reflect", "agent": a.id, "insights": len(new)})

    def step(self) -> None:
        self.emit({"type": "clock", "tick": self.world.clock.tick, "hhmm": self.world.clock.hhmm()})
        self._move()
        self._converse_round()
        self._reflect_round()
        self.world.clock.advance()

    def run(self, ticks: int) -> None:
        for _ in range(ticks):
            self.step()

    # -- helpers -----------------------------------------------------------
    def informed_agents(self) -> list[str]:
        return [a.id for a in self.agents.values() if self.knows_fact(a)]

    def emit(self, ev: dict) -> None:
        if callable(self.on_event):
            self.on_event(ev)


def format_event(ev: dict, names: dict | None = None) -> str:
    """Render a structured simulation event as a readable console line."""
    names = names or {}

    def nm(i):
        return names.get(i, i)

    t = ev.get("type")
    if t == "clock":
        return f"\n[{ev['hhmm']}] (tick {ev['tick']})"
    if t == "plan":
        return f"  [plan] {nm(ev['agent'])}: {ev['steps']} steps"
    if t == "seed":
        return f"  [seed] {nm(ev['agent'])} now knows: {ev['text']}"
    if t == "move":
        return f"  [move] {nm(ev['agent'])} -> {ev['to']}"
    if t == "talk_start":
        return f"  [talk] {nm(ev['a'])} <-> {nm(ev['b'])} @ {ev.get('loc')}"
    if t == "say":
        return f"      {nm(ev['agent'])}: {ev['text']}"
    if t == "gossip":
        return f"   >>> gossip spread: {nm(ev['src'])} -> {nm(ev['dst'])}"
    if t == "replan":
        return f"   *** {nm(ev['agent'])} changed plans to act on the news"
    if t == "reflect":
        return f"  [reflect] {nm(ev['agent'])}: {ev['insights']} insight(s)"
    return f"  [{t}] {ev}"
