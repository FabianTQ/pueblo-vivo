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
        // Built-in Standard shader uses "_Color" (not URP's "_BaseColor").
        private static readonly int ColorId = Shader.PropertyToID("_Color");

        private NavMeshAgent _nav;
        private Animator _anim;
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
                // No Animator on the capsule fallback: _anim stays null and Update()/Cheer() guard for it.
            }
            go.name = $"Agent_{id}";

            var avatar = go.GetComponent<AgentAvatar>();
            avatar._nav = go.GetComponent<NavMeshAgent>();
            avatar._anim = go.GetComponent<Animator>();
            avatar.AgentId = id;
            avatar.DisplayName = displayName;
            avatar._renderers = go.GetComponentsInChildren<Renderer>();
            avatar._mpb = new MaterialPropertyBlock();

            if (tint.HasValue) avatar.ApplyColor(tint.Value);

            // name tag only — dialogue now shows in the DirectorUI subtitle bar
            var nameBubble = SpeechBubble.Attach(go, NameHeight);
            nameBubble.Show(displayName, float.MaxValue);
            return avatar;
        }

        private void Update()
        {
            if (_anim == null || _nav == null) return;
            // Smoothed speed -> Animator blend (idle/walk/run).
            float target = _nav.velocity.magnitude;
            _animSpeed = Mathf.Lerp(_animSpeed, target, Time.deltaTime * 10f);
            _anim.SetFloat(SpeedHash, _animSpeed);
        }

        public void GoTo(Vector3 pos)
        {
            if (_nav != null && _nav.isOnNavMesh) _nav.SetDestination(pos);
            else transform.position = pos;
        }

        public void Say(string line) { /* dialogue is shown in the HUD subtitle bar */ }

        public void Cheer()
        {
            if (_anim != null && _anim.runtimeAnimatorController != null) _anim.SetTrigger(CheerHash);
        }

        // KayKit materials use a flat atlas with white "_Color", so highlight-off = white
        // restores the original look. (If a material ever uses a tinted "_Color", revisit this.)
        public void SetHighlight(bool on) => ApplyColor(on ? Color.yellow : Color.white);

        private void ApplyColor(Color c)
        {
            if (_renderers == null) return;
            foreach (var r in _renderers)
            {
                if (r == null) continue;
                r.GetPropertyBlock(_mpb);
                _mpb.SetColor(ColorId, c);
                r.SetPropertyBlock(_mpb);
            }
        }
    }
}
