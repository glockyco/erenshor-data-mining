namespace AdventureGuide.Plan;

/// <summary>
/// Canonical analyzed dependency plan for one quest. Entity nodes exist exactly
/// once; projections reference them through links and occurrence refs.
/// </summary>
public sealed class QuestPlan
{
    private readonly Dictionary<PlanNodeId, PlanNode> _nodes;

    public PlanNodeId RootId { get; }
    public IReadOnlyDictionary<PlanNodeId, PlanNode> Nodes => _nodes;
    public IReadOnlyDictionary<string, PlanEntityNode> EntityNodesByKey { get; }
    public IReadOnlyDictionary<PlanNodeId, PlanGroupNode> GroupNodes { get; }
    public IReadOnlyList<FrontierRef> Frontier { get; }
    public TrackerProjection Tracker { get; }
    public IReadOnlyList<NavCandidateSeed> NavigationSeeds { get; }

    public QuestPlan(
        PlanNodeId rootId,
        IDictionary<PlanNodeId, PlanNode> nodes,
        IDictionary<string, PlanEntityNode> entityNodesByKey,
        IDictionary<PlanNodeId, PlanGroupNode> groupNodes,
        IReadOnlyList<FrontierRef> frontier,
        TrackerProjection tracker,
        IReadOnlyList<NavCandidateSeed> navigationSeeds)
    {
        RootId = rootId;
        _nodes = new Dictionary<PlanNodeId, PlanNode>(nodes);
        EntityNodesByKey = new Dictionary<string, PlanEntityNode>(entityNodesByKey, System.StringComparer.Ordinal);
        GroupNodes = new Dictionary<PlanNodeId, PlanGroupNode>(groupNodes);
        Frontier = frontier;
        Tracker = tracker;
        NavigationSeeds = navigationSeeds;
    }

    public PlanNode? GetNode(PlanNodeId id)
    {
        _nodes.TryGetValue(id, out var node);
        return node;
    }
}