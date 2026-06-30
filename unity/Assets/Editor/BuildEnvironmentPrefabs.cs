using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;

namespace PuebloVivo.EditorTools
{
    /// <summary>
    /// Wraps each Medieval Hexagon building/prop FBX into a prefab under
    /// Resources/Environment/. The FBX live in colour subfolders, so models are found
    /// by an exact-name recursive search of the pack. Menu: Pueblo Vivo/Build Environment Prefabs.
    /// </summary>
    public static class BuildEnvironmentPrefabs
    {
        private const string PackRoot = "Assets/KayKit/MedievalHexagon";
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
                if (fbx == null) { Debug.LogWarning($"[Env] FBX not found: {model}"); missing++; continue; }
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
            foreach (var guid in AssetDatabase.FindAssets($"{model} t:Model", new[] { PackRoot }))
            {
                var p = AssetDatabase.GUIDToAssetPath(guid);
                if (Path.GetFileNameWithoutExtension(p).Equals(model, System.StringComparison.OrdinalIgnoreCase))
                    return AssetDatabase.LoadAssetAtPath<GameObject>(p);
            }
            return null;
        }
    }
}
