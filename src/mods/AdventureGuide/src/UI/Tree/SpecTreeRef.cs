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
    public SpecTreeRef(
        int nodeId,
        SpecTreeKind kind,
        int questIndex,
        string displayName,
        string label,
        bool isCompleted,
        bool isBlocked,
        int? blockedByNodeId = null,
        int[]? ancestry = null,
        SpecTreeRef[]? syntheticChildren = null)
    {
        NodeId = nodeId;
        Kind = kind;
        QuestIndex = questIndex;
        DisplayName = displayName;
        Label = label;
        IsCompleted = isCompleted;
        IsBlocked = isBlocked;
        BlockedByNodeId = blockedByNodeId;
        Ancestry = ancestry ?? Array.Empty<int>();
        SyntheticChildren = syntheticChildren;
    }

    public int NodeId { get; }
    public SpecTreeKind Kind { get; }
    public int QuestIndex { get; }
    public string DisplayName { get; }
    public string Label { get; }
    public bool IsCompleted { get; }
    public bool IsBlocked { get; }
    public int? BlockedByNodeId { get; }
    public int[] Ancestry { get; }
    public SpecTreeRef[]? SyntheticChildren { get; }
}
