using AdventureGuide.State;
using AdventureGuide.Views;

namespace AdventureGuide.Frontier;

/// <summary>
/// Computes the frontier of a quest's dependency tree: the set of all
/// leaf nodes whose parent dependencies are satisfied but which are not
/// yet completed themselves. These are the simultaneously actionable
/// objectives — everything the player can work on right now.
///
/// Returns <see cref="ViewNode"/>s (not bare keys) so consumers have full
/// context: edge type, keyword, quantity, and the graph node. This avoids
/// the need to walk the tree a second time to recover formatting context.
///
/// Pure function of (ViewNode tree, GameState). No state of its own.
/// </summary>
public static class FrontierComputer
{
    /// <summary>
    /// Compute frontier ViewNodes from a view tree built by QuestViewBuilder.
    /// Each returned ViewNode carries the edge that led to it (type, keyword,
    /// quantity) for action text formatting.
    /// </summary>
    public static List<ViewNode> ComputeFrontier(ViewNode root, GameState state)
    {
        var frontier = new List<ViewNode>();
        var seen = new HashSet<string>();
        CollectFrontier(root, state, frontier, seen);
        return frontier;
    }

    /// <summary>
    /// Recursive walk: a node is in the frontier if it is not satisfied
    /// AND all its children that are dependencies (not sources) are either
    /// satisfied or also in the frontier.
    ///
    /// Leaf nodes (no children) that are not satisfied are always frontier.
    /// Cycle references are never frontier (not actionable).
    /// </summary>
    private static void CollectFrontier(
        ViewNode node, GameState state, List<ViewNode> frontier, HashSet<string> seen)
    {
        if (node.IsCycleRef) return;

        var nodeState = state.GetState(node.NodeKey);

        // Already done — not in the frontier, and don't recurse.
        // For items with edge.Quantity, "done" means have >= required, not just > 0.
        if (IsSatisfied(nodeState, node.Edge)) return;

        if (node.Children.Count == 0)
        {
            // Leaf node, not satisfied → it's actionable.
            // Deduplicate: same node can appear in multiple branches.
            if (seen.Add(node.NodeKey))
                frontier.Add(node);
            return;
        }

        // Interior node: recurse into children. If any child contributes
        // to the frontier, this node's dependencies are being worked on.
        // If no child does, this node itself is the frontier (its children
        // are all satisfied but it isn't yet — e.g., a turn-in step where
        // all items are collected).
        int frontierBefore = frontier.Count;

        foreach (var child in node.Children)
            CollectFrontier(child, state, frontier, seen);

        if (frontier.Count == frontierBefore)
        {
            // No children contributed to the frontier — this node is
            // directly actionable (e.g., talk to NPC for turn-in)
            if (seen.Add(node.NodeKey))
                frontier.Add(node);
        }
    }

    /// <summary>
    /// Check whether a node is satisfied, accounting for edge quantity.
    /// For items: the player must have at least the required quantity.
    /// For everything else: delegates to NodeState.IsSatisfied.
    /// </summary>
    private static bool IsSatisfied(NodeState nodeState, Graph.Edge? edge)
    {
        if (nodeState is ItemCount ic && edge?.Quantity is int required)
            return ic.Count >= required;

        return nodeState.IsSatisfied;
    }
}
