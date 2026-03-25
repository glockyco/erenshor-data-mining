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
    /// </summary>
    public static void ComputeDistances(
        IReadOnlyList<string> quests,
        GuideData data,
        QuestStateTracker state,
        NavigationController nav,
        Vector3 playerPos,
        Dictionary<string, StepDistance> output)
    {
        output.Clear();
        string currentScene = state.CurrentZone;

        for (int i = 0; i < quests.Count; i++)
        {
            var dbName = quests[i];
            var quest = data.GetByDBName(dbName);
            if (quest == null)
            {
                output[dbName] = new StepDistance(false, float.MaxValue);
                continue;
            }

            // When actively navigating this quest, use live nav distance.
            if (nav.Target != null
                && string.Equals(nav.Target.QuestDBName, dbName, System.StringComparison.OrdinalIgnoreCase))
            {
                bool inZone = !nav.Target.IsCrossZone(currentScene);
                // Zone targets (fishing) are in the current zone but have
                // no specific position. Cross-zone targets show "Travel to"
                // without a distance — the zone line distance would confuse.
                float meters = inZone && nav.Target.TargetKind != NavigationTarget.Kind.Zone
                    ? nav.Distance
                    : float.MaxValue;
                output[dbName] = new StepDistance(inZone, meters);
                continue;
            }

            bool stepInZone = IsCurrentStepInZone(quest, state, data, currentScene);
            if (!stepInZone)
            {
                output[dbName] = new StepDistance(false, float.MaxValue);
                continue;
            }

            output[dbName] = new StepDistance(true,
                ComputeStepMeters(quest, state, data, currentScene, playerPos));
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
        IReadOnlyDictionary<string, StepDistance>? distances)
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
        List<string> quests, GuideData data, IReadOnlyDictionary<string, StepDistance> distances)
    {
        quests.Sort((a, b) =>
        {
            var da = distances.TryGetValue(a, out var va) ? va : new StepDistance(false, float.MaxValue);
            var db = distances.TryGetValue(b, out var vb) ? vb : new StepDistance(false, float.MaxValue);

            // Current-zone quests come first
            if (da.InCurrentZone != db.InCurrentZone)
                return da.InCurrentZone ? -1 : 1;

            // Within same zone group, sort by distance.
            // No-position entries (e.g. fishing) sort as closest (0m).
            if (da.InCurrentZone)
            {
                float ma = da.HasDistance ? da.Meters : 0f;
                float mb = db.HasDistance ? db.Meters : 0f;
                int cmp = ma.CompareTo(mb);
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
    /// Return the display zone name for a quest's current step, or null
    /// if the zone cannot be determined. Used by the tracker to show
    /// "Travel to {zone}" for cross-zone entries.
    /// </summary>
    public static string? GetStepZoneName(
        QuestEntry quest, QuestStateTracker state, GuideData data)
    {
        var step = GetCurrentStep(quest, state);
        if (step == null) return null;
        var scene = StepSceneResolver.ResolveScene(quest, step, data);
        return scene != null ? data.GetZoneDisplayName(scene) : null;
    }

    /// <summary>
    /// Check if the quest's current step takes place in the current scene.
    /// </summary>
    private static bool IsCurrentStepInZone(
        QuestEntry quest, QuestStateTracker state, GuideData data, string currentScene)
    {
        var step = GetCurrentStep(quest, state);
        if (step == null) return false;
        var scene = StepSceneResolver.ResolveScene(quest, step, data);
        return scene != null && string.Equals(scene, currentScene, System.StringComparison.OrdinalIgnoreCase);
    }

    private static float ComputeStepMeters(
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
        var sourceKey = StepSceneResolver.FindFirstSourceKey(quest, step);
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

    // ── Helpers ──────────────────────────────────────────────────────

    private static QuestStep? GetCurrentStep(QuestEntry quest, QuestStateTracker state)
    {
        if (quest.Steps == null || quest.Steps.Count == 0) return null;
        int idx = StepProgress.GetCurrentStepIndex(quest, state);
        return idx < quest.Steps.Count ? quest.Steps[idx] : null;
    }
}