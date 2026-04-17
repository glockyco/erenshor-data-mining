namespace AdventureGuide.State;

/// <summary>
/// Structured runtime delta emitted by guide runtime state adapters.
/// Downstream systems consume typed fact changes plus coarse domain flags to
/// invalidate only the maintained views actually affected by an event.
/// </summary>
public sealed class GuideChangeSet
{
    public static readonly GuideChangeSet None = new(
        inventoryChanged: false,
        questLogChanged: false,
        sceneChanged: false,
        liveWorldChanged: false,
        changedItemKeys: Array.Empty<string>(),
        changedQuestDbNames: Array.Empty<string>(),
        affectedQuestKeys: Array.Empty<string>(),
        changedFacts: Array.Empty<GuideFactKey>()
    );

    public bool InventoryChanged { get; }
    public bool QuestLogChanged { get; }
    public bool SceneChanged { get; }
    public bool LiveWorldChanged { get; }

    public IReadOnlyCollection<string> ChangedItemKeys { get; }
    public IReadOnlyCollection<string> ChangedQuestDbNames { get; }
    public IReadOnlyCollection<string> AffectedQuestKeys { get; }
    public IReadOnlyCollection<GuideFactKey> ChangedFacts { get; }

    public bool HasMeaningfulChanges =>
        InventoryChanged
        || QuestLogChanged
        || SceneChanged
        || LiveWorldChanged
        || ChangedItemKeys.Count > 0
        || ChangedQuestDbNames.Count > 0
        || AffectedQuestKeys.Count > 0
        || ChangedFacts.Count > 0;

    public GuideChangeSet(
        bool inventoryChanged,
        bool questLogChanged,
        bool sceneChanged,
        bool liveWorldChanged,
        IEnumerable<string> changedItemKeys,
        IEnumerable<string> changedQuestDbNames,
        IEnumerable<string> affectedQuestKeys,
        IEnumerable<GuideFactKey> changedFacts
    )
    {
        InventoryChanged = inventoryChanged;
        QuestLogChanged = questLogChanged;
        SceneChanged = sceneChanged;
        LiveWorldChanged = liveWorldChanged;
        ChangedItemKeys = FreezeStrings(changedItemKeys, StringComparer.Ordinal);
        ChangedQuestDbNames = FreezeStrings(changedQuestDbNames, StringComparer.OrdinalIgnoreCase);
        AffectedQuestKeys = FreezeStrings(affectedQuestKeys, StringComparer.Ordinal);
        ChangedFacts = FreezeFacts(changedFacts);
    }

    public GuideChangeSet WithAffectedQuestKeys(IEnumerable<string> affectedQuestKeys) =>
        new(
            InventoryChanged,
            QuestLogChanged,
            SceneChanged,
            LiveWorldChanged,
            ChangedItemKeys,
            ChangedQuestDbNames,
            affectedQuestKeys,
            ChangedFacts
        );

    public GuideChangeSet Merge(GuideChangeSet other) =>
        new(
            InventoryChanged || other.InventoryChanged,
            QuestLogChanged || other.QuestLogChanged,
            SceneChanged || other.SceneChanged,
            LiveWorldChanged || other.LiveWorldChanged,
            ChangedItemKeys.Concat(other.ChangedItemKeys),
            ChangedQuestDbNames.Concat(other.ChangedQuestDbNames),
            AffectedQuestKeys.Concat(other.AffectedQuestKeys),
            ChangedFacts.Concat(other.ChangedFacts)
        );

    private static IReadOnlyCollection<string> FreezeStrings(
        IEnumerable<string> values,
        StringComparer comparer
    )
    {
        if (values == null)
            return Array.Empty<string>();

        var set = new HashSet<string>(comparer);
        foreach (var value in values)
        {
            if (!string.IsNullOrWhiteSpace(value))
                set.Add(value);
        }

        return set.Count == 0 ? Array.Empty<string>() : set.ToArray();
    }

    private static IReadOnlyCollection<GuideFactKey> FreezeFacts(IEnumerable<GuideFactKey> values)
    {
        if (values == null)
            return Array.Empty<GuideFactKey>();

        var set = new HashSet<GuideFactKey>();
        foreach (var value in values)
            set.Add(value);

        return set.Count == 0 ? Array.Empty<GuideFactKey>() : set.ToArray();
    }
}
