using AdventureGuide.Graph;
using AdventureGuide.State;

namespace AdventureGuide.Views;

/// <summary>
/// Builds quest dependency trees on-demand from the entity graph and live game state.
///
/// The tree is a depth-first traversal of the quest's dependency subgraph with
/// cycle pruning. Item obtainability chains are inlined transitively: crafting
/// recipes expand to their ingredients, each ingredient expands to its sources.
///
/// Views are NOT pre-computed — they depend on live game state (quest completion,
/// inventory counts) for state indicators. Call <see cref="Build"/> each time the
/// quest page opens or game state changes.
/// </summary>
public sealed class QuestViewBuilder
{
    private readonly EntityGraph _graph;
    private readonly GameState _state;

    public QuestViewBuilder(EntityGraph graph, GameState state)
    {
        _graph = graph;
        _state = state;
    }

    /// <summary>Build the full dependency tree for a quest.</summary>
    public ViewNode? Build(string questKey)
    {
        var questNode = _graph.GetNode(questKey);
        if (questNode == null || questNode.Type != NodeType.Quest)
            return null;

        var visited = new HashSet<string>();
        return BuildQuestNode(questKey, questNode, edgeType: null, edge: null, visited);
    }

    // ── Quest node expansion ────────────────────────────────────────────

    private ViewNode BuildQuestNode(
        string key, Node node, EdgeType? edgeType, Edge? edge, HashSet<string> visited)
    {
        var viewNode = new ViewNode(key, node, edgeType, edge);

        if (!visited.Add(key))
        {
            // Cycle detected — mark as back-reference, don't expand
            return new ViewNode(key, node, edgeType, edge) { IsCycleRef = true };
        }

        // 1. Assignment (how the player gets this quest)
        AddEdgeChildren(viewNode, key, EdgeType.AssignedBy, visited);

        // 2. Prerequisites (quests that must be completed first)
        AddQuestPrereqs(viewNode, key, visited);

        // 3. Steps (ordered by ordinal when present)
        var stepTargets = AddStepChildren(viewNode, key, visited);

        // 4. Required items (with full obtainability chains)
        AddRequiredItems(viewNode, key, visited);

        // 5. Turn-in (how to complete) — skip targets already shown as steps
        AddCompletionChildren(viewNode, key, stepTargets, visited);

        visited.Remove(key);
        return viewNode;
    }

    // ── Step edges ──────────────────────────────────────────────────────

    private static readonly EdgeType[] StepEdgeTypes =
    {
        EdgeType.StepTalk, EdgeType.StepKill, EdgeType.StepTravel,
        EdgeType.StepShout, EdgeType.StepRead,
    };

    private HashSet<string> AddStepChildren(ViewNode parent, string questKey, HashSet<string> visited)
    {
        var stepTargets = new HashSet<string>();
        // Collect all step edges, sort by ordinal (null ordinals last)
        var steps = new List<(Edge edge, Node target)>();
        foreach (var stepType in StepEdgeTypes)
        {
            foreach (var edge in _graph.OutEdges(questKey, stepType))
            {
                var target = _graph.GetNode(edge.Target);
                if (target != null)
                {
                    steps.Add((edge, target));
                    stepTargets.Add(edge.Target);
                }
            }
        }

        steps.Sort((a, b) =>
        {
            int oa = a.edge.Ordinal ?? int.MaxValue;
            int ob = b.edge.Ordinal ?? int.MaxValue;
            return oa.CompareTo(ob);
        });

        foreach (var (edge, target) in steps)
        {
            var child = BuildLeafOrExpand(edge.Target, target, edge.Type, edge, visited);
            parent.Children.Add(child);
        }
        return stepTargets;
    }

    private void AddCompletionChildren(
        ViewNode parent, string questKey, HashSet<string> stepTargets, HashSet<string> visited)
    {
        foreach (var edge in _graph.OutEdges(questKey, EdgeType.CompletedBy))
        {
            // Skip completion targets that are already shown as step targets
            // (e.g., zone-entry quests have both step_travel and completed_by to same zone)
            if (stepTargets.Contains(edge.Target))
                continue;

            var target = _graph.GetNode(edge.Target);
            if (target == null) continue;

            var child = BuildLeafOrExpand(edge.Target, target, EdgeType.CompletedBy, edge, visited);
            parent.Children.Add(child);
        }
    }

    // ── Required items with obtainability ────────────────────────────────

    private void AddRequiredItems(ViewNode parent, string questKey, HashSet<string> visited)
    {
        foreach (var edge in _graph.OutEdges(questKey, EdgeType.RequiresItem))
        {
            var itemNode = _graph.GetNode(edge.Target);
            if (itemNode == null) continue;

            var child = BuildLeafOrExpand(edge.Target, itemNode, EdgeType.RequiresItem, edge, visited);
            parent.Children.Add(child);
        }
    }

