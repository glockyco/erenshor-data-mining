using AdventureGuide.Plan;

namespace AdventureGuide.UI.Tree;

/// <summary>
/// Flattens structural plan groups for the detail-tree projection so the player
/// sees meaningful entity nodes rather than internal AND/OR wrappers.
/// </summary>
public sealed class LazyTreeProjector
{
    private readonly QuestPlan _plan;
    private readonly QuestTreeSession _session;

    public LazyTreeProjector(QuestPlan plan, QuestTreeSession session)
    {
        _plan = plan;
        _session = session;
    }

    public IReadOnlyList<TreeRef> GetRootChildren()
    {
        var roots = _session.GetRootChildren();
        var visible = new List<TreeRef>();
        for (int i = 0; i < roots.Count; i++)
            CollectVisibleRefs(roots[i], visible);
        return visible;
    }

    public IReadOnlyList<TreeRef> GetChildren(TreeRef parentRef)
    {
        var children = _session.GetChildren(parentRef);
        var visible = new List<TreeRef>();
        for (int i = 0; i < children.Count; i++)
            CollectVisibleRefs(children[i], visible);
        return visible;
    }

    public bool HasVisibleChildren(TreeRef parentRef) => GetChildren(parentRef).Count > 0;

    private void CollectVisibleRefs(TreeRef candidate, List<TreeRef> output)
    {
        var node = _plan.GetNode(candidate.NodeId);
        if (node == null)
            return;

        if (node is PlanEntityNode)
        {
            output.Add(candidate);
            return;
        }

        // Groups are structural. For the detail tree we flatten them by default;
        // explicit rendering can be reintroduced later when the canonical groups
        // gain projection-specific labels worth showing to the player.
        var children = _session.GetChildren(candidate);
        for (int i = 0; i < children.Count; i++)
            CollectVisibleRefs(children[i], output);
    }
}