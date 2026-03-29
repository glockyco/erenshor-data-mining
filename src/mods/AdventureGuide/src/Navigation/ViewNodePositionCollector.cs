using AdventureGuide.Frontier;
using AdventureGuide.Graph;
using AdventureGuide.State;
using AdventureGuide.Views;

namespace AdventureGuide.Navigation;

/// <summary>
/// Collects world positions from an already-pruned <see cref="ViewNode"/> tree.
///
/// This is the shared bridge between the dependency tree and runtime consumers
/// that need positions (navigation, tracker distance computation).  It walks
/// the same pruned tree that the UI renders instead of re-traversing the raw
/// graph, so all consumers see the same cycle-free dependency state.
///
/// Rules:
/// - cycle refs are skipped entirely
/// - blocked nodes recurse into their unlock dependency instead of emitting the
///   blocked node's own position
/// - quest nodes recurse into their frontier so consumers navigate to the next
///   actionable steps, not the quest node itself
/// - item / recipe nodes recurse into their already-pruned source children
/// - leaf nodes resolve through <see cref="PositionResolverRegistry"/>
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
        var active = new HashSet<string>(StringComparer.Ordinal);
        Collect(node, results, active);
    }

    private void Collect(ViewNode node, List<ResolvedPosition> results, HashSet<string> active)
    {
        if (node.IsCycleRef)
            return;

        // A blocked node is not itself navigable yet — the actionable target is
        // the unlock requirement shown inline under it.
        if (node.UnlockDependency != null)
        {
            Collect(node.UnlockDependency, results, active);
            return;
        }

        string token = $"{node.NodeKey}|{node.EdgeType?.ToString() ?? "root"}";
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
                        Collect(frontierNode, results, active);
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
                        Collect(child, results, active);
                    }
                    return;
                }
            }

            int before = results.Count;
            _registry.Resolve(node.NodeKey, results);
            if (results.Count > before)
                return;

            // Fallback for non-leaf wrapper nodes that have no direct resolver
            // but still contain actionable children.
            for (int i = 0; i < node.Children.Count; i++)
                Collect(node.Children[i], results, active);
        }
        finally
        {
            active.Remove(token);
        }
    }
}
