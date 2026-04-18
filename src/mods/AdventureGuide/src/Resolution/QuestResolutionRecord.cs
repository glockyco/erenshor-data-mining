using AdventureGuide.Plan;

namespace AdventureGuide.Resolution;

/// <summary>
/// Canonical maintained-view record for one quest in one scene.
/// Shared across navigation, tracker, markers, and later detail projection.
/// </summary>
public sealed class QuestResolutionRecord
{
    private readonly QuestPhase[] _questPhases;
    private readonly int[] _itemCounts;
    private readonly IReadOnlyDictionary<string, int> _blockingZoneLineByScene;

    public QuestResolutionRecord(
        string questKey,
        string currentScene,
        int questIndex,
        IReadOnlyList<FrontierEntry> frontier,
        IReadOnlyList<ResolvedTarget> compiledTargets,
        IReadOnlyList<ResolvedQuestTarget> navigationTargets,
        IReadOnlyList<QuestPhase> questPhases,
        IReadOnlyList<int> itemCounts,
        IReadOnlyDictionary<string, int> blockingZoneLineByScene
    )
    {
        QuestKey = questKey;
        CurrentScene = currentScene ?? string.Empty;
        QuestIndex = questIndex;
        Frontier = frontier;
        CompiledTargets = compiledTargets;
        NavigationTargets = navigationTargets;
        _questPhases = questPhases.ToArray();
        _itemCounts = itemCounts.ToArray();
        _blockingZoneLineByScene = blockingZoneLineByScene;
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

    public QuestPhase GetQuestPhase(int questIndex) =>
        questIndex >= 0 && questIndex < _questPhases.Length
            ? _questPhases[questIndex]
            : QuestPhase.NotReady;

    public bool IsQuestCompleted(int questIndex) => GetQuestPhase(questIndex) == QuestPhase.Completed;

    public int GetItemCount(int itemIndex) =>
        itemIndex >= 0 && itemIndex < _itemCounts.Length ? _itemCounts[itemIndex] : 0;

    public bool TryGetBlockingZoneLineNodeId(string? targetScene, out int zoneLineNodeId)
    {
        zoneLineNodeId = default;
        if (string.IsNullOrWhiteSpace(targetScene))
            return false;

        return _blockingZoneLineByScene.TryGetValue(targetScene, out zoneLineNodeId);
    }
}
