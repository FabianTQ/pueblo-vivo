"""Live WebSocket client to validate the brain server protocol end to end.

Connects, reads the snapshot, then exercises pause / inspect / player_say and
confirms a mind_dump and a player reply come back over the socket.

Run (server already up on :8765):
    python -m scripts.ws_client
"""

from __future__ import annotations

import asyncio
import json

import websockets

URI = "ws://127.0.0.1:8765/ws"


async def main() -> int:
    async with websockets.connect(URI, max_size=2_000_000) as ws:
        snap = json.loads(await ws.recv())
        assert snap["type"] == "snapshot", snap
        agents = [a["id"] for a in snap["agents"]]
        print("snapshot OK — agents:", agents, "| locations:", len(snap["locations"]))
        aid = agents[0]

        await ws.send(json.dumps({"type": "time_control", "action": "pause"}))
        await ws.send(json.dumps({"type": "inspect", "agent": aid}))
        await ws.send(json.dumps({"type": "player_say", "agent": aid,
                                  "text": "Good morning! Anything exciting happening today?"}))

        got_mind = got_reply = False
        for _ in range(60):
            try:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=40))
            except asyncio.TimeoutError:
                break
            t = msg.get("type")
            if t == "mind_dump" and msg.get("agent") == aid:
                got_mind = True
                print(f"mind_dump OK — {msg['name']}: {len(msg['memories'])} memories, "
                      f"{len(msg['plan'])} plan steps")
            elif t == "say" and msg.get("agent") == aid and msg.get("to") == "player":
                got_reply = True
                print(f"player reply OK — {aid}: {msg['text']}")
            if got_mind and got_reply:
                break

        ok = got_mind and got_reply
        print("RESULT:", "PASS" if ok else "FAIL", f"(mind={got_mind}, reply={got_reply})")
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
