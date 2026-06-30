# Pueblo Vivo 🏘️

**A village of generative AI agents that runs 100% locally** — NPCs with memory,
plans and reflection, powered by a local LLM (Ollama) on a single consumer GPU, and
rendered in Unity. A local, Unity-based reimagining of the ideas in Stanford's
[*Generative Agents: Interactive Simulacra of Human Behavior*](https://arxiv.org/abs/2304.03442).

> **The "wow":** tell one villager about a party, then watch the news spread by word
> of mouth — agents who hear about it re-plan their day and show up at the right place
> and time. Nobody scripted that.

## What makes it different

- **No cloud, no API keys.** The whole brain runs against a local Ollama model on an
  RTX 4060 (8 GB). The famous Smallville experiment used GPT-3.5 in the cloud; this
  runs offline on a laptop GPU.
- **Single-GPU honest design.** The world advances in *ticks*; agents reason on a
  serial async queue (one inference at a time). Most ticks are free (just walking a
  plan); the LLM is only invoked for genuinely cognitive moments. Player dialogue is
  prioritised so it stays responsive.
- **Two clean processes.** A pure-Python "brain" (cognition + simulation + server)
  that is fully testable headless, and a thin Unity client that just renders and
  takes input. They speak JSON over a WebSocket on localhost.

## The cognitive model (per agent)

| Mechanism | What it does |
|---|---|
| **Memory stream** | Append-only log of observations, conversations, reflections, plans, each with an importance score and an embedding. |
| **Retrieval** | Blends **recency · importance · relevance** (cosine over `nomic-embed-text`), min-max normalised, top-k into the prompt. |
| **Reflection** | When accumulated importance crosses a threshold, the agent asks itself salient questions and synthesises higher-level insights (this grows opinions & relationships). |
| **Planning** | Drafts a daily plan; **re-plans when it learns something important** (e.g. a party) — the bridge from *knowing* gossip to *acting* on it. |
| **Conversation** | Co-located agents talk; each writes a first-person summary that captures new facts — the transmission channel for gossip. |

## Validated, live

Everything in the brain is built **and tested against a real local model**
(`llama3.1:8b` + `nomic-embed-text`):

- **`pytest` suite:** 33 tests green (memory/retrieval, simulation mechanics,
  runner controls, server protocol).
- **Acceptance test — the party experiment** (`python -m experiments.party`):
  with 5 villagers, **5/5 learned about the party, 4 by word of mouth through
  conversation chains** (Maria → Diego → Sofia → Carlos), and 3 re-planned to
  attend. Agents even invented a sub-plot about someone proposing at the party. ✅
- **WebSocket server:** validated end-to-end with a live client (snapshot, mind
  inspection, player dialogue).
- **Voice pipeline:** TTS↔STT round-trip validated on CPU (pyttsx3 + faster-whisper).
- **Unity client:** all C# compiles cleanly (Unity 6 batchmode, no errors). Playing
  it requires opening the project in the Editor (see `unity/SETUP.md`).

## Repository layout

```
pueblo-vivo/
├─ brain/                  # Python: cognition + simulation + server (the hard part)
│  ├─ pueblo/              # importable package (memory, planning, reflection, …)
│  ├─ experiments/party.py # the gossip acceptance test
│  ├─ scripts/            # live probes: live_smoke, ws_client, voice_probe, plan_probe
│  └─ tests/              # pytest suite (deterministic, fake LLM)
├─ unity/                 # Unity 6 client (C#) — renders the world, no game logic
│  └─ Assets/Scripts/     # BrainClient, VillageController, DirectorUI, …
└─ docs/superpowers/specs # the design spec
```

## Quickstart — the brain (the interesting part)

```bash
# 1) Models (once)
ollama pull llama3.2:3b          # or qwen2.5:7b / llama3.1:8b for higher quality
ollama pull nomic-embed-text

# 2) Python env
cd brain
python -m venv .venv && .venv\Scripts\activate     # Windows
pip install -r requirements.txt

# 3) Tests
pytest                                              # 33 green, no GPU needed

# 4) The party experiment (needs Ollama running)
python -m experiments.party --agents 5 --ticks 72
#   override the model:  --model qwen2.5:7b
```

## Quickstart — the live server + Unity

```bash
# Start the brain server (serves the simulation over WebSocket)
cd brain
uvicorn pueblo.server:app --host 127.0.0.1 --port 8765
```

Then open `unity/` in Unity 6 and follow [`unity/SETUP.md`](unity/SETUP.md):
`Pueblo Vivo ▸ Build Scene`, press Play, and the village comes alive. Toggle
**Character** mode to walk up and talk to an NPC, or **Director** mode to pause /
fast-forward time, click an agent to read its mind, and inject events.

## Configuration

All tunables live in `brain/pueblo/config.py` and can be overridden via env vars:
`PUEBLO_CHAT_MODEL`, `PUEBLO_EMBED_MODEL`, `OLLAMA_HOST`, `PUEBLO_AGENTS`, …

## Tech highlights (for the curious)

- Tolerant JSON extraction for small local models that wrap output in prose/fences.
- Semantic fact-tracking (keyword + embedding cosine) so paraphrases ("soirée" vs
  "party") still count as "knows about it".
- Thread-safe `SimRunner`: the sim loop runs on its own thread; the async server
  marshals reads/writes onto it via an RPC command queue to avoid SQLite races.
- IMGUI director HUD — zero scene wiring, builds itself in code.

## Roadmap

- Live capture of the gossip-graph as a portfolio clip.
- Swap placeholder capsules for low-poly art (Synty/Kenney/Mixamo).
- Piper TTS voices; push-to-talk mic in Unity.
- Relationship graph view; multi-day runs with overnight reflection.

## Credits

Inspired by Park et al., *Generative Agents* (2023). Built with Ollama, FastAPI and
Unity 6.

Character art: **KayKit "Adventurers"** by Kay Lousberg
([CC0 1.0](https://kaylousberg.itch.io/kaykit-adventurers)).

Environment art: **KayKit "Medieval Hexagon Pack"** by Kay Lousberg
([CC0 1.0](https://kaylousberg.itch.io/kaykit-medieval-hexagon)).
