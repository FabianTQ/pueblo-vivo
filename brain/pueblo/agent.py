"""The Agent: identity + state + its memory stream.

Cognitive operations (planning, reflection, conversation) live in their own modules
and operate on an Agent; the Agent itself just holds data and a couple of helpers
for building persona text used in prompts.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import DEFAULT, Config
from .memory import MemoryStore, MemoryStream


@dataclass
class PlanStep:
    start_tick: int
    activity: str
    location: str


@dataclass
class Agent:
    id: str
    name: str
    traits: str  # e.g. "warm, gossipy, curious"
    occupation: str
    background: str  # a sentence or two of backstory
    home: str  # location name
    # runtime state
    plan: list[PlanStep] = field(default_factory=list)
    current_action: str = "idle"
    last_reflection_tick: int = 0
    # set after construction
    memory: MemoryStream | None = None

    def attach_memory(self, store: MemoryStore, llm, cfg: Config = DEFAULT) -> None:
        self.memory = MemoryStream(self.id, store, llm, cfg)

    def persona(self) -> str:
        return (
            f"{self.name} is a {self.occupation}. "
            f"Personality: {self.traits}. "
            f"Background: {self.background}"
        )

    def current_step(self, tick: int) -> PlanStep | None:
        """The active plan step for the given tick (latest step whose start <= tick)."""
        active = [s for s in self.plan if s.start_tick <= tick]
        return active[-1] if active else None
