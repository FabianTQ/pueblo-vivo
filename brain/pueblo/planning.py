"""Daily planning and plan revision.

At the start of a day an agent drafts a coarse plan (a few timestamped activities
at locations). When something important happens (e.g. learning about a party) the
agent reconsiders and may insert new steps — this is what turns *knowing* a piece
of gossip into *acting* on it (the bridge to the acceptance criterion).
"""

from __future__ import annotations

from .agent import Agent, PlanStep
from .world import World

_PLAN_SYS = (
    "You are roleplaying a villager planning their day. "
    'Reply ONLY as JSON of this exact shape: {"schedule": ['
    '{"time": "HH:MM", "activity": "<short>", "location": "<one location name>"}, ...]}. '
    "Include 4 to 6 entries with increasing times. Use only the allowed locations. "
    "Villagers should spend time at shared places (plaza, tavern, market) where they meet others."
)


def _as_entry_list(data) -> list:
    """Coerce a model's JSON (object or array, any key) into a list of plan entries."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("schedule", "plan", "day", "activities", "entries", "items"):
            if isinstance(data.get(key), list):
                return data[key]
        for v in data.values():  # fall back to the first list value
            if isinstance(v, list):
                return v
    return []


def _coerce_location(name: str, world: World, fallback: str) -> str:
    if name in world.locations:
        return name
    # tolerant match: case-insensitive / substring
    low = name.lower().strip()
    for loc in world.locations:
        if loc.lower() == low or low in loc.lower() or loc.lower() in low:
            return loc
    return fallback


def generate_daily_plan(agent: Agent, world: World, tick: int, llm) -> list[PlanStep]:
    assert agent.memory is not None
    locs = ", ".join(world.locations)
    context_mems = agent.memory.retrieve(
        "my plans, intentions, routine, and important upcoming events", tick, k=8
    )
    context = "\n".join(f"- {m.text}" for m in context_mems) or "- (nothing notable)"
    prompt = (
        f"{agent.persona()}\n"
        f"Today is a new day. The time is {world.clock.hhmm()}.\n"
        f"Allowed locations: {locs}.\n"
        f"Things on your mind:\n{context}\n\n"
        "Plan your day."
    )
    data = llm.generate_json(prompt, system=_PLAN_SYS)
    steps: list[PlanStep] = []
    for entry in _as_entry_list(data):
        if not isinstance(entry, dict):
            continue
        try:
            hh, mm = str(entry["time"]).split(":")[:2]
            start = world.clock.tick_for(int(hh), int(mm))
            loc = _coerce_location(str(entry.get("location", agent.home)), world, agent.home)
            steps.append(PlanStep(start, str(entry["activity"]), loc))
        except (KeyError, ValueError, TypeError):
            continue
    steps.sort(key=lambda s: s.start_tick)
    agent.plan = steps
    if steps:
        plan_text = "Today's plan: " + "; ".join(
            f"{world.clock.cfg.day_start_hour:02d}+ {s.activity} @ {s.location}" for s in steps
        )
        agent.memory.add(plan_text, tick, kind="plan", importance=4)
    return steps


_RECONSIDER_SYS = (
    "You decide whether a villager changes their day plan after news. "
    'Reply ONLY as JSON: {"change": true|false, "new_steps": '
    '[{"time":"HH:MM","activity":"...","location":"..."}], "reason": "<short>"}.'
)


def reconsider_plan(agent: Agent, world: World, tick: int, trigger: str, llm) -> bool:
    """Given a salient new fact, possibly insert plan steps. Returns True if changed."""
    assert agent.memory is not None
    locs = ", ".join(world.locations)
    plan_text = "; ".join(f"{s.activity}@{s.location}" for s in agent.plan) or "(no plan yet)"
    prompt = (
        f"{agent.persona()}\n"
        f"Your current plan: {plan_text}\n"
        f"Allowed locations: {locs}\n"
        f"You just learned: \"{trigger}\"\n"
        "Would you change your plans to act on this (e.g. attend an event)? "
        "If yes, give the new steps to add."
    )
    data = llm.generate_json(prompt, system=_RECONSIDER_SYS)
    if not isinstance(data, dict) or not data.get("change"):
        return False
    added = 0
    for entry in data.get("new_steps", []) or []:
        try:
            hh, mm = str(entry["time"]).split(":")[:2]
            start = world.clock.tick_for(int(hh), int(mm))
            loc = _coerce_location(str(entry.get("location", agent.home)), world, agent.home)
            agent.plan.append(PlanStep(start, str(entry["activity"]), loc))
            added += 1
        except (KeyError, ValueError, TypeError):
            continue
    if added:
        agent.plan.sort(key=lambda s: s.start_tick)
        agent.memory.add(
            f"I changed my plans: {data.get('reason', trigger)}",
            tick,
            kind="plan",
            importance=6,
        )
        return True
    return False
