using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEditor.Animations;
using UnityEngine;
using UnityEngine.AI;

namespace PuebloVivo.EditorTools
{
    /// <summary>
    /// Builds a shared villager AnimatorController (idle/walk/run blend by Speed +
    /// a Cheer gesture) and one prefab per KayKit model under Resources/Avatars/.
    /// Reproducible — re-run after changing models or AgentAvatar.
    /// Menu: Pueblo Vivo/Build Avatar Prefabs.
    ///
    /// KayKit 2.0 specifics: all characters share the Rig_Medium skeleton (Generic),
    /// and animation clips live in separate FBX (Animations/Rig_Medium/*). Because the
    /// bone paths (Rig_Medium/root/...) are identical across characters, one set of
    /// clips drives all six.
    /// </summary>
    public static class BuildAvatarPrefabs
    {
        private const string FbxDir = "Assets/KayKit/Adventurers/Characters/fbx";
        private const string AnimDir = "Assets/KayKit/Adventurers/Animations/Rig_Medium";
        private const string OutDir = "Assets/Resources/Avatars";
        private const string ControllerPath = OutDir + "/VillagerAnimator.controller";

        [MenuItem("Pueblo Vivo/Build Avatar Prefabs")]
        public static void Build()
        {
            Directory.CreateDirectory(OutDir);
            var clips = LoadClips();
            var controller = BuildController(clips);

            int built = 0;
            foreach (var model in AvatarCatalog.AllModels())
            {
                var fbxPath = $"{FbxDir}/{model}.fbx";
                var fbx = AssetDatabase.LoadAssetAtPath<GameObject>(fbxPath);
                if (fbx == null) { Debug.LogWarning($"[Avatars] missing {fbxPath}, skipping {model}"); continue; }

                var inst = (GameObject)PrefabUtility.InstantiatePrefab(fbx);
                inst.name = model;

                var nav = inst.GetComponent<NavMeshAgent>();
                if (nav == null) nav = inst.AddComponent<NavMeshAgent>();
                nav.radius = 0.35f; nav.height = 1.8f; nav.speed = 3.5f;
                nav.angularSpeed = 720; nav.acceleration = 12;

                var anim = inst.GetComponent<Animator>();
                if (anim == null) anim = inst.AddComponent<Animator>();
                anim.runtimeAnimatorController = controller;
                anim.applyRootMotion = false;
                var av = LoadAvatar(fbxPath);
                if (av != null) anim.avatar = av;

                if (inst.GetComponent<AgentAvatar>() == null) inst.AddComponent<AgentAvatar>();

                PrefabUtility.SaveAsPrefabAsset(inst, $"{OutDir}/{model}.prefab");
                Object.DestroyImmediate(inst);
                built++;
            }
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
            Debug.Log($"[Avatars] built controller + {built} prefabs in {OutDir}");
        }

        private static Dictionary<string, AnimationClip> LoadClips()
        {
            var dict = new Dictionary<string, AnimationClip>();
            string[] files = { $"{AnimDir}/Rig_Medium_MovementBasic.fbx", $"{AnimDir}/Rig_Medium_General.fbx" };
            foreach (var f in files)
                foreach (var o in AssetDatabase.LoadAllAssetsAtPath(f))
                    if (o is AnimationClip c && !c.name.StartsWith("__preview"))
                        dict[c.name] = c;
            return dict;
        }

        private static Avatar LoadAvatar(string fbxPath)
        {
            foreach (var o in AssetDatabase.LoadAllAssetsAtPath(fbxPath))
                if (o is Avatar a) return a;
            return null;
        }

        private static AnimatorController BuildController(Dictionary<string, AnimationClip> clips)
        {
            var ctrl = AnimatorController.CreateAnimatorControllerAtPath(ControllerPath);
            ctrl.AddParameter("Speed", AnimatorControllerParameterType.Float);
            ctrl.AddParameter("Cheer", AnimatorControllerParameterType.Trigger);
            var sm = ctrl.layers[0].stateMachine;

            var blend = new BlendTree { name = "Locomotion", blendType = BlendTreeType.Simple1D, blendParameter = "Speed" };
            AssetDatabase.AddObjectToAsset(blend, ctrl);
            AddChild(blend, clips, "Idle_A", 0f);
            AddChild(blend, clips, "Walking_A", 2f);
            AddChild(blend, clips, "Running_A", 5.5f);

            var loco = sm.AddState("Locomotion");
            loco.motion = blend;
            sm.defaultState = loco;

            if (clips.TryGetValue("Interact", out var cheer))
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

        private static void AddChild(BlendTree tree, Dictionary<string, AnimationClip> clips, string name, float threshold)
        {
            if (clips.TryGetValue(name, out var clip)) tree.AddChild(clip, threshold);
            else Debug.LogWarning($"[Avatars] clip '{name}' not found");
        }
    }
}
