namespace AdventureGuide.UI.Tree;

internal enum DetailPruneReason : byte
{
    None,
    AncestorCycle,
    NoAcquisitionSource,
    RequiredChildPruned,
    NoUnlockAlternative,
    NoCompleterPath,
    EmptySemanticGoal,
}

internal sealed class DetailViabilityResult
{
    private static readonly DetailGoal[] EmptyChildren = Array.Empty<DetailGoal>();

    private DetailViabilityResult(
        bool isViable,
        DetailPruneReason reason,
        IReadOnlyList<DetailGoal> survivingChildren
    )
    {
        IsViable = isViable;
        Reason = reason;
        SurvivingChildren = survivingChildren;
    }

    public static DetailViabilityResult Viable(IReadOnlyList<DetailGoal> survivingChildren) =>
        new(true, DetailPruneReason.None, survivingChildren);

    public static DetailViabilityResult Pruned(DetailPruneReason reason) =>
        new(false, reason, EmptyChildren);

    public bool IsViable { get; }
    public DetailPruneReason Reason { get; }
    public IReadOnlyList<DetailGoal> SurvivingChildren { get; }
}
