using AdventureGuide.Graph;
using AdventureGuide.Plan.Semantics;
using AdventureGuide.Position;
using AdventureGuide.State;

namespace AdventureGuide.Plan;

/// <summary>
/// Builds the canonical, explicitly-grouped dependency plan from the immutable
/// entity graph plus live state needed for statuses, unlock requirements, and
/// source metadata.
///
/// Cycle detection: entities currently being built are tracked in
/// <see cref="_entitiesOnPath"/>. When a child reference creates a back-edge,
/// a lightweight cycle stub is created instead of reusing the real entity,
/// keeping the plan graph acyclic. After each entity's subtree is fully built,
/// infeasibility is propagated upward through AND/OR group semantics so that
/// entire unreachable branches are pruned from the plan.
/// </summary>
public sealed class QuestPlanBuilder
{
    private readonly EntityGraph _graph;
    private readonly GameState? _state;
    private readonly UnlockEvaluator? _unlocks;
    private readonly ZoneAccessResolver? _zoneAccess;
    private readonly Dictionary<PlanNodeId, PlanNode> _nodesById = new();
    private readonly Dictionary<string, PlanEntityNode> _entitiesByKey = new(StringComparer.Ordinal);
    private readonly Dictionary<PlanNodeId, PlanGroupNode> _groupsById = new();

    /// <summary>
    /// Entity keys currently on the DFS build stack. A child whose key is
    /// already in this set represents a cycle — a stub is created instead.
    /// Unified across quests, items, and recipes so that cross-type cycles
    /// (e.g. quest → item → quest) are caught.
    /// </summary>
    private readonly HashSet<string> _entitiesOnPath = new(StringComparer.Ordinal);

    /// <summary>
    /// Entity keys whose subtrees have been fully built and feasibility-
    /// propagated. Subsequent encounters reuse the existing entity without
    /// re-traversal.
    /// </summary>
    private readonly HashSet<string> _resolvedEntityKeys = new(StringComparer.Ordinal);

    /// <summary>Counter for generating unique cycle stub IDs.</summary>
    private int _cycleStubCounter;

    public QuestPlanBuilder(EntityGraph graph)
    {
        _graph = graph;
    }

    public QuestPlanBuilder(
        EntityGraph graph,
        GameState state,
        ZoneRouter router,
        QuestStateTracker tracker,
        UnlockEvaluator unlocks)
    {
        _graph = graph;
        _state = state;
        _unlocks = unlocks;
        _zoneAccess = new ZoneAccessResolver(graph, tracker, unlocks, router);
    }

    public QuestPlan Build(string questKey)
    {
        Reset();

        var rootNode = _graph.GetNode(questKey);
        if (rootNode == null || rootNode.Type != NodeType.Quest)
            throw new InvalidOperationException($"Quest '{questKey}' not found.");

        var root = GetOrCreateEntity(rootNode);
        BuildQuest(rootNode.Key);
        return CreatePlan(root.Id);
    }

    public QuestPlan BuildNode(string nodeKey)
    {
        Reset();

        var rootNode = _graph.GetNode(nodeKey)
            ?? throw new InvalidOperationException($"Node '{nodeKey}' not found.");

        var root = GetOrCreateEntity(rootNode);
        if (RequiresRecursiveBuild(rootNode.Type))
        {
            ApplyRuntimeState(root);
            AddUnlockRequirement(root);
        }
        else
        {
            InitializeNonBuildEntity(root);
        }

        switch (rootNode.Type)
        {
            case NodeType.Quest:
                BuildQuest(rootNode.Key);
                break;
            case NodeType.Item:
                BuildItem(rootNode.Key);
                break;
            case NodeType.Recipe:
                BuildRecipe(rootNode.Key);
                break;
        }

        return CreatePlan(root.Id);
    }

    private void Reset()
    {
        _nodesById.Clear();
        _entitiesByKey.Clear();
        _groupsById.Clear();
        _entitiesOnPath.Clear();
        _resolvedEntityKeys.Clear();
        _cycleStubCounter = 0;
    }

    private QuestPlan CreatePlan(PlanNodeId rootId)
    {
        var emptyFrontier = Array.Empty<FrontierRef>();
        return new QuestPlan(
            rootId,
            _nodesById,
            _entitiesByKey,
            _groupsById,
            emptyFrontier,
            new TrackerProjection(emptyFrontier),
            Array.Empty<NavCandidateSeed>());
    }

