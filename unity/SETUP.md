# Unity client — setup & run

The Unity project is a thin renderer for the Python brain. All scripts compile clean
on **Unity 6 (6000.2.x)**; the steps below get it playing. (These steps need the
Editor open and logged into Unity Hub — they can't be done headless.)

## 0. Prerequisites

- Unity 6 (`6000.2.15f1` or compatible), installed via Unity Hub and **signed in**
  (a free Personal licence is fine).
- The brain running:
  ```bash
  cd brain
  # default model is llama3.2:3b on localhost:11434
  uvicorn pueblo.server:app --host 127.0.0.1 --port 8765
  curl http://127.0.0.1:8765/health     # {"ok":true,"ollama":true,...}
  ```

## 1. Open the project

1. Unity Hub ▸ **Add** ▸ select the `unity/` folder.
2. Open it. First import downloads the packages declared in `Packages/manifest.json`
   (Newtonsoft JSON, AI Navigation) — needs internet once.

## 2. Build the scene (one click)

- Menu: **Pueblo Vivo ▸ Build Scene**.
- This generates `Assets/Scenes/Village.unity` with the ground, a baked NavMesh,
  lighting, camera, the `Brain` / `Village` / `DirectorUI` objects and a `Player`.
- Open that scene if it isn't already.

## 3. Play

Press **Play**. The client connects to `ws://127.0.0.1:8765/ws`, receives the world
snapshot, and spawns villagers (capsules) + location markers. Press **▶ Resume** (or
set 5x/10x) in the on-screen HUD to start the day; watch them walk and talk.

### Controls (on-screen IMGUI HUD)

| Mode | What you can do |
|---|---|
| **Character** | `WASD`/arrows to walk. Get close to a villager (they highlight) and a chat box appears — type and press Enter to talk to them. Anything you say enters their memory and can spread. |
| **Director** | Pause / Resume / Step / set speed. Click a villager to **read their mind** (memories, plan, reflections, whether they know the secret). Type an event and **Inject** it into the village. Gossip lines flash between agents as news spreads. |

Toggle modes with the **Mode** button (top-right).

## 4. Point at a different brain

Select the **Brain** GameObject and change `BrainClient.url` if your server isn't on
`127.0.0.1:8765`. The number of villagers is set by the brain (`PUEBLO_AGENTS` env).

## 5. Swap the placeholder art (optional polish)

Villagers and locations are primitives spawned at runtime in `VillageController` and
`AgentAvatar`. To use low-poly art (Synty / Kenney / Mixamo):
- Replace `GameObject.CreatePrimitive(...)` in `AgentAvatar.Spawn` with
  `Instantiate(yourPrefab)` (keep the `NavMeshAgent`).
- Replace location markers in `VillageController.CreateMarker` with your props.
- Re-run **Build Scene** (or just keep the runtime spawning).

## Notes / gotchas

- **Input:** scripts use the legacy `Input` axes (`Horizontal`/`Vertical`), which exist
  by default. If the project is set to the new Input System only, set
  *Project Settings ▸ Player ▸ Active Input Handling* to **Both**.
- **VRAM:** running Unity + an 8B model on an 8 GB GPU is tight. Keep the cognition
  model at `llama3.2:3b` (the default) while playing; use bigger models for headless
  experiments.
- **NavMesh:** placeholder capsules may float/sink slightly until you use properly
  pivoted character meshes — cosmetic only.
- **Voice (optional):** the brain exposes `POST /tts` (text→wav) and `POST /stt`
  (base64 wav→text). Wiring mic capture + audio playback in Unity is left as a
  follow-up; the pipeline itself is validated server-side (`scripts/voice_probe.py`).
