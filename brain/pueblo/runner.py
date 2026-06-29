"""SimRunner — drives a Simulation on a background thread with live controls.

This is the bridge between the synchronous cognitive core and the async server. The
sim loop runs in its own thread (LLM calls block, which is fine there). Control
methods (pause, speed, inject, player_say, inspect) are thread-safe. Player input is
drained every loop iteration *before* the next step, giving it priority over the
ambient NPC-to-NPC chatter — exactly the responsiveness the design calls for.
"""

from __future__ import annotations

import threading
import time

from .conversation import player_dialogue
from .planning import reconsider_plan
from .simulation import Simulation


class SimRunner:
    def __init__(self, sim: Simulation, max_ticks: int | None = None, speed: float = 2.0):
        self.sim = sim
        self.max_ticks = max_ticks
        self.speed = speed  # ticks per real second while running
        self.paused = True
        self._stop = False
        self._lock = threading.Lock()
        self._player_inputs: list[tuple[str, str]] = []
        self._commands: list[tuple] = []  # (fn, holder) run on the sim thread
        self._thread: threading.Thread | None = None
        self._planned = False

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="sim", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop = True

    def _loop(self) -> None:
        self.plan_day()
        while not self._stop:
            self._drain_inputs()
            self._drain_commands()
            if self.paused:
                time.sleep(0.05)
                continue
            if self.max_ticks is not None and self.sim.world.clock.tick >= self.max_ticks:
                self.paused = True
                self.sim.emit({"type": "day_over", "tick": self.sim.world.clock.tick})
                continue
            self.sim.step()
            time.sleep(1.0 / max(self.speed, 0.01))

    # -- one-time setup ----------------------------------------------------
    def plan_day(self) -> None:
        if not self._planned:
            self.sim.plan_day()
            self._planned = True

    # -- controls ----------------------------------------------------------
    def set_paused(self, paused: bool) -> None:
        self.paused = paused

    def set_speed(self, speed: float) -> None:
        self.speed = max(0.05, float(speed))

    def player_say(self, agent_id: str, text: str) -> None:
        if agent_id not in self.sim.agents:
            return
        with self._lock:
            self._player_inputs.append((agent_id, text))

    def _drain_inputs(self) -> None:
        with self._lock:
            items = self._player_inputs
            self._player_inputs = []
        tick = self.sim.world.clock.tick
        for agent_id, text in items:
            agent = self.sim.agents.get(agent_id)
            if agent is None:
                continue
            self.sim.emit({"type": "say", "agent": "player", "to": agent_id, "text": text, "tick": tick})
            try:
                reply = player_dialogue(agent, text, self.sim.world, tick, self.sim.llm)
            except Exception as e:  # noqa: BLE001 - keep the loop alive
                reply = f"(...{agent.name} is speechless: {e})"
            self.sim.emit({"type": "say", "agent": agent_id, "to": "player", "text": reply, "tick": tick})
            # If the player told them about the tracked fact, let them reconsider.
            if self.sim.fact_text and self.sim.knows_fact(agent):
                if reconsider_plan(agent, self.sim.world, tick, self.sim.fact_text, self.sim.llm):
                    self.sim.emit({"type": "replan", "agent": agent_id, "tick": tick})

    # -- thread-safe command execution ------------------------------------
    def execute_sync(self, fn, timeout: float = 60.0):
        """Run fn(self) on the sim thread and return its result (blocks the caller).

        Used so reads/writes of sim + SQLite state never race the sim thread. The
        server calls these via a thread pool so the async loop is never blocked.
        """
        holder = {"event": threading.Event(), "result": None, "error": None}
        with self._lock:
            self._commands.append((fn, holder))
        if not holder["event"].wait(timeout):
            raise TimeoutError("sim command timed out")
        if holder["error"] is not None:
            raise holder["error"]
        return holder["result"]

    def _drain_commands(self) -> None:
        with self._lock:
            cmds = self._commands
            self._commands = []
        for fn, holder in cmds:
            try:
                holder["result"] = fn(self)
            except Exception as e:  # noqa: BLE001 - surfaced to the caller
                holder["error"] = e
            finally:
                holder["event"].set()

    # -- event injection ---------------------------------------------------
    def inject_event(self, text: str, location: str | None = None, agents: list[str] | None = None) -> None:
        self.execute_sync(lambda r: r._inject_event_impl(text, location, agents))

    def _inject_event_impl(self, text: str, location, agents) -> None:
        tick = self.sim.world.clock.tick
        if agents:
            targets = [self.sim.agents[a] for a in agents if a in self.sim.agents]
        elif location:
            targets = [self.sim.agents[a] for a in self.sim.world.agents_at(location)]
        else:
            targets = list(self.sim.agents.values())
        for a in targets:
            if a.memory is not None:
                a.memory.add(f"I noticed: {text}", tick, kind="observation")
        self.sim.emit({"type": "event_injected", "text": text, "targets": [a.id for a in targets], "tick": tick})

    # -- introspection -----------------------------------------------------
    def inspect(self, agent_id: str) -> dict:
        return self.execute_sync(lambda r: r._inspect_impl(agent_id))

    def _inspect_impl(self, agent_id: str) -> dict:
        a = self.sim.agents.get(agent_id)
        if a is None or a.memory is None:
            return {"type": "mind_dump", "agent": agent_id, "error": "unknown agent"}
        mems = a.memory.all()
        return {
            "type": "mind_dump",
            "agent": a.id,
            "name": a.name,
            "occupation": a.occupation,
            "location": self.sim.world.location_of(a.id),
            "action": a.current_action,
            "plan": [
                {"start_tick": s.start_tick, "activity": s.activity, "location": s.location}
                for s in a.plan
            ],
            "reflections": [m.text for m in mems if m.kind == "reflection"][-8:],
            "memories": [
                {"text": m.text, "kind": m.kind, "importance": m.importance, "tick": m.created_tick}
                for m in mems[-15:]
            ],
            "knows_tracked_fact": self.sim.knows_fact(a),
        }

    def snapshot(self) -> dict:
        return self.execute_sync(lambda r: r._snapshot_impl())

    def _snapshot_impl(self) -> dict:
        return {
            "type": "snapshot",
            "clock": {"tick": self.sim.world.clock.tick, "hhmm": self.sim.world.clock.hhmm()},
            "paused": self.paused,
            "speed": self.speed,
            "locations": [
                {"name": loc.name, "description": loc.description}
                for loc in self.sim.world.locations.values()
            ],
            "agents": [
                {
                    "id": a.id,
                    "name": a.name,
                    "occupation": a.occupation,
                    "location": self.sim.world.location_of(a.id),
                    "action": a.current_action,
                }
                for a in self.sim.agents.values()
            ],
        }