    // ── Build methods ───────────────────────────────────────────────────

    private void BuildQuest(string questKey)
    {
        if (_resolvedEntityKeys.Contains(questKey))
            return;
        if (!_entitiesOnPath.Add(questKey))
            return;

        try
        {
            var quest = _graph.GetNode(questKey);
            if (quest == null)
                return;

            var questNode = GetOrCreateEntity(quest);

            // Entity may already be marked PrunedCycle by AddUnlockRequirement
            // (e.g. zone access cycle detected in PrepareChildEntity). Skip
            // building children for pruned nodes — they're unreachable.
            if (questNode.Status is PlanStatus.PrunedCycle or PlanStatus.PrunedInfeasible)
                return;

            ApplyRuntimeState(questNode);
            AddQuestGroup(
                questNode.Id,
                questNode,
                EdgeType.AssignedBy,
                PlanGroupKind.AnyOf,
                "assignment",
                label: "How to start");
            AddQuestObjectiveGroup(questNode);
            AddQuestGroup(
                questNode.Id,
                questNode,
                EdgeType.CompletedBy,
                PlanGroupKind.AnyOf,
                "completion",
                label: "How to complete");
            AddUnlockRequirement(questNode);

            PropagateEntityFeasibility(questNode);
        }
        finally
        {
            _entitiesOnPath.Remove(questKey);
            _resolvedEntityKeys.Add(questKey);
        }
    }

    private void BuildItem(string itemKey)
    {
        if (_resolvedEntityKeys.Contains(itemKey))
            return;
        if (!_entitiesOnPath.Add(itemKey))
            return;

        try
        {
            var item = _graph.GetNode(itemKey);
            if (item == null)
                return;

            var itemNode = GetOrCreateEntity(item);

            if (itemNode.Status is PlanStatus.PrunedCycle or PlanStatus.PrunedInfeasible)
                return;

            ApplyRuntimeState(itemNode);
            var sourceGroup = GetOrCreateGroup($"{itemNode.NodeKey}:sources:anyof", PlanGroupKind.AnyOf);

            bool hasSources = false;

            hasSources |= AddItemSourceEdges(itemNode, sourceGroup, EdgeType.CraftedFrom, outgoing: true);
            hasSources |= AddItemSourceEdges(itemNode, sourceGroup, EdgeType.DropsItem, outgoing: false);
            hasSources |= AddItemSourceEdges(itemNode, sourceGroup, EdgeType.SellsItem, outgoing: false);
            hasSources |= AddItemSourceEdges(itemNode, sourceGroup, EdgeType.GivesItem, outgoing: false);
            hasSources |= AddItemSourceEdges(itemNode, sourceGroup, EdgeType.YieldsItem, outgoing: false);
            hasSources |= AddItemSourceEdges(itemNode, sourceGroup, EdgeType.RewardsItem, outgoing: false);

            if (hasSources)
                AddLink(itemNode.Id, sourceGroup.Id, DependencySemantics.FromEdge(EdgeType.DropsItem), edgeType: null);

            PropagateEntityFeasibility(itemNode);
        }
        finally
        {
            _entitiesOnPath.Remove(itemKey);
            _resolvedEntityKeys.Add(itemKey);
        }
    }

