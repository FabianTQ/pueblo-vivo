"""Protocol-dispatch tests for the server's message handler (no network, no LLM)."""

from __future__ import annotations

import pueblo.server as server


class StubWS:
    def __init__(self):
        self.sent = []

    async def send_json(self, d):
        self.sent.append(d)


class StubSim:
    def __init__(self):
        self.stepped = 0

    def step(self):
        self.stepped += 1


class StubRunner:
    def __init__(self):
        self.calls = []
        self.sim = StubSim()

    def set_paused(self, b):
        self.calls.append(("paused", b))

    def set_speed(self, s):
        self.calls.append(("speed", s))

    def player_say(self, a, t):
        self.calls.append(("say", a, t))

    def inject_event(self, t, location=None, agents=None):
        self.calls.append(("inject", t, location, agents))

    def inspect(self, a):
        return {"type": "mind_dump", "agent": a}

    def snapshot(self):
        return {"type": "snapshot"}

    def execute_sync(self, fn, timeout: float = 60.0):
        return fn(self)


def _setup():
    runner = StubRunner()
    server.hub.runner = runner
    return runner, StubWS()


async def test_time_control_pause_resume_speed():
    r, ws = _setup()
    await server._handle({"type": "time_control", "action": "pause"}, ws)
    await server._handle({"type": "time_control", "action": "resume"}, ws)
    await server._handle({"type": "time_control", "action": "speed", "speed": 5}, ws)
    assert ("paused", True) in r.calls
    assert ("paused", False) in r.calls
    assert ("speed", 5.0) in r.calls


async def test_time_control_step():
    r, ws = _setup()
    await server._handle({"type": "time_control", "action": "step"}, ws)
    assert r.sim.stepped == 1


async def test_player_say_dispatch():
    r, ws = _setup()
    await server._handle({"type": "player_say", "agent": "maria", "text": "hi"}, ws)
    assert ("say", "maria", "hi") in r.calls


async def test_inject_event_dispatch():
    r, ws = _setup()
    await server._handle({"type": "inject_event", "text": "fire!", "location": "plaza"}, ws)
    assert ("inject", "fire!", "plaza", None) in r.calls


async def test_inspect_returns_dump_to_ws():
    r, ws = _setup()
    await server._handle({"type": "inspect", "agent": "diego"}, ws)
    assert ws.sent and ws.sent[-1] == {"type": "mind_dump", "agent": "diego"}


async def test_snapshot_returns_to_ws():
    r, ws = _setup()
    await server._handle({"type": "snapshot"}, ws)
    assert ws.sent[-1] == {"type": "snapshot"}


async def test_set_mode_acks():
    r, ws = _setup()
    await server._handle({"type": "set_mode", "mode": "director"}, ws)
    assert ws.sent[-1] == {"type": "mode_set", "mode": "director"}
