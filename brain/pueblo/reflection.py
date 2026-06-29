"""Reflection: periodically synthesising higher-level insights from raw memories.

When the importance accumulated since the last reflection crosses a threshold, the
agent asks itself the most salient questions about recent events, retrieves
supporting memories, and stores synthesised insights (with citations). This is what
grows opinions and relationships over time.
"""

from __future__ import annotations

from .agent import Agent
from .config import DEFAULT, Config
from .memory import Memory

_QUESTIONS_SYS = (
    "Given recent statements about/by a person, infer the most salient high-level "
    "questions we could answer about them or their world. "
    'Reply ONLY as JSON: {"questions": ["...", "..."]}.'
)

_INSIGHT_SYS = (
    "You synthesise high-level insights from statements. "
    'Reply ONLY as JSON: {"insights": [{"insight": "<one sentence>", "because": [<indices>]}]}. '
    "Indices refer to the numbered statements provided."
)


def should_reflect(agent: Agent, cfg: Config = DEFAULT) -> bool:
    assert agent.memory is not None
    return agent.memory.importance_since_reflection >= cfg.reflection.importance_threshold


def salient_questions(agent: Agent, tick: int, llm, cfg: Config = DEFAULT) -> list[str]:
    assert agent.memory is not None
    recent = agent.memory.all()[-30:]
    if not recent:
        return []
    listing = "\n".join(f"- {m.text}" for m in recent)
    data = llm.generate_json(
        f"Recent statements:\n{listing}\n\nGive {cfg.reflection.num_questions} questions.",
        system=_QUESTIONS_SYS,
    )
    qs = data.get("questions", []) if isinstance(data, dict) else []
    return [str(q) for q in qs][: cfg.reflection.num_questions]


def reflect(agent: Agent, tick: int, llm, cfg: Config = DEFAULT) -> list[Memory]:
    """Run one reflection cycle; returns the new reflection memories (may be empty)."""
    assert agent.memory is not None
    new_mems: list[Memory] = []
    for q in salient_questions(agent, tick, llm, cfg):
        evidence = agent.memory.retrieve(q, tick, k=cfg.reflection.retrieve_per_question)
        if not evidence:
            continue
        listing = "\n".join(f"[{i}] {m.text}" for i, m in enumerate(evidence))
        data = llm.generate_json(
            f"Question: {q}\nStatements:\n{listing}\n\nWhat do you infer?",
            system=_INSIGHT_SYS,
        )
        insights = data.get("insights", []) if isinstance(data, dict) else []
        for ins in insights:
            text = str(ins.get("insight", "")).strip()
            if not text:
                continue
            cites = []
            for idx in ins.get("because", []) or []:
                if isinstance(idx, int) and 0 <= idx < len(evidence) and evidence[idx].id:
                    cites.append(evidence[idx].id)
            m = agent.memory.add(text, tick, kind="reflection", importance=7, citations=cites)
            new_mems.append(m)
    # reset the trigger counter and stamp the time regardless of yield
    agent.memory.importance_since_reflection = 0.0
    agent.last_reflection_tick = tick
    return new_mems


def maybe_reflect(agent: Agent, tick: int, llm, cfg: Config = DEFAULT) -> list[Memory]:
    if should_reflect(agent, cfg):
        return reflect(agent, tick, llm, cfg)
    return []