    private void BuildRecipe(string recipeKey)
    {
        if (_resolvedEntityKeys.Contains(recipeKey))
            return;
        if (!_entitiesOnPath.Add(recipeKey))
            return;

        try
        {
            var recipe = _graph.GetNode(recipeKey);
            if (recipe == null)
                return;

            var recipeNode = GetOrCreateEntity(recipe);

            if (recipeNode.Status is PlanStatus.PrunedCycle or PlanStatus.PrunedInfeasible)
                return;

            ApplyRuntimeState(recipeNode);
            var materialEdges = _graph.OutEdges(recipeKey, EdgeType.RequiresMaterial);
            if (materialEdges.Count == 0)
                return;

            var materialsGroup = GetOrCreateGroup($"{recipeNode.NodeKey}:materials:allof", PlanGroupKind.AllOf);
            AddLink(recipeNode.Id, materialsGroup.Id, DependencySemantics.FromEdge(EdgeType.RequiresMaterial), edgeType: null);

            for (int i = 0; i < materialEdges.Count; i++)
            {
                var child = _graph.GetNode(materialEdges[i].Target);
                if (child == null)
                    continue;

                var childEntity = PrepareChildEntity(materialsGroup.Id, child,
                    DependencySemantics.FromEdge(EdgeType.RequiresMaterial),
                    edgeType: EdgeType.RequiresMaterial,
                    quantity: materialEdges[i].Quantity,
                    group: materialEdges[i].Group);
                if (childEntity == null)
                    continue;

                if (child.Type == NodeType.Item)
                    BuildItem(child.Key);
            }

            PropagateEntityFeasibility(recipeNode);
        }
        finally
        {
            _entitiesOnPath.Remove(recipeKey);
            _resolvedEntityKeys.Add(recipeKey);
        }
    }

    // ── Quest group builders ────────────────────────────────────────────

    private void AddQuestGroup(
        PlanNodeId parentId,
        PlanEntityNode questNode,
        EdgeType edgeType,
        PlanGroupKind groupKind,
        string suffix,
        string? label = null)
    {
        var edges = _graph.OutEdges(questNode.NodeKey, edgeType);
        if (edges.Count == 0)
            return;

        var semantic = DependencySemantics.FromEdge(edgeType);
        var group = GetOrCreateGroup(
            $"{questNode.NodeKey}:{suffix}:{groupKind.ToString().ToLowerInvariant()}",
            groupKind,
            label: label);
        AddLink(parentId, group.Id, semantic, edgeType: edgeType);

        for (int i = 0; i < edges.Count; i++)
        {
            var child = _graph.GetNode(edges[i].Target);
            if (child == null)
                continue;

            var childEntity = PrepareChildEntity(group.Id, child, semantic,
                edgeType: edgeType,
                ordinal: edges[i].Ordinal,
                quantity: edges[i].Quantity,
                keyword: edges[i].Keyword,
                group: edges[i].Group,
                note: edges[i].Note);
            if (childEntity == null)
                continue;

            if (child.Type == NodeType.Quest)
                BuildQuest(child.Key);
            else if (child.Type == NodeType.Item)
                BuildItem(child.Key);
            else if (child.Type == NodeType.Recipe)
                BuildRecipe(child.Key);
        }
    }

    private void AddQuestObjectiveGroup(PlanEntityNode questNode)
    {
        if (!HasQuestObjectives(questNode.NodeKey))
            return;

        var group = GetOrCreateGroup(
            $"{questNode.NodeKey}:objectives:allof",
            PlanGroupKind.AllOf,
            label: "What to do");
        AddLink(
            questNode.Id,
            group.Id,
            DependencySemantics.FromEdge(EdgeType.RequiresQuest),
            edgeType: null);

        AddQuestGroup(group.Id, questNode, EdgeType.RequiresQuest, PlanGroupKind.AllOf, "prerequisites");
        AddQuestStepGroup(group.Id, questNode);
        AddRequiredItems(group.Id, questNode);
    }

    private bool HasQuestObjectives(string questKey)
    {
        if (_graph.OutEdges(questKey, EdgeType.RequiresQuest).Count > 0)
            return true;
        if (_graph.OutEdges(questKey, EdgeType.RequiresItem).Count > 0)
            return true;

        var stepTypes = new[]
        {
            EdgeType.StepTalk,
            EdgeType.StepKill,
            EdgeType.StepTravel,
            EdgeType.StepShout,
            EdgeType.StepRead,
        };

        for (int i = 0; i < stepTypes.Length; i++)
        {
            if (_graph.OutEdges(questKey, stepTypes[i]).Count > 0)
                return true;
        }

        return false;
    }

