using AdventureGuide.Plan;
using AdventureGuide.Plan.Semantics;

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
        {
            if (IsUnlockRequirementRef(parentRef, children[i]))
                continue;
            CollectVisibleRefs(children[i], visible);
        }
        return visible;
    }

    public IReadOnlyList<TreeRef> GetUnlockChildren(TreeRef parentRef)
    {
        var parent = _plan.GetNode(parentRef.NodeId) as PlanEntityNode;
        if (parent?.UnlockRequirementId == null)
            return Array.Empty<TreeRef>();

        var children = _session.GetChildren(parentRef);
        var visible = new List<TreeRef>();
        for (int i = 0; i < children.Count; i++)
        {
            if (!IsUnlockRequirementRef(parentRef, children[i]))
                continue;
            CollectVisibleRefs(children[i], visible);
        }
        return visible;
    }

    public bool HasVisibleChildren(TreeRef parentRef) => GetChildren(parentRef).Count > 0 || GetUnlockChildren(parentRef).Count > 0;

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

        var group = (PlanGroupNode)node;
        if (ShouldRenderGroup(candidate, group))
        {
            output.Add(candidate);
            return;
        }

        // Structural groups that are usually flattened stay transparent in the
        // detail tree. Their children become siblings at the same visual level.
        var children = _session.GetChildren(candidate);
        for (int i = 0; i < children.Count; i++)
            CollectVisibleRefs(children[i], output);
    }

    private bool IsUnlockRequirementRef(TreeRef parentRef, TreeRef candidate)
    {
        var parent = _plan.GetNode(parentRef.NodeId) as PlanEntityNode;
        return parent?.UnlockRequirementId != null
            && candidate.NodeId == parent.UnlockRequirementId.Value;
    }

    private static bool ShouldRenderGroup(TreeRef candidate, PlanGroupNode group)
    {
        if (group.Label != null)
            return true;
        if (candidate.IncomingLink == null)
            return false;

        return candidate.IncomingLink.Semantic.GroupDisplayHint == GroupDisplayHint.UsuallyShow;
    }
}
