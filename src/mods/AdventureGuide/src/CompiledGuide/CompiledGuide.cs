using AdventureGuide.Graph;

namespace AdventureGuide.CompiledGuide;

public sealed class CompiledGuide
{
    private static readonly IReadOnlyList<Edge> EmptyEdgeList = Array.Empty<Edge>();
    private static readonly IReadOnlyList<Node> EmptyNodeList = Array.Empty<Node>();
    private static readonly IReadOnlyCollection<string> EmptyKeySet = Array.Empty<string>();
    private static readonly IReadOnlyList<QuestGiverBlueprint> EmptyGiverBlueprints = Array.Empty<QuestGiverBlueprint>();
    private static readonly IReadOnlyList<QuestCompletionBlueprint> EmptyCompletionBlueprints = Array.Empty<QuestCompletionBlueprint>();
    private static readonly IReadOnlyList<StaticSourceBlueprint> EmptyStaticBlueprints = Array.Empty<StaticSourceBlueprint>();

    // Raw DTO arrays (int-indexed access)
    private readonly CompiledNodeData[] _nodes;
    private readonly CompiledEdgeData[] _edges;
    private readonly int[][] _forwardAdj;
    private readonly int[][] _reverseAdj;
    private readonly int[] _questNodeIds;
    private readonly int[] _itemNodeIds;
    private readonly int[][] _prereqIds;
    private readonly ItemReq[][] _requiredItems;
    private readonly StepEntry[] _steps;
    private readonly int[] _stepOff;
    private readonly int[][] _giverIds;
    private readonly int[][] _completerIds;
    private readonly int[][] _chainsToIds;
    private readonly byte[] _questFlags;
    private readonly SourceSiteEntry[][] _itemSources;
    private readonly Dictionary<int, UnlockPredicateEntry> _unlocks;
    private readonly int[] _topoOrder;
    private readonly int[][] _itemToQuestIndices;
    private readonly int[][] _questToDependentQuestIndices;
    private readonly int[] _zoneNodeIds;
    private readonly int[][] _zoneAdj;
    private readonly Dictionary<string, string> _sceneToZoneDisplay;
    private readonly QuestGiverEntry[] _giverBlueprints;
    private readonly QuestCompletion[] _completionBlueprints;
    private readonly bool[] _infeasible;

    // Projected Node/Edge arrays (string-keyed access)
    private readonly Node[] _projectedNodes;
    private readonly Edge[] _projectedEdges;
    private readonly Dictionary<string, int> _keyToId;

    // Derived indexes
    private readonly Dictionary<NodeType, IReadOnlyList<Node>> _nodesByType;
    private readonly Dictionary<string, Node> _questsByDbName;
    private readonly Dictionary<int, int> _nodeIdToQuestIndex;
    private readonly Dictionary<int, int> _nodeIdToItemIndex;
    private readonly Dictionary<string, IReadOnlyCollection<string>> _questKeysByItemKey;
    private readonly Dictionary<string, IReadOnlyCollection<string>> _questKeysByQuestKey;
    private readonly Dictionary<string, IReadOnlyCollection<string>> _questKeysBySourceKey;
    private readonly Dictionary<string, IReadOnlyList<QuestGiverBlueprint>> _questGiversByScene;
    private readonly Dictionary<string, IReadOnlyList<QuestCompletionBlueprint>> _questCompletionsByScene;
    private readonly Dictionary<string, IReadOnlyList<StaticSourceBlueprint>> _staticSourcesByScene;

