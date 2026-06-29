"""Tests for SimRunner controls (deterministic, no thread, RouterLLM).

The thread + RPC path is exercised live by the server integration; here we call the
on-sim-thread implementations directly so the tests stay deterministic.
"""

from __future__ import annotations

from conftest import RouterLLM

from pueblo.agent import Agent
from pueblo.runner import SimRunner
from pueblo.simulation import Simulation
from pueblo.world import World


def _runner():
    w = World()
    for loc in ("plaza", "home_a", "home_b"):
        w.add_location(loc)
    sim = Simulation(world=w, llm=RouterLLM(), seed=1)
    sim.add_agent(Agent("a", "Ana", "warm", "baker", "Bakes.", home="home_a"), "home_a")
    sim.add_agent(Agent("b", "Ben", "quiet", "farmer", "Grows.", home="home_b"), "home_b")
    sim.track_fact(["party"], "There is a party at the plaza on Saturday at 5pm.")
    events = []
    sim.on_event = events.append
    return SimRunner(sim), events


def test_snapshot_structure():
    r, _ = _runner()
    snap = r._snapshot_impl()
    assert snap["type"] == "snapshot"
    assert len(snap["agents"]) == 2
    assert any(loc["name"] == "plaza" for loc in snap["locations"])
    assert snap["paused"] is True


def test_inject_event_adds_memory_and_emits():
    r, events = _runner()
    r._inject_event_impl("a fire broke out at the market!", None, None)
    for aid in ("a", "b"):
        texts = [m.text for m in r.sim.agents[aid].memory.all()]
        assert any("fire" in t.lower() for t in texts)
    assert any(e["type"] == "event_injected" for e in events)


def test_inject_event_targets_location():
    r, _ = _runner()
    r.sim.world.place("a", "plaza")
    r.sim.world.place("b", "home_b")
    r._inject_event_impl("a parade!", "plaza", None)
    assert any("parade" in m.text.lower() for m in r.sim.agents["a"].memory.all())
    assert not any("parade" in m.text.lower() for m in r.sim.agents["b"].memory.all())


def test_player_say_produces_reply_and_can_spread_fact():
    r, events = _runner()
    r.player_say("a", "Hey Ana, there is a party at the plaza on Saturday!")
    r._drain_inputs()
    says = [e for e in events if e["type"] == "say"]
    assert any(e["agent"] == "player" and e["to"] == "a" for e in says)
    assert any(e["agent"] == "a" and e["to"] == "player" for e in says)
    # Ana now knows about the party and reconsidered her plan
    assert r.sim.knows_fact(r.sim.agents["a"])
    assert any(e["type"] == "replan" and e["agent"] == "a" for e in events)


def test_inspect_returns_mind_dump():
    r, _ = _runner()
    r.sim.plan_day()
    dump = r._inspect_impl("a")
    assert dump["type"] == "mind_dump"
    assert dump["name"] == "Ana"
    assert isinstance(dump["plan"], list)
    assert isinstance(dump["memories"], list)


def test_inspect_unknown_agent():
    r, _ = _runner()
    dump = r._inspect_impl("nobody")
    assert "error" in dump
