using AdventureGuide.Graph;
using AdventureGuide.Plan.Semantics;
using AdventureGuide.Position;
using AdventureGuide.State;

namespace AdventureGuide.Plan;

/// <summary>
/// Builds the canonical, explicitly-grouped dependency plan from the immutable
/// entity graph plus live state needed for statuses, unlock requirements, and
/// source metadata.
/// </summary>
public sealed class QuestPlanBuilder
{
    private readonly EntityGraph _graph;
    private readonly GameState? _state;
    private readonly ZoneRouter? _router;
    private readonly QuestStateTracker? _tracker;
    private readonly UnlockEvaluator? _unlocks;
    private readonly Dictionary<PlanNodeId, PlanNode> _nodesById = new();
    private readonly Dictionary<string, PlanEntityNode> _entitiesByKey = new(StringComparer.Ordinal);
    private readonly Dictionary<PlanNodeId, PlanGroupNode> _groupsById = new();
    private readonly HashSet<string> _questsOnPath = new(StringComparer.Ordinal);
    private readonly HashSet<string> _itemsOnPath = new(StringComparer.Ordinal);

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
        _router = router;
        _tracker = tracker;
        _unlocks = unlocks;
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
        ApplyRuntimeState(root);
        AddUnlockRequirement(root);

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
        _questsOnPath.Clear();
        _itemsOnPath.Clear();
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

    private void BuildQuest(string questKey)
    {
        if (!_questsOnPath.Add(questKey))
            return;

        try
        {
            var quest = _graph.GetNode(questKey);
            if (quest == null)
                return;

            var questNode = GetOrCreateEntity(quest);
            ApplyRuntimeState(questNode);
            AddQuestGroup(questNode, EdgeType.AssignedBy, PlanGroupKind.AnyOf, "assignment");
            AddQuestGroup(questNode, EdgeType.RequiresQuest, PlanGroupKind.AllOf, "prerequisites");
            AddQuestStepGroup(questNode);
            AddRequiredItems(questNode);
            AddQuestGroup(questNode, EdgeType.CompletedBy, PlanGroupKind.AnyOf, "completion");
            AddUnlockRequirement(questNode);
        }
        finally
        {
            _questsOnPath.Remove(questKey);
        }
    }

    private void AddQuestGroup(PlanEntityNode questNode, EdgeType edgeType, PlanGroupKind groupKind, string suffix)
    {
        var edges = _graph.OutEdges(questNode.NodeKey, edgeType);
        if (edges.Count == 0)
            return;

        var semantic = DependencySemantics.FromEdge(edgeType);
        var group = GetOrCreateGroup($"{questNode.NodeKey}:{suffix}:{groupKind.ToString().ToLowerInvariant()}", groupKind);
        AddLink(questNode.Id, group.Id, semantic, edgeType: edgeType);

        for (int i = 0; i < edges.Count; i++)
        {
            var child = _graph.GetNode(edges[i].Target);
            if (child == null)
                continue;

            var childNode = GetOrCreateEntity(child);
            ApplyRuntimeState(childNode);
            AddUnlockRequirement(childNode);
            AddLink(group.Id, childNode.Id, semantic,
                edgeType: edgeType,
                ordinal: edges[i].Ordinal,
                quantity: edges[i].Quantity,
                keyword: edges[i].Keyword,
                group: edges[i].Group,
                note: edges[i].Note);

            if (child.Type == NodeType.Quest)
                BuildQuest(child.Key);
        }
    }

    private void AddQuestStepGroup(PlanEntityNode questNode)
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

        var group = GetOrCreateGroup($"{questNode.NodeKey}:steps:allof", PlanGroupKind.AllOf);
        AddLink(questNode.Id, group.Id, DependencySemantics.FromEdge(EdgeType.StepTalk), edgeType: null);