    private void AddQuestStepGroup(PlanNodeId parentId, PlanEntityNode questNode)
    {
        var stepTypes = new[]
        {
            EdgeType.StepTalk,
            EdgeType.StepKill,
            EdgeType.StepTravel,
            EdgeType.StepShout,
            EdgeType.StepRead,
        };

        var collected = new List<(Edge edge, Node node)>();
        for (int i = 0; i < stepTypes.Length; i++)
        {
            var edges = _graph.OutEdges(questNode.NodeKey, stepTypes[i]);
            for (int j = 0; j < edges.Count; j++)
            {
                var child = _graph.GetNode(edges[j].Target);
                if (child != null)
                    collected.Add((edges[j], child));
            }
        }

        if (collected.Count == 0)
            return;

        collected.Sort((a, b) => (a.edge.Ordinal ?? int.MaxValue).CompareTo(b.edge.Ordinal ?? int.MaxValue));

        var group = GetOrCreateGroup(
            $"{questNode.NodeKey}:steps:allof",
            PlanGroupKind.AllOf);
        AddLink(parentId, group.Id, DependencySemantics.FromEdge(EdgeType.StepTalk), edgeType: null);

        for (int i = 0; i < collected.Count; i++)
        {
            var edge = collected[i].edge;
            var child = collected[i].node;

            var childEntity = PrepareChildEntity(group.Id, child,
                DependencySemantics.FromEdge(edge.Type),
                edgeType: edge.Type,
                ordinal: edge.Ordinal,
                quantity: edge.Quantity,
                keyword: edge.Keyword,
                group: edge.Group,
                note: edge.Note);
            if (childEntity == null)
                continue;

            if (child.Type == NodeType.Item)
                BuildItem(child.Key);
            else if (child.Type == NodeType.Quest)
                BuildQuest(child.Key);
        }
    }

    private void AddRequiredItems(PlanNodeId parentId, PlanEntityNode questNode)
    {
        var edges = _graph.OutEdges(questNode.NodeKey, EdgeType.RequiresItem);
        if (edges.Count == 0)
            return;

        var byGroup = new Dictionary<string, List<Edge>>(StringComparer.Ordinal);
        for (int i = 0; i < edges.Count; i++)
        {
            var key = edges[i].Group ?? string.Empty;
            if (!byGroup.TryGetValue(key, out var list))
                byGroup[key] = list = new List<Edge>();
            list.Add(edges[i]);
        }

        if (byGroup.Count == 1 && byGroup.ContainsKey(string.Empty))
        {
            var allOf = GetOrCreateGroup($"{questNode.NodeKey}:required-items:allof", PlanGroupKind.AllOf);
            AddLink(parentId, allOf.Id, DependencySemantics.FromEdge(EdgeType.RequiresItem), edgeType: EdgeType.RequiresItem);
            AddRequiredItemChildren(allOf.Id, byGroup[string.Empty], DependencySemantics.FromEdge(EdgeType.RequiresItem));
            return;
        }

        var anyOf = GetOrCreateGroup($"{questNode.NodeKey}:required-items:anyof", PlanGroupKind.AnyOf);
        AddLink(parentId, anyOf.Id, DependencySemantics.FromEdge(EdgeType.RequiresItem), edgeType: EdgeType.RequiresItem);

        foreach (var pair in byGroup)
        {
            var variantId = $"{questNode.NodeKey}:required-items:{(pair.Key.Length == 0 ? "default" : pair.Key)}:allof";
            var allOf = GetOrCreateGroup(variantId, PlanGroupKind.AllOf, pair.Key.Length == 0 ? null : pair.Key);
            AddLink(anyOf.Id, allOf.Id, DependencySemantics.FromEdge(EdgeType.RequiresItem), edgeType: EdgeType.RequiresItem, group: pair.Key);
            AddRequiredItemChildren(allOf.Id, pair.Value, DependencySemantics.FromEdge(EdgeType.RequiresItem));
        }
    }

    private void AddRequiredItemChildren(PlanNodeId parentId, List<Edge> edges, DependencySemantic semantic)
    {
        for (int i = 0; i < edges.Count; i++)
        {
            var child = _graph.GetNode(edges[i].Target);
            if (child == null)
                continue;

            var childEntity = PrepareChildEntity(parentId, child, semantic,
                edgeType: EdgeType.RequiresItem,
                quantity: edges[i].Quantity,
                group: edges[i].Group);
            if (childEntity == null)
                continue;

            if (child.Type == NodeType.Item)
                BuildItem(child.Key);
        }
    }

    // ── Item source edges ───────────────────────────────────────────────

