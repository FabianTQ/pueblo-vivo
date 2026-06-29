"""FastAPI + WebSocket server — the live bridge between the brain and a Unity client.

The simulation runs on its own thread (see SimRunner). This server:
- streams every structured sim event to all connected clients over /ws, and
- accepts control/input messages from clients (time control, player_say,
  inject_event, inspect, snapshot).

Run (from brain/, venv active, Ollama up):
    uvicorn pueblo.server:app --host 127.0.0.1 --port 8765
    python -m pueblo.server            # convenience launcher
"""

from __future__ import annotations

import asyncio
import base64
import os
import queue

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from . import voice as voicemod
from .config import Config, LLMConfig
from .llm import OllamaClient
from .runner import SimRunner
from .scenarios import HOST_ID, PARTY_FACT, build_village
from .simulation import Simulation
from .world import Clock, World


class Hub:
    def __init__(self) -> None:
        self.event_q: queue.Queue = queue.Queue()
        self.clients: set[WebSocket] = set()
        self.runner: SimRunner | None = None


hub = Hub()


def build_runner(
    n_agents: int = 5, model: str | None = None, seed: int = 0,
    max_ticks: int | None = None, speed: float = 2.0, seed_party: bool = True,
) -> SimRunner:
    cfg = Config(llm=LLMConfig(chat_model=model)) if model else Config()
    sim = Simulation(world=World(clock=Clock(cfg.time)), llm=OllamaClient(cfg.llm), cfg=cfg, seed=seed)
    build_village(sim, n_agents)
    sim.on_event = hub.event_q.put  # thread-safe sink
    return SimRunner(
        sim, max_ticks=max_ticks, speed=speed,
        seed_agent=HOST_ID if seed_party else None,
        seed_text=PARTY_FACT if seed_party else None,
    )


def _drain_one(q: queue.Queue):
    try:
        return q.get(timeout=0.5)
    except queue.Empty:
        return None


async def _pump() -> None:
    """Forward sim events from the thread-safe queue to all websocket clients."""
    loop = asyncio.get_running_loop()
    while True:
        ev = await loop.run_in_executor(None, _drain_one, hub.event_q)
        if ev is None:
            continue
        for ws in list(hub.clients):
            try:
                await ws.send_json(ev)
            except Exception:  # noqa: BLE001 - drop dead clients
                hub.clients.discard(ws)


@asynccontextmanager
async def lifespan(app: FastAPI):
    n = int(os.environ.get("PUEBLO_AGENTS", "5"))
    model = os.environ.get("PUEBLO_CHAT_MODEL") or None
    mt = os.environ.get("PUEBLO_MAX_TICKS")
    seed_party = os.environ.get("PUEBLO_SEED_PARTY", "1") != "0"
    hub.runner = build_runner(
        n_agents=n, model=model, max_ticks=int(mt) if mt else None, seed_party=seed_party
    )
    hub.runner.start()
    pump = asyncio.create_task(_pump())
    try:
        yield
    finally:
        pump.cancel()
        if hub.runner:
            hub.runner.stop()


app = FastAPI(title="Pueblo Vivo brain", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    r = hub.runner
    return {
        "ok": True,
        "ollama": bool(r and r.sim.llm.is_up()),
        "agents": len(r.sim.agents) if r else 0,
        "tick": r.sim.world.clock.tick if r else 0,
    }


@app.get("/voice/health")
async def voice_health() -> dict:
    return voicemod.available()


@app.post("/tts")
async def tts(req: Request):
    """Text -> WAV audio (NPC speech). Returns raw audio/wav."""
    body = await req.json()
    text = str(body.get("text", "")).strip()
    if not text:
        return JSONResponse({"error": "no text"}, status_code=400)
    try:
        wav = await asyncio.get_running_loop().run_in_executor(None, voicemod.tts_to_wav, text)
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": f"tts unavailable: {e}"}, status_code=503)
    return Response(content=wav, media_type="audio/wav")


@app.post("/stt")
async def stt(req: Request):
    """Base64 WAV (player mic) -> transcribed text."""
    body = await req.json()
    b64 = body.get("audio_b64")
    if not b64:
        return JSONResponse({"error": "no audio_b64"}, status_code=400)
    try:
        wav = base64.b64decode(b64)
        text = await asyncio.get_running_loop().run_in_executor(None, voicemod.stt_from_wav, wav)
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": f"stt unavailable: {e}"}, status_code=503)
    return {"text": text}


async def _handle(msg: dict, ws: WebSocket) -> None:
    r = hub.runner
    if r is None:
        return
    loop = asyncio.get_running_loop()
    t = msg.get("type")
    if t == "time_control":
        action = msg.get("action")
        if action == "pause":
            r.set_paused(True)
        elif action == "resume":
            r.set_paused(False)
        elif action == "speed":
            r.set_speed(float(msg.get("speed", 2.0)))
        elif action == "step":
            await loop.run_in_executor(None, lambda: r.execute_sync(lambda rr: rr.sim.step()))
    elif t == "player_say":
        r.player_say(str(msg.get("agent", "")), str(msg.get("text", "")))
    elif t == "inject_event":
        await loop.run_in_executor(
            None, lambda: r.inject_event(str(msg.get("text", "")), msg.get("location"), msg.get("agents"))
        )
    elif t == "inspect":
        dump = await loop.run_in_executor(None, r.inspect, str(msg.get("agent", "")))
        await ws.send_json(dump)
    elif t == "snapshot":
        await ws.send_json(await loop.run_in_executor(None, r.snapshot))
    elif t == "set_mode":
        await ws.send_json({"type": "mode_set", "mode": msg.get("mode")})


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    hub.clients.add(ws)
    loop = asyncio.get_running_loop()
    try:
        await ws.send_json(await loop.run_in_executor(None, hub.runner.snapshot))
        while True:
            msg = await ws.receive_json()
            await _handle(msg, ws)
    except WebSocketDisconnect:
        pass
    finally:
        hub.clients.discard(ws)


def main() -> None:
    import uvicorn

    uvicorn.run(
        "pueblo.server:app",
        host=os.environ.get("PUEBLO_HOST", "127.0.0.1"),
        port=int(os.environ.get("PUEBLO_PORT", "8765")),
        log_level="info",
    )


if __name__ == "__main__":
    main()
