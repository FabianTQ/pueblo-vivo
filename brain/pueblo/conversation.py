"""Conversation between two agents (or an agent and the player).

This is the transmission channel for gossip. Each turn, the speaker retrieves what's
most on their mind (recent news, plans, relationship to the other) and produces a
line in character; they are nudged to share interesting news. After the dialogue,
each participant stores a first-person summary that explicitly captures any *new
information learned* — so a fact heard here re-enters that agent's memory and can be
passed on later.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .agent import Agent
from .memory import score_importance
from .world import World

MAX_TURNS = 6


@dataclass
class ConversationResult:
    participants: tuple[str, str]
    transcript: list[tuple[str, str]] = field(default_factory=list)  # (agent_id, line)
    summaries: dict[str, str] = field(default_factory=dict)  # agent_id -> summary


_UTTER_SYS = (
    "You roleplay a villager in a short, natural conversation. Speak in first person, "
    "ONE or TWO sentences only. Stay in character. Do not narrate actions.\n"
    "IMPORTANT: if you know about an upcoming event, an invitation, or a piece of news, "
    "mention it CLEARLY and SPECIFICALLY in your line — say exactly what it is, where, and "
    "when (e.g. 'there's a party at the plaza tonight at 5'). Don't be vague or coy about it; "
    "villagers love sharing news."
)

_SUMMARY_SYS = (
    "Summarise a conversation from one participant's point of view. "
    'Reply ONLY as JSON: {"learned": ["<new fact or piece of news>", ...], '
    '"summary": "<one first-person sentence>"}. '
    "Put any events, invitations, plans, or gossip you heard into \"learned\"."
)


def _utterance(
    speaker: Agent, other: Agent, transcript, name_of: dict, world: World, tick: int, llm
) -> str:
    assert speaker.memory is not None
    q = f"what to say to {other.name}: recent news, gossip, plans, our relationship"
    mems = speaker.memory.retrieve(q, tick, k=6)
    on_mind = "\n".join(f"- {m.text}" for m in mems) or "- (nothing in particular)"
    # Surface the single most important thing on the speaker's mind so the model
    # grounds its line in real memory instead of inventing — the key to faithful
    # gossip propagation. Only nudge when it's genuinely newsworthy (importance>=6).
    news = max(mems, key=lambda m: m.importance, default=None)
    news_line = ""
    if news is not None and news.importance >= 6:
        news_line = (
            f"\nThe most important thing on your mind is: \"{news.text}\" — "
            f"if it is news or an invitation and hasn't been said yet, tell {other.name} "
            f"about it clearly (what, where, when)."
        )
    convo = "\n".join(
        f"{name_of[sid]}: {line}" for sid, line in transcript
    ) or "(the conversation is just starting)"
    prompt = (
        f"{speaker.persona()}\n"
        f"You are talking with {other.name} at {world.location_of(speaker.id)}. "
        f"It is {world.clock.hhmm()}.\n"
        f"On your mind:\n{on_mind}{news_line}\n\n"
        f"Conversation so far:\n{convo}\n\n"
        f"What does {speaker.name} say next?"
    )
    line = llm.complete(prompt, system=_UTTER_SYS, temperature=0.6).strip()
    # keep it tidy: strip a leading "Name:" if the model added one
    if line.lower().startswith(speaker.name.lower() + ":"):
        line = line[len(speaker.name) + 1 :].strip()
    return line


def _summarize(agent: Agent, other: Agent, transcript, name_of: dict, tick: int, llm) -> str:
    convo = "\n".join(f"{name_of[sid]}: {line}" for sid, line in transcript)
    data = llm.generate_json(
        f"You are {agent.name}. Conversation with {other.name}:\n{convo}",
        system=_SUMMARY_SYS,
    )
    learned, summary = [], ""
    if isinstance(data, dict):
        learned = [str(x) for x in (data.get("learned") or [])]
        summary = str(data.get("summary", "")).strip()
    parts = []
    if summary:
        parts.append(summary)
    for fact in learned:
        parts.append(f"I heard from {other.name} that {fact}")
    return " ".join(parts) or f"I chatted with {other.name}."


def converse(
    a: Agent,
    b: Agent,
    world: World,
    tick: int,
    llm,
    max_turns: int = MAX_TURNS,
    on_utterance=None,
) -> ConversationResult:
    """Run a short dialogue and write a summary memory into BOTH agents.

    `on_utterance(speaker_id, other_id, line)` is called per turn (live streaming for
    the server); it's optional so the headless path stays simple.
    """
    assert a.memory is not None and b.memory is not None
    result = ConversationResult(participants=(a.id, b.id))
    name_of = {a.id: a.name, b.id: b.name}
    speakers = [a, b]
    for turn in range(max_turns):
        sp = speakers[turn % 2]
        ot = speakers[(turn + 1) % 2]
        line = _utterance(sp, ot, result.transcript, name_of, world, tick, llm)
        result.transcript.append((sp.id, line))
        if callable(on_utterance):
            on_utterance(sp.id, ot.id, line)
        if _is_farewell(line):
            break
    for ag, ot in ((a, b), (b, a)):
        summary = _summarize(ag, ot, result.transcript, name_of, tick, llm)
        result.summaries[ag.id] = summary
        ag.memory.add(summary, tick, kind="conversation", importance=score_importance(summary))
    return result


def player_dialogue(
    agent: Agent, player_text: str, world: World, tick: int, llm, player_name: str = "the traveler"
) -> str:
    """A single exchange between the player and one agent (priority path).

    The agent observes what the player said, replies in character, and remembers
    both — so anything the player tells them (e.g. about the party) enters the
    gossip network just like any other observation.
    """
    assert agent.memory is not None
    agent.memory.add(
        f'{player_name} said to me: "{player_text}"', tick, kind="conversation"
    )
    mems = agent.memory.retrieve(player_text, tick, k=6)
    on_mind = "\n".join(f"- {m.text}" for m in mems) or "- (nothing in particular)"
    prompt = (
        f"{agent.persona()}\n"
        f"You are at {world.location_of(agent.id)}. It is {world.clock.hhmm()}.\n"
        f"On your mind:\n{on_mind}\n\n"
        f'{player_name} says to you: "{player_text}"\n'
        f"How does {agent.name} reply?"
    )
    reply = llm.complete(prompt, system=_UTTER_SYS, temperature=0.85).strip()
    if reply.lower().startswith(agent.name.lower() + ":"):
        reply = reply[len(agent.name) + 1 :].strip()
    agent.memory.add(f'I told {player_name}: "{reply}"', tick, kind="conversation", importance=3)
    return reply


_FAREWELLS = ("bye", "goodbye", "see you", "adiós", "adios", "hasta luego", "nos vemos")


def _is_farewell(line: str) -> bool:
    low = line.lower()
    return any(f in low for f in _FAREWELLS)
