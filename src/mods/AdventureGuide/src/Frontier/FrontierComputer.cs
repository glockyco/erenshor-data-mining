using AdventureGuide.Graph;
using AdventureGuide.State;
using AdventureGuide.Views;

namespace AdventureGuide.Frontier;

/// <summary>
/// Computes the frontier of a quest's dependency tree: the set of all
/// nodes whose parent dependencies are satisfied but which are not yet
/// completed themselves. These are the simultaneously actionable
/// objectives — everything the player can work on right now.
///
/// Returns <see cref="ViewNode"/>s (not bare keys) so consumers have full
/// context: edge type, keyword, quantity, and the graph node. This avoids
/// the need to walk the tree a second time to recover formatting context.
///
/// Edge-type-aware satisfaction and ordering:
/// - AssignedBy: satisfied when the owning quest is active or completed.
/// - CompletedBy: deferred until all other siblings are satisfied.
///   Only appears in the frontier as the final "turn in" step.
///   Satisfied only when the owning quest is completed.
/// - RequiresItem with source children: the RequiresItem node is the
///   frontier entry, NOT its individual sources (drops, vendors, etc.).
///   Sources are acquisition paths, not player objectives.
/// - Sub-quest nodes: questState switches to the sub-quest's own state
///   so its edges check the correct quest, not the root.
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

        // Resolve the quest's own state for edge-aware satisfaction checks.
        var questState = state.GetState(root.NodeKey);

        CollectFrontier(root, state, questState, frontier, seen);
        return frontier;
    }

    /// <summary>
    /// Edge types that represent item acquisition paths (sources), not
    /// direct objectives. When a RequiresItem node has only source
    /// children, the RequiresItem node itself is the frontier entry.
    /// </summary>
    private static bool IsSourceEdge(EdgeType? edgeType)
    {
        return edgeType is EdgeType.DropsItem
            or EdgeType.SellsItem
            or EdgeType.GivesItem
            or EdgeType.YieldsItem
            or EdgeType.RewardsItem
            or EdgeType.CraftedFrom;
    }

    /// <summary>
    /// Recursive walk: a node is in the frontier if it is not satisfied
    /// AND all its children that are dependencies (not sources) are either
    /// satisfied or also in the frontier.
    ///
    /// Leaf nodes (no children) that are not satisfied are always frontier.
    /// Cycle references are never frontier (not actionable).
    ///
    /// CompletedBy children are deferred: they only enter the frontier
    /// when all non-CompletedBy siblings are satisfied. This ensures
    /// "Turn in to NPC" only appears after all objectives are met.
    /// </summary>
    private static void CollectFrontier(
        ViewNode node, GameState state, NodeState questState,
        List<ViewNode> frontier, HashSet<string> seen)
    {
        if (node.IsCycleRef) return;

        // When entering a sub-quest node, switch to that quest's state
        // so its AssignedBy/CompletedBy edges check the right quest.
        if (node.Node.Type == NodeType.Quest)
            questState = state.GetState(node.NodeKey);
        if (node.IsCycleRef) return;

        // Edge-aware satisfaction check.
        if (IsEdgeSatisfied(node, state, questState)) return;

        // RequiresItem nodes with source children: the item is the objective,
        // not the individual sources. Add the RequiresItem node itself and
        // don't recurse into sources.
        if (node.EdgeType == EdgeType.RequiresItem && HasOnlySourceChildren(node))
        {
            if (seen.Add(node.NodeKey))
                frontier.Add(node);
            return;
        }

        if (node.Children.Count == 0)
        {
            // Leaf node, not satisfied → it's actionable.
            // Deduplicate: same node can appear in multiple branches.
            if (seen.Add(node.NodeKey))
                frontier.Add(node);
            return;
        }

        // Interior node: recurse into non-CompletedBy children first.
        // CompletedBy is deferred — it's the turn-in step and should only
        // appear in the frontier after all other objectives are met.
        int frontierBefore = frontier.Count;
        List<ViewNode>? deferredCompletedBy = null;

        foreach (var child in node.Children)
        {
            if (child.EdgeType == EdgeType.CompletedBy)
            {
                // Defer — evaluate after all other children.
                deferredCompletedBy ??= new List<ViewNode>();
                deferredCompletedBy.Add(child);
                continue;
            }
            CollectFrontier(child, state, questState, frontier, seen);
        }

        // If non-CompletedBy children contributed to the frontier, objectives
        // are still in progress — don't show turn-in yet.
        // If none contributed (all objectives done), process deferred
        // CompletedBy children — they become the frontier ("Turn in").
        if (frontier.Count == frontierBefore && deferredCompletedBy != null)
        {
            foreach (var cb in deferredCompletedBy)
                CollectFrontier(cb, state, questState, frontier, seen);
        }

        // If still nothing contributed (no children, no deferred), this
        // interior node itself is the frontier entry.
        if (frontier.Count == frontierBefore)
        {
            if (seen.Add(node.NodeKey))
                frontier.Add(node);
        }
    }

    /// <summary>
    /// Check whether a node's edge is satisfied, accounting for edge type,
    /// quest state, and item quantity.
    ///
    /// AssignedBy: satisfied when the quest is active or completed (the
    /// acceptance step is done). CompletedBy: satisfied only when the quest
    /// is completed (turn-in is done). RequiresItem with quantity: satisfied
    /// when the player has enough. Everything else: delegates to the node's
    /// intrinsic state.
    /// </summary>
    private static bool IsEdgeSatisfied(ViewNode node, GameState state, NodeState questState)
    {
        // AssignedBy: done once the quest is accepted
        if (node.EdgeType == EdgeType.AssignedBy)
            return questState is QuestActive or QuestCompleted or QuestImplicitlyActive;

        // CompletedBy: done only when the quest is fully completed
        if (node.EdgeType == EdgeType.CompletedBy)
            return questState is QuestCompleted;

        var nodeState = state.GetState(node.NodeKey);

        // Items with quantity requirements
        if (nodeState is ItemCount ic && node.Edge?.Quantity is int required)
            return ic.Count >= required;

        return nodeState.IsSatisfied;
    }

    /// <summary>
    /// Check whether all children are simple acquisition sources (drops, vendors,
    /// gathering, crafting). If so, the parent item node is the frontier entry.
    /// Quest sources (RewardsItem from a quest) are NOT simple — they have their
    /// own dependency chains the player must work through.
    /// </summary>
    private static bool HasOnlySourceChildren(ViewNode node)
    {
        if (node.Children.Count == 0) return false;

        foreach (var child in node.Children)
        {
            if (!IsSourceEdge(child.EdgeType))
                return false;
            // Quest sources have their own objectives — recurse into them.
            if (child.Node.Type == NodeType.Quest)
                return false;
        }
        return true;
    }
}
