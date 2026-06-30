using System.Collections.Generic;

namespace PuebloVivo
{
    /// <summary>
    /// Maps a brain location name to a KayKit Medieval Hexagon model (the prefab name
    /// under Resources/Environment/). Null = no building (the area is decorated instead).
    /// Model names match the real FBX filenames in the imported pack.
    /// </summary>
    public static class EnvironmentCatalog
    {
        private static readonly Dictionary<string, string> ByLocation = new()
        {
            { "tavern", "building_tavern_red" },
            { "market", "building_market_yellow" },
            { "bakery", "building_windmill_blue" },   // mill ~ bakery (flour/bread)
            { "school", "building_church_green" },    // church ~ schoolhouse
            { "well",   "building_well_blue" },
            // "garden" and "plaza" have no building — decorated by EnvironmentDecorator.
        };

        // Villager homes alternate across house models + colours for variety.
        private static readonly string[] HomeModels =
        {
            "building_home_A_blue", "building_home_B_red",
            "building_home_A_green", "building_home_B_yellow",
            "building_home_A_red", "building_home_B_blue",
        };

        // Decorative props scattered by EnvironmentDecorator (real FBX names).
        public static readonly string[] PropModels =
        {
            "tree_single_A", "tree_single_B", "trees_A_medium", "trees_B_medium",
            "rock_single_A", "rock_single_C", "fence_wood_straight",
            "barrel", "crate_A_big", "sack", "wheelbarrow",
        };

        public static string ModelFor(string location)
        {
            if (string.IsNullOrEmpty(location)) return null;
            if (location.StartsWith("home_"))
            {
                int h = 0;
                foreach (char c in location) h = h * 31 + c;
                return HomeModels[(h & 0x7fffffff) % HomeModels.Length];
            }
            return ByLocation.TryGetValue(location, out var m) ? m : null;
        }

        public static IEnumerable<string> BuildingModels()
        {
            var seen = new HashSet<string>();
            foreach (var m in ByLocation.Values) if (seen.Add(m)) yield return m;
            foreach (var m in HomeModels) if (seen.Add(m)) yield return m;
        }
    }
}
