using AdventureGuide.Frontier;
using AdventureGuide.Graph;
using AdventureGuide.State;
using AdventureGuide.Views;

namespace AdventureGuide.Navigation;

/// <summary>
/// Collects world positions from an already-pruned <see cref="ViewNode"/> tree.
///
/// This is the shared bridge between the dependency tree and runtime consumers
/// that need positions (navigation, tracker distance computation). It walks the
/// same pruned tree that the UI renders instead of re-traversing the raw graph,
/// so all consumers see the same cycle-free dependency state.
///
/// Rules:
/// - cycle refs are skipped entirely
/// - blocked nodes recurse into their unlock dependency instead of emitting the
///   blocked node's own position
/// - quest nodes recurse into their frontier so consumers navigate to the next
///   actionable steps, not the quest node itself
/// - item / recipe nodes recurse into their already-pruned source children
/// - leaf nodes resolve through <see cref="PositionResolverRegistry"/>
/// - when an item / recipe has at least one reachable top-level source branch,
///   blocked alternative branches are ignored so they cannot override usable
///   direct sources during candidate selection
/// </summary>
public sealed class ViewNodePositionCollector
{
    private readonly PositionResolverRegistry _registry;
    private readonly GameState _state;

    public ViewNodePositionCollector(PositionResolverRegistry registry, GameState state)
    {
        _registry = registry;
        _state = state;
    }

    /// <summary>
    /// Append all reachable world positions represented by this pruned view node.
    /// </summary>
    public void Collect(ViewNode node, List<ResolvedPosition> results)
    {
        var detailed = new List<ResolvedViewPosition>();
        CollectDetailed(node, detailed);
        for (int i = 0; i < detailed.Count; i++)
        {
            var item = detailed[i];
            results.Add(new ResolvedPosition(item.Position, item.Scene, item.SourceKey));
        }
    }

    /// <summary>
    /// Append all reachable world positions represented by this pruned view node,
    /// attributed to both the current actionable goal node and the immediate target
    /// node that produced each candidate.
    /// </summary>
    public void CollectDetailed(ViewNode node, List<ResolvedViewPosition> results)
    {
        var active = new HashSet<string>(StringComparer.Ordinal);
        CollectDetailed(node, results, active, node);
    }

    private void CollectDetailed(
        ViewNode node,
        List<ResolvedViewPosition> results,
        HashSet<string> active,
        ViewNode goalNode)
    {
        if (node.IsCycleRef)
            return;

        // A blocked node is not itself actionable. Recurse into the unlock
        // requirement and promote that requirement to the current goal.
        if (node.UnlockDependency != null)
        {
            CollectDetailed(node.UnlockDependency, results, active, node.UnlockDependency);
            return;
        }

        string token = $"{goalNode.NodeKey}|{node.NodeKey}|{node.EdgeType?.ToString() ?? "root"}";
        if (!active.Add(token))
            return;

        try
        {
            switch (node.Node.Type)
            {
                case NodeType.Quest:
                {
                    var frontier = FrontierComputer.ComputeFrontier(node, _state);
                    for (int i = 0; i < frontier.Count; i++)
                    {
                        var frontierNode = frontier[i];
                        // FrontierComputer can fall back to the quest node itself
                        // when nothing contributed. Re-entering it would loop.
                        if (frontierNode.NodeKey == node.NodeKey
                            && frontierNode.EdgeType == node.EdgeType)
                            continue;
                        // Subquests should promote their next actionable leaf as the
                        // goal. Surfaces need the true next step, not a redundant
                        // "Complete <subquest>" wrapper around that same subquest.
                        CollectDetailed(frontierNode, results, active, frontierNode);
                    }
                    return;
                }

                case NodeType.Item:
                case NodeType.Recipe:
                {
                    bool hasReachableChild = false;
                    for (int i = 0; i < node.Children.Count; i++)
                    {
                        if (!node.Children[i].IsCycleRef && node.Children[i].UnlockDependency == null)
                        {
                            hasReachableChild = true;
                            break;
                        }
                    }

                    for (int i = 0; i < node.Children.Count; i++)
                    {
                        var child = node.Children[i];
                        if (hasReachableChild && child.UnlockDependency != null)
                            continue;

                        var childRole = ClassifyRole(child);
                        if (childRole == FrontierComputer.EdgeRole.Done)
                            continue;

                        var childGoalNode = childRole == FrontierComputer.EdgeRole.Source
                            ? goalNode
                            : child;
                        CollectDetailed(child, results, active, childGoalNode);
                    }
                    return;
                }
            }

            int before = _scratch.Count;
            _registry.Resolve(node.NodeKey, _scratch);
            for (int i = before; i < _scratch.Count; i++)
            {
                var rp = _scratch[i];
                results.Add(new ResolvedViewPosition(rp.Position, rp.Scene, rp.SourceKey, goalNode, node));
            }
            if (_scratch.Count > before)
            {
                _scratch.RemoveRange(before, _scratch.Count - before);
                return;
            }

            // Fallback for non-leaf wrapper nodes that have no direct resolver
            // but still contain actionable children.
            for (int i = 0; i < node.Children.Count; i++)
                CollectDetailed(node.Children[i], results, active, goalNode);
        }
        finally
        {
            active.Remove(token);
        }
    }

    private FrontierComputer.EdgeRole ClassifyRole(ViewNode node) =>
        FrontierComputer.ClassifyEdge(node, _state, _state.GetState(node.NodeKey));

    // Reusable internal scratch list to avoid per-recursion allocations.
    private readonly List<ResolvedPosition> _scratch = new();
}