    internal CompiledGuide(CompiledGuideData data)
    {
        _nodes = data.Nodes;
        _edges = data.Edges;
        _forwardAdj = data.ForwardAdjacency;
        _reverseAdj = data.ReverseAdjacency;
        _questNodeIds = data.QuestNodeIds;
        _itemNodeIds = data.ItemNodeIds;
        _topoOrder = data.TopoOrder;
        _zoneNodeIds = data.ZoneNodeIds;
        _zoneAdj = data.ZoneAdjacency;
        _itemToQuestIndices = data.ItemToQuestIndices;
        _questToDependentQuestIndices = data.QuestToDependentQuestIndices;

        // Key-to-ID lookup
        _keyToId = new Dictionary<string, int>(_nodes.Length, StringComparer.Ordinal);
        for (int i = 0; i < _nodes.Length; i++)
            _keyToId[_nodes[i].Key] = i;

        // Project CompiledNodeData → Node
        _projectedNodes = new Node[_nodes.Length];
        for (int i = 0; i < _nodes.Length; i++)
            _projectedNodes[i] = ProjectNode(_nodes[i]);

        // Project CompiledEdgeData → Edge
        _projectedEdges = new Edge[_edges.Length];
        for (int i = 0; i < _edges.Length; i++)
            _projectedEdges[i] = ProjectEdge(_edges[i]);

        // Build quest spec arrays from DTO
        int questCount = data.QuestSpecs.Length;
        _prereqIds = new int[questCount][];
        _requiredItems = new ItemReq[questCount][];
        var stepsList = new List<StepEntry>();
        _stepOff = new int[questCount];
        _giverIds = new int[questCount][];
        _completerIds = new int[questCount][];
        _chainsToIds = new int[questCount][];
        _questFlags = new byte[questCount];

        for (int qi = 0; qi < questCount; qi++)
        {
            CompiledQuestSpecData spec = data.QuestSpecs[qi];
            _prereqIds[qi] = spec.PrereqQuestIds;
            _requiredItems[qi] = spec.RequiredItems
                .Select(r => new ItemReq(r.ItemId, r.Qty, r.Group))
                .ToArray();
            _stepOff[qi] = stepsList.Count;
            foreach (CompiledStepData step in spec.Steps)
            {
                stepsList.Add(new StepEntry((byte)step.StepType, step.TargetId, (byte)step.Ordinal));
            }
            _giverIds[qi] = spec.GiverNodeIds;
            _completerIds[qi] = spec.CompleterNodeIds;
            _chainsToIds[qi] = spec.ChainsToIds;
            _questFlags[qi] = spec.IsImplicit ? (byte)1 : (byte)0;
        }
        _steps = stepsList.ToArray();

        // Build item sources from DTO
        _itemSources = new SourceSiteEntry[data.ItemSources.Length][];
        for (int ii = 0; ii < data.ItemSources.Length; ii++)
        {
            CompiledSourceSiteData[] dtoSources = data.ItemSources[ii];
            var entries = new SourceSiteEntry[dtoSources.Length];
            for (int si = 0; si < dtoSources.Length; si++)
            {
                CompiledSourceSiteData s = dtoSources[si];
                var positions = s.Positions
                    .Select(p => new SpawnPositionEntry(p.SpawnId, p.X, p.Y, p.Z))
                    .ToArray();
                entries[si] = new SourceSiteEntry(
                    s.SourceId,
                    (byte)s.SourceType,
                    (byte)s.EdgeType,
                    s.DirectItemId,
                    s.Scene,
                    positions,
                    s.Keyword);
            }
            _itemSources[ii] = entries;
        }

        // Build unlock predicates from DTO
        _unlocks = new Dictionary<int, UnlockPredicateEntry>();
        foreach (CompiledUnlockPredicateData pred in data.UnlockPredicates)
        {
            var conditions = pred.Conditions
                .Select(c => new UnlockConditionEntry(c.SourceId, (byte)c.CheckType, (byte)c.Group))
                .ToArray();
            _unlocks[pred.TargetId] = new UnlockPredicateEntry(conditions, pred.GroupCount, (byte)pred.Semantics);
        }

        // Build blueprints from DTO
        _giverBlueprints = data.GiverBlueprints
            .Select(g => new QuestGiverEntry(
                g.QuestId,
                g.CharacterId,
                g.PositionId,
                (byte)g.InteractionType,
                g.Keyword,
                g.RequiredQuestDbNames))
            .ToArray();

        _completionBlueprints = data.CompletionBlueprints
            .Select(c => new QuestCompletion(
                c.QuestId,
                c.CharacterId,
                c.PositionId,
                (byte)c.InteractionType,
                c.Keyword))
            .ToArray();

        // Build infeasible bitset from DTO
        _infeasible = new bool[_nodes.Length];
        foreach (int nodeId in data.InfeasibleNodeIds)
        {
            if (nodeId >= 0 && nodeId < _infeasible.Length)
                _infeasible[nodeId] = true;
        }

        // --- Derived indexes ---

        // Node ID → quest/item index reverse lookups
        _nodeIdToQuestIndex = new Dictionary<int, int>(_questNodeIds.Length);
        for (int qi = 0; qi < _questNodeIds.Length; qi++)
            _nodeIdToQuestIndex[_questNodeIds[qi]] = qi;

        _nodeIdToItemIndex = new Dictionary<int, int>(_itemNodeIds.Length);
        for (int ii = 0; ii < _itemNodeIds.Length; ii++)
            _nodeIdToItemIndex[_itemNodeIds[ii]] = ii;

        // Nodes grouped by type
        _nodesByType = BuildNodesByType(_projectedNodes);

        // Quest nodes indexed by db_name
        _questsByDbName = BuildQuestsByDbName(_projectedNodes, _questNodeIds);

        // String-keyed dependency indexes
        _questKeysByItemKey = BuildQuestKeysByItemKey();
        _questKeysByQuestKey = BuildQuestKeysByQuestKey();

        // Scene-indexed blueprints (projected from int-ID blueprints)
        _questGiversByScene = BuildQuestGiversByScene();
        _questCompletionsByScene = BuildQuestCompletionsByScene();
        _staticSourcesByScene = BuildStaticSourcesByScene();

        // Scene name → user-facing zone display name
        _sceneToZoneDisplay = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        for (int i = 0; i < _zoneNodeIds.Length; i++)
        {
            var zoneNode = _projectedNodes[_zoneNodeIds[i]];
            if (!string.IsNullOrEmpty(zoneNode.Scene) && !string.IsNullOrEmpty(zoneNode.DisplayName))
                _sceneToZoneDisplay[zoneNode.Scene] = zoneNode.DisplayName;
        }

        // Source → quest key reverse index (from projected blueprints)
        _questKeysBySourceKey = BuildQuestKeysBySourceKey();
    }

