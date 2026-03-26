namespace AdventureGuide.Data;

/// <summary>
/// Resolves the scene where a quest step takes place.
/// Shared by TrackerSorter (dynamic current step) and QuestStateTracker
/// (completion zone for implicit quest activation).
/// </summary>
public static class StepSceneResolver
{
    /// <summary>
    /// Resolve the scene name for a specific quest step.
    /// Tries step.ZoneName → target spawn location → item source NPC location.
    /// Returns null when the scene cannot be determined.
    /// </summary>
    public static string? ResolveScene(QuestEntry quest, QuestStep step, GuideData data)
    {
        // Try resolving zone_name to scene
        if (step.ZoneName != null)
        {
            var scene = data.GetSceneName(step.ZoneName);
            if (scene != null) return scene;
        }

        // Check character target spawns — use the first matching scene
        if (step.TargetKey != null && data.CharacterSpawns.TryGetValue(step.TargetKey, out var spawns))
        {
            if (spawns.Count > 0) return spawns[0].Scene;
        }

        // For item steps, check source NPC spawns
        var sourceKey = FindFirstSourceKey(quest, step);
        if (sourceKey != null && data.CharacterSpawns.TryGetValue(sourceKey, out var srcSpawns))
        {
            if (srcSpawns.Count > 0) return srcSpawns[0].Scene;
        }

        return null;
    }

    /// <summary>
    /// Find the first navigable source key for an item step by looking
    /// through the quest's RequiredItems sources.
    /// </summary>
    public static string? FindFirstSourceKey(QuestEntry quest, QuestStep step)
    {
        if (step.TargetType != "item" || quest.RequiredItems == null)
            return null;

        var item = quest.RequiredItems.Find(ri =>
            string.Equals(ri.ItemName, step.TargetName, System.StringComparison.OrdinalIgnoreCase));
        if (item?.Sources == null) return null;

        foreach (var src in item.Sources)
        {
            if (src.SourceKey != null)
                return src.SourceKey;
            // Recurse into children (e.g., crafted items with sub-sources)
            if (src.Children != null)
            {
                foreach (var child in src.Children)
                {
                    if (child.SourceKey != null)
                        return child.SourceKey;
                }
            }
        }
        return null;
    }

    /// <summary>
    /// Check whether any source for an item step has spawns in the given scene.
    /// Recurses into children (quest_reward → transitive drop sources).
    /// For non-item steps, falls back to ResolveScene comparison.
    /// </summary>
    public static bool HasSourceInScene(QuestEntry quest, QuestStep step, GuideData data, string scene)
    {
        if (step.TargetType != "item" || quest.RequiredItems == null)
            return ResolveScene(quest, step, data) is string s
                && string.Equals(s, scene, System.StringComparison.OrdinalIgnoreCase);

        var item = quest.RequiredItems.Find(ri =>
            string.Equals(ri.ItemName, step.TargetName, System.StringComparison.OrdinalIgnoreCase));
        if (item?.Sources == null) return false;

        return AnySourceInScene(item.Sources, data, scene);
    }

    private static bool AnySourceInScene(List<ItemSource> sources, GuideData data, string scene)
    {
        foreach (var src in sources)
        {
            if (src.SourceKey != null
                && data.CharacterSpawns.TryGetValue(src.SourceKey, out var spawns))
            {
                foreach (var sp in spawns)
                {
                    if (string.Equals(sp.Scene, scene, System.StringComparison.OrdinalIgnoreCase))
                        return true;
                }
            }
            if (src.Children != null && AnySourceInScene(src.Children, data, scene))
                return true;
        }
        return false;
    }
}