using System.Collections.Generic;

namespace PuebloVivo
{
    /// <summary>
    /// Single source of truth mapping a brain occupation to a KayKit model name.
    /// The model name is also the prefab name under Resources/Avatars/.
    /// </summary>
    public static class AvatarCatalog
    {
        public const string DefaultModel = "Knight";

        // occupation (from brain scenarios.py) -> KayKit model
        private static readonly Dictionary<string, string> ByOccupation = new()
        {
            { "innkeeper", "Mage" },        // maria (host)
            { "bartender", "Barbarian" },   // diego
            { "baker",     "Ranger" },      // lucia
            { "farmer",    "RogueHooded" }, // carlos
            { "teacher",   "Knight" },      // sofia
            { "merchant",  "Rogue" },       // pedro
            { "gardener",  "Ranger" },      // elena (7th; reuses Ranger, tinted)
        };

        public static string ModelFor(string occupation)
        {
            if (!string.IsNullOrEmpty(occupation) && ByOccupation.TryGetValue(occupation, out var m))
                return m;
            return DefaultModel;
        }

        /// <summary>Distinct model names that need a prefab built.</summary>
        public static IEnumerable<string> AllModels()
        {
            var seen = new HashSet<string>();
            foreach (var m in ByOccupation.Values)
                if (seen.Add(m)) yield return m;
            if (seen.Add(DefaultModel)) yield return DefaultModel;
        }
    }
}