    private bool AddItemSourceEdges(PlanEntityNode itemNode, PlanGroupNode sourceGroup, EdgeType edgeType, bool outgoing)
    {
        var semantic = DependencySemantics.FromEdge(edgeType);
        bool any = false;

        if (outgoing)
        {
            var edges = _graph.OutEdges(itemNode.NodeKey, edgeType);
            for (int i = 0; i < edges.Count; i++)
            {
                var child = _graph.GetNode(edges[i].Target);
                if (child == null)
                    continue;
                any = true;

                var childEntity = PrepareChildEntity(sourceGroup.Id, child, semantic,
                    edgeType: edgeType,
                    ordinal: edges[i].Ordinal,
                    quantity: edges[i].Quantity,
                    keyword: edges[i].Keyword,
                    group: edges[i].Group,
                    note: edges[i].Note);
                if (childEntity == null)
                    continue;

                if (child.Type == NodeType.Recipe)
                    BuildRecipe(child.Key);
                else if (child.Type == NodeType.Quest)
                    BuildQuest(child.Key);
            }

            return any;
        }

        var incoming = _graph.InEdges(itemNode.NodeKey, edgeType);
        for (int i = 0; i < incoming.Count; i++)
        {
            var source = _graph.GetNode(incoming[i].Source);
            if (source == null)
                continue;
            any = true;

            var sourceEntity = PrepareChildEntity(sourceGroup.Id, source, semantic,
                edgeType: edgeType,
                ordinal: incoming[i].Ordinal,
                quantity: incoming[i].Quantity,
                keyword: incoming[i].Keyword,
                group: incoming[i].Group,
                note: incoming[i].Note);
            if (sourceEntity == null)
                continue;

            EnrichSourceMetadata(sourceEntity, source);

            if (source.Type == NodeType.Quest)
                BuildQuest(source.Key);
            else if (source.Type == NodeType.Item)
                BuildItem(source.Key);
            else if (source.Type == NodeType.Recipe)
                BuildRecipe(source.Key);
        }

        return any;
    }

    // ── Unlock requirements ─────────────────────────────────────────────

    private void AddUnlockRequirement(PlanEntityNode node)
    {
        if (_unlocks == null)
            return;

        var blockingSources = new List<Node>();
        bool hadCyclicSources = false;
        EdgeType semanticEdgeType = EdgeType.UnlocksZoneLine;

        if (UnlockEvaluator.TryGetUnlockEdgeType(node.Node.Type, out var unlockEdgeType))
        {
            semanticEdgeType = unlockEdgeType;
            hadCyclicSources |= CollectBlockingSources(blockingSources, _unlocks.Evaluate(node.Node));
        }

        if (_zoneAccess != null)
        {
            var scenes = ResolveEntityScenes(node.Node);
            for (int si = 0; si < scenes.Count; si++)
            {
                var lockedRoute = _zoneAccess.FindBlockedRoute(scenes[si]);
                if (lockedRoute == null)
                    continue;
                if (blockingSources.Count == 0)
                    semanticEdgeType = EdgeType.UnlocksZoneLine;
                hadCyclicSources |= CollectBlockingSources(blockingSources, lockedRoute.Evaluation);
                break;  // One blocked route is sufficient
            }
        }

        // When we had blocking sources but ALL were dropped because they are
        // on the current build path, the entity is unreachable due to a cycle.
        if (blockingSources.Count == 0)
        {
            if (hadCyclicSources)
                node.Status = PlanStatus.PrunedCycle;
            NormalizeUnlockBlockedStatus(node);
            return;
        }

        AddUnlockRequirement(
            node,
            blockingSources,
            semanticEdgeType,
            node.Node.Type == NodeType.Door ? "Unlock" : "Requires");
        NormalizeUnlockBlockedStatus(node);
    }

    /// <summary>
    /// Collects non-cyclic blocking sources from an unlock evaluation.
    /// Returns true when at least one source was dropped because its key
    /// is on <see cref="_entitiesOnPath"/> (i.e. a cyclic reference).
    /// </summary>
    private bool CollectBlockingSources(List<Node> target, UnlockEvaluation evaluation)
    {
        if (evaluation.IsUnlocked || evaluation.BlockingSources.Count == 0)
            return false;

        bool foundCyclic = false;
        for (int i = 0; i < evaluation.BlockingSources.Count; i++)
        {
            var source = evaluation.BlockingSources[i];
            if (_entitiesOnPath.Contains(source.Key))
            {
                foundCyclic = true;
                continue;
            }
            if (target.Any(existing => string.Equals(existing.Key, source.Key, StringComparison.Ordinal)))
                continue;
            target.Add(source);
        }
        return foundCyclic;
    }

