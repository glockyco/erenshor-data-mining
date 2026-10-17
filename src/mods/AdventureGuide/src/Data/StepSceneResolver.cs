using AdventureGuide.Navigation;

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
    /// Tries the step zone, target spawn location, then item source location.
    /// Returns null when the scene cannot be determined. Sources failing
    /// <paramref name="isSourceAvailable"/> are skipped.
    /// </summary>
    public static string? ResolveScene(
        QuestEntry quest,
        QuestStep step,
        GuideData data,
        Func<ItemSource, bool>? isSourceAvailable = null,
        Func<string, int>? countItem = null
    )
    {
        if (step.Location != null)
            return step.Location.Scene;

        // Try resolving zone_name to scene
        if (step.TargetType != "item" && step.ZoneName != null)
        {
            var scene = data.GetSceneName(step.ZoneName);
            if (scene != null)
                return scene;
        }

        // Check character target spawns — use the first matching scene
        if (
            step.TargetKey != null
            && data.CharacterSpawns.TryGetValue(step.TargetKey, out var spawns)
        )
        {
            if (spawns.Count > 0)
                return spawns[0].Scene;
        }

        var sources = ItemSourcePolicy.SourcesFor(quest, step);
        var source =
            step.TargetType == "item" && sources != null
                ? FindFirstLeafSource(sources, isSourceAvailable, countItem)
                : null;
        if (source?.AcquisitionKey != null)
            return source.CanonicalLocation?.Scene;
        var sourceKey = source?.SourceKey;
        if (sourceKey != null)
        {
            if (PositionedSource.TryParse(sourceKey, out var positioned))
                return positioned.Scene;

            if (
                data.CharacterSpawns.TryGetValue(sourceKey, out var srcSpawns)
                && srcSpawns.Count > 0
            )
                return srcSpawns[0].Scene;
        }

        return step.ZoneName == null ? null : data.GetSceneName(step.ZoneName);
    }

    /// <summary>
    /// Find the first obtainable source key for an item step.
    /// Skips quest_reward source keys (those point to the quest giver NPC,
    /// not the actual drop source) and recurses into children.
    /// </summary>
    public static string? FindFirstSourceKey(
        QuestEntry quest,
        QuestStep step,
        Func<ItemSource, bool>? isSourceAvailable = null,
        Func<string, int>? countItem = null
    )
    {
        if (step.TargetType != "item")
            return null;
        var sources = ItemSourcePolicy.SourcesFor(quest, step);
        return sources == null
            ? null
            : FindFirstLeafSource(sources, isSourceAvailable, countItem)?.MakeSourceId();
    }

    private static ItemSource? FindFirstLeafSource(
        List<ItemSource> sources,
        Func<ItemSource, bool>? isSourceAvailable,
        Func<string, int>? countItem
    )
    {
        foreach (var src in sources)
        {
            if (
                ItemSourcePolicy.IsRandomSource(src)
                || !ItemSourcePolicy.NeedsUsedItem(src, countItem, sources)
            )
                continue;
            if (isSourceAvailable != null && !isSourceAvailable(src))
                continue;

            // Container keys describe a reward or used item, not a spawn.
            if (
                !ItemSourcePolicy.IsStaticCandidate(src)
                || ItemSourcePolicy.HasPendingChildren(src, countItem)
            )
            {
                var childKey =
                    src.Children == null
                        ? null
                        : FindFirstLeafSource(src.Children, isSourceAvailable, countItem);
                if (childKey != null)
                    return childKey;
                continue;
            }

            if (src.AcquisitionKey != null)
            {
                if (src.CanonicalLocation?.Scene != null)
                    return src;
                continue;
            }
            if (src.SourceKey != null || src.Scene != null)
                return src;

            if (src.Children != null)
            {
                var childKey = FindFirstLeafSource(src.Children, isSourceAvailable, countItem);
                if (childKey != null)
                    return childKey;
            }
        }
        return null;
    }

    /// <summary>
    /// Check whether any source for an item step has spawns in the given scene.
    /// Recurses into children (quest_reward → transitive drop sources).
    /// For non-item steps, falls back to ResolveScene comparison.
    /// </summary>
    public static bool HasSourceInScene(
        QuestEntry quest,
        QuestStep step,
        GuideData data,
        string scene,
        Func<ItemSource, bool>? isSourceAvailable = null,
        Func<string, int>? countItem = null
    )
    {
        if (
            step.TargetType == "character"
            && step.TargetKey != null
            && data.CharacterSpawns.TryGetValue(step.TargetKey, out var spawns)
        )
            return spawns.Exists(sp =>
                string.Equals(sp.Scene, scene, StringComparison.OrdinalIgnoreCase)
            );
        if (step.TargetType != "item")
            return ResolveScene(quest, step, data, isSourceAvailable, countItem) is string s
                && string.Equals(s, scene, System.StringComparison.OrdinalIgnoreCase);
        var sources = ItemSourcePolicy.SourcesFor(quest, step);
        return sources != null
            && AnySourceInScene(sources, data, scene, isSourceAvailable, countItem);
    }

    private static bool AnySourceInScene(
        List<ItemSource> sources,
        GuideData data,
        string scene,
        Func<ItemSource, bool>? isSourceAvailable,
        Func<string, int>? countItem
    )
    {
        foreach (var src in sources)
        {
            if (
                ItemSourcePolicy.IsRandomSource(src)
                || !ItemSourcePolicy.NeedsUsedItem(src, countItem, sources)
            )
                continue;
            if (isSourceAvailable != null && !isSourceAvailable(src))
                continue;

            // Container source keys are not the places their children come from.
            if (
                !ItemSourcePolicy.IsStaticCandidate(src)
                || ItemSourcePolicy.HasPendingChildren(src, countItem)
            )
            {
                if (
                    src.Children != null
                    && AnySourceInScene(src.Children, data, scene, isSourceAvailable, countItem)
                )
                    return true;
                continue;
            }

            if (src.AcquisitionKey != null)
            {
                if (
                    string.Equals(
                        src.CanonicalLocation?.Scene,
                        scene,
                        StringComparison.OrdinalIgnoreCase
                    )
                )
                    return true;
                continue;
            }

            if (src.SourceKey != null)
            {
                if (PositionedSource.TryParse(src.SourceKey, out var positioned))
                {
                    if (
                        string.Equals(
                            positioned.Scene,
                            scene,
                            System.StringComparison.OrdinalIgnoreCase
                        )
                    )
                        return true;
                }
                else if (data.CharacterSpawns.TryGetValue(src.SourceKey, out var spawns))
                {
                    foreach (var sp in spawns)
                    {
                        if (
                            string.Equals(
                                sp.Scene,
                                scene,
                                System.StringComparison.OrdinalIgnoreCase
                            )
                        )
                            return true;
                    }
                }
            }
            if (
                src.Children != null
                && AnySourceInScene(src.Children, data, scene, isSourceAvailable, countItem)
            )
                return true;
        }
        return false;
    }
}
