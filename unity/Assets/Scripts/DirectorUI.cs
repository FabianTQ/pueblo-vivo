using System.Collections.Generic;
using Newtonsoft.Json.Linq;
using UnityEngine;

namespace PuebloVivo
{
    /// <summary>
    /// Immediate-mode (OnGUI) director + player HUD. Chosen over uGUI so the whole UI
    /// is built in code with zero scene wiring: time controls, the event log, per-agent
    /// mind inspection, event injection, and player dialogue with the nearest NPC.
    /// </summary>
    public class DirectorUI : MonoBehaviour
    {
        public BrainClient client;
        public VillageController village;
        public PlayerController player;

        private string _clock = "--:--";
        private bool _connected;
        private readonly List<string> _log = new();
        private JObject _mind;
        private Vector2 _logScroll, _mindScroll;
        private string _injectText = "A traveling merchant just arrived with exotic goods.";
        private string _chatText = "";

        private void Awake()
        {
            if (client == null) client = FindObjectOfType<BrainClient>();
            if (village == null) village = FindObjectOfType<VillageController>();
            if (player == null) player = FindObjectOfType<PlayerController>();
        }

        private void OnEnable()
        {
            if (village != null)
            {
                village.OnClock += OnClock;
                village.OnLog += OnLog;
                village.OnMind += OnMind;
            }
            if (client != null)
            {
                client.OnConnected += () => _connected = true;
                client.OnDisconnected += () => _connected = false;
            }
        }

        private void OnDisable()
        {
            if (village != null)
            {
                village.OnClock -= OnClock;
                village.OnLog -= OnLog;
                village.OnMind -= OnMind;
            }
        }

        private void OnClock(int tick, string hhmm) => _clock = $"{hhmm} (t{tick})";

        private void OnLog(string msg)
        {
            _log.Add(msg);
            if (_log.Count > 200) _log.RemoveAt(0);
            _logScroll.y = float.MaxValue;
        }

        private void OnMind(JObject mind) => _mind = mind;

        private void OnGUI()
        {
            DrawTopBar();
            DrawControls();
            DrawAgents();
            DrawLog();
            DrawMind();
            DrawChat();
        }

        private void DrawTopBar()
        {
            GUILayout.BeginArea(new Rect(10, 6, Screen.width - 20, 26), GUI.skin.box);
            GUILayout.BeginHorizontal();
            GUILayout.Label($"Pueblo Vivo  |  {(_connected ? "● connected" : "○ offline")}  |  🕑 {_clock}");
            GUILayout.FlexibleSpace();
            bool director = player != null && player.DirectorMode;
            if (GUILayout.Button(director ? "Mode: DIRECTOR" : "Mode: CHARACTER", GUILayout.Width(160)))
                if (player != null) player.DirectorMode = !player.DirectorMode;
            GUILayout.EndHorizontal();
            GUILayout.EndArea();
        }

        private void DrawControls()
        {
            GUILayout.BeginArea(new Rect(10, 40, 230, 170), GUI.skin.box);
            GUILayout.Label("Time");
            GUILayout.BeginHorizontal();
            if (GUILayout.Button("⏸ Pause")) client?.Pause();
            if (GUILayout.Button("▶ Resume")) client?.Resume();
            if (GUILayout.Button("⏭ Step")) client?.Step();
            GUILayout.EndHorizontal();
            GUILayout.BeginHorizontal();
            foreach (var s in new[] { 1f, 2f, 5f, 10f })
                if (GUILayout.Button($"{s}x")) client?.SetSpeed(s);
            GUILayout.EndHorizontal();
            GUILayout.Space(6);
            GUILayout.Label("Inject event (director):");
            _injectText = GUILayout.TextField(_injectText);
            if (GUILayout.Button("Inject to village"))
                client?.InjectEvent(_injectText);
            GUILayout.EndArea();
        }

        private void DrawAgents()
        {
            if (village == null) return;
            GUILayout.BeginArea(new Rect(10, 218, 230, 220), GUI.skin.box);
            GUILayout.Label("Villagers (click to read their mind):");
            foreach (var kv in village.Agents)
            {
                if (GUILayout.Button(kv.Value.DisplayName))
                    client?.Inspect(kv.Key);
            }
            GUILayout.EndArea();
        }

        private void DrawLog()
        {
            GUILayout.BeginArea(new Rect(10, Screen.height - 180, 360, 170), GUI.skin.box);
            GUILayout.Label("Event log");
            _logScroll = GUILayout.BeginScrollView(_logScroll);
            foreach (var line in _log) GUILayout.Label(line);
            GUILayout.EndScrollView();
            GUILayout.EndArea();
        }

        private void DrawMind()
        {
            if (_mind == null) return;
            GUILayout.BeginArea(new Rect(Screen.width - 360, 40, 350, 420), GUI.skin.box);
            GUILayout.Label($"🧠 {(string)_mind["name"]} — {(string)_mind["occupation"]}");
            GUILayout.Label($"At: {(string)_mind["location"]}   Doing: {(string)_mind["action"]}");
            GUILayout.Label($"Knows the secret/fact: {(bool?)_mind["knows_tracked_fact"]}");
            _mindScroll = GUILayout.BeginScrollView(_mindScroll);

            var plan = _mind["plan"] as JArray;
            if (plan != null && plan.Count > 0)
            {
                GUILayout.Label("— Plan —");
                foreach (var s in plan)
                    GUILayout.Label($"t{(int)s["start_tick"]}: {(string)s["activity"]} @ {(string)s["location"]}");
            }
            var refl = _mind["reflections"] as JArray;
            if (refl != null && refl.Count > 0)
            {
                GUILayout.Label("— Reflections —");
                foreach (var r in refl) GUILayout.Label("• " + (string)r);
            }
            var mems = _mind["memories"] as JArray;
            if (mems != null)
            {
                GUILayout.Label("— Recent memories —");
                foreach (var m in mems)
                    GUILayout.Label($"[{(string)m["kind"]} i{(float)m["importance"]:0}] {(string)m["text"]}");
            }
            GUILayout.EndScrollView();
            GUILayout.EndArea();
        }

        private void DrawChat()
        {
            if (player == null || player.DirectorMode || player.Nearest == null) return;
            GUILayout.BeginArea(new Rect(Screen.width / 2 - 200, Screen.height - 70, 400, 60), GUI.skin.box);
            GUILayout.Label($"Talking to {player.Nearest.DisplayName} (Enter to send):");
            GUILayout.BeginHorizontal();
            GUI.SetNextControlName("chat");
            _chatText = GUILayout.TextField(_chatText);
            bool enter = Event.current.type == EventType.KeyDown && Event.current.keyCode == KeyCode.Return;
            if ((GUILayout.Button("Send", GUILayout.Width(60)) || enter) && !string.IsNullOrWhiteSpace(_chatText))
            {
                client?.PlayerSay(player.Nearest.AgentId, _chatText.Trim());
                _chatText = "";
            }
            GUILayout.EndHorizontal();
            GUILayout.EndArea();
        }
    }
}
