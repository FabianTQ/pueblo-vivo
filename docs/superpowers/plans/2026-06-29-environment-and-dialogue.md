# Environment + Dialogue Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the village a living low-poly environment (themed KayKit Medieval Hexagon buildings per location, grass ground, scattered trees/fences/props) and replace floating speech bubbles with a subtitle-style dialogue bar.

**Architecture:** A `EnvironmentCatalog` maps each brain location to a Medieval Hexagon model; an Editor tool builds building/prop prefabs under `Resources/Environment/`. At runtime `VillageController.CreateMarker` instantiates the themed building per location (capsule/cylinder fallback if assets missing), and an `EnvironmentDecorator` scatters trees/fences/props with a fixed seed. For dialogue, `AgentAvatar` drops its floating dialogue bubble (keeps the name tag), `VillageController` raises an `OnDialogue` event, and `DirectorUI` draws a bottom-center subtitle bar.

**Tech Stack:** Unity 6 (6000.3.0f1), Built-in render pipeline, C#, KayKit Medieval Hexagon CC0 assets, IMGUI (OnGUI) HUD.

## Global Constraints

- Unity **6000.3.0f1**, **Built-in** render pipeline. Materials are **Standard** (`_Color` / `_MainTex`); KayKit uses one shared gradient atlas (1024²).
- Art license **CC0 1.0**; commit assets to the public repo with the pack's `License.txt`. No secrets/personal data in any commit.
- **Do not break** the brain↔Unity flow: NavMesh movement, name tags, Director HUD, and `snapshot/move/say/talk_start/clock` handling must keep working. Villagers must still walk (NavMesh stays baked over the same ground).
- **Never leave the repo broken:** if `Resources/Environment/<model>` is missing, `CreateMarker` falls back to the current gray cylinder so `Build Scene` + Play still run.
- **Verification pattern (Unity side):** clean compile (`read_console`, 0 errors) + visual validation in Play (screenshots). No C# test framework is introduced.
- Code identifiers in English. The scene `Village.unity` is regenerable via `Pueblo Vivo/Build Scene` (it is untracked).
- Branch: work on `feat/environment-dialogue` (already created). Commit after each task. Unity driven via UnityMCP tools.

---

### Task 0: Prerequisite — user downloads KayKit Medieval Hexagon (manual gate)

**Files:** none.

- [ ] **Step 1: Download the free pack**

User: https://kaylousberg.itch.io/kaykit-medieval-hexagon → **Download** → **"No thanks, just take me to the downloads"** → the **free** tier (≈33 MB). Note the saved path.

- [ ] **Step 2: Confirm the zip exists**

Run (Bash): `ls -la "<path-to-zip>"` — expect ≈33 MB. Record the path for Task 1.

---

### Task 1: Import & configure Medieval Hexagon assets

**Files:**
- Create: `unity/Assets/KayKit/MedievalHexagon/**` (extracted, prefer the `fbx(unity)/` models + atlas)
- Create: `unity/Assets/KayKit/MedievalHexagon/License.txt`

**Interfaces:**
- Produces: imported FBX models (`well, tavern, market, church, windmill, home_A, home_B, tree_single_A, rock_single_A, fence_wood_straight, barrel, ...`) with Standard materials + the gradient atlas, at a scale compatible with ~1.8u characters.

- [ ] **Step 1: Extract into the project**

