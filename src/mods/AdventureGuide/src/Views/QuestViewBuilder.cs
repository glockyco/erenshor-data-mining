using AdventureGuide.Graph;
using AdventureGuide.Position;
using AdventureGuide.State;

namespace AdventureGuide.Views;

/// <summary>
/// Builds quest dependency trees on-demand from the entity graph and live game state.
///
/// The tree is a depth-first traversal of the quest's dependency subgraph.
/// Item obtainability chains are inlined transitively: crafting recipes expand
/// to their ingredients (including the consumed mold), each ingredient expands
/// to its sources.
///
/// Views are NOT pre-computed — they depend on live game state (quest completion,
/// inventory counts) for state indicators. Call <see cref="Build"/> each time
/// the quest page opens or game state changes.
///
/// Quest traversal uses three-colour DFS to correctly distinguish structural
/// cycles from DAG cross-edges:
///
///   _questsOnPath   (grey)  — currently on the DFS stack; a reference to one of
///                             these is a true back-edge (deadlock cycle).
///   _questsExpanded (black) — fully processed; a reference is a cross-edge that
///                             is safe and already rendered elsewhere in the tree.
///   _questsInfeasible       — determined infeasible during this build; cascade
///                             makes any quest that requires an infeasible one
///                             infeasible too.
///
/// Item expansion uses a separate <c>itemVisited</c> set (passed as a parameter)
/// to guard only the current item path. Expanded item subtrees are cached and
/// cloned so repeated requirements still show their full obtainability details.
/// </summary>
public sealed class QuestViewBuilder
{
    private readonly EntityGraph _graph;
    private readonly GameState _state;
    private readonly ZoneRouter _router;
    private readonly QuestStateTracker _tracker;
    private readonly UnlockEvaluator _unlocks;

    // ── DFS state — reset at the start of every Build() call ────────────────

    /// <summary>Grey set: quest keys currently on the DFS stack.</summary>
    private readonly HashSet<string> _questsOnPath = new();
    /// <summary>Quests that have been fully built and cached this pass.</summary>
    private readonly HashSet<string> _questsExpanded = new();
    /// <summary>Quest keys determined to be structurally infeasible.</summary>
    private readonly HashSet<string> _questsInfeasible = new();
    /// <summary>Successfully built quest subtrees for reuse when they recur.</summary>
    private readonly Dictionary<string, EntityViewNode> _questCache = new(StringComparer.Ordinal);
    /// <summary>Successfully built item subtrees for reuse when they recur.</summary>
    private readonly Dictionary<string, EntityViewNode> _itemCache = new(StringComparer.Ordinal);
    /// <summary>Cached unlock dependency subtrees keyed by zone-line key.</summary>
    private readonly Dictionary<string, ViewNode?> _unlockDepCache = new(StringComparer.Ordinal);

    public QuestViewBuilder(EntityGraph graph, GameState state,
        ZoneRouter router, QuestStateTracker tracker, UnlockEvaluator unlocks)
    {
        _graph = graph;
        _state = state;
        _router = router;
        _tracker = tracker;
        _unlocks = unlocks;
    }

    /// <summary>Build the full dependency tree for a quest.</summary>
    public ViewNode? Build(string questKey)
    {
        var questNode = _graph.GetNode(questKey);
        if (questNode == null || questNode.Type != NodeType.Quest)
            return null;

        return BuildNode(questKey);
    }

    /// <summary>Build a pruned dependency/source tree for any graph node.</summary>
    public ViewNode? BuildNode(string nodeKey)
    {
        var node = _graph.GetNode(nodeKey);
        if (node == null)
            return null;

        ResetBuildState();
        var itemVisited = new HashSet<string>();

        return node.Type == NodeType.Quest
            ? BuildQuestNode(nodeKey, node, edgeType: null, edge: null, itemVisited)
            : BuildLeafOrExpand(nodeKey, node, edgeType: null, edge: null, itemVisited);
    }

    private void ResetBuildState()
    {
        // DFS state is scoped to one build.

        _questsOnPath.Clear();
        _questsExpanded.Clear();
        _questsInfeasible.Clear();
        _questCache.Clear();
        _itemCache.Clear();
        _unlockDepCache.Clear();
    }