    private void AddUnlockRequirement(
        PlanEntityNode node,
        List<Node> blockingSources,
        EdgeType unlockEdgeType,
        string label)
    {
        if (blockingSources.Count == 0)
            return;

        var groupId = $"{node.NodeKey}:unlock:allof";
        var group = GetOrCreateGroup(groupId, PlanGroupKind.AllOf, label);
        node.UnlockRequirementId = group.Id;
        AddLink(node.Id, group.Id, DependencySemantics.FromEdge(unlockEdgeType), edgeType: null);

        for (int i = 0; i < blockingSources.Count; i++)
        {
            var source = blockingSources[i];

            var entity = PrepareChildEntity(group.Id, source,
                DependencySemantics.FromEdge(unlockEdgeType), edgeType: null);
            if (entity == null)
                continue;

            if (source.Type == NodeType.Quest)
                BuildQuest(source.Key);
            else if (source.Type == NodeType.Item)
                BuildItem(source.Key);
            else if (source.Type == NodeType.Recipe)
                BuildRecipe(source.Key);
        }

        // After building all blocking sources, the unlock group tells us whether
        // the entity is truly infeasible or merely blocked by a feasible path.
        NormalizeUnlockBlockedStatus(node);
    }

    private void NormalizeUnlockBlockedStatus(PlanEntityNode node)
    {
        if (node.UnlockRequirementId == null)
            return;
        if (!_nodesById.TryGetValue(node.UnlockRequirementId.Value, out var unlockNode)
            || unlockNode is not PlanGroupNode unlockGroup)
        {
            return;
        }

        if (IsGroupInfeasible(unlockGroup))
        {
            node.Status = PlanStatus.PrunedInfeasible;
            return;
        }

        if (node.Status != PlanStatus.Satisfied)
            node.Status = PlanStatus.Blocked;
    }

    // ── Cycle detection and feasibility propagation ─────────────────────

    /// <summary>
    /// Creates a lightweight stub node for a cyclic back-reference. The stub
    /// has <see cref="PlanStatus.PrunedCycle"/> status and no outgoing links.
    /// It goes into <see cref="_nodesById"/> for plan traversal but NOT into
    /// <see cref="_entitiesByKey"/>, keeping the real entity undisturbed.
    /// </summary>
    private PlanEntityNode CreateCycleStub(Node node)
    {
        _cycleStubCounter++;
        PlanNodeId stubId = $"cycle:{node.Key}:{_cycleStubCounter}";
        var stub = new PlanEntityNode(stubId, node, PlanStatus.PrunedCycle);
        _nodesById[stubId] = stub;
        return stub;
    }

    /// <summary>
    /// Creates or retrieves the entity for a child node, handling cycle
    /// detection and memoization. If the child's key is already on
    /// <see cref="_entitiesOnPath"/>, a cycle stub is created and linked
    /// instead — the method returns null so the caller skips Build* calls.
    ///
    /// For non-cyclic children, applies runtime state and evaluates unlock
    /// requirements (unless the entity was already resolved in a previous
    /// subtree traversal).
    /// </summary>
    private PlanEntityNode? PrepareChildEntity(
        PlanNodeId parentId,
        Node childNode,
        DependencySemantic semantic,
        EdgeType? edgeType = null,
        int? ordinal = null,
        int? quantity = null,
        string? keyword = null,
        string? group = null,
        string? note = null)
    {
        if (_entitiesOnPath.Contains(childNode.Key))
        {
            var stub = CreateCycleStub(childNode);
            AddLink(parentId, stub.Id, semantic, edgeType, ordinal, quantity, keyword, group, note);
            return null;
        }

        var entity = GetOrCreateEntity(childNode);
        if (!_resolvedEntityKeys.Contains(childNode.Key))
        {
            if (RequiresRecursiveBuild(childNode.Type))
            {
                ApplyRuntimeState(entity);
                AddUnlockRequirement(entity);
            }
            else
            {
                InitializeNonBuildEntity(entity);
            }
        }
        AddLink(parentId, entity.Id, semantic, edgeType, ordinal, quantity, keyword, group, note);
        return entity;
    }

