namespace AdventureGuide.Plan;

/// <summary>
/// Base class for canonical plan nodes. The plan is immutable to consumers after
/// construction, but builders may populate outgoing links during assembly.
/// </summary>
public abstract class PlanNode
{
    public PlanNodeId Id { get; }
    public PlanNodeKind Kind { get; }
    public PlanStatus Status { get; internal set; }
    public List<PlanLink> Outgoing { get; } = new();

    protected PlanNode(PlanNodeId id, PlanNodeKind kind, PlanStatus status)
    {
        Id = id;
        Kind = kind;
        Status = status;
    }
}