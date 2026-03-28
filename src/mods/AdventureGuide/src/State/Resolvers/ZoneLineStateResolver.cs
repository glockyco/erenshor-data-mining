using System.Text;
using AdventureGuide.Graph;

namespace AdventureGuide.State.Resolvers;

/// <summary>
/// Resolves zone line accessibility from <see cref="EdgeType.GatedByQuest"/>
/// edges using AND/OR group semantics.
/// <para>
/// Edges sharing the same <see cref="Edge.Group"/> form an AND group —
/// all quests in the group must be completed. Different groups are OR'd —
/// any single satisfied group unlocks the zone line.
/// Edges with null Group are unconditional prerequisites that must also
/// be satisfied regardless of which OR group passes.
/// </para>
/// </summary>
public sealed class ZoneLineStateResolver : INodeStateResolver
{
    private readonly EntityGraph _graph;
    private readonly QuestStateTracker _tracker;

    public ZoneLineStateResolver(EntityGraph graph, QuestStateTracker tracker)
    {
        _graph = graph;
        _tracker = tracker;
    }

    public NodeState Resolve(Node node)
    {
        var gates = _graph.OutEdges(node.Key, EdgeType.GatedByQuest);
        if (gates.Count == 0)
            return NodeState.Accessible;

        // Partition edges into unconditional (null group) and named groups.
        List<Edge>? unconditional = null;
        Dictionary<string, List<Edge>>? groups = null;

        foreach (var edge in gates)
        {
            if (edge.Group == null)
            {
                unconditional ??= new List<Edge>();
                unconditional.Add(edge);
            }
            else
            {
                groups ??= new Dictionary<string, List<Edge>>();
                if (!groups.TryGetValue(edge.Group, out var list))
                {
                    list = new List<Edge>();
                    groups[edge.Group] = list;
                }
                list.Add(edge);
            }
        }

        // Unconditional edges must all be satisfied regardless.
        bool unconditionalSatisfied = IsGroupSatisfied(unconditional);

        if (unconditionalSatisfied)
        {
            // No named groups → unconditional gates are the only requirement.
            if (groups == null)
                return NodeState.Accessible;

            // Any named group fully satisfied → accessible.
            foreach (var group in groups.Values)
            {
                if (IsGroupSatisfied(group))
                    return NodeState.Accessible;
            }
        }

        // Locked — build a reason string from the first unsatisfied group.
        string reason = BuildReason(unconditional, unconditionalSatisfied, groups);
        return new ZoneLineLocked(reason);
    }

    /// <summary>
    /// True when every quest target in the group is completed.
    /// Null/empty groups are trivially satisfied.
    /// </summary>
    private bool IsGroupSatisfied(List<Edge>? edges)
    {
        if (edges == null || edges.Count == 0)
            return true;

        foreach (var edge in edges)
        {
            if (!_tracker.IsCompleted(TargetDbName(edge)))
                return false;
        }
        return true;
    }

    /// <summary>
    /// Builds a human-readable reason listing uncompleted quest prerequisites.
    /// Prefers the first unsatisfied named group; falls back to unconditional.
    /// </summary>
    private string BuildReason(
        List<Edge>? unconditional,
        bool unconditionalSatisfied,
        Dictionary<string, List<Edge>>? groups)
    {
        // Collect from the first source of unsatisfied edges.
        List<Edge>? source = null;

        if (!unconditionalSatisfied && unconditional != null)
        {
            source = unconditional;
        }
        else if (groups != null)
        {
            foreach (var group in groups.Values)
            {
                if (!IsGroupSatisfied(group))
                {
                    source = group;
                    break;
                }
            }
        }

        if (source == null)
            return "Locked";

        var sb = new StringBuilder("Requires: ");
        bool first = true;
        foreach (var edge in source)
        {
            if (_tracker.IsCompleted(TargetDbName(edge)))
                continue;

            if (!first) sb.Append(", ");
            first = false;

            var questNode = _graph.GetNode(edge.Target);
            sb.Append(questNode?.DisplayName ?? edge.Target);
        }

        return sb.ToString();
    }

    /// <summary>
    /// The edge target key for a GatedByQuest edge points to a quest node.
    /// Quest node DbName is the quest identifier for completion checks.
    /// Falls back to the target key if the node is missing or has no DbName.
    /// </summary>
    private string TargetDbName(Edge edge)
    {
        var questNode = _graph.GetNode(edge.Target);
        return questNode?.DbName ?? edge.Target;
    }
}
