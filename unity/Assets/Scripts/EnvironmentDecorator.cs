using System.Collections.Generic;
using UnityEngine;

namespace PuebloVivo
{
    /// <summary>
    /// Scatters environment props (trees, rocks, fences, barrels) across the town with a
    /// fixed seed (reproducible), filling the space but skipping a radius around each
    /// building so nothing sits on a location. Props ship at miniature scale, so they're
    /// enlarged to read next to the ~1.8u villagers.
    /// </summary>
    public static class EnvironmentDecorator
    {
        private const float PropScale = 2f;

        public static void Decorate(Transform parent, ICollection<Vector3> avoid,
                                    float avoidRadius = 5f, int count = 80, float maxRadius = 29f, int seed = 1234)
        {
            var rng = new System.Random(seed);
            int placed = 0, tries = 0;
            while (placed < count && tries < count * 6)
            {
                tries++;
                double ang = rng.NextDouble() * System.Math.PI * 2;
                double r = 6 + rng.NextDouble() * (maxRadius - 6);
                var pos = new Vector3((float)(System.Math.Cos(ang) * r), 0, (float)(System.Math.Sin(ang) * r));
                bool tooClose = false;
                foreach (var a in avoid)
                    if ((a - pos).sqrMagnitude < avoidRadius * avoidRadius) { tooClose = true; break; }
                if (tooClose) continue;
                var prop = EnvironmentCatalog.PropModels[rng.Next(EnvironmentCatalog.PropModels.Length)];
                var prefab = Resources.Load<GameObject>($"Environment/{prop}");
                if (prefab == null) continue;
                var go = Object.Instantiate(prefab, pos, Quaternion.Euler(0, rng.Next(360), 0), parent);
                go.transform.localScale = Vector3.one * PropScale;
                go.name = $"Decor_{prop}_{placed}";
                placed++;
            }
        }
    }
}