    /// <summary>
    /// Expand an item node with all its obtainability sources:
    /// crafting recipes, drops, vendors, dialog gives, resource yields, quest rewards.
    /// </summary>
    private void ExpandItemSources(ViewNode itemViewNode, string itemKey, HashSet<string> visited)
    {
        // Crafting: item → CRAFTED_FROM → recipe → REQUIRES_MATERIAL → ingredients
        foreach (var craftEdge in _graph.OutEdges(itemKey, EdgeType.CraftedFrom))
        {
            var recipeNode = _graph.GetNode(craftEdge.Target);
            if (recipeNode == null) continue;

            var recipeView = new ViewNode(craftEdge.Target, recipeNode, EdgeType.CraftedFrom, craftEdge);

            if (visited.Add(craftEdge.Target))
            {
                foreach (var matEdge in _graph.OutEdges(craftEdge.Target, EdgeType.RequiresMaterial))
                {
                    var matNode = _graph.GetNode(matEdge.Target);
                    if (matNode == null) continue;

                    var matView = new ViewNode(matEdge.Target, matNode, EdgeType.RequiresMaterial, matEdge);

                    if (visited.Add(matEdge.Target))
                    {
                        ExpandItemSources(matView, matEdge.Target, visited);
                        visited.Remove(matEdge.Target);
                    }
                    else
                    {
                        matView = new ViewNode(matEdge.Target, matNode, EdgeType.RequiresMaterial, matEdge) { IsCycleRef = true };
                    }

                    recipeView.Children.Add(matView);
                }

                visited.Remove(craftEdge.Target);
            }

            itemViewNode.Children.Add(recipeView);
        }

        // Drop sources: character → DROPS_ITEM → this item (walk incoming)
        AddIncomingSources(itemViewNode, itemKey, EdgeType.DropsItem, visited);

        // Vendor sources: character → SELLS_ITEM → this item
        AddIncomingSources(itemViewNode, itemKey, EdgeType.SellsItem, visited);

        // Dialog give sources: character → GIVES_ITEM → this item
        AddIncomingSources(itemViewNode, itemKey, EdgeType.GivesItem, visited);

        // Resource yields: mining_node/water/item_bag → YIELDS_ITEM → this item
        AddIncomingSources(itemViewNode, itemKey, EdgeType.YieldsItem, visited);

        // Quest reward sources: quest → REWARDS_ITEM → this item
        AddIncomingSources(itemViewNode, itemKey, EdgeType.RewardsItem, visited);

        // Source lists start collapsed — the item name is the objective,
        // the sources are detail the player expands on demand.
        if (itemViewNode.Children.Count > 0)
            itemViewNode.DefaultExpanded = false;
    }

    /// <summary>
    /// Add children from incoming edges of a given type. The source nodes become
    /// children of the target's view node (e.g., characters that drop an item
    /// become children of the item view node).
    /// </summary>
    private void AddIncomingSources(
        ViewNode parent, string targetKey, EdgeType incomingType, HashSet<string> visited)
    {
        foreach (var edge in _graph.InEdges(targetKey, incomingType))
        {
            var sourceNode = _graph.GetNode(edge.Source);
            if (sourceNode == null) continue;

            var child = BuildLeafOrExpand(edge.Source, sourceNode, incomingType, edge, visited);
            child.SourceZones = CollectZones(sourceNode);
            parent.Children.Add(child);
        }
    }

    /// <summary>
    /// Collect unique zone display names for a node. Characters get zones
    /// from their spawn points. Other node types use their own Zone field.
    /// </summary>
    private List<string>? CollectZones(Node node)
    {
        if (node.Zone != null)
            return new List<string> { node.Zone };

        if (node.Type != NodeType.Character)
            return null;

        var spawnEdges = _graph.OutEdges(node.Key, EdgeType.HasSpawn);
        if (spawnEdges.Count == 0)
            return null;

        var zones = new HashSet<string>();
        for (int i = 0; i < spawnEdges.Count; i++)
        {
            var sp = _graph.GetNode(spawnEdges[i].Target);
            if (sp?.Zone != null)
                zones.Add(sp.Zone);
        }

        if (zones.Count == 0)
            return null;

        var sorted = new List<string>(zones);
        sorted.Sort(StringComparer.OrdinalIgnoreCase);
        return sorted;
    }

    // ── Quest prerequisites ─────────────────────────────────────────────

    private void AddQuestPrereqs(ViewNode parent, string questKey, HashSet<string> visited)
    {
        foreach (var edge in _graph.OutEdges(questKey, EdgeType.RequiresQuest))
        {
            var prereqNode = _graph.GetNode(edge.Target);
            if (prereqNode == null) continue;

            if (prereqNode.Type == NodeType.Quest)
            {
                // Full recursive expansion of prerequisite quest
                var child = BuildQuestNode(edge.Target, prereqNode, EdgeType.RequiresQuest, edge, visited);
                parent.Children.Add(child);
            }
            else
            {
                var child = new ViewNode(edge.Target, prereqNode, EdgeType.RequiresQuest, edge);
                parent.Children.Add(child);
            }
        }

        // Character unlock dependencies: if the quest's assigned_by or step
        // targets have GATED_BY_QUEST spawn edges, those quests are implicit
        // prerequisites. We don't inline those here — the spawn state is shown
        // on the character node itself. The GameState system handles it.
    }

    // ── Generic edge expansion ──────────────────────────────────────────

    private void AddEdgeChildren(
        ViewNode parent, string sourceKey, EdgeType type, HashSet<string> visited)
    {
        foreach (var edge in _graph.OutEdges(sourceKey, type))
        {
            var target = _graph.GetNode(edge.Target);
            if (target == null) continue;

            var child = BuildLeafOrExpand(edge.Target, target, type, edge, visited);
            parent.Children.Add(child);
        }
    }

    /// <summary>
    /// Build a child node. Quests get full recursive expansion. Items get
    /// their obtainability sources expanded (drops, vendors, gathering, etc.).
    /// Other node types are leaves.
    /// </summary>
    private ViewNode BuildLeafOrExpand(
        string key, Node node, EdgeType edgeType, Edge edge, HashSet<string> visited)
    {
        if (node.Type == NodeType.Quest)
            return BuildQuestNode(key, node, edgeType, edge, visited);

        var viewNode = new ViewNode(key, node, edgeType, edge);

        // Items need obtainability chains — you must get the item before you
        // can read it, turn it in, use it as a crafting ingredient, etc.
        if (node.Type == NodeType.Item && visited.Add(key))
        {
            ExpandItemSources(viewNode, key, visited);
            visited.Remove(key);
        }

        return viewNode;
    }
}
