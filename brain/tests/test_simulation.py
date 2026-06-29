"""Mechanics tests for the simulation loop using a deterministic routing fake LLM.

These validate orchestration — movement, co-location, gossip-edge detection and
plan reconsideration — independently of whether a real model is faithful. The live
faithfulness of propagation is checked separately by the party experiment.
"""

from __future__ import annotations

from conftest import RouterLLM

from pueblo.agent import Agent
from pueblo.simulation import Simulation
from pueblo.world import World


def _world() -> World:
    w = World()
    w.add_location("plaza", "the central square")
    w.add_location("home_a", "Ana's house")
    w.add_location("home_b", "Ben's house")
    return w


def _sim() -> Simulation:
    w = _world()
    sim = Simulation(world=w, llm=RouterLLM(), seed=1)
    sim.add_agent(Agent("a", "Ana", "warm, chatty", "baker", "Bakes bread.", home="home_a"), "home_a")
    sim.add_agent(Agent("b", "Ben", "quiet, curious", "farmer", "Grows wheat.", home="home_b"), "home_b")
    sim.track_fact(["party"], "There is a party at the plaza on Saturday at 5pm.")
    return sim


def test_agents_move_to_planned_location():
    sim = _sim()
    sim.plan_day()  # both plan to be at plaza at 09:00 (tick 12)
    sim.world.clock.tick = 12
    sim._move()
    assert sim.world.location_of("a") == "plaza"
    assert sim.world.location_of("b") == "plaza"


def test_agents_at_home_before_plan_starts():
    sim = _sim()
    sim.plan_day()
    sim.world.clock.tick = 0
    sim._move()
    assert sim.world.location_of("a") == "home_a"


def test_gossip_spreads_and_triggers_replan():
    sim = _sim()
    sim.plan_day()
    sim.seed_fact("a", "There is a party at the plaza on Saturday at 5pm.")
    assert sim.knows_fact(sim.agents["a"]) is True
    assert sim.knows_fact(sim.agents["b"]) is False
    # run past 09:00 so both reach the plaza and converse
    sim.run(16)
    assert sim.knows_fact(sim.agents["b"]) is True, "Ben should have learned about the party"
    assert any(e.src == "a" and e.dst == "b" for e in sim.gossip_edges)
    # Ben reconsidered and now plans to be at the plaza for the party (tick ~60)
    party_tick = sim.world.clock.tick_for(17, 0)
    assert any(
        s.location == "plaza" and abs(s.start_tick - party_tick) <= 6 for s in sim.agents["b"].plan
    )


def test_no_self_edge_and_direction_correct():
    sim = _sim()
    sim.plan_day()
    sim.seed_fact("a", "There is a party at the plaza on Saturday at 5pm.")
    sim.run(16)
    # the only edge should be a -> b, never b -> a (b didn't know first)
    assert all(e.src == "a" and e.dst == "b" for e in sim.gossip_edges)


def test_conversation_cooldown_limits_repeat_talk():
    sim = _sim()
    sim.plan_day()
    sim.world.clock.tick = 12
    # force both to plaza and converse twice across ticks within cooldown
    sim._move()
    sim._converse_round()
    n_after_first = len(sim.conversations)
    sim.world.clock.advance()
    sim._move()
    sim._converse_round()  # within cooldown -> no new conversation
    assert len(sim.conversations) == n_after_first