    // ── Quest node expansion ─────────────────────────────────────────────────

    private EntityViewNode BuildQuestNode(
        string key, Node node, EdgeType? edgeType, Edge? edge, HashSet<string> itemVisited)
    {
        // (1) Explicitly infeasible — no valid accept/complete path exists.
        if (_questsInfeasible.Contains(key))
            return new EntityViewNode(key, node, edgeType, edge) { IsCycleRef = true };

        // (2) Already fully expanded elsewhere — cross-edge. Create a thin
        // wrapper that shares the canonical children instead of deep-cloning.
        if (_questsExpanded.Contains(key))
        {
            if (_questCache.TryGetValue(key, out var cached))
                return CreateSharedReference(cached, edgeType, edge);
            return new EntityViewNode(key, node, edgeType, edge) { IsCycleRef = true };
        }

        // (3) Currently on the DFS stack — back-edge (true structural cycle).
        if (!_questsOnPath.Add(key))
        return new EntityViewNode(key, node, edgeType, edge) { IsCycleRef = true };

        var viewNode = new EntityViewNode(key, node, edgeType, edge);

        // 1. Assignment (how the player gets this quest)
        AddEdgeChildren(viewNode, key, EdgeType.AssignedBy, itemVisited);

        // 2. Prerequisites (quests that must be completed first)
        AddQuestPrereqs(viewNode, key, itemVisited);

        // 3. Steps (ordered by ordinal when present)
        var stepTargets = AddStepChildren(viewNode, key, itemVisited);

        // 4. Required items (with full obtainability chains)
        AddRequiredItems(viewNode, key, itemVisited);

        // 5. Turn-in (how to complete) — skip targets already shown as steps
        AddCompletionChildren(viewNode, key, stepTargets, itemVisited);

        // Remove from the grey set before the feasibility check so that
        // _questsOnPath reflects only true ancestors at check time.
        _questsOnPath.Remove(key);

        if (IsQuestInfeasible(viewNode, key))
        {
            _questsInfeasible.Add(key);
            return new EntityViewNode(key, node, edgeType, edge) { IsCycleRef = true };
        }

        _questsExpanded.Add(key);
        _questCache[key] = viewNode;
        return viewNode;
    }

    /// <summary>
    /// Create a thin wrapper that shares the canonical children, SourceZones,
    /// EffectiveLevel, and UnlockDependency from <paramref name="canonical"/>.
    /// Only EdgeType and Edge are overridden for the root — the subtree is the
    /// same shared instance, not a deep clone.
    /// </summary>
    private static EntityViewNode CreateSharedReference(
        EntityViewNode canonical,
        EdgeType? edgeType,
        Edge? edge)
    {
        var wrapper = new EntityViewNode(canonical.NodeKey, canonical.Node, edgeType, edge)
        {
            IsCycleRef = canonical.IsCycleRef,
            DefaultExpanded = canonical.DefaultExpanded,
            EffectiveLevel = canonical.EffectiveLevel,
            SourceZones = canonical.SourceZones,
            UnlockDependency = canonical.UnlockDependency,
        };

        // Share the canonical children list by reference. These are immutable
        // after building — no consumer mutates children post-build.
        for (int i = 0; i < canonical.Children.Count; i++)
            wrapper.Children.Add(canonical.Children[i]);

        return wrapper;
    }

    // ── Quest feasibility ────────────────────────────────────────────────────