        for (int i = 0; i < collected.Count; i++)
        {
            var edge = collected[i].edge;
            var child = collected[i].node;
            var childNode = GetOrCreateEntity(child);
            ApplyRuntimeState(childNode);
            AddUnlockRequirement(childNode);
            AddLink(group.Id, childNode.Id, DependencySemantics.FromEdge(edge.Type),
                edgeType: edge.Type,
                ordinal: edge.Ordinal,
                quantity: edge.Quantity,
                keyword: edge.Keyword,
                group: edge.Group,
                note: edge.Note);

            if (child.Type == NodeType.Item)
                BuildItem(child.Key);
            else if (child.Type == NodeType.Quest)
                BuildQuest(child.Key);
        }
    }

    private void AddRequiredItems(PlanEntityNode questNode)
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
            AddLink(questNode.Id, allOf.Id, DependencySemantics.FromEdge(EdgeType.RequiresItem), edgeType: EdgeType.RequiresItem);
            AddRequiredItemChildren(allOf.Id, byGroup[string.Empty], DependencySemantics.FromEdge(EdgeType.RequiresItem));
            return;
        }

        var anyOf = GetOrCreateGroup($"{questNode.NodeKey}:required-items:anyof", PlanGroupKind.AnyOf);
        AddLink(questNode.Id, anyOf.Id, DependencySemantics.FromEdge(EdgeType.RequiresItem), edgeType: EdgeType.RequiresItem);

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

            var childNode = GetOrCreateEntity(child);
            ApplyRuntimeState(childNode);
            AddUnlockRequirement(childNode);
            AddLink(parentId, childNode.Id, semantic,
                edgeType: EdgeType.RequiresItem,
                quantity: edges[i].Quantity,
                group: edges[i].Group);
            if (child.Type == NodeType.Item)
                BuildItem(child.Key);
        }
    }

    private void BuildItem(string itemKey)
    {
        if (!_itemsOnPath.Add(itemKey))
            return;

        try
        {
            var item = _graph.GetNode(itemKey);
            if (item == null)
                return;

            var itemNode = GetOrCreateEntity(item);
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
        }
        finally
        {
            _itemsOnPath.Remove(itemKey);
        }
    }

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
                var childNode = GetOrCreateEntity(child);
                ApplyRuntimeState(childNode);
                AddUnlockRequirement(childNode);
                AddLink(sourceGroup.Id, childNode.Id, semantic,
                    edgeType: edgeType,
                    ordinal: edges[i].Ordinal,
                    quantity: edges[i].Quantity,
                    keyword: edges[i].Keyword,
                    group: edges[i].Group,
                    note: edges[i].Note);

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
            var sourceNode = GetOrCreateEntity(source);
            ApplyRuntimeState(sourceNode);
            AddUnlockRequirement(sourceNode);
            EnrichSourceMetadata(sourceNode, source);
            AddLink(sourceGroup.Id, sourceNode.Id, semantic,
                edgeType: edgeType,
                ordinal: incoming[i].Ordinal,
                quantity: incoming[i].Quantity,
                keyword: incoming[i].Keyword,
                group: incoming[i].Group,
                note: incoming[i].Note);

            if (source.Type == NodeType.Quest)
                BuildQuest(source.Key);
            else if (source.Type == NodeType.Item)
                BuildItem(source.Key);
            else if (source.Type == NodeType.Recipe)
                BuildRecipe(source.Key);
        }

        return any;
    }

    private void BuildRecipe(string recipeKey)
    {
        var recipe = _graph.GetNode(recipeKey);
        if (recipe == null)
            return;

        var recipeNode = GetOrCreateEntity(recipe);
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

            var childNode = GetOrCreateEntity(child);
            ApplyRuntimeState(childNode);
            AddUnlockRequirement(childNode);
            AddLink(materialsGroup.Id, childNode.Id, DependencySemantics.FromEdge(EdgeType.RequiresMaterial),
                edgeType: EdgeType.RequiresMaterial,
                quantity: materialEdges[i].Quantity,
                group: materialEdges[i].Group);
            if (child.Type == NodeType.Item)
                BuildItem(child.Key);
        }
    }


    private void ApplyRuntimeState(PlanEntityNode node)
    {
        if (_state == null)
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

    private void AddUnlockRequirement(PlanEntityNode node)
    {
        if (_unlocks == null)
            return;
        if (!UnlockEvaluator.TryGetUnlockEdgeType(node.Node.Type, out _))
            return;

        var evaluation = _unlocks.Evaluate(node.Node);
        if (evaluation.IsUnlocked || evaluation.BlockingSources.Count == 0)
            return;

        var groupId = $"{node.NodeKey}:unlock:allof";
        var group = GetOrCreateGroup(groupId, PlanGroupKind.AllOf, node.Node.Type == NodeType.Door ? "Unlock" : "Requires");
        node.UnlockRequirementId = group.Id;
        AddLink(node.Id, group.Id, DependencySemantics.FromEdge(
            node.Node.Type == NodeType.Door ? EdgeType.UnlocksDoor :
            node.Node.Type == NodeType.Character ? EdgeType.UnlocksCharacter : EdgeType.UnlocksZoneLine), edgeType: null);

        for (int i = 0; i < evaluation.BlockingSources.Count; i++)
        {
            var source = evaluation.BlockingSources[i];
            var sourceNode = GetOrCreateEntity(source);
            ApplyRuntimeState(sourceNode);
            AddLink(group.Id, sourceNode.Id, DependencySemantics.FromEdge(
                node.Node.Type == NodeType.Door ? EdgeType.UnlocksDoor :
                node.Node.Type == NodeType.Character ? EdgeType.UnlocksCharacter : EdgeType.UnlocksZoneLine), edgeType: null);

            if (source.Type == NodeType.Quest)
                BuildQuest(source.Key);
            else if (source.Type == NodeType.Item)
                BuildItem(source.Key);
            else if (source.Type == NodeType.Recipe)
                BuildRecipe(source.Key);
        }
    }

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