    // ---------------------------------------------------------------
    // Counts
    // ---------------------------------------------------------------

    public int NodeCount => _nodes.Length;
    public int EdgeCount => _edges.Length;
    public int QuestCount => _questNodeIds.Length;
    public int ItemCount => _itemNodeIds.Length;

    // ---------------------------------------------------------------
    // Node access (int-indexed)
    // ---------------------------------------------------------------

    /// <summary>Returns the projected Node for the given node ID.</summary>
    public Node GetNode(int nodeId) => _projectedNodes[nodeId];

    public bool TryGetNodeId(string key, out int nodeId) => _keyToId.TryGetValue(key, out nodeId);

    public string GetNodeKey(int nodeId) => _nodes[nodeId].Key;

    public string GetDisplayName(int nodeId) => _projectedNodes[nodeId].DisplayName;

    public string? GetScene(int nodeId) => _projectedNodes[nodeId].Scene;

    public string? GetSourceScene(SourceSiteEntry source)
    {
        if (!string.IsNullOrWhiteSpace(source.Scene))
            return source.Scene;
        if (source.Positions.Length > 0)
            return GetScene(source.Positions[0].SpawnId);
        return GetScene(source.SourceId);
    }

    /// <summary>
    /// Translates a raw Unity scene name to the user-facing zone display name.
    /// Falls back to the raw name when no Zone node maps to that scene.
    /// </summary>
    public string? GetZoneDisplay(string? scene) =>
        string.IsNullOrEmpty(scene) ? null
        : _sceneToZoneDisplay.TryGetValue(scene, out string? display) ? display : scene;

    public string? GetDbName(int nodeId) => _nodes[nodeId].DbName;

    /// <summary>Returns the raw DTO node type as int for low-level consumers.</summary>
    public int GetNodeType(int nodeId) => _nodes[nodeId].NodeType;

    // ---------------------------------------------------------------
    // Node access (string-keyed, high-level API)
    // ---------------------------------------------------------------

    /// <summary>Returns the projected Node for the given key, or null if not found.</summary>
    public Node? GetNode(string key) =>
        _keyToId.TryGetValue(key, out int nodeId) ? _projectedNodes[nodeId] : null;

    /// <summary>Returns all projected nodes.</summary>
    public IReadOnlyList<Node> AllNodes => _projectedNodes;

    /// <summary>Returns all projected nodes of the given type.</summary>
    public IReadOnlyList<Node> NodesOfType(NodeType type) =>
        _nodesByType.TryGetValue(type, out var list) ? list : EmptyNodeList;

    /// <summary>Returns the quest node with the given db_name, or null.</summary>
    public Node? GetQuestByDbName(string dbName) =>
        _questsByDbName.TryGetValue(dbName, out var node) ? node : null;

    // ---------------------------------------------------------------
    // Edge access (int-indexed)
    // ---------------------------------------------------------------

    public ReadOnlySpan<int> ForwardEdgeIds(int nodeId) => _forwardAdj[nodeId];

