using AdventureGuide.Data;
using AdventureGuide.Navigation;
using AdventureGuide.State;
using UnityEngine;

namespace AdventureGuide.UI;

/// <summary>
/// Computes per-quest distances and sorts tracked quest DB names.
/// Distances are computed once per cycle and reused for both sorting
/// and display — avoiding redundant spawn lookups in sort comparators.
/// </summary>
internal static class TrackerSorter
{
    /// <summary>
    /// Compute distance from the player to each quest's current step target.
    /// Quests whose step is not in the current zone (or has no resolvable
    /// position) get <see cref="float.MaxValue"/>.
    /// </summary>
    public static void ComputeDistances(
        IReadOnlyList<string> quests,
        GuideData data,
        QuestStateTracker state,
        NavigationController nav,
        Vector3 playerPos,
        Dictionary<string, float> output)
    {
        output.Clear();
        string currentScene = state.CurrentZone;

        for (int i = 0; i < quests.Count; i++)
        {
            var dbName = quests[i];
            var quest = data.GetByDBName(dbName);
            if (quest == null)
            {
                output[dbName] = float.MaxValue;
                continue;
            }

            // When the player is actively navigating to a specific source
            // for this quest, use the live nav distance (accounts for zone
            // line routing) instead of the default spawn-based estimate.
            if (nav.Target != null
                && string.Equals(nav.Target.QuestDBName, dbName, System.StringComparison.OrdinalIgnoreCase))
            {
                output[dbName] = nav.Distance;
                continue;
            }

            if (!IsCurrentStepInZone(quest, state, data, currentScene))
            {
                output[dbName] = float.MaxValue;
                continue;
            }

            output[dbName] = StepDistance(quest, state, data, currentScene, playerPos);
        }
    }

    /// <summary>
    /// Sort <paramref name="quests"/> in place. Proximity mode uses
    /// precomputed <paramref name="distances"/>; other modes ignore it.
    /// </summary>
    public static void Sort(
        List<string> quests,
        TrackerSortMode mode,
        GuideData data,
        IReadOnlyDictionary<string, float>? distances)
    {
        switch (mode)
        {
            case TrackerSortMode.Proximity when distances != null:
                SortByProximity(quests, data, distances);
                break;
            case TrackerSortMode.Level:
                SortByLevel(quests, data);
                break;
            default: // Alphabetical, or Proximity without position data
                SortAlphabetical(quests, data);
                break;
        }
    }

    // ── Proximity ────────────────────────────────────────────────────

    private static void SortByProximity(
        List<string> quests, GuideData data, IReadOnlyDictionary<string, float> distances)
    {
        quests.Sort((a, b) =>
        {
            float da = distances.TryGetValue(a, out float va) ? va : float.MaxValue;
            float db = distances.TryGetValue(b, out float vb) ? vb : float.MaxValue;

            bool aInZone = da < float.MaxValue;
            bool bInZone = db < float.MaxValue;

            // Current-zone quests come first
            if (aInZone != bInZone)
                return aInZone ? -1 : 1;

            // Within same zone group, sort by distance
            if (aInZone)
            {
                int cmp = da.CompareTo(db);
                if (cmp != 0) return cmp;
            }

            // Fallback: alphabetical
            var qa = data.GetByDBName(a);
            var qb = data.GetByDBName(b);
            return string.Compare(
                qa?.DisplayName, qb?.DisplayName, System.StringComparison.OrdinalIgnoreCase);
        });
    }

    // ── Level ────────────────────────────────────────────────────────

    private static void SortByLevel(List<string> quests, GuideData data)
    {
        quests.Sort((a, b) =>
        {
            var qa = data.GetByDBName(a);
            var qb = data.GetByDBName(b);
            int la = qa?.LevelEstimate?.Recommended ?? int.MaxValue;
            int lb = qb?.LevelEstimate?.Recommended ?? int.MaxValue;
            int cmp = la.CompareTo(lb);
            if (cmp != 0) return cmp;
            return string.Compare(
                qa?.DisplayName, qb?.DisplayName, System.StringComparison.OrdinalIgnoreCase);
        });
    }

