using System;
using System.Collections.Generic;
using Newtonsoft.Json.Linq;
using UnityEngine;

namespace PuebloVivo
{
    /// <summary>
    /// Turns brain events into a living 3D scene: lays out locations, spawns agent
    /// avatars, and applies move/say/gossip/clock events. Raises C# events that the
    /// HUD, director UI and gossip overlay subscribe to.
    /// </summary>
    public class VillageController : MonoBehaviour
    {
        public BrainClient client;
        public float layoutRadius = 14f;

        public event Action<string> OnLog;
        public event Action<int, string> OnClock;
        public event Action<JObject> OnMind;
        public event Action<string, string> OnGossip;

        private readonly Dictionary<string, Vector3> _locPos = new();
        private readonly Dictionary<string, AgentAvatar> _agents = new();
        private readonly System.Random _rng = new(12345);

        private static readonly Color[] Palette =
        {
            new(0.91f,0.30f,0.24f), new(0.18f,0.55f,0.34f), new(0.20f,0.40f,0.85f),
            new(0.95f,0.61f,0.07f), new(0.61f,0.35f,0.71f), new(0.10f,0.74f,0.61f),
            new(0.83f,0.33f,0.64f),
        };

        private void Awake()
        {
            if (client == null) client = FindObjectOfType<BrainClient>();
        }

        private void OnEnable()
        {
            if (client != null) client.OnEvent += Handle;
        }

        private void OnDisable()
        {
            if (client != null) client.OnEvent -= Handle;
        }

        public IReadOnlyDictionary<string, AgentAvatar> Agents => _agents;

        private void Handle(JObject ev)
        {
            switch ((string)ev["type"])
            {
                case "snapshot": BuildWorld(ev); break;
                case "move": OnMove(ev); break;
                case "say": OnSay(ev); break;
                case "clock": OnClock?.Invoke((int)ev["tick"], (string)ev["hhmm"]); break;
                case "gossip": OnGossip?.Invoke((string)ev["src"], (string)ev["dst"]);
                    Log($"gossip: {(string)ev["src"]} -> {(string)ev["dst"]}"); break;
                case "mind_dump": OnMind?.Invoke(ev); break;
                case "talk_start":
                    Log($"talk: {(string)ev["a"]} <-> {(string)ev["b"]}");
                    if (_agents.TryGetValue((string)ev["a"], out var a1)) a1.Cheer();
                    if (_agents.TryGetValue((string)ev["b"], out var a2)) a2.Cheer();
                    break;
                case "plan": Log($"{(string)ev["agent"]} planned {(int)ev["steps"]} steps"); break;
                case "reflect": Log($"{(string)ev["agent"]} reflected"); break;
                case "seed": Log($"SEED: {(string)ev["text"]}"); break;
                case "replan": Log($"{(string)ev["agent"]} changed plans"); break;
                case "event_injected": Log($"EVENT: {(string)ev["text"]}"); break;
                case "day_over": Log("--- the day is over ---"); break;
            }
        }

        private void BuildWorld(JObject snap)
        {
            // place locations evenly on a circle
            var locs = (JArray)snap["locations"];
            for (int i = 0; i < locs.Count; i++)
            {
                string name = (string)locs[i]["name"];
                float ang = (float)i / locs.Count * Mathf.PI * 2f;
                var pos = new Vector3(Mathf.Cos(ang) * layoutRadius, 0, Mathf.Sin(ang) * layoutRadius);
                _locPos[name] = pos;
                CreateMarker(name, pos);
            }
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
            Log($"world built: {agents.Count} villagers, {locs.Count} locations");
        }

        private void OnMove(JObject ev)
        {
            string id = (string)ev["agent"];
            string to = (string)ev["to"];
            if (_agents.TryGetValue(id, out var avatar))
                avatar.GoTo(LocPos(to) + Jitter());
        }

        private void OnSay(JObject ev)
        {
            string id = (string)ev["agent"];
            string text = (string)ev["text"];
            if (id != "player" && _agents.TryGetValue(id, out var avatar))
                avatar.Say(text);
            string who = _agents.TryGetValue(id, out var a) ? a.DisplayName : id;
            Log($"{who}: {text}");
        }

        public Vector3 LocPos(string name) =>
            name != null && _locPos.TryGetValue(name, out var p) ? p : Vector3.zero;

        private Vector3 Jitter() =>
            new((float)(_rng.NextDouble() - 0.5) * 3f, 0, (float)(_rng.NextDouble() - 0.5) * 3f);

        private void CreateMarker(string name, Vector3 pos)
        {
            var go = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            go.name = $"Loc_{name}";
            go.transform.position = pos + new Vector3(0, 0.05f, 0);
            go.transform.localScale = new Vector3(3.5f, 0.1f, 3.5f);
            go.GetComponent<Renderer>().material.color = new Color(0.6f, 0.6f, 0.62f);
            Destroy(go.GetComponent<Collider>());
            var label = SpeechBubble.Attach(go, 1.2f);
            label.Show(name, float.MaxValue);
        }

        private void Log(string msg) => OnLog?.Invoke(msg);
    }
}