    public ReadOnlySpan<int> ReverseEdgeIds(int nodeId) => _reverseAdj[nodeId];

    /// <summary>Returns the projected Edge for the given edge ID.</summary>
    public Edge GetEdge(int edgeId) => _projectedEdges[edgeId];

    // ---------------------------------------------------------------
    // Edge access (string-keyed, high-level API)
    // ---------------------------------------------------------------

    /// <summary>Returns all outgoing edges for the given node key.</summary>
    public IReadOnlyList<Edge> OutEdges(string key)
    {
        if (!_keyToId.TryGetValue(key, out int nodeId))
            return EmptyEdgeList;
        var edgeIds = _forwardAdj[nodeId];
        if (edgeIds.Length == 0)
            return EmptyEdgeList;
        var result = new Edge[edgeIds.Length];
        for (int i = 0; i < edgeIds.Length; i++)
            result[i] = _projectedEdges[edgeIds[i]];
        return result;
    }

    /// <summary>Returns outgoing edges of a specific type for the given node key.</summary>
    public IReadOnlyList<Edge> OutEdges(string key, EdgeType type)
    {
        if (!_keyToId.TryGetValue(key, out int nodeId))
            return EmptyEdgeList;
        var edgeIds = _forwardAdj[nodeId];
        if (edgeIds.Length == 0)
            return EmptyEdgeList;
        List<Edge>? result = null;
        for (int i = 0; i < edgeIds.Length; i++)
        {
            var edge = _projectedEdges[edgeIds[i]];
            if (edge.Type == type)
                (result ??= new List<Edge>()).Add(edge);
        }
        return result ?? EmptyEdgeList;
    }

    /// <summary>Returns incoming edges of a specific type for the given node key.</summary>
    public IReadOnlyList<Edge> InEdges(string key, EdgeType type)
    {
        if (!_keyToId.TryGetValue(key, out int nodeId))
            return EmptyEdgeList;
        var edgeIds = _reverseAdj[nodeId];
        if (edgeIds.Length == 0)
            return EmptyEdgeList;
        List<Edge>? result = null;
        for (int i = 0; i < edgeIds.Length; i++)
        {
            var edge = _projectedEdges[edgeIds[i]];
            if (edge.Type == type)
                (result ??= new List<Edge>()).Add(edge);
        }
        return result ?? EmptyEdgeList;
    }

    // ---------------------------------------------------------------
    // Quest spec access (int-indexed)
    // ---------------------------------------------------------------

    public int QuestNodeId(int questIndex) => _questNodeIds[questIndex];

    public ReadOnlySpan<int> PrereqQuestIds(int questIndex) => _prereqIds[questIndex];

    public ReadOnlySpan<ItemReq> RequiredItems(int questIndex) => _requiredItems[questIndex];

    public ReadOnlySpan<int> GiverIds(int questIndex) => _giverIds[questIndex];

    public ReadOnlySpan<int> CompleterIds(int questIndex) => _completerIds[questIndex];

    public ReadOnlySpan<int> ChainsToIds(int questIndex) => _chainsToIds[questIndex];

    public ReadOnlySpan<StepEntry> Steps(int questIndex)
    {
        int start = _stepOff[questIndex];
        int end = questIndex + 1 < _stepOff.Length ? _stepOff[questIndex + 1] : _steps.Length;
        return _steps.AsSpan(start, end - start);
    }

    public bool IsImplicit(int questIndex) => (_questFlags[questIndex] & 1) != 0;

    public bool IsInfeasibleNode(int nodeId) => nodeId >= 0 && nodeId < _infeasible.Length && _infeasible[nodeId];

    // ---------------------------------------------------------------
    // Item access (int-indexed)
    // ---------------------------------------------------------------

    public int ItemNodeId(int itemIndex) => _itemNodeIds[itemIndex];

    public ReadOnlySpan<SourceSiteEntry> GetItemSources(int itemIndex) =>
        itemIndex >= 0 && itemIndex < _itemSources.Length
            ? _itemSources[itemIndex].AsSpan()
            : ReadOnlySpan<SourceSiteEntry>.Empty;

    // ---------------------------------------------------------------
    // Unlock predicates
    // ---------------------------------------------------------------

    public bool TryGetUnlockPredicate(int nodeId, out UnlockPredicateEntry predicate) =>
        _unlocks.TryGetValue(nodeId, out predicate);

    // ---------------------------------------------------------------
    // Topological order and zone routing
    // ---------------------------------------------------------------

