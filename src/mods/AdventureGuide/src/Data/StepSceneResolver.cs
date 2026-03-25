namespace AdventureGuide.Data;

/// <summary>
/// Resolves the scene where a quest step takes place.
/// Shared by TrackerSorter (dynamic current step) and QuestStateTracker
/// (static activation step for implicit quest zone-gating).
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
    /// Find the step index where a quest becomes actionable once all
    /// collect steps are satisfied. For quests with no items this is
    /// step 0. For item quests it's the first non-collect step.
    /// Returns 0 when the quest has no steps.
    /// </summary>
    public static int FindActivationStepIndex(QuestEntry quest)
    {
        if (quest.Steps == null || quest.Steps.Count == 0)
            return 0;

        for (int i = 0; i < quest.Steps.Count; i++)
        {
            if (quest.Steps[i].Action != "collect")
                return i;
        }

        // All steps are collect — point to last step
        return quest.Steps.Count - 1;
    }
}
