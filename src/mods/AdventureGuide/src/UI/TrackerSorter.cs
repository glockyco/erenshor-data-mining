using AdventureGuide.Data;
using AdventureGuide.Navigation;
using AdventureGuide.State;
using UnityEngine;

namespace AdventureGuide.UI;

/// <summary>
/// Computes per-quest distances and sorts tracked quest runtime keys.
/// Distances are computed once per cycle and reused for both sorting
/// and display — avoiding redundant spawn lookups in sort comparators.
/// </summary>
internal static class TrackerSorter
{
    /// <summary>
    /// Result from source distance computation. Carries both the distance
    /// and an optional display label for zone-level sources (e.g. "Fishing").
    /// </summary>
    private readonly struct SourceDistance
    {
        public readonly float Meters;
        public readonly string? Label;

        public SourceDistance(float meters, string? label = null)
        {
            Meters = meters;
            Label = label;
        }

        public static SourceDistance None => new(float.MaxValue);

        /// <summary>
        /// Pick the better of two results. Labeled sources (zone-level,
        /// already available) always beat unlabeled positional sources —
        /// "available right here" is better than "N meters away".
        /// Among two positional sources, pick the closer one.
        /// </summary>
        public static SourceDistance Best(SourceDistance a, SourceDistance b)
        {
            // Labeled (zone-level) beats unlabeled (positional)
            if (a.Label != null && b.Label == null)
                return a;
            if (b.Label != null && a.Label == null)
                return b;
            return a.Meters <= b.Meters ? a : b;
        }
    }