    public ReadOnlySpan<int> TopologicalOrder => _topoOrder;

    public ReadOnlySpan<int> ZoneNodeIds => _zoneNodeIds;

    public ReadOnlySpan<int> ZoneNeighbors(int zoneIndex) => _zoneAdj[zoneIndex];

    // ---------------------------------------------------------------
    // Dependency lookups (int-indexed)
    // ---------------------------------------------------------------

    public ReadOnlySpan<int> QuestsDependingOnItem(int itemIndex) => _itemToQuestIndices[itemIndex];

    public ReadOnlySpan<int> QuestsDependingOnQuest(int questIndex) => _questToDependentQuestIndices[questIndex];

    // ---------------------------------------------------------------
    // Dependency lookups (string-keyed, high-level API)
    // ---------------------------------------------------------------

    /// <summary>Returns quest keys that depend on the given item key.</summary>
    public IReadOnlyCollection<string> GetQuestsDependingOnItem(string itemKey) =>
        _questKeysByItemKey.TryGetValue(itemKey, out var quests) ? quests : EmptyKeySet;

    /// <summary>Returns quest keys that depend on the given quest key as a prerequisite.</summary>
    public IReadOnlyCollection<string> GetQuestsDependingOnQuest(string questKey) =>
        _questKeysByQuestKey.TryGetValue(questKey, out var quests) ? quests : EmptyKeySet;

    /// <summary>Returns quest keys whose giver/completion blueprints reference the given source key.</summary>
    public IReadOnlyCollection<string> GetQuestsTouchingSource(string sourceKey) =>
        _questKeysBySourceKey.TryGetValue(sourceKey, out var quests) ? quests : EmptyKeySet;

    // ---------------------------------------------------------------
    // Blueprint access (int-indexed, raw)
    // ---------------------------------------------------------------

    public ReadOnlySpan<QuestGiverEntry> GiverBlueprints => _giverBlueprints;

    public ReadOnlySpan<QuestCompletion> CompletionBlueprints => _completionBlueprints;

    // ---------------------------------------------------------------
    // Blueprint access (string-keyed, scene-indexed)
    // ---------------------------------------------------------------

    public IReadOnlyList<QuestGiverBlueprint> GetQuestGiversInScene(string scene) =>
        _questGiversByScene.TryGetValue(scene, out var list) ? list : EmptyGiverBlueprints;

    public IReadOnlyList<QuestCompletionBlueprint> GetQuestCompletionsInScene(string scene) =>
        _questCompletionsByScene.TryGetValue(scene, out var list) ? list : EmptyCompletionBlueprints;

    public IReadOnlyList<StaticSourceBlueprint> GetStaticSourcesInScene(string scene) =>
        _staticSourcesByScene.TryGetValue(scene, out var list) ? list : EmptyStaticBlueprints;

    // ---------------------------------------------------------------
    // Index lookup helpers
    // ---------------------------------------------------------------

    /// <summary>Returns the quest array index for a node ID, or -1.</summary>
    public int FindQuestIndex(int nodeId) =>
        _nodeIdToQuestIndex.TryGetValue(nodeId, out int qi) ? qi : -1;

    /// <summary>Returns the item array index for a node ID, or -1.</summary>
    public int FindItemIndex(int nodeId) =>
        _nodeIdToItemIndex.TryGetValue(nodeId, out int ii) ? ii : -1;

    // ---------------------------------------------------------------
    // Projection helpers
    // ---------------------------------------------------------------

    private Node ProjectNode(CompiledNodeData d)
    {
        var flags = (NodeFlags)d.Flags;
        return new Node
        {
            Key = d.Key,
            Type = (NodeType)d.NodeType,
            DisplayName = d.DisplayName,
            Scene = d.Scene,
            X = d.X,
            Y = d.Y,
            Z = d.Z,
            Level = d.Level != 0 ? d.Level : null,
            ZoneKey = d.ZoneKey,
            DbName = d.DbName,
            Description = d.Description,
            Keyword = d.Keyword,
            Zone = d.ZoneDisplay,
            XpReward = d.XpReward != 0 ? d.XpReward : null,
            GoldReward = d.GoldReward != 0 ? d.GoldReward : null,
            RewardItemKey = d.RewardItemKey,
            DisabledText = d.DisabledText,
            KeyItemKey = d.KeyItemKey,
            DestinationZoneKey = d.DestinationZoneKey,
            DestinationDisplay = d.DestinationDisplay,
            IsFriendly = flags.HasFlag(NodeFlags.IsFriendly),
            IsVendor = flags.HasFlag(NodeFlags.IsVendor),
            NightSpawn = flags.HasFlag(NodeFlags.NightSpawn),
            Implicit = flags.HasFlag(NodeFlags.Implicit),
            Repeatable = flags.HasFlag(NodeFlags.Repeatable),
            Disabled = flags.HasFlag(NodeFlags.Disabled),
            IsDirectlyPlaced = flags.HasFlag(NodeFlags.IsDirectlyPlaced),
            IsEnabled = flags.HasFlag(NodeFlags.IsEnabled),
            Invulnerable = flags.HasFlag(NodeFlags.Invulnerable),
            IsRare = flags.HasFlag(NodeFlags.IsRare),
            IsTriggerSpawn = flags.HasFlag(NodeFlags.IsTriggerSpawn),
        };
    }