    private void InitializeNonBuildEntity(PlanEntityNode entity)
    {
        if (_resolvedEntityKeys.Contains(entity.NodeKey))
            return;
        if (!_entitiesOnPath.Add(entity.NodeKey))
            return;

        try
        {
            ApplyRuntimeState(entity);
            AddUnlockRequirement(entity);
        }
        finally
        {
            _entitiesOnPath.Remove(entity.NodeKey);
        }

        _resolvedEntityKeys.Add(entity.NodeKey);
    }

    private static bool RequiresRecursiveBuild(NodeType nodeType) =>
        nodeType is NodeType.Quest or NodeType.Item or NodeType.Recipe;

    /// <summary>
    /// Evaluates feasibility of an entity after its full subtree is built.
    /// If any outgoing group is infeasible, the entity is marked
    /// <see cref="PlanStatus.PrunedInfeasible"/>.
    /// </summary>
    private void PropagateEntityFeasibility(PlanEntityNode entity)
    {
        if (entity.Status is PlanStatus.PrunedCycle or PlanStatus.PrunedInfeasible)
            return;

        for (int i = 0; i < entity.Outgoing.Count; i++)
        {
            var link = entity.Outgoing[i];
            if (!_nodesById.TryGetValue(link.ToId, out var child))
                continue;
            if (child is PlanGroupNode group && IsGroupInfeasible(group))
            {
                entity.Status = PlanStatus.PrunedInfeasible;
                return;
            }
        }
    }

    /// <summary>
    /// Evaluates whether a group is infeasible based on its children's statuses.
    /// AllOf: infeasible if ANY child is infeasible.
    /// AnyOf: infeasible if ALL children are infeasible.
    /// Marks the group <see cref="PlanStatus.PrunedInfeasible"/> when true.
    /// </summary>
    private bool IsGroupInfeasible(PlanGroupNode group)
    {
        if (group.Status is PlanStatus.PrunedInfeasible)
            return true;
        if (group.Status is PlanStatus.Satisfied)
            return false;

        int infeasibleCount = 0;
        int totalCount = 0;

        for (int i = 0; i < group.Outgoing.Count; i++)
        {
            if (!_nodesById.TryGetValue(group.Outgoing[i].ToId, out var child))
                continue;

            totalCount++;
            if (IsNodeInfeasible(child))
                infeasibleCount++;
        }

        if (totalCount == 0)
            return false;

        bool infeasible = group.GroupKind switch
        {
            PlanGroupKind.AllOf => infeasibleCount > 0,
            PlanGroupKind.AnyOf => infeasibleCount == totalCount,
            _ => false,
        };

        if (infeasible)
            group.Status = PlanStatus.PrunedInfeasible;

        return infeasible;
    }

    /// <summary>
    /// Checks whether a plan node should be treated as infeasible for
    /// propagation purposes. Entities still on the build path are treated
    /// as infeasible because referencing them creates a cycle.
    /// </summary>
    private bool IsNodeInfeasible(PlanNode node)
    {
        if (node.Status is PlanStatus.PrunedCycle or PlanStatus.PrunedInfeasible)
            return true;

        // An entity still on the build path is an ancestor — referencing it
        // here means a cycle that cannot be resolved.
        if (node is PlanEntityNode entity && _entitiesOnPath.Contains(entity.NodeKey))
            return true;

        if (node is PlanGroupNode group)
            return IsGroupInfeasible(group);

        return false;
    }

    /// <summary>
    /// Returns the scene(s) to check for zone accessibility. For characters
    /// whose own Scene field is empty, resolves scenes from spawn points.
    /// </summary>
    private IReadOnlyList<string> ResolveEntityScenes(Node node)
    {
        if (!string.IsNullOrEmpty(node.Scene))
            return new[] { node.Scene };

        // Characters often have no scene on the character node itself;
        // their actual location comes from spawn point nodes.
        if (node.Type == NodeType.Character)
        {
            var spawnEdges = _graph.OutEdges(node.Key, EdgeType.HasSpawn);
            var scenes = new List<string>(spawnEdges.Count);
            for (int i = 0; i < spawnEdges.Count; i++)
            {
                var sp = _graph.GetNode(spawnEdges[i].Target);
                if (sp?.Scene != null && !scenes.Contains(sp.Scene))
                    scenes.Add(sp.Scene);
            }
            return scenes;
        }

        return Array.Empty<string>();
    }

