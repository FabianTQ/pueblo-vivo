"""The world: locations, a simulated clock, and the agent registry.

Movement in the headless brain is abstract — an agent simply *is* at a location and
can set a destination it reaches on the next tick. Unity turns these location
changes into NavMesh walks; the brain doesn't care about geometry.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import DEFAULT, TimeConfig


@dataclass
class Location:
    name: str
    description: str = ""


class Clock:
    """Maps integer ticks to a human-readable simulated time of day."""

    def __init__(self, cfg: TimeConfig = DEFAULT.time, tick: int = 0):
        self.cfg = cfg
        self.tick = tick

    def advance(self, n: int = 1) -> None:
        self.tick += n

    @property
    def total_minutes(self) -> int:
        return self.cfg.day_start_hour * 60 + self.tick * self.cfg.minutes_per_tick

    @property
    def hour(self) -> int:
        return (self.total_minutes // 60) % 24

    @property
    def minute(self) -> int:
        return self.total_minutes % 60

    def hhmm(self) -> str:
        return f"{self.hour:02d}:{self.minute:02d}"

    def tick_for(self, hour: int, minute: int = 0) -> int:
        """The tick at which the clock shows the given wall time (same day)."""
        target = hour * 60 + minute
        start = self.cfg.day_start_hour * 60
        return (target - start) // self.cfg.minutes_per_tick

    def ticks_per_day(self) -> int:
        span = (self.cfg.day_end_hour - self.cfg.day_start_hour) * 60
        return span // self.cfg.minutes_per_tick


@dataclass
class World:
    locations: dict[str, Location] = field(default_factory=dict)
    clock: Clock = field(default_factory=Clock)
    # agent_id -> location name; filled by the simulation as agents are added.
    positions: dict[str, str] = field(default_factory=dict)

    def add_location(self, name: str, description: str = "") -> Location:
        loc = Location(name, description)
        self.locations[name] = loc
        return loc

    def place(self, agent_id: str, location: str) -> None:
        if location not in self.locations:
            raise KeyError(f"unknown location {location!r}")
        self.positions[agent_id] = location

    def location_of(self, agent_id: str) -> str | None:
        return self.positions.get(agent_id)

    def agents_at(self, location: str) -> list[str]:
        return sorted(a for a, loc in self.positions.items() if loc == location)

    def co_located_pairs(self) -> list[tuple[str, str]]:
        """All unordered pairs of agents sharing a location (sorted, deterministic)."""
        pairs: list[tuple[str, str]] = []
        by_loc: dict[str, list[str]] = {}
        for a, loc in self.positions.items():
            by_loc.setdefault(loc, []).append(a)
        for loc, members in by_loc.items():
            members.sort()
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    pairs.append((members[i], members[j]))
        return sorted(pairs)