    private Edge ProjectEdge(CompiledEdgeData d)
    {
        return new Edge
        {
            Source = _nodes[d.SourceId].Key,
            Target = _nodes[d.TargetId].Key,
            Type = (EdgeType)d.EdgeType,
            Group = d.Group,
            Ordinal = d.Ordinal != 0 ? d.Ordinal : null,
            Quantity = d.Quantity != 0 ? d.Quantity : null,
            Keyword = d.Keyword,
            Chance = d.Chance != 0 ? d.Chance / 100f : null,
            Note = d.Note,
            Amount = d.Amount != 0 ? d.Amount : null,
        };
    }

    // ---------------------------------------------------------------
    // Index construction
    // ---------------------------------------------------------------

    private static Dictionary<NodeType, IReadOnlyList<Node>> BuildNodesByType(Node[] nodes)
    {
        var map = new Dictionary<NodeType, List<Node>>();
        for (int i = 0; i < nodes.Length; i++)
        {
            var node = nodes[i];
            if (!map.TryGetValue(node.Type, out var list))
            {
                list = new List<Node>();
                map[node.Type] = list;
            }
            list.Add(node);
        }

        var result = new Dictionary<NodeType, IReadOnlyList<Node>>(map.Count);
        foreach (var pair in map)
            result[pair.Key] = pair.Value;
        return result;
    }

    private static Dictionary<string, Node> BuildQuestsByDbName(Node[] projectedNodes, int[] questNodeIds)
    {
        var map = new Dictionary<string, Node>(questNodeIds.Length, StringComparer.Ordinal);
        for (int qi = 0; qi < questNodeIds.Length; qi++)
        {
            var node = projectedNodes[questNodeIds[qi]];
            if (node.DbName != null)
                map[node.DbName] = node;
        }
        return map;
    }

    private Dictionary<string, IReadOnlyCollection<string>> BuildQuestKeysByItemKey()
    {
        var map = new Dictionary<string, HashSet<string>>(StringComparer.Ordinal);
        for (int ii = 0; ii < _itemNodeIds.Length; ii++)
        {
            string itemKey = _nodes[_itemNodeIds[ii]].Key;
            var questIndices = _itemToQuestIndices[ii];
            for (int q = 0; q < questIndices.Length; q++)
            {
                string questKey = _nodes[_questNodeIds[questIndices[q]]].Key;
                if (!map.TryGetValue(itemKey, out var set))
                {
                    set = new HashSet<string>(StringComparer.Ordinal);
                    map[itemKey] = set;
                }
                set.Add(questKey);
            }
        }
        return FreezeSetMap(map);
    }

    private Dictionary<string, IReadOnlyCollection<string>> BuildQuestKeysByQuestKey()
    {
        var map = new Dictionary<string, HashSet<string>>(StringComparer.Ordinal);
        for (int qi = 0; qi < _questNodeIds.Length; qi++)
        {
            string questKey = _nodes[_questNodeIds[qi]].Key;
            var dependentIndices = _questToDependentQuestIndices[qi];
            for (int d = 0; d < dependentIndices.Length; d++)
            {
                string dependentKey = _nodes[_questNodeIds[dependentIndices[d]]].Key;
                if (!map.TryGetValue(questKey, out var set))
                {
                    set = new HashSet<string>(StringComparer.Ordinal);
                    map[questKey] = set;
                }
                set.Add(dependentKey);
            }
        }
        return FreezeSetMap(map);
    }