```bash
mkdir -p "/d/dev/proyectos/pueblo-vivo/unity/Assets/KayKit/MedievalHexagon"
unzip -o "<zip>" -d "/d/dev/proyectos/pueblo-vivo/unity/Assets/KayKit/MedievalHexagon"
ls -R "/d/dev/proyectos/pueblo-vivo/unity/Assets/KayKit/MedievalHexagon" | head -60
```
Identify the folder holding individual building FBX (likely `Assets/fbx(unity)/` or `models/`). Record the real subpath and the exact model filenames (they may differ slightly from the spec — adjust the catalog/decorator paths to match what's on disk).

- [ ] **Step 2: Import + material setup**

`refresh_unity` (all, compile). Then, via `execute_code`: for each character-relevant material set its shader to **Standard** and assign the pack's atlas PNG to `_MainTex` (mirror what was done for Adventurers — most KayKit packs auto-assign the atlas, but verify no pink/magenta). Set the atlas texture **Filter Mode = Point**. `read_console` (error) → 0.

- [ ] **Step 3: Verify look + scale**

Instantiate `home_A` + one character side by side via `execute_code`, screenshot Scene view, and check: not magenta, and the house is a sane size next to a ~1.8u villager. If off, set the FBX `globalScale`/prefab scale and note the factor for Task 3. Destroy the preview objects.

- [ ] **Step 4: Commit**

```bash
cd /d/dev/proyectos/pueblo-vivo
git add unity/Assets/KayKit/MedievalHexagon
git commit -m "feat(unity): import KayKit Medieval Hexagon (CC0) environment assets"
```

---

### Task 2: EnvironmentCatalog — location → building model

**Files:**
- Create: `unity/Assets/Scripts/EnvironmentCatalog.cs`

**Interfaces:**
- Produces: `static string EnvironmentCatalog.ModelFor(string location)` (null = no building), `static IEnumerable<string> EnvironmentCatalog.BuildingModels()`, `static readonly string[] EnvironmentCatalog.PropModels`. Consumed by Task 3 (prefab builder), Task 4 (CreateMarker), Task 5 (decorator).

- [ ] **Step 1: Create the catalog**

`create_script` `Assets/Scripts/EnvironmentCatalog.cs`:
```csharp
using System.Collections.Generic;

namespace PuebloVivo
{
    /// <summary>
    /// Maps a brain location name to a KayKit Medieval Hexagon model (the prefab name
    /// under Resources/Environment/). Null = no building (decorated instead).
    /// Adjust the model names here if the imported FBX filenames differ.
    /// </summary>
    public static class EnvironmentCatalog
    {
        private static readonly Dictionary<string, string> ByLocation = new()
        {
            { "tavern", "tavern" },
            { "market", "market" },
            { "bakery", "windmill" },
            { "school", "church" },
            { "well",   "well" },
            // "garden" and "plaza" have no building — EnvironmentDecorator dresses them.
        };

        private static readonly string[] HomeModels = { "home_A", "home_B" };

        // Decorative props scattered by EnvironmentDecorator.
        public static readonly string[] PropModels =
        {
            "tree_single_A", "tree_single_B", "rock_single_A", "rock_single_C",
            "fence_wood_straight", "barrel", "crates",
        };

        public static string ModelFor(string location)
        {
            if (string.IsNullOrEmpty(location)) return null;
            if (location.StartsWith("home_"))
            {
                int h = 0;
                foreach (char c in location) h = h * 31 + c;
                return HomeModels[(h & 0x7fffffff) % HomeModels.Length];
            }
            return ByLocation.TryGetValue(location, out var m) ? m : null;
        }

        public static IEnumerable<string> BuildingModels()
        {
            var seen = new HashSet<string>();
            foreach (var m in ByLocation.Values) if (seen.Add(m)) yield return m;
            foreach (var m in HomeModels) if (seen.Add(m)) yield return m;
        }
    }
}
```

- [ ] **Step 2: Verify compile + commit**

`validate_script` + `read_console` (error) → 0.
```bash
git add unity/Assets/Scripts/EnvironmentCatalog.cs
git commit -m "feat(unity): add EnvironmentCatalog (location -> Medieval Hexagon model)"
```

---

### Task 3: Editor tool — build environment prefabs

**Files:**
- Create: `unity/Assets/Editor/BuildEnvironmentPrefabs.cs`
- Produces: `unity/Assets/Resources/Environment/<model>.prefab` for every building + prop model.

**Interfaces:**
- Consumes: `EnvironmentCatalog.BuildingModels()` + `EnvironmentCatalog.PropModels`; imported FBX from Task 1.
- Produces: prefabs loadable via `Resources.Load<GameObject>($"Environment/{model}")`.

- [ ] **Step 1: Write the tool**

`create_script` `Assets/Editor/BuildEnvironmentPrefabs.cs`:
```csharp
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;

namespace PuebloVivo.EditorTools
{
    /// <summary>
    /// Wraps each Medieval Hexagon building/prop FBX into a prefab under
    /// Resources/Environment/. Reproducible. Menu: Pueblo Vivo/Build Environment Prefabs.
    /// FbxDir must point at the folder holding the individual model FBX (set in Task 1).
    /// </summary>
    public static class BuildEnvironmentPrefabs
    {
        // TODO-on-import: set to the real subfolder found in Task 1 (e.g. ".../fbx(unity)").
        private const string FbxDir = "Assets/KayKit/MedievalHexagon/Assets/fbx(unity)";
        private const string OutDir = "Assets/Resources/Environment";

        [MenuItem("Pueblo Vivo/Build Environment Prefabs")]
        public static void Build()
        {
            Directory.CreateDirectory(OutDir);
            var names = EnvironmentCatalog.BuildingModels().Concat(EnvironmentCatalog.PropModels).Distinct();
            int built = 0, missing = 0;
            foreach (var model in names)
            {
                var fbx = FindFbx(model);
                if (fbx == null) { Debug.LogWarning($"[Env] FBX not found for '{model}' under {FbxDir}"); missing++; continue; }
                var inst = (GameObject)PrefabUtility.InstantiatePrefab(fbx);
                inst.name = model;
                PrefabUtility.SaveAsPrefabAsset(inst, $"{OutDir}/{model}.prefab");
                Object.DestroyImmediate(inst);
                built++;
            }
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
            Debug.Log($"[Env] built {built} prefabs ({missing} missing) in {OutDir}");
        }

        private static GameObject FindFbx(string model)
        {
            var direct = AssetDatabase.LoadAssetAtPath<GameObject>($"{FbxDir}/{model}.fbx");
            if (direct != null) return direct;
            // fallback: search the pack folder for a model whose name matches (case-insensitive)
            foreach (var guid in AssetDatabase.FindAssets($"{model} t:Model", new[] { "Assets/KayKit/MedievalHexagon" }))
            {
                var p = AssetDatabase.GUIDToAssetPath(guid);
                if (Path.GetFileNameWithoutExtension(p).Equals(model, System.StringComparison.OrdinalIgnoreCase))
                    return AssetDatabase.LoadAssetAtPath<GameObject>(p);
            }
            return null;
        }
    }
}
```

- [ ] **Step 2: Compile, set FbxDir, run**

`validate_script`; `read_console` (error) → 0. After Task 1 you know the real model folder — if it isn't `Assets/fbx(unity)`, fix `FbxDir`. Then `execute_menu_item` `Pueblo Vivo/Build Environment Prefabs`. `read_console` (log): expect `[Env] built N prefabs (0 missing)`. If any are missing, reconcile the names in `EnvironmentCatalog` with the real filenames and re-run.

- [ ] **Step 3: Verify + commit**

Confirm `Assets/Resources/Environment/*.prefab` exist (one per building + prop).
```bash
git add unity/Assets/Editor/BuildEnvironmentPrefabs.cs unity/Assets/Resources/Environment
git commit -m "feat(unity): editor tool builds Medieval Hexagon environment prefabs"
```

---

### Task 4: Buildings per location + grass ground

**Files:**
- Modify: `unity/Assets/Scripts/VillageController.cs` (`CreateMarker`)
- Modify: `unity/Assets/Editor/SceneBootstrap.cs` (ground material)

**Interfaces:**
- Consumes: `EnvironmentCatalog.ModelFor` (Task 2), `Resources/Environment/<model>` (Task 3).

- [ ] **Step 1: Instantiate the themed building in `CreateMarker`**

Replace `VillageController.CreateMarker` (currently makes a gray cylinder) with:
```csharp
        private void CreateMarker(string name, Vector3 pos)
        {
            var model = EnvironmentCatalog.ModelFor(name);
            GameObject go = null;
            if (model != null)
            {
                var prefab = Resources.Load<GameObject>($"Environment/{model}");
                if (prefab != null) go = Object.Instantiate(prefab, pos, Quaternion.identity);
            }
            if (go == null)
            {
                // fallback: the original gray disc, so the scene still reads without art
                go = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
                go.transform.position = pos + new Vector3(0, 0.05f, 0);
                go.transform.localScale = new Vector3(3.5f, 0.1f, 3.5f);
                go.GetComponent<Renderer>().material.color = new Color(0.6f, 0.6f, 0.62f);
                Destroy(go.GetComponent<Collider>());
            }
            go.name = $"Loc_{name}";
            var label = SpeechBubble.Attach(go, 3.0f);
            label.Show(name, float.MaxValue);
        }
```

- [ ] **Step 2: Grass ground in `SceneBootstrap`**

In `SceneBootstrap.BuildScene`, after the ground is created, tint it grass-green. Replace the `ground` block's end with:
```csharp
            ground.isStatic = true;
            var groundMat = new Material(Shader.Find("Standard"));
            groundMat.color = new Color(0.42f, 0.62f, 0.32f); // grass
            ground.GetComponent<Renderer>().sharedMaterial = groundMat;
```

- [ ] **Step 3: Compile + commit**

`validate_script` both files; `read_console` (error) → 0.
```bash
git add unity/Assets/Scripts/VillageController.cs unity/Assets/Editor/SceneBootstrap.cs
git commit -m "feat(unity): themed building per location + grass ground"
```

---

### Task 5: EnvironmentDecorator — scatter trees/fences/props (fixed seed)

**Files:**
- Create: `unity/Assets/Scripts/EnvironmentDecorator.cs`
- Modify: `unity/Assets/Scripts/VillageController.cs` (call decorator after `BuildWorld`)

**Interfaces:**
- Consumes: `EnvironmentCatalog.PropModels`, `Resources/Environment/<prop>`, `VillageController.layoutRadius`.
- Produces: scattered, non-colliding decoration with a fixed seed (reproducible).

- [ ] **Step 1: Create the decorator**

`create_script` `Assets/Scripts/EnvironmentDecorator.cs`:
```csharp
using UnityEngine;

namespace PuebloVivo
{
    /// <summary>
    /// Scatters environment props (trees, rocks, fences, barrels) around the village
    /// with a fixed seed so the layout is reproducible. Keeps a clear radius around the
    /// village centre and avoids the building ring so it doesn't block NavMesh paths.
    /// </summary>
    public static class EnvironmentDecorator
    {
        public static void Decorate(Transform parent, float layoutRadius, int count = 40, int seed = 1234)
        {
            var rng = new System.Random(seed);
            float inner = layoutRadius + 3f;   // outside the building ring
            float outer = layoutRadius + 14f;  // within the 60x60 ground
            for (int i = 0; i < count; i++)
            {
                var prop = EnvironmentCatalog.PropModels[rng.Next(EnvironmentCatalog.PropModels.Length)];
                var prefab = Resources.Load<GameObject>($"Environment/{prop}");
                if (prefab == null) continue;
                double ang = rng.NextDouble() * System.Math.PI * 2;
                double r = inner + rng.NextDouble() * (outer - inner);
                var pos = new Vector3((float)(System.Math.Cos(ang) * r), 0, (float)(System.Math.Sin(ang) * r));
                var go = Object.Instantiate(prefab, pos, Quaternion.Euler(0, rng.Next(360), 0), parent);
                go.name = $"Decor_{prop}_{i}";
            }
        }
    }
}
```

- [ ] **Step 2: Call it once after the world is built**

In `VillageController`, add a guard field and call the decorator at the end of `BuildWorld` (after the agent loop), so it runs once:
```csharp
        private bool _decorated;
        // ... at the end of BuildWorld(), after the agents loop and before Log(...):
            if (!_decorated) { EnvironmentDecorator.Decorate(transform, layoutRadius); _decorated = true; }
```

- [ ] **Step 3: Compile + commit**

`validate_script`; `read_console` (error) → 0.
```bash
git add unity/Assets/Scripts/EnvironmentDecorator.cs unity/Assets/Scripts/VillageController.cs
git commit -m "feat(unity): scatter environment props with a fixed seed"
```

---

### Task 6: Dialogue subtitle bar (replace floating bubbles)

**Files:**
- Modify: `unity/Assets/Scripts/AgentAvatar.cs` (drop dialogue bubble, keep name tag)
- Modify: `unity/Assets/Scripts/VillageController.cs` (`OnDialogue` event + raise it in `OnSay`)
- Modify: `unity/Assets/Scripts/DirectorUI.cs` (`DrawSubtitle`)

**Interfaces:**
- Produces: `event Action<string,string,string> VillageController.OnDialogue` (speaker, target, text).
- Consumes: existing `AgentAvatar.DisplayName`, `DirectorUI.OnGUI`.

- [ ] **Step 1: AgentAvatar — keep only the name tag**

In `AgentAvatar.Spawn`, remove the dialogue bubble; keep the name tag. Replace the two `SpeechBubble.Attach` lines:
```csharp
            // name tag only — dialogue now shows in the DirectorUI subtitle bar
            var nameBubble = SpeechBubble.Attach(go, NameHeight);
            nameBubble.Show(displayName, float.MaxValue);
```
And make `Say` a no-op for the bubble (the text routes through VillageController.OnDialogue):
```csharp
        public void Say(string line) { /* dialogue is shown in the HUD subtitle bar */ }
```
Remove the now-unused `_bubble` field.

- [ ] **Step 2: VillageController — raise OnDialogue in OnSay**

Add the event near the other events:
```csharp
        public event Action<string, string, string> OnDialogue;
```
In `OnSay`, after computing `who`, raise it (target may be "player" or an agent id; resolve to a display name when possible):
```csharp
        private void OnSay(JObject ev)
        {
            string id = (string)ev["agent"];
            string text = (string)ev["text"];
            string who = _agents.TryGetValue(id, out var a) ? a.DisplayName : id;
            string toId = (string)ev["to"];
            string to = _agents.TryGetValue(toId, out var b) ? b.DisplayName : toId;
            OnDialogue?.Invoke(who, to, text);
            Log($"{who}: {text}");
        }
```

- [ ] **Step 3: DirectorUI — subtitle bar**

Add fields, subscribe in `OnEnable`/`OnDisable`, and draw. Add to fields:
```csharp
        private string _subtitle = "";
        private float _subtitleUntil;
```
In `OnEnable` (where village events are wired): `village.OnDialogue += OnDialogue;`
In `OnDisable`: `village.OnDialogue -= OnDialogue;`
Add the handler + drawer:
```csharp
        private void OnDialogue(string speaker, string target, string text)
        {
            _subtitle = string.IsNullOrEmpty(target) || target == "player"
                ? $"{speaker}: {text}" : $"{speaker} → {target}: {text}";
            _subtitleUntil = Time.time + 8f;
        }

        private void DrawSubtitle()
        {
            if (Time.time > _subtitleUntil || string.IsNullOrEmpty(_subtitle)) return;
            float w = Mathf.Min(640, Screen.width - 740);
            var rect = new Rect((Screen.width - w) / 2f, Screen.height - 130, w, 56);
            var prev = GUI.color; GUI.color = new Color(1, 1, 1, 0.9f);
            GUILayout.BeginArea(rect, GUI.skin.box);
            GUILayout.Label(_subtitle);
            GUILayout.EndArea();
            GUI.color = prev;
        }
```
Call it in `OnGUI` (last, so it draws on top): add `DrawSubtitle();` after `DrawChat();`.

- [ ] **Step 4: Compile + commit**

`validate_script` all three; `read_console` (error) → 0.
```bash
git add unity/Assets/Scripts/AgentAvatar.cs unity/Assets/Scripts/VillageController.cs unity/Assets/Scripts/DirectorUI.cs
git commit -m "feat(unity): subtitle dialogue bar; drop floating speech bubbles"
```

---

### Task 7: End-to-end visual validation in Play

**Files:** none (validation + tuning; may re-touch scale/positions). Brain server must be up on `:8765`.

- [ ] **Step 1: Rebuild scene + enter Play**

`execute_menu_item` `Pueblo Vivo/Build Scene`; `read_console` (error) → 0. `manage_editor` `play`. If avatars/buildings don't appear within a few seconds (handshake timing), send `BrainClient.RequestSnapshot()` via `execute_code`.

- [ ] **Step 2: Screenshot + inspect**

`manage_camera` screenshot game_view (include_image, max_resolution 1000). Expect: themed buildings at each location (tavern/market/church/windmill/well/houses — not gray discs), grass ground, scattered trees/fences/props, villagers walking between them at sane scale, the **subtitle bar** showing the current line at bottom-center, and **no** floating dialogue bubbles (name tags still present).

- [ ] **Step 3: Tune**

If buildings have a distracting hex base, scale/offset or hide the base submesh. If scale is off, adjust prefab scale in the Task 3 tool and re-run. If decoration blocks villager paths, reduce `count`/increase `inner`, or re-bake NavMesh after buildings (note: buildings without colliders won't block NavMesh — acceptable). Stop Play when satisfied (`manage_editor` stop).

- [ ] **Step 4: Commit any tuning**

```bash
git add -A unity/Assets/Scripts unity/Assets/Editor unity/Assets/Resources/Environment
git commit -m "fix(unity): tune environment scale/placement"
```
(Skip if no tuning needed.)

---

### Task 8: Credits + finalize

**Files:** Modify `README.md`.

- [ ] **Step 1: Add credit**

Under "Credits" in `README.md`, add:
```markdown
- Environment art: **KayKit "Medieval Hexagon Pack"** by Kay Lousberg (CC0 1.0) — https://kaylousberg.itch.io/kaykit-medieval-hexagon
```

- [ ] **Step 2: Confirm license file committed**

`git ls-files | grep MedievalHexagon/License` — add it if missing.

- [ ] **Step 3: Commit + hand off**

```bash
git add README.md
git commit -m "docs: credit KayKit Medieval Hexagon (CC0) environment art"
```
`read_console` (error) → 0. Hand off to `superpowers:finishing-a-development-branch`.

---

## Self-Review

**Spec coverage:**
- §3.1 import Hexagon + license + commit → Task 0/1/8 ✓
- §3.2 EnvironmentCatalog location→building (+ homes, + garden/plaza none) → Task 2 ✓
- §3.3 CreateMarker instantiates buildings, grass ground, EnvironmentDecorator (fixed seed), Editor tool → Tasks 3/4/5 ✓
- §4 drop dialogue bubble, OnDialogue event, DirectorUI subtitle bar (bottom-center, semitransparent, above chat) → Task 6 ✓
- §5 clean compile + visual validation + regression (villagers walk) → each task verify + Task 7 ✓
- §6 risks (hex base, scale, decoration/NavMesh, itch download, atlas seams) → Task 1/3/5/7 notes ✓

**Placeholder scan:** The `FbxDir` const is intentionally flagged "set in Task 1" with a fallback name-search in `FindFbx`, not a placeholder — the tool works and warns on misses. No TBD/empty steps; all code shown in full.

**Type consistency:** `EnvironmentCatalog.ModelFor/BuildingModels/PropModels` used identically in Tasks 3/4/5. `VillageController.OnDialogue(speaker,target,text)` defined in Task 6 and consumed by `DirectorUI.OnDialogue` with the same 3-string signature. `CreateMarker(string,Vector3)` signature unchanged. `EnvironmentDecorator.Decorate(Transform,float,int,int)` called with `(transform, layoutRadius)` (defaults for count/seed) ✓.
