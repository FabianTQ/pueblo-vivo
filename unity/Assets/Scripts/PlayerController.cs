using UnityEngine;

namespace PuebloVivo
{
    /// <summary>
    /// First/third-person-ish player movement and proximity detection. Movement is
    /// disabled while in director mode. The nearest agent within range is highlighted
    /// and becomes the target for player dialogue (sent by the UI).
    /// </summary>
    [RequireComponent(typeof(CharacterController))]
    public class PlayerController : MonoBehaviour
    {
        public VillageController village;
        public float speed = 6f;
        public float interactRange = 4f;

        public bool DirectorMode { get; set; }
        public AgentAvatar Nearest { get; private set; }

        private CharacterController _cc;

        private void Awake()
        {
            _cc = GetComponent<CharacterController>();
            if (village == null) village = FindObjectOfType<VillageController>();
        }

        private void Update()
        {
            if (!DirectorMode)
            {
                float h = Input.GetAxisRaw("Horizontal");
                float v = Input.GetAxisRaw("Vertical");
                var move = new Vector3(h, 0, v);
                if (move.sqrMagnitude > 1f) move.Normalize();
                _cc.SimpleMove(move * speed);
            }
            UpdateNearest();
        }

        private void UpdateNearest()
        {
            if (village == null) return;
            AgentAvatar best = null;
            float bestDist = interactRange;
            foreach (var kv in village.Agents)
            {
                var a = kv.Value;
                if (a == null) continue;
                float d = Vector3.Distance(transform.position, a.transform.position);
                if (d < bestDist) { bestDist = d; best = a; }
            }
            if (best != Nearest)
            {
                Nearest?.SetHighlight(false);
                Nearest = best;
                Nearest?.SetHighlight(true);
            }
        }
    }
}
