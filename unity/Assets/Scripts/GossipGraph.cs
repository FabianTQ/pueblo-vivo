using System.Collections.Generic;
using UnityEngine;

namespace PuebloVivo
{
    /// <summary>
    /// Pure data model of the gossip propagation graph (testable without a scene).
    /// </summary>
    public class GossipModel
    {
        private readonly HashSet<(string, string)> _edges = new();
        public IReadOnlyCollection<(string, string)> Edges => _edges;
        public int Count => _edges.Count;

        /// <summary>Adds a directed edge; returns true if it was new.</summary>
        public bool Add(string src, string dst) => _edges.Add((src, dst));

        public bool Contains(string src, string dst) => _edges.Contains((src, dst));
    }

    /// <summary>
    /// Draws a fading 3D line between two avatars when gossip passes between them.
    /// </summary>
    public class GossipGraph : MonoBehaviour
    {
        public VillageController village;
        public Color color = new(1f, 0.85f, 0.2f);
        private readonly GossipModel _model = new();

        public GossipModel Model => _model;

        private void Awake()
        {
            if (village == null) village = FindObjectOfType<VillageController>();
        }

        private void OnEnable()
        {
            if (village != null) village.OnGossip += OnGossip;
        }

        private void OnDisable()
        {
            if (village != null) village.OnGossip -= OnGossip;
        }

        private void OnGossip(string src, string dst)
        {
            _model.Add(src, dst);
            if (village.Agents.TryGetValue(src, out var a) && village.Agents.TryGetValue(dst, out var b))
                GossipLine.Create(a.transform, b.transform, color);
        }
    }

    public class GossipLine : MonoBehaviour
    {
        private Transform _a, _b;
        private LineRenderer _lr;
        private float _t;
        private const float Life = 6f;

        public static GossipLine Create(Transform a, Transform b, Color color)
        {
            var go = new GameObject("GossipLine");
            var lr = go.AddComponent<LineRenderer>();
            lr.material = new Material(Shader.Find("Sprites/Default"));
            lr.widthMultiplier = 0.15f;
            lr.positionCount = 2;
            lr.startColor = lr.endColor = color;
            var line = go.AddComponent<GossipLine>();
            line._a = a; line._b = b; line._lr = lr;
            return line;
        }

        private void Update()
        {
            _t += Time.deltaTime;
            if (_a != null && _b != null)
            {
                var up = Vector3.up * 1.4f;
                _lr.SetPosition(0, _a.position + up);
                _lr.SetPosition(1, _b.position + up);
            }
            float alpha = Mathf.Clamp01(1f - _t / Life);
            var c = _lr.startColor; c.a = alpha;
            _lr.startColor = _lr.endColor = c;
            if (_t >= Life) Destroy(gameObject);
        }
    }
}
