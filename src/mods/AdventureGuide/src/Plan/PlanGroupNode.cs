namespace AdventureGuide.Plan;

/// <summary>
/// Synthetic structural node used to make implicit AND/OR semantics explicit in
/// the canonical plan. Projections may flatten or render the group explicitly.
/// </summary>
public sealed class PlanGroupNode : PlanNode
{
    public PlanGroupKind GroupKind { get; }
    public string? Label { get; }

    public PlanGroupNode(
        PlanNodeId id,
        PlanGroupKind groupKind,
        string? label = null,
        PlanStatus status = PlanStatus.Available)
        : base(id, PlanNodeKind.Group, status)
    {
        GroupKind = groupKind;
        Label = label;
    }
}