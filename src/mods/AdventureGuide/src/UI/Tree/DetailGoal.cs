namespace AdventureGuide.UI.Tree;

internal enum DetailGoalKind : byte
{
    AcquireItem,
    CompleteQuest,
    UnlockSource,
    UseItemAction,
    SatisfyUnlockGroup,
}

internal readonly record struct DetailGoal(DetailGoalKind Kind, int NodeId, int? GroupId = null);