    /// <summary>
    /// Compute distance from the player to each quest's current step target.
    /// </summary>
    public static void ComputeDistances(
        IReadOnlyList<string> quests,
        GuideData data,
        QuestStateTracker state,
        NavigationTarget? navigationTarget,
        float navigationDistance,
        Vector3 playerPos,
        Dictionary<string, StepDistance> output
    )
    {
        output.Clear();
        string currentScene = state.CurrentZone;

        for (int i = 0; i < quests.Count; i++)
        {
            var questKey = quests[i];
            var quest = data.GetByRuntimeKey(questKey);
            if (quest == null)
            {
                output[questKey] = new StepDistance(false, float.MaxValue);
                continue;
            }

            // When actively navigating this quest, use live nav distance.
            if (
                navigationTarget != null
                && string.Equals(
                    navigationTarget.QuestKey,
                    questKey,
                    System.StringComparison.OrdinalIgnoreCase
                )
            )
            {
                bool inZone = !navigationTarget.IsCrossZone(currentScene);
                // Zone targets (fishing) are in the current zone but have
                // no specific position — show a label instead of meters.
                if (inZone && navigationTarget.TargetKind == NavigationTarget.Kind.Zone)
                {
                    string? label =
                        navigationTarget.SourceId != null
                        && navigationTarget.SourceId.StartsWith(
                            "fishing:",
                            System.StringComparison.Ordinal
                        )
                            ? "Fishing"
                            : null;
                    output[questKey] = new StepDistance(true, float.MaxValue, label);
                }
                else
                {
                    float meters = inZone ? navigationDistance : float.MaxValue;
                    output[questKey] = new StepDistance(inZone, meters);
                }
                continue;
            }

            bool stepInZone = IsCurrentStepInZone(quest, state, data, currentScene);
            if (!stepInZone)
            {
                output[questKey] = new StepDistance(false, float.MaxValue);
                continue;
            }

            var sd = ComputeStepDistance(quest, state, data, currentScene, playerPos);
            output[questKey] = new StepDistance(true, sd.Meters, sd.Label);
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
        IReadOnlyDictionary<string, StepDistance>? distances
    )
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
        List<string> quests,
        GuideData data,
        IReadOnlyDictionary<string, StepDistance> distances
    )
    {
        quests.Sort(
            (a, b) =>
            {
                var da = distances.TryGetValue(a, out var va)
                    ? va
                    : new StepDistance(false, float.MaxValue);
                var db = distances.TryGetValue(b, out var vb)
                    ? vb
                    : new StepDistance(false, float.MaxValue);

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
                    if (cmp != 0)
                        return cmp;
                }

                // Fallback: alphabetical
                var qa = data.GetByRuntimeKey(a);
                var qb = data.GetByRuntimeKey(b);
                return string.Compare(
                    qa?.DisplayName,
                    qb?.DisplayName,
                    System.StringComparison.OrdinalIgnoreCase
                );
            }
        );
    }

    // ── Level ────────────────────────────────────────────────────────

    private static void SortByLevel(List<string> quests, GuideData data)
    {
        quests.Sort(
            (a, b) =>
            {
                var qa = data.GetByRuntimeKey(a);
                var qb = data.GetByRuntimeKey(b);
                int la = qa?.LevelEstimate?.Recommended ?? int.MaxValue;
                int lb = qb?.LevelEstimate?.Recommended ?? int.MaxValue;
                int cmp = la.CompareTo(lb);
                if (cmp != 0)
                    return cmp;
                return string.Compare(
                    qa?.DisplayName,
                    qb?.DisplayName,
                    System.StringComparison.OrdinalIgnoreCase
                );
            }
        );
    }

    // ── Alphabetical ─────────────────────────────────────────────────

    private static void SortAlphabetical(List<string> quests, GuideData data)
    {
        quests.Sort(
            (a, b) =>
            {
                var qa = data.GetByRuntimeKey(a);
                var qb = data.GetByRuntimeKey(b);
                return string.Compare(
                    qa?.DisplayName ?? a,
                    qb?.DisplayName ?? b,
                    System.StringComparison.OrdinalIgnoreCase
                );
            }
        );
    }

    // ── Distance helpers ─────────────────────────────────────────────

    /// <summary>
    /// Return the display zone name for a quest's current step, or null
    /// if the zone cannot be determined. Used by the tracker to show
    /// "Travel to {zone}" for cross-zone entries.
    /// </summary>
    public static string? GetStepZoneName(QuestEntry quest, QuestStateTracker state, GuideData data)
    {
        var raw = GetCurrentStep(quest, state, data);
        if (raw == null)
            return null;
        var (step, resolvedQuest) = StepProgress.ResolveActiveStep(raw, quest, state, data);
        if (step == null)
            return null;
        var scene = StepSceneResolver.ResolveScene(
            resolvedQuest ?? quest,
            step,
            data,
            state.IsGameQuestCompleted
        );
        return scene != null ? data.GetZoneDisplayName(scene) : null;
    }

    /// <summary>
    /// Check if the quest's current step takes place in the current scene.
    /// </summary>
    private static bool IsCurrentStepInZone(
        QuestEntry quest,
        QuestStateTracker state,
        GuideData data,
        string currentScene
    )
    {
        var raw = GetCurrentStep(quest, state, data);
        if (raw == null)
            return false;
        var (step, resolvedQuest) = StepProgress.ResolveActiveStep(raw, quest, state, data);
        if (step == null)
            return false;
        return StepSceneResolver.HasSourceInScene(
            resolvedQuest ?? quest,
            step,
            data,
            currentScene,
            state.IsGameQuestCompleted
        );
    }

    private static SourceDistance ComputeStepDistance(
        QuestEntry quest,
        QuestStateTracker state,
        GuideData data,
        string currentScene,
        Vector3 playerPos
    )
    {
        var raw = GetCurrentStep(quest, state, data);
        if (raw == null)
            return SourceDistance.None;

        var (step, resolvedQuest) = StepProgress.ResolveActiveStep(raw, quest, state, data);
        if (step == null)
            return SourceDistance.None;
        var effectiveQuest = resolvedQuest ?? quest;

        if (
            step.Location != null
            && StepSceneResolver.ResolveScene(
                effectiveQuest,
                step,
                data,
                state.IsGameQuestCompleted
            )
                is string locationScene
            && string.Equals(locationScene, currentScene, System.StringComparison.OrdinalIgnoreCase)
        )
        {
            return new SourceDistance(
                Vector3.Distance(
                    playerPos,
                    new Vector3(step.Location.X, step.Location.Y, step.Location.Z)
                )
            );
        }

        // Try character target directly (talk, kill, turn_in steps)
        string? key = step.TargetKey;
        if (key != null && step.TargetType == "character" && data.CharacterSpawns.ContainsKey(key))
            return NearestSpawnDistance(data, key, currentScene, playerPos);

        // For item steps, check ALL sources for the closest in-zone spawn
        if (step.TargetType == "item" && effectiveQuest.RequiredItems != null)
        {
            var item = effectiveQuest.RequiredItems.Find(ri =>
                string.Equals(
                    ri.ItemName,
                    step.TargetName,
                    System.StringComparison.OrdinalIgnoreCase
                )
            );
            if (item?.Sources != null)
                return NearestSourceDistance(item.Sources, data, state, currentScene, playerPos);
        }

        return SourceDistance.None;
    }

    /// <summary>
    /// Find the nearest spawn among ALL sources (recursing into children) in the current scene.
    /// </summary>
    private static SourceDistance NearestSourceDistance(
        List<ItemSource> sources,
        GuideData data,
        QuestStateTracker state,
        string currentScene,
        Vector3 playerPos
    )
    {
        var best = SourceDistance.None;
        foreach (var src in sources)
        {
            if (
                src.RequiredQuestDBNames != null
                && !src.RequiredQuestDBNames.TrueForAll(state.IsGameQuestCompleted)
            )
                continue;

            // quest_reward: SourceKey is the quest giver, not an obtainable source.
            if (src.Type == "quest_reward" && src.Children is { Count: > 0 })
            {
                best = SourceDistance.Best(
                    best,
                    NearestSourceDistance(src.Children, data, state, currentScene, playerPos)
                );
                continue;
            }

            if (src.SourceKey != null)
                best = SourceDistance.Best(
                    best,
                    NearestSpawnDistance(data, src.SourceKey, currentScene, playerPos)
                );
            if (src.Children != null)
                best = SourceDistance.Best(
                    best,
                    NearestSourceDistance(src.Children, data, state, currentScene, playerPos)
                );
        }
        return best;
    }

    private static SourceDistance NearestSpawnDistance(
        GuideData data,
        string key,
        string currentScene,
        Vector3 playerPos
    )
    {
        // Fishing sources are zone-level — no specific position.
        // In the fishing zone: report as available with label. Otherwise: unreachable.
        if (key.StartsWith("fishing:", System.StringComparison.Ordinal))
        {
            var fishScene = key.Substring("fishing:".Length);
            return string.Equals(fishScene, currentScene, System.StringComparison.OrdinalIgnoreCase)
                ? new SourceDistance(float.MaxValue, "Fishing")
                : SourceDistance.None;
        }

        if (!data.CharacterSpawns.TryGetValue(key, out var spawns) || spawns.Count == 0)
            return SourceDistance.None;

        float best = float.MaxValue;
        foreach (var sp in spawns)
        {
            if (!string.Equals(sp.Scene, currentScene, System.StringComparison.OrdinalIgnoreCase))
                continue;
            float d = Vector3.Distance(playerPos, new Vector3(sp.X, sp.Y, sp.Z));
            if (d < best)
                best = d;
        }
        return new SourceDistance(best);
    }

    // ── Helpers ──────────────────────────────────────────────────────

    private static QuestStep? GetCurrentStep(
        QuestEntry quest,
        QuestStateTracker state,
        GuideData data
    )
    {
        if (quest.Steps == null || quest.Steps.Count == 0)
            return null;
        int idx = StepProgress.GetCurrentStepIndex(quest, state, data);
        return idx >= 0 && idx < quest.Steps.Count ? quest.Steps[idx] : null;
    }
}
