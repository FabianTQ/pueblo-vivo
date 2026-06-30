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
        public event Action<string, string, string> OnDialogue;

        private readonly Dictionary<string, Vector3> _locPos = new();
        private readonly Dictionary<string, AgentAvatar> _agents = new();
        private readonly System.Random _rng = new(12345);
        private const float BuildingScale = 2.5f; // hex buildings ship at miniature scale
        private bool _decorated;

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
            // place locations evenly on a circle (idempotent: skip any already placed, so a
            // re-sent snapshot — e.g. after a reconnect — does not duplicate markers)
            var locs = (JArray)snap["locations"];
            for (int i = 0; i < locs.Count; i++)
            {
                string name = (string)locs[i]["name"];
                if (_locPos.ContainsKey(name)) continue;
                float ang = (float)i / locs.Count * Mathf.PI * 2f;
                var pos = new Vector3(Mathf.Cos(ang) * layoutRadius, 0, Mathf.Sin(ang) * layoutRadius);
                _locPos[name] = pos;
                CreateMarker(name, pos);
            }
            // spawn agents (idempotent: reuse an avatar already in the scene — survives a
            // VillageController re-init / snapshot resend that would otherwise duplicate them)
            var agents = (JArray)snap["agents"];
            for (int i = 0; i < agents.Count; i++)
            {
                string id = (string)agents[i]["id"];
                if (_agents.ContainsKey(id)) continue;
                var existing = GameObject.Find($"Agent_{id}");
                if (existing != null) { _agents[id] = existing.GetComponent<AgentAvatar>(); continue; }
                string name = (string)agents[i]["name"];
                string loc = (string)agents[i]["location"];
                string occupation = (string)agents[i]["occupation"];
                string model = AvatarCatalog.ModelFor(occupation);
                Vector3 pos = LocPos(loc) + Jitter();
                _agents[id] = AgentAvatar.Spawn(model, id, name, pos);
            }
            if (!_decorated) { EnvironmentDecorator.Decorate(transform, layoutRadius); _decorated = true; }
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
            string who = _agents.TryGetValue(id, out var a) ? a.DisplayName : id;
            string toId = (string)ev["to"];
            string to = _agents.TryGetValue(toId, out var b) ? b.DisplayName : toId;
            OnDialogue?.Invoke(who, to, text);
            Log($"{who}: {text}");
        }

        public Vector3 LocPos(string name) =>
            name != null && _locPos.TryGetValue(name, out var p) ? p : Vector3.zero;

        private Vector3 Jitter() =>
            new((float)(_rng.NextDouble() - 0.5) * 3f, 0, (float)(_rng.NextDouble() - 0.5) * 3f);

        private void CreateMarker(string name, Vector3 pos)
        {
            // holder stays unscaled so the floating label keeps a sane size/height
            var holder = new GameObject($"Loc_{name}");
            holder.transform.position = pos;
            var model = EnvironmentCatalog.ModelFor(name);
            GameObject building = null;
            if (model != null)
            {
                var prefab = Resources.Load<GameObject>($"Environment/{model}");
                if (prefab != null)
                {
                    building = Instantiate(prefab, holder.transform);
                    building.transform.localPosition = Vector3.zero;
                    building.transform.localRotation = Quaternion.Euler(0, _rng.Next(4) * 90, 0);
                    building.transform.localScale = Vector3.one * BuildingScale;
                }
            }
            if (building == null)
            {
                // fallback: the original gray disc so the scene still reads without art
                building = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
                building.transform.SetParent(holder.transform, false);
                building.transform.localPosition = new Vector3(0, 0.05f, 0);
                building.transform.localScale = new Vector3(3.5f, 0.1f, 3.5f);
                building.GetComponent<Renderer>().material.color = new Color(0.6f, 0.6f, 0.62f);
                Destroy(building.GetComponent<Collider>());
            }
            var label = SpeechBubble.Attach(holder, model != null ? 4.5f : 1.5f);
            label.Show(name, float.MaxValue);
        }

        private void Log(string msg) => OnLog?.Invoke(msg);
    }
}
