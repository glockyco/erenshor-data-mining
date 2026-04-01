using AdventureGuide.Graph;

namespace AdventureGuide.Plan;

/// <summary>
/// Canonical per-entity node in a <see cref="QuestPlan"/>. A graph entity exists
/// exactly once here regardless of how many visual occurrences later reference it.
/// </summary>
public sealed class PlanEntityNode : PlanNode
{
    public string NodeKey { get; }
    public Node Node { get; }
    public PlanNodeId? UnlockRequirementId { get; internal set; }
    public IReadOnlyList<string>? SourceZones { get; internal set; }
    public int? EffectiveLevel { get; internal set; }

    public PlanEntityNode(PlanNodeId id, Node node, PlanStatus status = PlanStatus.Available)
        : base(id, PlanNodeKind.Entity, status)
    {
        Node = node;
        NodeKey = node.Key;
    }
}