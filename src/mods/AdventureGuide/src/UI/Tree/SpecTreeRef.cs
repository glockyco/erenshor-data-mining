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
        bool isCompleted,
        bool isBlocked)
    {
        NodeId = nodeId;
        Kind = kind;
        QuestIndex = questIndex;
        DisplayName = displayName;
        IsCompleted = isCompleted;
        IsBlocked = isBlocked;
    }

    public int NodeId { get; }
    public SpecTreeKind Kind { get; }
    public int QuestIndex { get; }
    public string DisplayName { get; }
    public bool IsCompleted { get; }
    public bool IsBlocked { get; }
}
