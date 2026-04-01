using AdventureGuide.Plan;

namespace AdventureGuide.UI.Tree;

/// <summary>
/// One visual occurrence of a canonical plan node in a specific ancestry path.
/// Canonical nodes remain unique in the plan; TreeRefs may repeat them under
/// different parents without cloning analysis state.
/// </summary>
public sealed class TreeRef
{
    public TreeRefId Id { get; }
    public PlanNodeId NodeId { get; }
    public TreeRefId? ParentRefId { get; }
    public PlanLink? IncomingLink { get; }
    public int Depth { get; }

    internal HashSet<string> AncestorEntityKeys { get; }

    internal TreeRef(
        TreeRefId id,
        PlanNodeId nodeId,
        TreeRefId? parentRefId,
        PlanLink? incomingLink,
        int depth,
        HashSet<string> ancestorEntityKeys)
    {
        Id = id;
        NodeId = nodeId;
        ParentRefId = parentRefId;
        IncomingLink = incomingLink;
        Depth = depth;
        AncestorEntityKeys = ancestorEntityKeys;
    }
}