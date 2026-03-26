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

        // For item steps, check source NPC spawns or zone-level sources
        var sourceKey = FindFirstSourceKey(quest, step);
        if (sourceKey != null)
        {
            // Fishing sources encode the scene in the key (fishing:{scene})
            if (sourceKey.StartsWith("fishing:", System.StringComparison.Ordinal))
                return sourceKey.Substring("fishing:".Length);

            if (data.CharacterSpawns.TryGetValue(sourceKey, out var srcSpawns) && srcSpawns.Count > 0)
                return srcSpawns[0].Scene;
        }

        return null;
    }

    /// <summary>
    /// Find the first obtainable source key for an item step.
    /// Skips quest_reward source keys (those point to the quest giver NPC,
    /// not the actual drop source) and recurses into children.
    /// </summary>
    public static string? FindFirstSourceKey(QuestEntry quest, QuestStep step)
    {
        if (step.TargetType != "item" || quest.RequiredItems == null)
            return null;

        var item = quest.RequiredItems.Find(ri =>
            string.Equals(ri.ItemName, step.TargetName, System.StringComparison.OrdinalIgnoreCase));
        if (item?.Sources == null) return null;

        return FindFirstLeafSourceKey(item.Sources);
    }

    private static string? FindFirstLeafSourceKey(List<ItemSource> sources)
    {
        foreach (var src in sources)
        {
            // quest_reward: SourceKey is the quest giver, not an obtainable source.
            // Always recurse into children for actual drop/vendor sources.
            if (src.Type == "quest_reward" && src.Children is { Count: > 0 })
                return FindFirstLeafSourceKey(src.Children);

            if (src.SourceKey != null)
                return src.SourceKey;

            if (src.Children != null)
            {
                var childKey = FindFirstLeafSourceKey(src.Children);
                if (childKey != null) return childKey;
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
            // quest_reward: SourceKey is the quest giver NPC. The quest giver
            // being in-zone doesn't mean the item is obtainable here.
            // Skip to children which hold the actual obtainable sources.
            if (src.Type == "quest_reward" && src.Children is { Count: > 0 })
            {
                if (AnySourceInScene(src.Children, data, scene))
                    return true;
                continue;
            }

            if (src.SourceKey != null)
            {
                // Fishing sources: scene is encoded in the key
                if (src.SourceKey.StartsWith("fishing:", System.StringComparison.Ordinal))
                {
                    var fishScene = src.SourceKey.Substring("fishing:".Length);
                    if (string.Equals(fishScene, scene, System.StringComparison.OrdinalIgnoreCase))
                        return true;
                }
                else if (data.CharacterSpawns.TryGetValue(src.SourceKey, out var spawns))
                {
                    foreach (var sp in spawns)
                    {
                        if (string.Equals(sp.Scene, scene, System.StringComparison.OrdinalIgnoreCase))
                            return true;
                    }
                }
            }
            if (src.Children != null && AnySourceInScene(src.Children, data, scene))
                return true;
        }
        return false;
    }
}