    private Dictionary<string, IReadOnlyCollection<string>> BuildQuestKeysBySourceKey()
    {
        var map = new Dictionary<string, HashSet<string>>(StringComparer.Ordinal);

        for (int i = 0; i < _giverBlueprints.Length; i++)
        {
            var bp = _giverBlueprints[i];
            string sourceKey = _nodes[bp.PositionId].Key;
            string questKey = _nodes[bp.QuestId].Key;
            AddToSetMap(map, sourceKey, questKey);
        }

        for (int i = 0; i < _completionBlueprints.Length; i++)
        {
            var bp = _completionBlueprints[i];
            string sourceKey = _nodes[bp.PositionId].Key;
            string questKey = _nodes[bp.QuestId].Key;
            AddToSetMap(map, sourceKey, questKey);
        }

        return FreezeSetMap(map);
    }

    private Dictionary<string, IReadOnlyList<QuestGiverBlueprint>> BuildQuestGiversByScene()
    {
        var map = new Dictionary<string, List<QuestGiverBlueprint>>(StringComparer.OrdinalIgnoreCase);
        for (int i = 0; i < _giverBlueprints.Length; i++)
        {
            var bp = _giverBlueprints[i];
            var questNode = _projectedNodes[bp.QuestId];
            var positionNode = _projectedNodes[bp.PositionId];
            if (questNode.DbName == null || string.IsNullOrEmpty(positionNode.Scene))
                continue;

            var blueprint = new QuestGiverBlueprint(
                questNode.Key,
                questNode.DbName,
                questNode.DisplayName,
                _nodes[bp.CharacterId].Key,
                positionNode.Key,
                positionNode.Scene,
                new MarkerInteraction(
                    bp.InteractionType == 1 ? MarkerInteractionKind.SayKeyword : MarkerInteractionKind.TalkTo,
                    bp.Keyword),
                questNode.Repeatable,
                bp.RequiredQuestDbNames);

            if (!map.TryGetValue(positionNode.Scene, out var list))
            {
                list = new List<QuestGiverBlueprint>();
                map[positionNode.Scene] = list;
            }
            list.Add(blueprint);
        }

        return FreezeListMap(map);
    }

    private Dictionary<string, IReadOnlyList<QuestCompletionBlueprint>> BuildQuestCompletionsByScene()
    {
        var map = new Dictionary<string, List<QuestCompletionBlueprint>>(StringComparer.OrdinalIgnoreCase);
        for (int i = 0; i < _completionBlueprints.Length; i++)
        {
            var bp = _completionBlueprints[i];
            var questNode = _projectedNodes[bp.QuestId];
            var positionNode = _projectedNodes[bp.PositionId];
            if (questNode.DbName == null || string.IsNullOrEmpty(positionNode.Scene))
                continue;

            // The target (completer) character may differ from the position node
            var targetKey = _nodes[bp.CharacterId].Key;
            var blueprint = new QuestCompletionBlueprint(
                questNode.Key,
                questNode.DbName,
                questNode.DisplayName,
                targetKey,
                positionNode.Key,
                positionNode.Scene,
                new MarkerInteraction(
                    bp.InteractionType == 1 ? MarkerInteractionKind.SayKeyword : MarkerInteractionKind.TalkTo,
                    bp.Keyword),
                questNode.Repeatable);

            if (!map.TryGetValue(positionNode.Scene, out var list))
            {
                list = new List<QuestCompletionBlueprint>();
                map[positionNode.Scene] = list;
            }
            list.Add(blueprint);
        }

        return FreezeListMap(map);
    }

    private Dictionary<string, IReadOnlyList<StaticSourceBlueprint>> BuildStaticSourcesByScene()
    {
        var map = new Dictionary<string, List<StaticSourceBlueprint>>(StringComparer.OrdinalIgnoreCase);
        for (int i = 0; i < _projectedNodes.Length; i++)
        {
            var node = _projectedNodes[i];
            if (string.IsNullOrEmpty(node.Scene))
                continue;
            if (node.X == null && node.Y == null && node.Z == null)
                continue;
            if (node.Type is not (NodeType.MiningNode or NodeType.Water or NodeType.Forge
                or NodeType.ItemBag or NodeType.ZoneLine or NodeType.WorldObject))
                continue;

            if (!map.TryGetValue(node.Scene, out var list))
            {
                list = new List<StaticSourceBlueprint>();
                map[node.Scene] = list;
            }
            list.Add(new StaticSourceBlueprint(node.Key, node.Scene, node.Type));
        }

        return FreezeListMap(map);
    }