    // ── Alphabetical ─────────────────────────────────────────────────

    private static void SortAlphabetical(List<string> quests, GuideData data)
    {
        quests.Sort((a, b) =>
        {
            var qa = data.GetByDBName(a);
            var qb = data.GetByDBName(b);
            return string.Compare(
                qa?.DisplayName ?? a, qb?.DisplayName ?? b,
                System.StringComparison.OrdinalIgnoreCase);
        });
    }

    // ── Distance helpers ─────────────────────────────────────────────

    /// <summary>
    /// Check if the quest's current step takes place in the current scene.
    /// Uses the step's ZoneName (display) resolved to scene via GuideData,
    /// or falls back to checking spawn positions of the step's target.
    /// </summary>
    private static bool IsCurrentStepInZone(
        QuestEntry quest, QuestStateTracker state, GuideData data, string currentScene)
    {
        var step = GetCurrentStep(quest, state);
        if (step == null) return false;

        // Try resolving zone_name to scene
        if (step.ZoneName != null)
        {
            var scene = data.GetSceneName(step.ZoneName);
            if (scene != null)
                return string.Equals(scene, currentScene, System.StringComparison.OrdinalIgnoreCase);
        }

        // Check character target spawns
        if (step.TargetKey != null && data.CharacterSpawns.TryGetValue(step.TargetKey, out var spawns))
            return spawns.Exists(s => string.Equals(s.Scene, currentScene, System.StringComparison.OrdinalIgnoreCase));

        // For item steps, check source NPC spawns
        var sourceKey = FindFirstSourceKey(quest, step);
        if (sourceKey != null && data.CharacterSpawns.TryGetValue(sourceKey, out var srcSpawns))
            return srcSpawns.Exists(s => string.Equals(s.Scene, currentScene, System.StringComparison.OrdinalIgnoreCase));

        return false;
    }

    private static float StepDistance(
        QuestEntry quest, QuestStateTracker state, GuideData data,
        string currentScene, Vector3 playerPos)
    {
        var step = GetCurrentStep(quest, state);
        if (step == null) return float.MaxValue;

        // Try character target directly
        string? key = step.TargetKey;
        if (key != null && data.CharacterSpawns.ContainsKey(key))
            return NearestSpawnDistance(data, key, currentScene, playerPos);

        // For item steps, use the first source NPC
        var sourceKey = FindFirstSourceKey(quest, step);
        if (sourceKey != null)
            return NearestSpawnDistance(data, sourceKey, currentScene, playerPos);

        return float.MaxValue;
    }

    private static float NearestSpawnDistance(
        GuideData data, string key, string currentScene, Vector3 playerPos)
    {
        if (!data.CharacterSpawns.TryGetValue(key, out var spawns) || spawns.Count == 0)
            return float.MaxValue;

        float best = float.MaxValue;
        foreach (var sp in spawns)
        {
            if (!string.Equals(sp.Scene, currentScene, System.StringComparison.OrdinalIgnoreCase))
                continue;
            float d = Vector3.Distance(playerPos, new Vector3(sp.X, sp.Y, sp.Z));
            if (d < best) best = d;
        }
        return best;
    }

    /// <summary>
    /// Find the first navigable source key for an item step by looking
    /// through the quest's RequiredItems sources.
    /// </summary>
    private static string? FindFirstSourceKey(QuestEntry quest, QuestStep step)
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

    // ── Helpers ──────────────────────────────────────────────────────

    private static QuestStep? GetCurrentStep(QuestEntry quest, QuestStateTracker state)
    {
        if (quest.Steps == null || quest.Steps.Count == 0) return null;
        int idx = StepProgress.GetCurrentStepIndex(quest, state);
        return idx < quest.Steps.Count ? quest.Steps[idx] : null;
    }
}