    /// <summary>
    /// Returns true when the quest has no viable path to acceptance or completion
    /// given the current expansion.
    ///
    /// Three rules:
    ///
    /// 1. Non-implicit quests with AssignedBy edges must have at least one
    ///    AssignedBy child that is not a cycle ref. (Implicit quests activate
    ///    in-zone without an acceptance interaction, so they have no AssignedBy
    ///    edges and must not be penalised for lacking them.)
    ///
    /// 2. Quests with CompletedBy edges must have at least one CompletedBy child
    ///    that is not a cycle ref.
    ///
    /// 3. Any RequiresQuest child is a cycle ref AND its key is in
    ///    _questsOnPath (back-edge — the ancestor that the cycle returns to) or
    ///    _questsInfeasible (already proven infeasible) makes this quest
    ///    infeasible too.  A cycle ref that comes from _questsExpanded is merely
    ///    a cross-edge: the prerequisite was already shown and IS completable.
    /// </summary>
    private bool IsQuestInfeasible(ViewNode questNode, string questKey)
    {
        var node = _graph.GetNode(questKey);

        // Rule 1 — non-implicit quests need a reachable assignment.
        if (node?.Implicit == false)
        {
            var assignEdges = _graph.OutEdges(questKey, EdgeType.AssignedBy);
            if (assignEdges.Count > 0)
            {
                bool hasValidAssignment = false;
                foreach (var c in questNode.Children)
                {
                    if (c.EdgeType == EdgeType.AssignedBy && !c.IsCycleRef)
                    {
                        hasValidAssignment = true;
                        break;
                    }
                }
                if (!hasValidAssignment)
                    return true;
            }
        }

        // Rule 2 — quests with explicit completion targets need a reachable one.
        // CompletedBy targets are intentionally de-duplicated when the same
        // node already appears as a step target (e.g. talk-to-X also completes
        // the quest). In that case the step node itself is the valid completion
        // path and must count here.
        var completeEdges = _graph.OutEdges(questKey, EdgeType.CompletedBy);
        if (completeEdges.Count > 0)
        {
            var completionTargets = new HashSet<string>(StringComparer.Ordinal);
            for (int i = 0; i < completeEdges.Count; i++)
                completionTargets.Add(completeEdges[i].Target);

            bool hasValidCompletion = false;
            foreach (var c in questNode.Children)
            {
                if (c.IsCycleRef)
                    continue;

                bool isExplicitCompletion = c.EdgeType == EdgeType.CompletedBy;
                bool isCompletionStep = c.EdgeType.HasValue
                    && System.Array.IndexOf(StepEdgeTypes, c.EdgeType.Value) >= 0
                    && completionTargets.Contains(c.NodeKey);

                if (isExplicitCompletion || isCompletionStep)
                {
                    hasValidCompletion = true;
                    break;
                }
            }
            if (!hasValidCompletion)
                return true;
        }

        // Rule 3 — a prerequisite that is a back-edge or infeasible propagates.
        foreach (var c in questNode.Children)
        {
            if (c.EdgeType != EdgeType.RequiresQuest || !c.IsCycleRef)
                continue;
            // Cross-edges (_questsExpanded) are safe — prereq already shown.
            if (_questsOnPath.Contains(c.NodeKey) || _questsInfeasible.Contains(c.NodeKey))
                return true;
        }

        return false;
    }

    // ── Step edges ───────────────────────────────────────────────────────────

    private static readonly EdgeType[] StepEdgeTypes =
    {
        EdgeType.StepTalk, EdgeType.StepKill, EdgeType.StepTravel,
        EdgeType.StepShout, EdgeType.StepRead,
    };

