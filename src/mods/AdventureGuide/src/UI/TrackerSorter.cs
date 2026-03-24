using AdventureGuide.Data;
using AdventureGuide.State;
using UnityEngine;

namespace AdventureGuide.UI;

/// <summary>
/// Sorts tracked quest DB names according to the selected TrackerSortMode.
/// Stateless helper — all context passed as parameters.
/// </summary>
internal static class TrackerSorter
{
    /// <summary>
    /// Sort <paramref name="quests"/> in place. The list contains DB names
    /// of tracked quests; GuideData provides quest metadata for comparisons.
    /// </summary>
    public static void Sort(
        List<string> quests,
        TrackerSortMode mode,
        GuideData data,
        QuestStateTracker state,
        Vector3? playerPos)
    {
        switch (mode)
        {
            case TrackerSortMode.Proximity:
                SortByProximity(quests, data, state, playerPos);
                break;
            case TrackerSortMode.Level:
                SortByLevel(quests, data);
                break;
            case TrackerSortMode.Alphabetical:
                SortAlphabetical(quests, data);
                break;
        }
    }

    // ── Proximity ────────────────────────────────────────────────────

    private static void SortByProximity(
        List<string> quests, GuideData data, QuestStateTracker state, Vector3? playerPos)
    {
        string currentScene = state.CurrentZone;

        quests.Sort((a, b) =>
        {
            var qa = data.GetByDBName(a);
            var qb = data.GetByDBName(b);
            if (qa == null || qb == null) return string.Compare(a, b, System.StringComparison.OrdinalIgnoreCase);

            bool aInZone = IsCurrentStepInZone(qa, state, data, currentScene);
            bool bInZone = IsCurrentStepInZone(qb, state, data, currentScene);

            // Current-zone quests come first
            if (aInZone != bInZone)
                return aInZone ? -1 : 1;

            // Within same zone group, sort by distance if we have player position
            if (aInZone && playerPos.HasValue)
            {
                float da = StepDistance(qa, state, data, currentScene, playerPos.Value);
                float db = StepDistance(qb, state, data, currentScene, playerPos.Value);
                int cmp = da.CompareTo(db);
                if (cmp != 0) return cmp;
            }

            // Fallback: alphabetical
            return string.Compare(
                qa.DisplayName, qb.DisplayName, System.StringComparison.OrdinalIgnoreCase);
        });
    }

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

        // Fall back to checking if step target has spawns in current scene
        if (step.TargetKey != null && data.CharacterSpawns.TryGetValue(step.TargetKey, out var spawns))
            return spawns.Exists(s => string.Equals(s.Scene, currentScene, System.StringComparison.OrdinalIgnoreCase));

        return false;
    }

    /// <summary>
    /// Estimate the distance from the player to the quest's current step
    /// target. Returns float.MaxValue if no position can be determined.
    /// </summary>
    private static float StepDistance(
        QuestEntry quest, QuestStateTracker state, GuideData data,
        string currentScene, Vector3 playerPos)
    {
        var step = GetCurrentStep(quest, state);
        if (step?.TargetKey == null) return float.MaxValue;

        if (!data.CharacterSpawns.TryGetValue(step.TargetKey, out var spawns) || spawns.Count == 0)
            return float.MaxValue;

        // Find nearest spawn in the current scene
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

    // ── Helpers ──────────────────────────────────────────────────────

    private static QuestStep? GetCurrentStep(QuestEntry quest, QuestStateTracker state)
    {
        if (quest.Steps == null || quest.Steps.Count == 0) return null;
        int idx = StepProgress.GetCurrentStepIndex(quest, state);
        return idx < quest.Steps.Count ? quest.Steps[idx] : null;
    }
}
