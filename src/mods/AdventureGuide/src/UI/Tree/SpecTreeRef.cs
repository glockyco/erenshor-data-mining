namespace AdventureGuide.UI.Tree;

public enum SpecTreeKind : byte
{
    Quest,
    Item,
    Character,
    Step,
    Group,
    Giver,
    Completer,
    Prerequisite,
    Source,
}

public readonly struct SpecTreeRef
{
    private SpecTreeRef(
        string stableId,
        int? graphNodeId,
        SpecTreeKind kind,
        int questIndex,
        string displayName,
        string label,
        bool isCompleted,
        bool isBlocked,
        int? blockedByGraphNodeId = null,
        int[]? ancestry = null,
        SpecTreeRef[]? syntheticChildren = null,
        bool requiresVisibleChildren = false
    )
    {
        StableId = stableId;
        GraphNodeId = graphNodeId;
        Kind = kind;
        QuestIndex = questIndex;
        DisplayName = displayName;
        Label = label;
        IsCompleted = isCompleted;
        IsBlocked = isBlocked;
        BlockedByGraphNodeId = blockedByGraphNodeId;
        Ancestry = ancestry ?? Array.Empty<int>();
        SyntheticChildren = syntheticChildren;
        RequiresVisibleChildren = requiresVisibleChildren;
    }

    public static SpecTreeRef ForGraphNode(
        int graphNodeId,
        SpecTreeKind kind,
        int questIndex,
        string displayName,
        string label,
        bool isCompleted,
        bool isBlocked,
        int? blockedByGraphNodeId = null,
        int[]? ancestry = null,
        SpecTreeRef[]? syntheticChildren = null,
        bool requiresVisibleChildren = false
    ) =>
        new(
            $"node:{graphNodeId}",
            graphNodeId,
            kind,
            questIndex,
            displayName,
            label,
            isCompleted,
            isBlocked,
            blockedByGraphNodeId,
            ancestry,
            syntheticChildren,
            requiresVisibleChildren
        );

    public static SpecTreeRef ForSynthetic(
        string stableId,
        SpecTreeKind kind,
        int questIndex,
        string displayName,
        string label,
        bool isCompleted,
        bool isBlocked,
        int? blockedByGraphNodeId = null,
        int[]? ancestry = null,
        SpecTreeRef[]? syntheticChildren = null,
        bool requiresVisibleChildren = false
    ) =>
        new(
            stableId,
            null,
            kind,
            questIndex,
            displayName,
            label,
            isCompleted,
            isBlocked,
            blockedByGraphNodeId,
            ancestry,
            syntheticChildren,
            requiresVisibleChildren
        );

    public string StableId { get; }
    public int? GraphNodeId { get; }
    public SpecTreeKind Kind { get; }
    public int QuestIndex { get; }
    public string DisplayName { get; }
    public string Label { get; }
    public bool IsCompleted { get; }
    public bool IsBlocked { get; }
    public int? BlockedByGraphNodeId { get; }
    public int[] Ancestry { get; }
    public SpecTreeRef[]? SyntheticChildren { get; }
    public bool RequiresVisibleChildren { get; }
}