    // ── Runtime state and source metadata ───────────────────────────────

    private void ApplyRuntimeState(PlanEntityNode node)
    {
        if (_state == null)
            return;

        // Don't overwrite pruning decisions with runtime state.
        if (node.Status is PlanStatus.PrunedCycle or PlanStatus.PrunedInfeasible)
            return;

        var nodeState = _state.GetState(node.NodeKey);
        node.Status = nodeState.IsSatisfied ? PlanStatus.Satisfied : PlanStatus.Available;
    }

    private void EnrichSourceMetadata(PlanEntityNode planNode, Node sourceNode)
    {
        if (sourceNode.Type == NodeType.Character)
        {
            var (zones, maxZoneLevel) = CollectCharacterZonesAndMaxLevel(sourceNode);
            planNode.SourceZones = zones;

            int? charLevel = sourceNode.Level;
            if (charLevel.HasValue && maxZoneLevel.HasValue)
                planNode.EffectiveLevel = Math.Max(charLevel.Value, maxZoneLevel.Value);
            else
                planNode.EffectiveLevel = charLevel ?? maxZoneLevel;
            return;
        }

        if (sourceNode.Zone != null)
            planNode.SourceZones = new List<string> { sourceNode.Zone };
        planNode.EffectiveLevel = sourceNode.Level;
    }

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
                    maxZoneLevel = maxZoneLevel.HasValue
                        ? Math.Max(maxZoneLevel.Value, zoneNode.Level.Value)
                        : zoneNode.Level.Value;
            }
        }

        if (zoneNames.Count == 0)
            return (null, maxZoneLevel);

        var sorted = new List<string>(zoneNames);
        sorted.Sort(StringComparer.OrdinalIgnoreCase);
        return (sorted, maxZoneLevel);
    }

    // ── Plan node management ────────────────────────────────────────────

    private PlanEntityNode GetOrCreateEntity(Node node)
    {
        if (_entitiesByKey.TryGetValue(node.Key, out var existing))
            return existing;

        var created = new PlanEntityNode(node.Key, node);
        _entitiesByKey[node.Key] = created;
        _nodesById[created.Id] = created;
        return created;
    }

    private PlanGroupNode GetOrCreateGroup(string id, PlanGroupKind groupKind, string? label = null)
    {
        PlanNodeId nodeId = id;
        if (_groupsById.TryGetValue(nodeId, out var existing))
            return existing;

        var created = new PlanGroupNode(nodeId, groupKind, label);
        _groupsById[nodeId] = created;
        _nodesById[nodeId] = created;
        return created;
    }

    private void AddLink(
        PlanNodeId fromId,
        PlanNodeId toId,
        DependencySemantic semantic,
        EdgeType? edgeType,
        int? ordinal = null,
        int? quantity = null,
        string? keyword = null,
        string? group = null,
        string? note = null)
    {
        var from = _nodesById[fromId];
        if (HasEquivalentLink(from.Outgoing, toId, semantic.Kind, edgeType, ordinal, quantity, keyword, group, note))
            return;

        from.Outgoing.Add(new PlanLink(fromId, toId, semantic, edgeType, ordinal, quantity, keyword, group, note));
    }

    private static bool HasEquivalentLink(
        List<PlanLink> existing,
        PlanNodeId toId,
        DependencySemanticKind semanticKind,
        EdgeType? edgeType,
        int? ordinal,
        int? quantity,
        string? keyword,
        string? group,
        string? note)
    {
        for (int i = 0; i < existing.Count; i++)
        {
            var link = existing[i];
            if (link.ToId == toId
                && link.Semantic.Kind == semanticKind
                && link.EdgeType == edgeType
                && link.Ordinal == ordinal
                && link.Quantity == quantity
                && string.Equals(link.Keyword, keyword, StringComparison.Ordinal)
                && string.Equals(link.Group, group, StringComparison.Ordinal)
                && string.Equals(link.Note, note, StringComparison.Ordinal))
                return true;
        }

        return false;
    }
}
