# Villager Character Models — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace each NPC's placeholder colored capsule with a rigged, animated KayKit "Adventurers" (CC0) humanoid, one model per villager role, animated idle↔walk by NavMesh speed.

**Architecture:** Import KayKit FBX as Unity Humanoid (one shared avatar). A reproducible Editor tool builds a shared `AnimatorController` (idle/walk/run blend + `Cheer` trigger) and one prefab per model under `Resources/Avatars/`. At runtime `AgentAvatar.Spawn` loads the prefab for the agent's occupation (falling back to a capsule if assets are missing) and drives the Animator from the agent's NavMesh velocity. `VillageController` reads `occupation` from the brain snapshot to pick the model.

**Tech Stack:** Unity 6 (6000.3.0f1), URP, C#, Unity AI Navigation (NavMesh), Newtonsoft.Json (already used), KayKit Adventurers CC0 assets.

## Global Constraints

- Unity version: **6000.3.0f1**, render pipeline **URP**. (verbatim from project)
- Art license: **CC0 1.0** — assets are committed to the public repo; include the pack's `LICENSE.txt`. No personal data/credentials in any commit.
- **Do not break** the existing brain↔Unity flow: NavMesh movement, speech bubbles, name tags, Director highlight, and the `snapshot/move/say/talk_start/clock` event handling must keep working.
- **Follow the project's Unity verification pattern:** clean compile (`read_console`, 0 errors) + visual validation in Play (screenshots). No C# unit-test framework is introduced (the Python brain holds the automated suite).
- **Never leave the repo broken:** if KayKit assets are absent, `AgentAvatar.Spawn` must fall back to the current capsule so `Build Scene` + Play still run.
- Code identifiers in English; the model uses the brain's `occupation` string as the mapping key.
- Branch: work happens on `feat/villager-models` (already created). Commit after each task.
- Unity operations are driven via the UnityMCP tools (`manage_asset`, `manage_editor`, `execute_menu_item`, `read_console`, `manage_camera`, `manage_scene`, `create_script`/`apply_text_edits`, `validate_script`, `refresh_unity`). The Unity Editor must be open with the project loaded.

---

### Task 0: Prerequisite — user downloads KayKit Adventurers (manual gate)

**Files:** none (asset acquisition).

This is a manual step the user performs once; nothing else can proceed without it.

- [ ] **Step 1: Download the free pack**

User goes to https://kaylousberg.itch.io/kaykit-adventurers → **Download Now** → **"No thanks, just take me to the downloads"** → download **`Free 2.0`** (≈12 MB). Note the saved path (e.g. `D:\Descargas\kaykit_adventurers_FREE_2.0.zip`).

- [ ] **Step 2: Confirm the zip exists**

Run (Bash): `ls -la "<path-to-zip>"`
Expected: the zip is listed, size ≈12 MB. Record the absolute path for Task 1.

---

### Task 1: Import & configure KayKit assets

**Files:**
- Create: `unity/Assets/KayKit/Adventurers/Characters/fbx/*.fbx` (+ `*_texture.png`) — extracted from the zip
- Create: `unity/Assets/KayKit/Adventurers/LICENSE.txt`

**Interfaces:**
- Produces: imported FBX models named `Knight`, `Barbarian`, `Rogue`, `RogueHooded`, `Mage`, `Ranger`, each with a Unity **Humanoid** avatar; a shared avatar so animation clips retarget; URP materials. Animation clips `Idle`, `Walking_A`, `Running_A`, `Cheer` exist as sub-assets of each FBX.

- [ ] **Step 1: Extract the zip into the project**

Run (Bash), substituting the real zip path from Task 0:
```bash
mkdir -p "/d/dev/proyectos/pueblo-vivo/unity/Assets/KayKit/Adventurers"
unzip -o "<path-to-zip>" -d "/d/dev/proyectos/pueblo-vivo/unity/Assets/KayKit/Adventurers"
ls -R "/d/dev/proyectos/pueblo-vivo/unity/Assets/KayKit/Adventurers" | head -40
```
Expected: a `Characters/fbx/` folder with `Knight.fbx`, `Barbarian.fbx`, `Rogue.fbx`, `RogueHooded.fbx`, `Mage.fbx`, `Ranger.fbx` (+ `*_texture.png`), plus `Textures/`, `Assets/`, `LICENSE.txt`. If the top-level folder name differs, move contents so FBX live under `Assets/KayKit/Adventurers/Characters/fbx/`.

