using System.IO;
using Unity.AI.Navigation;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace PuebloVivo.EditorTools
{
    /// <summary>
    /// Builds the entire playable scene from code — ground, baked NavMesh, lighting,
    /// camera, the Brain/Village/Director objects and a Player — so the project runs
    /// with zero manual scene setup. Menu: "Pueblo Vivo/Build Scene", or in batchmode
    /// via -executeMethod PuebloVivo.EditorTools.SceneBootstrap.BuildScene.
    /// </summary>
    public static class SceneBootstrap
    {
        [MenuItem("Pueblo Vivo/Build Scene")]
        public static void BuildScene()
        {
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

            // Ground (60 x 60)
            var ground = GameObject.CreatePrimitive(PrimitiveType.Plane);
            ground.name = "Ground";
            ground.transform.localScale = new Vector3(6, 1, 6);
            ground.isStatic = true;

            // Lighting
            var sun = new GameObject("Sun");
            var light = sun.AddComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = 1.1f;
            sun.transform.rotation = Quaternion.Euler(50, -30, 0);

            // Camera (angled overhead)
            var camGo = new GameObject("Main Camera");
            camGo.tag = "MainCamera";
            var cam = camGo.AddComponent<Camera>();
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = new Color(0.55f, 0.72f, 0.85f);
            cam.fieldOfView = 55;
            camGo.AddComponent<AudioListener>();
            // Closer, slightly lower framing so the KayKit villagers read clearly.
            camGo.transform.position = new Vector3(0, 21, -23);
            camGo.transform.rotation = Quaternion.Euler(43, 0, 0);

            // Brain client
            var brainGo = new GameObject("Brain");
            var client = brainGo.AddComponent<BrainClient>();

            // Village controller (+ gossip overlay)
            var villageGo = new GameObject("Village");
            var village = villageGo.AddComponent<VillageController>();
            village.client = client;
            var gossip = villageGo.AddComponent<GossipGraph>();
            gossip.village = village;

            // Player
            var player = GameObject.CreatePrimitive(PrimitiveType.Capsule);
            player.name = "Player";
            player.transform.position = new Vector3(0, 1, 0);
            player.GetComponent<Renderer>().sharedMaterial.color = Color.white;
            player.AddComponent<CharacterController>();
            var pc = player.AddComponent<PlayerController>();
            pc.village = village;

            // Director / player HUD (IMGUI — no canvas needed)
            var uiGo = new GameObject("DirectorUI");
            var ui = uiGo.AddComponent<DirectorUI>();
            ui.client = client;
            ui.village = village;
            ui.player = pc;

            // NavMesh: bake AFTER the ground exists
            var navGo = new GameObject("NavMesh");
            var surface = navGo.AddComponent<NavMeshSurface>();
            surface.collectObjects = CollectObjects.All;
            surface.BuildNavMesh();

            Directory.CreateDirectory("Assets/Scenes");
            EditorSceneManager.SaveScene(scene, "Assets/Scenes/Village.unity");
            Debug.Log("[PuebloVivo] Scene built at Assets/Scenes/Village.unity");
        }
    }
}
