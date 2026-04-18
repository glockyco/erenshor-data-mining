using AdventureGuide.Plan;

namespace AdventureGuide.Resolution;

/// <summary>
/// Canonical maintained-view record for one quest in one scene.
/// Shared across navigation, tracker, markers, and later detail projection.
/// </summary>
public sealed class QuestResolutionRecord
{
    public QuestResolutionRecord(
        string questKey,
        string currentScene,
        int questIndex,
        IReadOnlyList<FrontierEntry> frontier,
        IReadOnlyList<ResolvedTarget> compiledTargets,
        IReadOnlyList<ResolvedQuestTarget> navigationTargets
    )
    {
        QuestKey = questKey;
        CurrentScene = currentScene ?? string.Empty;
        QuestIndex = questIndex;
        Frontier = frontier;
        CompiledTargets = compiledTargets;
        NavigationTargets = navigationTargets;
    }

    public string QuestKey { get; }

    public string CurrentScene { get; }

    public int QuestIndex { get; }

    public IReadOnlyList<FrontierEntry> Frontier { get; }

    public IReadOnlyList<ResolvedTarget> CompiledTargets { get; }

    /// <summary>
    /// Pre-projected navigation view of <see cref="CompiledTargets"/>. Shared
    /// across navigation, marker, and tracker surfaces so there is exactly one
    /// cache entry per quest+scene for the projected form.
    /// </summary>
    public IReadOnlyList<ResolvedQuestTarget> NavigationTargets { get; }
}