> If `Ranger.fbx` is absent (the research could not byte-confirm it in 2.0), proceed; Task 2's catalog default + Task 3's fallback handle a missing model, and you can duplicate `Rogue` later.

- [ ] **Step 2: Import into Unity**

Use `refresh_unity` (or `manage_asset` refresh) so Unity imports the new files. Then `read_console` (types: error). Expected: import completes, 0 import errors. Some material/shader warnings are acceptable (fixed next).

- [ ] **Step 3: Set each character FBX rig to Humanoid with a shared avatar**

For `Knight.fbx`: set ModelImporter `animationType = Human`, `avatarSetup = CreateFromThisModel`. Reimport. This produces `Knight`'s avatar (the shared `Rig_Medium` avatar).
For the other five FBX: set `animationType = Human`, `avatarSetup = CopyFromOtherAvatar`, and assign `sourceAvatar` = Knight's avatar. Reimport each.

Do this via an `execute_code`/editor snippet using `UnityEditor.ModelImporter` (`animationType`, `avatarSetup`, `sourceAvatar`) + `AssetDatabase.WriteImportSettingsIfDirty` + `AssetDatabase.ImportAsset`. After: `read_console` (error) → 0 errors.

Verify: load each FBX's avatar (`AssetDatabase.LoadAllAssetsAtPath`) and assert each has an `Avatar` sub-asset with `isHuman == true`.

- [ ] **Step 4: Convert materials to URP**

