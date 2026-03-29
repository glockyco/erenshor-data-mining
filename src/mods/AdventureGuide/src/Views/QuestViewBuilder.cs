using AdventureGuide.Graph;
using AdventureGuide.Navigation;
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
    private readonly ZoneRouter _router;
    private readonly QuestStateTracker _tracker;

    public QuestViewBuilder(EntityGraph graph, GameState state,
        ZoneRouter router, QuestStateTracker tracker)
    {
        _graph = graph;
        _state = state;
        _router = router;
        _tracker = tracker;
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

        // Sort sources by effective level ascending so the easiest
        // targets appear first. Null levels sort last.
        itemViewNode.Children.Sort((a, b) =>
        {
            int la = a.EffectiveLevel ?? int.MaxValue;
            int lb = b.EffectiveLevel ?? int.MaxValue;
            return la.CompareTo(lb);
        });

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

            // Skip cycle references in source lists — they're graph artifacts,
            // not viable acquisition paths.
            if (child.IsCycleRef) continue;

            EnrichSourceMetadata(child, sourceNode, visited);
            parent.Children.Add(child);
        }
    }

    /// <summary>
    /// Populate SourceZones, EffectiveLevel, and UnlockDependency on a source
    /// view node. Characters get zones from spawn points and effective level as
    /// max(character level, zone median). Non-characters use their own Zone and
    /// Level fields directly.
    /// </summary>
    private void EnrichSourceMetadata(ViewNode viewNode, Node sourceNode, HashSet<string> visited)
    {
        if (sourceNode.Type == NodeType.Character)
        {
            var (zones, maxZoneLevel) = CollectCharacterZonesAndMaxLevel(sourceNode);
            viewNode.SourceZones = zones;

            int? charLevel = sourceNode.Level;
            if (charLevel.HasValue && maxZoneLevel.HasValue)
                viewNode.EffectiveLevel = Math.Max(charLevel.Value, maxZoneLevel.Value);
            else
                viewNode.EffectiveLevel = charLevel ?? maxZoneLevel;
        }
        else
        {
            if (sourceNode.Zone != null)
                viewNode.SourceZones = new List<string> { sourceNode.Zone };
            viewNode.EffectiveLevel = sourceNode.Level;
        }
    }

    /// <summary>
    /// If the character is disabled, find the gating quest via UnlocksCharacter
    /// edges and build its dependency tree as an inline unlock requirement.
    /// The disabled variant is the specific node the tree references — even if
    /// an enabled variant of the same NPC exists, it doesn't help because that
    /// variant doesn't provide the same interaction (e.g., different GivesItem).
    /// </summary>
    private void CheckCharacterUnlock(ViewNode viewNode, Node charNode, HashSet<string> visited)
    {
        if (charNode.IsEnabled) return;

        // Find the quest that unlocks this character
        var unlockEdges = _graph.InEdges(charNode.Key, EdgeType.UnlocksCharacter);
        if (unlockEdges.Count == 0) return;

        var gatingQuestKey = unlockEdges[0].Source;
        var gatingQuestState = _state.GetState(gatingQuestKey);
        if (gatingQuestState is QuestCompleted) return; // Already unlocked

        // Blocked: build the gating quest's tree as an unlock dependency
        var gatingQuest = _graph.GetNode(gatingQuestKey);
        if (gatingQuest == null) return;

        viewNode.UnlockDependency = BuildQuestNode(
            gatingQuestKey, gatingQuest, EdgeType.RequiresQuest, null, visited);
    }

    /// <summary>
    /// If the node is in a zone that's unreachable from the player's current
    /// zone (route goes through a locked zone line), find the gating quest and
    /// build its dependency tree as an inline unlock requirement.
    /// </summary>
    private void CheckZoneReachability(ViewNode viewNode, Node node, HashSet<string> visited)
    {
        string? scene = node.Scene;
        if (scene == null) return;

        string currentScene = _tracker.CurrentZone;
        if (string.IsNullOrEmpty(currentScene)) return;
        if (string.Equals(scene, currentScene, StringComparison.OrdinalIgnoreCase)) return;

        var route = _router.FindRoute(currentScene, scene);
        if (route == null || !route.IsLocked) return;

        // Find which zone line is locked on this route by checking zone lines
        // in the first hop zone that connect to the next zone in the path.
        // The route's NextHopZoneKey tells us which zone we need to get to.
        // Look for locked zone lines from current scene to that zone.
        string nextHop = route.NextHopZoneKey;
        var zoneLines = _graph.NodesOfType(NodeType.ZoneLine);
        foreach (var zl in zoneLines)
        {
            // Zone line must be from current scene and connect to the next hop
            if (!string.Equals(zl.Scene, currentScene, StringComparison.OrdinalIgnoreCase)) continue;
            if (!string.Equals(zl.DestinationZoneKey, nextHop, StringComparison.OrdinalIgnoreCase)) continue;

            var zlState = _state.GetState(zl.Key);
            if (zlState.IsSatisfied) continue; // Not locked

            // Found the locked zone line. Find the quest that unlocks it.
            var unlockEdges = _graph.InEdges(zl.Key, EdgeType.UnlocksZoneLine);
            if (unlockEdges.Count == 0) continue;

            var gatingQuestKey = unlockEdges[0].Source;
            if (_state.GetState(gatingQuestKey) is QuestCompleted) continue;

            var gatingQuest = _graph.GetNode(gatingQuestKey);
            if (gatingQuest == null) continue;

            viewNode.UnlockDependency = BuildQuestNode(
                gatingQuestKey, gatingQuest, EdgeType.RequiresQuest, null, visited);
            return;
        }
    }

    /// <summary>
    /// Collect unique zone names and the maximum zone median level for a character
    /// by walking its spawn point edges. Returns (zones, maxZoneLevel).
    /// </summary>
    private (List<string>? zones, int? maxZoneLevel) CollectCharacterZonesAndMaxLevel(Node charNode)
    {
        var spawnEdges = _graph.OutEdges(charNode.Key, EdgeType.HasSpawn);
        if (spawnEdges.Count == 0)
            return (null, null);

        var zoneNames = new HashSet<string>();
        int? maxZoneLevel = null;

        for (int i = 0; i < spawnEdges.Count; i++)
        {
            var sp = _graph.GetNode(spawnEdges[i].Target);
            if (sp == null) continue;

            if (sp.Zone != null)
                zoneNames.Add(sp.Zone);

            // Look up the zone node to get its median level
            if (sp.ZoneKey != null)
            {
                var zoneNode = _graph.GetNode(sp.ZoneKey);
                if (zoneNode?.Level != null)
                {
                    maxZoneLevel = maxZoneLevel.HasValue
                        ? Math.Max(maxZoneLevel.Value, zoneNode.Level.Value)
                        : zoneNode.Level.Value;
                }
            }
        }

        if (zoneNames.Count == 0)
            return (null, maxZoneLevel);

        var sorted = new List<string>(zoneNames);
        sorted.Sort(StringComparer.OrdinalIgnoreCase);
        return (sorted, maxZoneLevel);
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

        // Check for unsatisfied unlock requirements on any character node,
        // regardless of edge type (source, step, assignment, etc.).
        if (node.Type == NodeType.Character)
            CheckCharacterUnlock(viewNode, node, visited);

        // Check if this node is in an unreachable zone (locked zone line).
        // Only check if no character unlock already set (character unlock is
        // more specific and already explains why the node is blocked).
        if (viewNode.UnlockDependency == null && node.Scene != null)
            CheckZoneReachability(viewNode, node, visited);

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
