using UnityEngine;

namespace PuebloVivo
{
    /// <summary>
    /// Scatters environment props (trees, rocks, fences, barrels) around the village
    /// with a fixed seed so the layout is reproducible. Keeps clear of the building ring
    /// so it doesn't sit on the locations. Props ship at miniature scale, so they're
    /// enlarged to read next to the ~1.8u villagers.
    /// </summary>
    public static class EnvironmentDecorator
    {
        private const float PropScale = 2f;

        public static void Decorate(Transform parent, float layoutRadius, int count = 44, int seed = 1234)
        {
            var rng = new System.Random(seed);
            float inner = layoutRadius + 3f;   // outside the building ring
            float outer = layoutRadius + 13f;  // within the 60x60 ground
            for (int i = 0; i < count; i++)
            {
                var prop = EnvironmentCatalog.PropModels[rng.Next(EnvironmentCatalog.PropModels.Length)];
                var prefab = Resources.Load<GameObject>($"Environment/{prop}");
                if (prefab == null) continue;
                double ang = rng.NextDouble() * System.Math.PI * 2;
                double r = inner + rng.NextDouble() * (outer - inner);
                var pos = new Vector3((float)(System.Math.Cos(ang) * r), 0, (float)(System.Math.Sin(ang) * r));
                var go = Object.Instantiate(prefab, pos, Quaternion.Euler(0, rng.Next(360), 0), parent);
                go.transform.localScale = Vector3.one * PropScale;
                go.name = $"Decor_{prop}_{i}";
            }
        }
    }
}
