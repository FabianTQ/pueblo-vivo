using UnityEngine;
using UnityEngine.AI;

namespace PuebloVivo
{
    /// <summary>
    /// A villager's body in the 3D world. Walks to target positions via NavMesh and
    /// shows speech bubbles. Built from a primitive at runtime (placeholder art) so
    /// the project runs with zero imported assets; swap the mesh for low-poly later.
    /// </summary>
    [RequireComponent(typeof(NavMeshAgent))]
    public class AgentAvatar : MonoBehaviour
    {
        public string AgentId { get; private set; }
        public string DisplayName { get; private set; }

        private NavMeshAgent _nav;
        private SpeechBubble _bubble;
        private Renderer _renderer;
        private Color _baseColor;

        public static AgentAvatar Spawn(string id, string displayName, Vector3 pos, Color color)
        {
            var go = GameObject.CreatePrimitive(PrimitiveType.Capsule);
            go.name = $"Agent_{id}";
            go.transform.position = pos;
            var nav = go.AddComponent<NavMeshAgent>();
            nav.radius = 0.35f;
            nav.height = 2f;
            nav.speed = 3.5f;
            nav.angularSpeed = 720;
            nav.acceleration = 12;

            var avatar = go.AddComponent<AgentAvatar>();
            avatar.AgentId = id;
            avatar.DisplayName = displayName;
            avatar._nav = nav;
            avatar._renderer = go.GetComponent<Renderer>();
            avatar._baseColor = color;
            avatar._renderer.material.color = color;
            avatar._bubble = SpeechBubble.Attach(go, 2.2f);

            // a floating name tag
            var nameBubble = SpeechBubble.Attach(go, 2.7f);
            nameBubble.Show(displayName, float.MaxValue);
            return avatar;
        }

        public void GoTo(Vector3 pos)
        {
            if (_nav != null && _nav.isOnNavMesh)
                _nav.SetDestination(pos);
            else
                transform.position = pos;
        }

        public void Say(string line) => _bubble?.Show(line);

        public void SetHighlight(bool on)
        {
            if (_renderer == null) return;
            _renderer.material.color = on ? Color.yellow : _baseColor;
        }
    }
}
