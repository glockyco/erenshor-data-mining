using AdventureGuide.State;
using AdventureGuide.Views;

namespace AdventureGuide.Frontier;

/// <summary>
/// Computes the frontier of a quest's dependency tree: the set of all
/// leaf nodes whose parent dependencies are satisfied but which are not
/// yet completed themselves. These are the simultaneously actionable
/// objectives — everything the player can work on right now.
///
/// Pure function of (ViewNode tree, GameState). No state of its own.
/// </summary>
public static class FrontierComputer
{
    /// <summary>
    /// Compute frontier node keys from a view tree built by QuestViewBuilder.
    /// </summary>
    public static HashSet<string> ComputeFrontier(ViewNode root, GameState state)
    {
        var frontier = new HashSet<string>();
        CollectFrontier(root, state, frontier);
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
    private static void CollectFrontier(ViewNode node, GameState state, HashSet<string> frontier)
    {
        if (node.IsCycleRef) return;

        var nodeState = state.GetState(node.NodeKey);

        // Already done — not in the frontier, and don't recurse
        if (nodeState.IsSatisfied) return;

        if (node.Children.Count == 0)
        {
            // Leaf node, not satisfied → it's actionable
            frontier.Add(node.NodeKey);
            return;
        }

        // Interior node: recurse into children. If any child contributes
        // to the frontier, this node's dependencies are being worked on.
        // If no child does, this node itself is the frontier (its children
        // are all satisfied but it isn't yet — e.g., a turn-in step where
        // all items are collected).
        int frontierBefore = frontier.Count;

        foreach (var child in node.Children)
            CollectFrontier(child, state, frontier);

        if (frontier.Count == frontierBefore)
        {
            // No children contributed to the frontier — this node is
            // directly actionable (e.g., talk to NPC for turn-in)
            frontier.Add(node.NodeKey);
        }
    }
}
