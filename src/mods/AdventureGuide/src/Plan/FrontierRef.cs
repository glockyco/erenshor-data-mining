using AdventureGuide.Plan.Semantics;

namespace AdventureGuide.Plan;

/// <summary>
/// Occurrence-aware frontier entry over a canonical quest plan. Carries the
/// incoming link context without requiring visual tree duplication.
/// </summary>
public sealed class FrontierRef
{
    public PlanNodeId GoalId { get; }
    public PlanNodeId NodeId { get; }
    public PlanLink IncomingLink { get; }
    public DependencyPhase Phase => IncomingLink.Semantic.Phase;

    public FrontierRef(PlanNodeId goalId, PlanNodeId nodeId, PlanLink incomingLink)
    {
        GoalId = goalId;
        NodeId = nodeId;
        IncomingLink = incomingLink;
    }
}