Open **Window ▸ Rendering ▸ Render Pipeline Converter**, select **Built-in to URP ▸ Material Upgrade**, Initialize and Convert. (Or, since the atlas is flat: create one `URP/Lit` material per character with `*_texture.png` as Base Map and assign it to the model's renderer.) Then set each `*_texture.png` import: **Filter Mode = Point**, and disable sRGB only if colors look washed.

Verify: `read_console` (error) → 0. A quick Scene-view look (`manage_camera` scene_view screenshot of a dragged-in model) shows correctly colored, non-magenta materials.

- [ ] **Step 5: Commit**

```bash
cd /d/dev/proyectos/pueblo-vivo
git add unity/Assets/KayKit
git commit -m "feat(unity): import KayKit Adventurers (CC0) humanoid models"
```

---

### Task 2: AvatarCatalog — occupation → model mapping

**Files:**
- Create: `unity/Assets/Scripts/AvatarCatalog.cs`

**Interfaces:**
- Produces: `static string AvatarCatalog.ModelFor(string occupation)`, `const string AvatarCatalog.DefaultModel`, `static IEnumerable<string> AvatarCatalog.AllModels()`. Consumed by Task 3 (prefab builder) and Task 6 (VillageController).

- [ ] **Step 1: Create the catalog**

Create `unity/Assets/Scripts/AvatarCatalog.cs` (via `create_script`):
```csharp
using System.Collections.Generic;

namespace PuebloVivo
{
    /// <summary>
    /// Single source of truth mapping a brain occupation to a KayKit model name.
    /// The model name is also the prefab name under Resources/Avatars/.
    /// </summary>
    public static class AvatarCatalog
    {
        public const string DefaultModel = "Knight";

        // occupation (from brain scenarios.py) -> KayKit model
        private static readonly Dictionary<string, string> ByOccupation = new()
        {
            { "innkeeper", "Mage" },        // maria (host)
            { "bartender", "Barbarian" },   // diego
            { "baker",     "Ranger" },      // lucia
            { "farmer",    "RogueHooded" }, // carlos
            { "teacher",   "Knight" },      // sofia
            { "merchant",  "Rogue" },       // pedro
            { "gardener",  "Ranger" },      // elena (7th; reuses Ranger, tinted)
        };

        public static string ModelFor(string occupation)
        {
            if (!string.IsNullOrEmpty(occupation) && ByOccupation.TryGetValue(occupation, out var m))
                return m;
            return DefaultModel;
        }

        /// <summary>Distinct model names that need a prefab built.</summary>
        public static IEnumerable<string> AllModels()
        {
            var seen = new HashSet<string>();
            foreach (var m in ByOccupation.Values)
                if (seen.Add(m)) yield return m;
            if (seen.Add(DefaultModel)) yield return DefaultModel;
        }
    }
}
```

- [ ] **Step 2: Verify it compiles**

`validate_script` on the new file, then `read_console` (error). Expected: 0 errors. Confirm by inspection: `AllModels()` yields 6 distinct names (Mage, Barbarian, Ranger, RogueHooded, Knight, Rogue).

- [ ] **Step 3: Commit**

```bash
cd /d/dev/proyectos/pueblo-vivo
git add unity/Assets/Scripts/AvatarCatalog.cs
git commit -m "feat(unity): add AvatarCatalog (occupation -> KayKit model)"
```

---

### Task 3: Editor tool — build AnimatorController + avatar prefabs

**Files:**
- Create: `unity/Assets/Editor/BuildAvatarPrefabs.cs`
- Produces (assets): `unity/Assets/Resources/Avatars/VillagerAnimator.controller`, `unity/Assets/Resources/Avatars/<Model>.prefab` (one per `AvatarCatalog.AllModels()`)

**Interfaces:**
- Consumes: `AvatarCatalog.AllModels()`; imported FBX from Task 1; `AgentAvatar` (Task 5) — add the component reference; until Task 5 lands, the tool still builds model+NavMeshAgent+Animator and adds `AgentAvatar` which already exists (capsule version) so this compiles. Re-run after Task 5.
- Produces: prefabs loadable via `Resources.Load<GameObject>($"Avatars/{model}")`, each with `NavMeshAgent`, `Animator` (controller = VillagerAnimator, avatar = shared), `AgentAvatar`.

- [ ] **Step 1: Write the Editor tool**

Create `unity/Assets/Editor/BuildAvatarPrefabs.cs`:
```csharp
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Animations;
using UnityEngine;
using UnityEngine.AI;

namespace PuebloVivo.EditorTools
{
    /// <summary>
    /// Builds a shared villager AnimatorController (idle/walk/run blend + Cheer)
    /// and one prefab per KayKit model under Resources/Avatars/. Reproducible:
    /// re-run after changing models or AgentAvatar. Menu: Pueblo Vivo/Build Avatar Prefabs.
    /// </summary>
    public static class BuildAvatarPrefabs
    {
        private const string FbxDir = "Assets/KayKit/Adventurers/Characters/fbx";
        private const string OutDir = "Assets/Resources/Avatars";
        private const string ControllerPath = OutDir + "/VillagerAnimator.controller";

        [MenuItem("Pueblo Vivo/Build Avatar Prefabs")]
        public static void Build()
        {
            Directory.CreateDirectory(OutDir);
            var controller = BuildController();

            int built = 0;
            foreach (var model in AvatarCatalog.AllModels())
            {
                var fbxPath = $"{FbxDir}/{model}.fbx";
                var fbx = AssetDatabase.LoadAssetAtPath<GameObject>(fbxPath);
                if (fbx == null) { Debug.LogWarning($"[Avatars] missing {fbxPath}, skipping {model}"); continue; }

                var inst = (GameObject)PrefabUtility.InstantiatePrefab(fbx);
                inst.name = model;

                var nav = inst.AddComponent<NavMeshAgent>();
                nav.radius = 0.35f; nav.height = 1.8f; nav.speed = 3.5f;
                nav.angularSpeed = 720; nav.acceleration = 12;

                var anim = inst.GetComponent<Animator>() ?? inst.AddComponent<Animator>();
                anim.runtimeAnimatorController = controller;
                anim.applyRootMotion = false;

                inst.AddComponent<AgentAvatar>();

                Directory.CreateDirectory(OutDir);
                PrefabUtility.SaveAsPrefabAsset(inst, $"{OutDir}/{model}.prefab");
                Object.DestroyImmediate(inst);
                built++;
            }
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
            Debug.Log($"[Avatars] built controller + {built} prefabs in {OutDir}");
        }

        private static AnimatorController BuildController()
        {
            var clips = LoadClips("Knight"); // shared avatar -> Knight's clips drive all
            var ctrl = AnimatorController.CreateAnimatorControllerAtPath(ControllerPath);
            ctrl.AddParameter("Speed", AnimatorControllerParameterType.Float);
            ctrl.AddParameter("Cheer", AnimatorControllerParameterType.Trigger);

            var sm = ctrl.layers[0].stateMachine;

            var blend = new BlendTree { name = "Locomotion", blendType = BlendTreeType.Simple1D, blendParameter = "Speed" };
            AssetDatabase.AddObjectToAsset(blend, ctrl);
            if (clips.TryGetValue("Idle", out var idle)) blend.AddChild(idle, 0f);
            if (clips.TryGetValue("Walking_A", out var walk)) blend.AddChild(walk, 2f);
            if (clips.TryGetValue("Running_A", out var run)) blend.AddChild(run, 5.5f);

            var loco = sm.AddState("Locomotion");
            loco.motion = blend;
            sm.defaultState = loco;

            if (clips.TryGetValue("Cheer", out var cheer))
            {
                var cheerState = sm.AddState("Cheer");
                cheerState.motion = cheer;
                var toCheer = sm.AddAnyStateTransition(cheerState);
                toCheer.AddCondition(AnimatorConditionMode.If, 0, "Cheer");
                toCheer.duration = 0.1f; toCheer.canTransitionToSelf = false;
                var back = cheerState.AddTransition(loco);
                back.hasExitTime = true; back.exitTime = 0.9f; back.duration = 0.1f;
            }
            EditorUtility.SetDirty(ctrl);
            AssetDatabase.SaveAssets();
            return ctrl;
        }

        private static System.Collections.Generic.Dictionary<string, AnimationClip> LoadClips(string model)
        {
            var dict = new System.Collections.Generic.Dictionary<string, AnimationClip>();
            var path = $"{FbxDir}/{model}.fbx";
            foreach (var o in AssetDatabase.LoadAllAssetsAtPath(path))
                if (o is AnimationClip c && !c.name.StartsWith("__preview"))
                    dict[c.name] = c;
            if (dict.Count == 0) Debug.LogWarning($"[Avatars] no clips found in {path}");
            return dict;
        }
    }
}
```

- [ ] **Step 2: Compile, then run the tool**

`validate_script` the file; `read_console` (error) → 0. Then `execute_menu_item` `Pueblo Vivo/Build Avatar Prefabs`. `read_console` (log+error): expect `[Avatars] built controller + 6 prefabs` and 0 errors.

- [ ] **Step 3: Verify the assets**

Confirm `Assets/Resources/Avatars/VillagerAnimator.controller` and 6 `<Model>.prefab` exist (`manage_asset` search or `ls unity/Assets/Resources/Avatars`). Load one prefab and assert it has `NavMeshAgent`, `Animator` (controller set), `AgentAvatar`. If `Idle`/`Walking_A` clip names differ, fix the names in `LoadClips`/`BuildController` thresholds and re-run.

- [ ] **Step 4: Commit**

```bash
cd /d/dev/proyectos/pueblo-vivo
git add unity/Assets/Editor/BuildAvatarPrefabs.cs unity/Assets/Resources/Avatars
git commit -m "feat(unity): editor tool builds villager AnimatorController + prefabs"
```

---

### Task 4: Refactor AgentAvatar to instantiate models + animate

**Files:**
- Modify: `unity/Assets/Scripts/AgentAvatar.cs` (full rewrite below)

**Interfaces:**
- Consumes: `Resources/Avatars/<model>.prefab` (Task 3); brain occupation→model via caller.
- Produces: `static AgentAvatar Spawn(string model, string id, string displayName, Vector3 pos, Color? tint = null)`; instance methods `GoTo(Vector3)`, `Say(string)`, `SetHighlight(bool)`, `Cheer()`. **Note the new signature** — Task 6 calls `Spawn(model, id, name, pos, tint)`.

- [ ] **Step 1: Rewrite AgentAvatar.cs**

Replace the file contents:
```csharp
using UnityEngine;
using UnityEngine.AI;

namespace PuebloVivo
{
    /// <summary>
    /// A villager's body in the 3D world. Instantiates a KayKit model prefab for the
    /// agent's role (falling back to a capsule if assets are missing), walks via
    /// NavMesh, drives idle/walk animation from velocity, and shows speech bubbles.
    /// </summary>
    [RequireComponent(typeof(NavMeshAgent))]
    public class AgentAvatar : MonoBehaviour
    {
        public string AgentId { get; private set; }
        public string DisplayName { get; private set; }

        private static readonly int SpeedHash = Animator.StringToHash("Speed");
        private static readonly int CheerHash = Animator.StringToHash("Cheer");
        private static readonly int BaseColor = Shader.PropertyToID("_BaseColor");

        private NavMeshAgent _nav;
        private Animator _anim;
        private SpeechBubble _bubble;
        private Renderer[] _renderers;
        private MaterialPropertyBlock _mpb;
        private float _animSpeed;

        // Heights tuned for the ~1.8u KayKit models (capsule fallback is 2u tall).
        private const float BubbleHeight = 1.9f;
        private const float NameHeight = 2.3f;

        public static AgentAvatar Spawn(string model, string id, string displayName, Vector3 pos, Color? tint = null)
        {
            GameObject go;
            var prefab = Resources.Load<GameObject>($"Avatars/{model}");
            if (prefab != null)
            {
                go = Object.Instantiate(prefab, pos, Quaternion.identity);
            }
            else
            {
                // Fallback: the original capsule, so the repo runs without art assets.
                go = GameObject.CreatePrimitive(PrimitiveType.Capsule);
                go.transform.position = pos;
                var nav0 = go.AddComponent<NavMeshAgent>();
                nav0.radius = 0.35f; nav0.height = 2f; nav0.speed = 3.5f;
                nav0.angularSpeed = 720; nav0.acceleration = 12;
                go.AddComponent<AgentAvatar>();
            }
            go.name = $"Agent_{id}";

            var avatar = go.GetComponent<AgentAvatar>();
            avatar._nav = go.GetComponent<NavMeshAgent>();
            avatar._anim = go.GetComponent<Animator>();
            avatar.AgentId = id;
            avatar.DisplayName = displayName;
            avatar._renderers = go.GetComponentsInChildren<Renderer>();
            avatar._mpb = new MaterialPropertyBlock();

            if (tint.HasValue) avatar.ApplyTint(tint.Value);

            avatar._bubble = SpeechBubble.Attach(go, BubbleHeight);
            var nameBubble = SpeechBubble.Attach(go, NameHeight);
            nameBubble.Show(displayName, float.MaxValue);
            return avatar;
        }

        private void Update()
        {
            if (_anim == null || _nav == null) return;
            // Smoothed planar speed -> Animator blend (idle/walk/run).
            float target = _nav.velocity.magnitude;
            _animSpeed = Mathf.Lerp(_animSpeed, target, Time.deltaTime * 10f);
            _anim.SetFloat(SpeedHash, _animSpeed);
        }

        public void GoTo(Vector3 pos)
        {
            if (_nav != null && _nav.isOnNavMesh) _nav.SetDestination(pos);
            else transform.position = pos;
        }

        public void Say(string line) => _bubble?.Show(line);

        public void Cheer()
        {
            if (_anim != null && _anim.runtimeAnimatorController != null) _anim.SetTrigger(CheerHash);
        }

        public void SetHighlight(bool on)
        {
            var c = on ? Color.yellow : Color.white;
            ApplyColor(c);
        }

        private void ApplyTint(Color c) => ApplyColor(c);

        private void ApplyColor(Color c)
        {
            if (_renderers == null) return;
            foreach (var r in _renderers)
            {
                if (r == null) continue;
                r.GetPropertyBlock(_mpb);
                _mpb.SetColor(BaseColor, c);
                r.SetPropertyBlock(_mpb);
            }
        }
    }
}
```

- [ ] **Step 2: Verify it compiles**

`validate_script`, `read_console` (error). Expected: 0 errors. (Task 3's tool references `AgentAvatar`; still compiles.)

- [ ] **Step 3: Rebuild prefabs against the new component**

`execute_menu_item` `Pueblo Vivo/Build Avatar Prefabs` again so prefabs carry the updated `AgentAvatar`. `read_console` → 0 errors, `built controller + 6 prefabs`.

- [ ] **Step 4: Commit**

```bash
cd /d/dev/proyectos/pueblo-vivo
git add unity/Assets/Scripts/AgentAvatar.cs unity/Assets/Resources/Avatars
git commit -m "feat(unity): AgentAvatar instantiates KayKit model + animates by speed"
```

---

### Task 5: VillageController — pick model by occupation + Cheer on talk_start

**Files:**
- Modify: `unity/Assets/Scripts/VillageController.cs` (`BuildWorld` agent loop + `Handle` talk_start)

**Interfaces:**
- Consumes: `AvatarCatalog.ModelFor(occupation)` (Task 2), `AgentAvatar.Spawn(model, id, name, pos, tint)` and `AgentAvatar.Cheer()` (Task 4); `occupation` field already present in the brain snapshot.

- [ ] **Step 1: Update the agent spawn loop in `BuildWorld`**

Replace the agent loop (currently `VillageController.cs:85-94`) with:
```csharp
            // spawn agents
            var agents = (JArray)snap["agents"];
            for (int i = 0; i < agents.Count; i++)
            {
                string id = (string)agents[i]["id"];
                string name = (string)agents[i]["name"];
                string loc = (string)agents[i]["location"];
                string occupation = (string)agents[i]["occupation"];
                string model = AvatarCatalog.ModelFor(occupation);
                Vector3 pos = LocPos(loc) + Jitter();
                if (!_agents.ContainsKey(id))
                    _agents[id] = AgentAvatar.Spawn(model, id, name, pos);
            }
```

- [ ] **Step 2: Fire Cheer on talk_start**

Replace the `talk_start` case (currently `VillageController.cs:62`) with:
```csharp
                case "talk_start":
                    Log($"talk: {(string)ev["a"]} <-> {(string)ev["b"]}");
                    if (_agents.TryGetValue((string)ev["a"], out var a1)) a1.Cheer();
                    if (_agents.TryGetValue((string)ev["b"], out var a2)) a2.Cheer();
                    break;
```

- [ ] **Step 3: Verify it compiles**

`validate_script` on `VillageController.cs`; `read_console` (error) → 0 errors.

- [ ] **Step 4: Commit**

```bash
cd /d/dev/proyectos/pueblo-vivo
git add unity/Assets/Scripts/VillageController.cs
git commit -m "feat(unity): pick villager model by occupation; cheer on talk_start"
```

---

### Task 6: End-to-end visual validation in Play

**Files:** none (validation + tuning). May re-touch `AgentAvatar.cs` heights / NavMeshAgent if scale is off.

**Interfaces:** consumes everything above; the brain server must be running on `:8765` (it already is; if not: `cd brain && uvicorn pueblo.server:app --host 127.0.0.1 --port 8765`).

- [ ] **Step 1: Rebuild the scene**

`execute_menu_item` `Pueblo Vivo/Build Scene`. `read_console` (error) → 0. (`Build Scene` is unchanged; avatars spawn at runtime from prefabs.)

- [ ] **Step 2: Enter Play and resume the sim**

`manage_editor` `play`. Confirm the brain connects (HUD shows "connected"). Resume + brisk speed via the scratchpad observer or the Director HUD:
`python <scratchpad>/live_observer.py 40 3.0` (resumes the shared sim).

- [ ] **Step 3: Screenshot the Game view and inspect**

`manage_camera` action=screenshot, capture_source=game_view, include_image=true, max_resolution=900.
Expected: **6 distinct humanoid models** (not capsules) standing/walking, each with a floating name tag and the right look per role; walking models play the walk animation; idle ones play idle. Verify against the AvatarCatalog mapping (Mage=Maria, Barbarian=Diego, …).

- [ ] **Step 4: Verify highlight + bubbles + flow**

In the Director HUD click a villager (or send an `inspect`); confirm `SetHighlight` tints the model yellow and a mind dump returns. Confirm speech bubbles appear over heads during conversations and `move`/`say`/`snapshot` still work (`read_console` no runtime errors).

- [ ] **Step 5: Tune scale/heights if needed**

If models import too small/large or name tags float wrong, adjust `NavMeshAgent.height`/FBX `Scale Factor` and `BubbleHeight`/`NameHeight` in `AgentAvatar.cs`; re-run Task 3 tool + re-Play until correct. Stop Play (`manage_editor` stop) when done.

- [ ] **Step 6: Commit any tuning**

```bash
cd /d/dev/proyectos/pueblo-vivo
git add -A unity/Assets/Scripts unity/Assets/Resources/Avatars
git commit -m "fix(unity): tune villager model scale and bubble heights"
```
(If no tuning was needed, skip this commit.)

---

### Task 7: Credits + finalize

**Files:**
- Modify: `README.md` (credits)

**Interfaces:** none.

- [ ] **Step 1: Add a credits note to the README**

Under the existing "Credits" section in `README.md`, add:
```markdown
- Character art: **KayKit "Adventurers"** by Kay Lousberg (CC0 1.0) — https://kaylousberg.itch.io/kaykit-adventurers
```

- [ ] **Step 2: Confirm the pack license file is committed**

Verify `unity/Assets/KayKit/Adventurers/LICENSE.txt` is tracked (`git ls-files | grep KayKit/Adventurers/LICENSE`). If missing, add it.

- [ ] **Step 3: Commit**

```bash
cd /d/dev/proyectos/pueblo-vivo
git add README.md
git commit -m "docs: credit KayKit Adventurers (CC0) character art"
```

- [ ] **Step 4: Final verification**

`read_console` (error) → 0. Confirm the branch `feat/villager-models` holds: spec, assets, AvatarCatalog, Editor tool, refactored AgentAvatar/VillageController, README credit. Hand off to `superpowers:finishing-a-development-branch` to decide merge to `main`.

---

## Self-Review

**Spec coverage:**
- §2 read `occupation` from snapshot → Task 5 ✓
- §3 import KayKit Free 2.0, location, commit, CC0 license file → Task 0/1/7 ✓
- §4 occupation→model mapping → Task 2 ✓
- §5.1 Humanoid + shared avatar + URP + atlas Point → Task 1 ✓
- §5.2 Editor tool builds prefabs in Resources/Avatars → Task 3 ✓
- §5.3 AnimatorController blend + Cheer → Task 3 ✓
- §5.4 AgentAvatar refactor (load prefab, fallback, animate, highlight MPB, heights, Cheer) → Task 4 ✓
- §5.5 VillageController occupation + Cheer on talk_start → Task 5 ✓
- §6 idle/walk/run + Cheer → Task 3/4 ✓
- §7 clean compile + edit-mode-equivalent verification + visual + regression → each task's verify + Task 6 ✓
- §8 risks (Ranger missing, root motion, scale, loop time, atlas filter, URP) → Task 1 notes + Task 6 tuning ✓

**Placeholder scan:** No TBD/TODO; all code shown in full; commands have expected output.

**Type consistency:** `AvatarCatalog.ModelFor/AllModels/DefaultModel` used identically in Tasks 3 & 5. `AgentAvatar.Spawn(string model, string id, string displayName, Vector3 pos, Color? tint)` defined in Task 4, called with `Spawn(model, id, name, pos)` in Task 5 (tint optional) ✓. `Cheer()`/`SetHighlight(bool)`/`GoTo`/`Say` consistent across Tasks 4–5. Animator params `"Speed"`(float)/`"Cheer"`(trigger) consistent between Task 3 controller and Task 4 setters.