    private static void AddToSetMap(Dictionary<string, HashSet<string>> map, string key, string value)
    {
        if (!map.TryGetValue(key, out var set))
        {
            set = new HashSet<string>(StringComparer.Ordinal);
            map[key] = set;
        }
        set.Add(value);
    }

    private static Dictionary<string, IReadOnlyCollection<string>> FreezeSetMap(
        Dictionary<string, HashSet<string>> map)
    {
        var result = new Dictionary<string, IReadOnlyCollection<string>>(map.Count, map.Comparer);
        foreach (var pair in map)
            result[pair.Key] = pair.Value;
        return result;
    }

    private static Dictionary<string, IReadOnlyList<T>> FreezeListMap<T>(
        Dictionary<string, List<T>> map)
    {
        var result = new Dictionary<string, IReadOnlyList<T>>(map.Count, map.Comparer);
        foreach (var pair in map)
            result[pair.Key] = pair.Value;
        return result;
    }
}

public readonly struct ItemReq
{
    public ItemReq(int itemId, int quantity, int group)
    {
        ItemId = itemId;
        Quantity = quantity;
        Group = group;
    }

    public int ItemId { get; }
    public int Quantity { get; }
    public int Group { get; }
}

public readonly struct StepEntry
{
    public StepEntry(byte stepType, int targetId, byte ordinal)
    {
        StepType = stepType;
        TargetId = targetId;
        Ordinal = ordinal;
    }

    public byte StepType { get; }
    public int TargetId { get; }
    public byte Ordinal { get; }
}

public readonly struct SpawnPositionEntry
{
    public SpawnPositionEntry(int spawnId, float x, float y, float z)
    {
        SpawnId = spawnId;
        X = x;
        Y = y;
        Z = z;
    }

    public int SpawnId { get; }
    public float X { get; }
    public float Y { get; }
    public float Z { get; }
}

public readonly struct SourceSiteEntry
{
    public SourceSiteEntry(
        int sourceId,
        byte sourceType,
        byte edgeType,
        int directItemId,
        string? scene,
        SpawnPositionEntry[] positions,
        string? keyword)
    {
        SourceId = sourceId;
        SourceType = sourceType;
        EdgeType = edgeType;
        DirectItemId = directItemId;
        Scene = scene;
        Positions = positions;
        Keyword = keyword;
    }

    public int SourceId { get; }
    public byte SourceType { get; }
    public byte EdgeType { get; }
    public int DirectItemId { get; }
    public string? Scene { get; }
    public SpawnPositionEntry[] Positions { get; }
    public string? Keyword { get; }
}

public readonly struct UnlockConditionEntry
{
    public UnlockConditionEntry(int sourceId, byte checkType, byte group)
    {
        SourceId = sourceId;
        CheckType = checkType;
        Group = group;
    }

    public int SourceId { get; }
    public byte CheckType { get; }
    public byte Group { get; }
}

public readonly struct UnlockPredicateEntry
{
    public UnlockPredicateEntry(
        UnlockConditionEntry[] conditions,
        int groupCount,
        byte semantics)
    {
        Conditions = conditions;
        GroupCount = groupCount;
        Semantics = semantics;
    }

    public UnlockConditionEntry[] Conditions { get; }
    public int GroupCount { get; }
    public byte Semantics { get; }
}

public readonly struct QuestGiverEntry
{
    public QuestGiverEntry(
        int questId,
        int characterId,
        int positionId,
        byte interactionType,
        string? keyword,
        string[] requiredQuestDbNames)
    {
        QuestId = questId;
        CharacterId = characterId;
        PositionId = positionId;
        InteractionType = interactionType;
        Keyword = keyword;
        RequiredQuestDbNames = requiredQuestDbNames;
    }

    public int QuestId { get; }
    public int CharacterId { get; }
    public int PositionId { get; }
    public byte InteractionType { get; }
    public string? Keyword { get; }
    public string[] RequiredQuestDbNames { get; }
}

public readonly struct QuestCompletion
{
    public QuestCompletion(int questId, int characterId, int positionId, byte interactionType, string? keyword)
    {
        QuestId = questId;
        CharacterId = characterId;
        PositionId = positionId;
        InteractionType = interactionType;
        Keyword = keyword;
    }

    public int QuestId { get; }
    public int CharacterId { get; }
    public int PositionId { get; }
    public byte InteractionType { get; }
    public string? Keyword { get; }
}
