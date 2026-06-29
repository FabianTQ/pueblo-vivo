"""Reusable village scenario, shared by the experiment and the server.

Keeps the cast, the map and the party constants in one place so the headless
experiment and the live server simulate the same world.
"""

from __future__ import annotations

from .agent import Agent
from .simulation import Simulation

HOST_ID = "maria"
PARTY_HOUR = 17
PARTY_LOCATION = "plaza"
PARTY_FACT = (
    "I, Maria, am throwing a party at the plaza this evening at 5pm and I want to "
    "invite everyone in the village to come."
)
FACT_KEYWORDS = [
    "party", "fiesta", "soiree", "soirée", "gathering", "celebration",
    "get-together", "invite", "invitation",
]

# id, name, traits, occupation, background, home
VILLAGERS = [
    ("maria", "Maria", "warm, sociable, generous", "innkeeper",
     "Runs the inn and loves bringing people together.", "home_maria"),
    ("diego", "Diego", "talkative, jovial, a gossip", "bartender",
     "Pours drinks at the tavern and knows everyone's business.", "home_diego"),
    ("lucia", "Lucia", "kind, hardworking, curious", "baker",
     "Bakes the village bread before dawn.", "home_lucia"),
    ("carlos", "Carlos", "quiet, reliable, a bit shy", "farmer",
     "Tends the fields outside the village.", "home_carlos"),
    ("sofia", "Sofia", "thoughtful, caring, well-liked", "teacher",
     "Teaches the village children at the school.", "home_sofia"),
    ("pedro", "Pedro", "shrewd, friendly, chatty", "merchant",
     "Sells goods at the market stall.", "home_pedro"),
    ("elena", "Elena", "cheerful, energetic, social", "gardener",
     "Keeps the village garden blooming.", "home_elena"),
]

HUBS = [
    ("plaza", "the central square where villagers gather"),
    ("tavern", "the lively tavern"),
    ("bakery", "the warm bakery"),
    ("market", "the busy market"),
    ("garden", "the village garden"),
    ("school", "the little schoolhouse"),
    ("well", "the old well"),
]


def build_village(sim: Simulation, n_agents: int = 5) -> None:
    for name, desc in HUBS:
        sim.world.add_location(name, desc)
    chosen = VILLAGERS[:n_agents]
    if all(v[0] != HOST_ID for v in chosen):
        chosen = [VILLAGERS[0], *chosen[:-1]]
    for aid, name, traits, occ, bg, home in chosen:
        sim.world.add_location(home, f"{name}'s home")
        sim.add_agent(Agent(aid, name, traits, occ, bg, home=home), home)
    sim.track_fact(FACT_KEYWORDS, PARTY_FACT)


def attendees(sim: Simulation) -> list[str]:
    """Agents whose plan puts them at the party location around party time."""
    party_tick = sim.world.clock.tick_for(PARTY_HOUR, 0)
    out = []
    for a in sim.agents.values():
        if any(
            s.location == PARTY_LOCATION and abs(s.start_tick - party_tick) <= 6
            for s in a.plan
        ):
            out.append(a.id)
    return out
