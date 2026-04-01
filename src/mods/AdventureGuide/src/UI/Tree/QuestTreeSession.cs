using AdventureGuide.Plan;

namespace AdventureGuide.UI.Tree;

/// <summary>
/// UI-only lazy tree session for one quest plan. Owns expansion state and
/// one-level-at-a-time child materialization with path-local cycle pruning.
/// </summary>
public sealed class QuestTreeSession
{
    private readonly QuestPlan _plan;
    private readonly Dictionary<TreeRefId, IReadOnlyList<TreeRef>> _materializedChildren = new();
    private readonly HashSet<TreeRefId> _expanded = new();
    private int _nextRefId;

    public string QuestKey => _plan.RootId.Value;
    public IReadOnlyCollection<TreeRefId> Expanded => _expanded;

    public QuestTreeSession(QuestPlan plan)
    {
        _plan = plan;
    }

    public IReadOnlyList<TreeRef> GetRootChildren()
    {
        const string rootRefId = "root";
        if (_materializedChildren.TryGetValue(rootRefId, out var cached))
            return cached;

        var root = CreateRootRef();
        var children = MaterializeChildren(root);
        _materializedChildren[root.Id] = children;
        return children;
    }

    public IReadOnlyList<TreeRef> GetChildren(TreeRef parentRef)
    {
        if (_materializedChildren.TryGetValue(parentRef.Id, out var cached))
            return cached;

        var children = MaterializeChildren(parentRef);
        _materializedChildren[parentRef.Id] = children;
        return children;
    }

    public bool IsExpanded(TreeRefId id) => _expanded.Contains(id);

    public void SetExpanded(TreeRefId id, bool expanded)
    {
        if (expanded)
            _expanded.Add(id);
        else
            _expanded.Remove(id);
    }

    private TreeRef CreateRootRef()
    {
        var root = _plan.GetNode(_plan.RootId) as PlanEntityNode
            ?? throw new InvalidOperationException($"Quest plan root '{_plan.RootId}' missing entity node.");

        var ancestry = new HashSet<string>(StringComparer.Ordinal)
        {
            root.NodeKey,
        };

        return new TreeRef("root", root.Id, null, null, depth: -1, ancestry);
    }

    private IReadOnlyList<TreeRef> MaterializeChildren(TreeRef parentRef)
    {
        var parent = _plan.GetNode(parentRef.NodeId)
            ?? throw new InvalidOperationException($"Plan node '{parentRef.NodeId}' not found.");

        var children = new List<TreeRef>();
        for (int i = 0; i < parent.Outgoing.Count; i++)
        {
            var link = parent.Outgoing[i];
            var target = _plan.GetNode(link.ToId);
            if (target == null)
                continue;
            if (target.Status is PlanStatus.PrunedCycle or PlanStatus.PrunedInfeasible)
                continue;

            if (target is PlanEntityNode entity
                && parentRef.AncestorEntityKeys.Contains(entity.NodeKey))
            {
                // Path-local cycle pruning for lazy detail projection.
                continue;
            }

            var ancestry = new HashSet<string>(parentRef.AncestorEntityKeys, StringComparer.Ordinal);
            if (target is PlanEntityNode entityTarget)
                ancestry.Add(entityTarget.NodeKey);

            var childRef = new TreeRef(
                NextRefId(link.ToId),
                link.ToId,
                parentRef.Id,
                link,
                parentRef.Depth + 1,
                ancestry);
            children.Add(childRef);
        }

        return children;
    }

    private TreeRefId NextRefId(PlanNodeId nodeId)
    {
        _nextRefId++;
        return $"ref:{_nextRefId}:{nodeId.Value}";
    }
}