    private HashSet<string> AddStepChildren(ViewNode parent, string questKey, HashSet<string> itemVisited)
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
            var child = BuildLeafOrExpand(edge.Target, target, edge.Type, edge, itemVisited);
            if (child.IsCycleRef) continue;
            parent.Children.Add(child);
        }
        return stepTargets;
    }

    private void AddCompletionChildren(
        ViewNode parent, string questKey, HashSet<string> stepTargets, HashSet<string> itemVisited)
    {
        foreach (var edge in _graph.OutEdges(questKey, EdgeType.CompletedBy))
        {
            // Skip completion targets that are already shown as step targets
            // (e.g., zone-entry quests have both step_travel and completed_by to same zone)
            if (stepTargets.Contains(edge.Target))
                continue;

            var target = _graph.GetNode(edge.Target);
            if (target == null) continue;

            var child = BuildLeafOrExpand(edge.Target, target, EdgeType.CompletedBy, edge, itemVisited);
            if (child.IsCycleRef) continue;
            parent.Children.Add(child);
        }
    }

    // ── Required items with obtainability ────────────────────────────────────

    private void AddRequiredItems(ViewNode parent, string questKey, HashSet<string> itemVisited)
    {
        var edges = _graph.OutEdges(questKey, EdgeType.RequiresItem);
        if (edges.Count == 0) return;

        // Group edges by variant group key.
        // Null group means single-variant: no OR semantics, emit flat as before.
        var groups = new Dictionary<string, List<Edge>>(StringComparer.Ordinal);
        foreach (var edge in edges)
        {
            string key = edge.Group ?? string.Empty;
            if (!groups.TryGetValue(key, out var list))
                groups[key] = list = new List<Edge>();
            list.Add(edge);
        }

        if (groups.Count <= 1)
        {
            // Single group (or ungrouped) — flat, same behaviour as before.
            foreach (var edge in edges)
            {
                var itemNode = _graph.GetNode(edge.Target);
                if (itemNode == null) continue;
                var child = BuildLeafOrExpand(edge.Target, itemNode,
                    EdgeType.RequiresItem, edge, itemVisited);
                parent.Children.Add(child);
            }
            return;
        }

        // Multiple groups — wrap each in an OR-variant container so the
        // renderer can show them as alternatives rather than concurrent
        // requirements.
        var rewardsByGroup = CollectRewardsByGroup(questKey);
        bool rewardsDiffer = rewardsByGroup.Values.Distinct(StringComparer.Ordinal).Count() > 1;

        foreach (var (groupKey, groupEdges) in groups)
        {
            // Label the container by its variant's reward item when rewards
            // differ across groups (e.g. Malaroth Food good vs. bad recipe).
            string label = string.Empty;
            if (rewardsDiffer && rewardsByGroup.TryGetValue(groupKey, out var rewardKey))
            {
                var rewardNode = _graph.GetNode(rewardKey);
                label = rewardNode?.DisplayName ?? string.Empty;
            }

            var container = new VariantGroupNode(
                $"variant-group:{questKey}:{groupKey}",
                label,
                EdgeType.RequiresItem);

            foreach (var edge in groupEdges)
            {
                var itemNode = _graph.GetNode(edge.Target);
                if (itemNode == null) continue;
                var child = BuildLeafOrExpand(edge.Target, itemNode,
                    EdgeType.RequiresItem, edge, itemVisited);
                container.Children.Add(child);
            }

            if (container.Children.Count > 0)
                parent.Children.Add(container);
        }
    }

    /// <summary>
    /// Returns the per-variant reward item keys for this quest's REWARDS_ITEM
    /// edges that carry a group field. Used to label OR-variant containers by
    /// their outcome when variants produce different items.
    /// </summary>
    private Dictionary<string, string> CollectRewardsByGroup(string questKey)
    {
        var result = new Dictionary<string, string>(StringComparer.Ordinal);
        foreach (var edge in _graph.OutEdges(questKey, EdgeType.RewardsItem))
            if (edge.Group != null)
                result[edge.Group] = edge.Target;
        return result;
    }

    /// <summary>
    /// Expand an item node with all its obtainability sources:
    /// crafting recipes (including the consumed mold), drops, vendors,
    /// dialog gives, resource yields, quest rewards.
    /// </summary>
    private void ExpandItemSources(ViewNode itemViewNode, string itemKey, HashSet<string> itemVisited)
    {
        // Crafting: item → CRAFTED_FROM → recipe → REQUIRES_MATERIAL → ingredients + mold
        foreach (var craftEdge in _graph.OutEdges(itemKey, EdgeType.CraftedFrom))
        {
            var recipeNode = _graph.GetNode(craftEdge.Target);
            if (recipeNode == null) continue;

            var recipeView = new EntityViewNode(craftEdge.Target, recipeNode, EdgeType.CraftedFrom, craftEdge);

            if (itemVisited.Add(craftEdge.Target))
            {
                foreach (var matEdge in _graph.OutEdges(craftEdge.Target, EdgeType.RequiresMaterial))
                {
                    var matNode = _graph.GetNode(matEdge.Target);
                    if (matNode == null) continue;

                    var matView = new EntityViewNode(matEdge.Target, matNode, EdgeType.RequiresMaterial, matEdge);

                    if (itemVisited.Add(matEdge.Target))
                    {
                        ExpandItemSources(matView, matEdge.Target, itemVisited);
                        itemVisited.Remove(matEdge.Target);
                    }
                    else
                    {
                        matView = new EntityViewNode(matEdge.Target, matNode, EdgeType.RequiresMaterial, matEdge) { IsCycleRef = true };
                    }

                    recipeView.Children.Add(matView);
                }

                itemVisited.Remove(craftEdge.Target);
            }

            itemViewNode.Children.Add(recipeView);
        }

        // Drop sources: character → DROPS_ITEM → this item (walk incoming)
        AddIncomingSources(itemViewNode, itemKey, EdgeType.DropsItem, itemVisited);

        // Vendor sources: character → SELLS_ITEM → this item
        AddIncomingSources(itemViewNode, itemKey, EdgeType.SellsItem, itemVisited);

        // Dialog give sources: character → GIVES_ITEM → this item
        AddIncomingSources(itemViewNode, itemKey, EdgeType.GivesItem, itemVisited);

        // Resource yields: mining_node/water/item_bag → YIELDS_ITEM → this item
        AddIncomingSources(itemViewNode, itemKey, EdgeType.YieldsItem, itemVisited);

        // Quest reward sources: quest → REWARDS_ITEM → this item
        AddIncomingSources(itemViewNode, itemKey, EdgeType.RewardsItem, itemVisited);

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
        ViewNode parent, string targetKey, EdgeType incomingType, HashSet<string> itemVisited)
    {
        foreach (var edge in _graph.InEdges(targetKey, incomingType))
        {
            var sourceNode = _graph.GetNode(edge.Source);
            if (sourceNode == null) continue;

            var child = BuildLeafOrExpand(edge.Source, sourceNode, incomingType, edge, itemVisited);

            // Skip cycle references in source lists — they're graph artifacts,
            // not viable acquisition paths.
            if (child.IsCycleRef) continue;

            EnrichSourceMetadata(child, sourceNode, itemVisited);
            parent.Children.Add(child);
        }
    }

    /// <summary>
    /// Populate SourceZones, EffectiveLevel, and UnlockDependency on a source
    /// view node. Characters get zones from spawn points and effective level as
    /// max(character level, zone median). Non-characters use their own Zone and
    /// Level fields directly.
    /// </summary>
    private void EnrichSourceMetadata(EntityViewNode viewNode, Node sourceNode, HashSet<string> itemVisited)
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
    /// If the character has an unsatisfied incoming unlock requirement, build the
    /// blocking source tree inline as an unlock dependency.
    /// </summary>
    private void CheckCharacterUnlock(EntityViewNode viewNode, Node charNode, HashSet<string> itemVisited)
    {
        ApplyUnlockDependency(viewNode, charNode.Key, _unlocks.Evaluate(charNode), itemVisited);
    }

    /// <summary>
    /// If the node is in a zone that's unreachable from the player's current zone
    /// (route goes through a locked zone line), build the blocking source tree for
    /// that locked hop inline as an unlock dependency.
    /// </summary>
    private void CheckZoneReachability(EntityViewNode viewNode, Node node, HashSet<string> itemVisited)
    {
        string currentScene = _tracker.CurrentZone;
        if (string.IsNullOrEmpty(currentScene)) return;

        var candidateScenes = CollectReachabilityScenes(node);
        if (candidateScenes.Count == 0) return;

        IReadOnlyList<ZoneRouter.LockedHop>? bestLockedHops = null;
        int bestPathLength = int.MaxValue;

        for (int i = 0; i < candidateScenes.Count; i++)
        {
            string targetScene = candidateScenes[i];
            if (string.Equals(targetScene, currentScene, StringComparison.OrdinalIgnoreCase))
                return; // At least one target is directly in-zone

            var route = _router.FindRoute(currentScene, targetScene);
            if (route == null)
                continue;

            var lockedHops = _router.FindLockedHops(currentScene, targetScene);
            if (lockedHops.Count == 0)
                return; // At least one target scene is already reachable

            if (route.Path.Count < bestPathLength)
            {
                bestPathLength = route.Path.Count;
                bestLockedHops = lockedHops;
            }
        }

        if (bestLockedHops == null || bestLockedHops.Count == 0)
            return;

        var dependencyRoots = new List<ViewNode>();
        for (int i = 0; i < bestLockedHops.Count; i++)
        {
            var zoneLineKey = bestLockedHops[i].ZoneLineKey;

            // Share cached unlock dependency subtrees. Every node blocked by
            // the same zone line gets the same shared subtree reference instead
            // of an independent deep clone.
            if (_unlockDepCache.TryGetValue(zoneLineKey, out var cachedDep))
            {
                if (cachedDep != null)
                    dependencyRoots.Add(cachedDep);
                continue;
            }

            var lockedZoneLine = _graph.GetNode(zoneLineKey);
            if (lockedZoneLine == null)
            {
                _unlockDepCache[zoneLineKey] = null;
                continue;
            }

            var evaluation = _unlocks.Evaluate(lockedZoneLine);
            if (evaluation.IsUnlocked || evaluation.BlockingSources.Count == 0)
            {
                _unlockDepCache[zoneLineKey] = null;
                continue;
            }

            var dependency = BuildUnlockDependency(lockedZoneLine.Key, evaluation.BlockingSources, itemVisited);
            _unlockDepCache[zoneLineKey] = dependency;
            if (dependency == null)
                continue;
            if (IsUnlockDependencyInfeasible(dependency))
            {
                viewNode.IsCycleRef = true;
                viewNode.UnlockDependency = null;
                return;
            }

            dependencyRoots.Add(dependency);
        }

        if (dependencyRoots.Count == 0)
            return;

        if (dependencyRoots.Count == 1)
        {
            viewNode.UnlockDependency = dependencyRoots[0];
            return;
        }

        var group = new UnlockGroupNode($"reachability:{viewNode.NodeKey}", "Requires all of");
        for (int i = 0; i < dependencyRoots.Count; i++)
            group.Children.Add(dependencyRoots[i]);
        viewNode.UnlockDependency = group;
    }

    private void ApplyUnlockDependency(
        EntityViewNode viewNode,
        string targetKey,
        UnlockEvaluation evaluation,
        HashSet<string> itemVisited)
    {
        if (evaluation.IsUnlocked || evaluation.BlockingSources.Count == 0)
            return;

        viewNode.UnlockDependency = BuildUnlockDependency(targetKey, evaluation.BlockingSources, itemVisited);
        if (viewNode.UnlockDependency == null)
            return;

        if (IsUnlockDependencyInfeasible(viewNode.UnlockDependency))
        {
            viewNode.IsCycleRef = true;
            viewNode.UnlockDependency = null;
        }
    }

    private ViewNode? BuildUnlockDependency(
        string targetKey,
        IReadOnlyList<Node> blockingSources,
        HashSet<string> itemVisited)
    {
        if (blockingSources.Count == 1)
            return BuildUnlockSourceNode(blockingSources[0], itemVisited);

        var group = new UnlockGroupNode($"unlock-group:{targetKey}", "Requires all of");
        for (int i = 0; i < blockingSources.Count; i++)
        {
            group.Children.Add(BuildUnlockSourceNode(blockingSources[i], itemVisited));
        }

        return group.Children.Count == 0 ? null : group;
    }

    private EntityViewNode BuildUnlockSourceNode(Node sourceNode, HashSet<string> itemVisited)
    {
        return sourceNode.Type == NodeType.Quest
            ? BuildQuestNode(sourceNode.Key, sourceNode, edgeType: null, edge: null, itemVisited)
            : BuildLeafOrExpand(sourceNode.Key, sourceNode, edgeType: null, edge: null, itemVisited);
    }

    private static bool IsUnlockDependencyInfeasible(ViewNode dependency)
    {
        if (dependency.IsCycleRef)
            return true;

        if (dependency is UnlockGroupNode group)
        {
            for (int i = 0; i < group.Children.Count; i++)
            {
                if (IsUnlockDependencyInfeasible(group.Children[i]))
                    return true;
            }
        }

        return false;
    }

    private List<string> CollectReachabilityScenes(Node node)
    {
        var scenes = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        if (!string.IsNullOrEmpty(node.Scene))
            scenes.Add(node.Scene);

        if (node.Type == NodeType.Character)
        {
            var spawnEdges = _graph.OutEdges(node.Key, EdgeType.HasSpawn);
            for (int i = 0; i < spawnEdges.Count; i++)
            {
                var spawn = _graph.GetNode(spawnEdges[i].Target);
                if (!string.IsNullOrEmpty(spawn?.Scene))
                    scenes.Add(spawn.Scene!);
            }
        }

        return scenes.ToList();
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

    // ── Quest prerequisites ──────────────────────────────────────────────────

    private void AddQuestPrereqs(ViewNode parent, string questKey, HashSet<string> itemVisited)
    {
        foreach (var edge in _graph.OutEdges(questKey, EdgeType.RequiresQuest))
        {
            var prereqNode = _graph.GetNode(edge.Target);
            if (prereqNode == null) continue;

            if (prereqNode.Type == NodeType.Quest)
            {
                // Full recursive expansion; cycle refs are kept as children so
                // IsQuestInfeasible can inspect them for back-edge detection.
                var child = BuildQuestNode(edge.Target, prereqNode, EdgeType.RequiresQuest, edge, itemVisited);
                parent.Children.Add(child);
            }
            else
            {
                var child = new EntityViewNode(edge.Target, prereqNode, EdgeType.RequiresQuest, edge);
                parent.Children.Add(child);
            }
        }
    }

    // ── Generic edge expansion ───────────────────────────────────────────────

    private void AddEdgeChildren(
        ViewNode parent, string sourceKey, EdgeType type, HashSet<string> itemVisited)
    {
        foreach (var edge in _graph.OutEdges(sourceKey, type))
        {
            var target = _graph.GetNode(edge.Target);
            if (target == null) continue;

            var child = BuildLeafOrExpand(edge.Target, target, type, edge, itemVisited);
            if (child.IsCycleRef) continue;
            parent.Children.Add(child);
        }
    }

    /// <summary>
    /// Build a child node. Quests get full recursive expansion. Items get
    /// their obtainability sources expanded (drops, vendors, gathering, etc.).
    /// Other node types are leaves.
    /// </summary>
    private EntityViewNode BuildLeafOrExpand(
        string key, Node node, EdgeType? edgeType, Edge? edge, HashSet<string> itemVisited)
    {
        if (node.Type == NodeType.Quest)
            return BuildQuestNode(key, node, edgeType, edge, itemVisited);

        var viewNode = new EntityViewNode(key, node, edgeType, edge);

        // Check for unsatisfied unlock requirements on any character node,
        // regardless of edge type (source, step, assignment, etc.).
        if (node.Type == NodeType.Character)
            CheckCharacterUnlock(viewNode, node, itemVisited);

        // Check if this node is in an unreachable zone (locked zone line).
        // Only check if no character unlock already set (character unlock is
        // more specific and already explains why the node is blocked).
        // Reachability is not limited to node.Scene — characters often carry
        // their scene only on spawn points, so CheckZoneReachability derives
        // candidate scenes from the node type.
        if (viewNode.UnlockDependency == null)
            CheckZoneReachability(viewNode, node, itemVisited);

        // Items need obtainability chains — you must get the item before you
        // can read it, turn it in, use it as a crafting ingredient, etc.
        if (node.Type == NodeType.Item)
        {
            if (itemVisited.Contains(key))
                return new EntityViewNode(key, node, edgeType, edge) { IsCycleRef = true };

            if (_itemCache.TryGetValue(key, out var cachedItem))
                return CreateSharedReference(cachedItem, edgeType, edge);

            itemVisited.Add(key);
            ExpandItemSources(viewNode, key, itemVisited);
            itemVisited.Remove(key);
            _itemCache[key] = viewNode;
        }

        return viewNode;
    }
}
