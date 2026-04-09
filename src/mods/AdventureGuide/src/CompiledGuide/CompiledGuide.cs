namespace AdventureGuide.CompiledGuide;

public sealed class CompiledGuide
{
    private readonly CompiledNodeData[] _nodes;
    private readonly Dictionary<string, int> _keyToId;
    private readonly CompiledEdgeData[] _edges;
    private readonly int[][] _forwardAdj;
    private readonly int[][] _reverseAdj;
    private readonly int[] _questNodeIds;
    private readonly int[][] _prereqIds;
    private readonly ItemReq[][] _requiredItems;
    private readonly StepEntry[] _steps;
    private readonly int[] _stepOff;
    private readonly int[][] _giverIds;
    private readonly int[][] _completerIds;
    private readonly int[][] _chainsToIds;
    private readonly byte[] _questFlags;
    private readonly int[] _itemNodeIds;
    private readonly SourceSiteEntry[][] _itemSources;
    private readonly Dictionary<int, UnlockPredicateEntry> _unlocks;
    private readonly int[] _topoOrder;
    private readonly int[][] _itemToQuestIndices;
    private readonly int[][] _questToDependentQuestIndices;
    private readonly int[] _zoneNodeIds;
    private readonly int[][] _zoneAdj;
    private readonly QuestGiverEntry[] _giverBlueprints;
    private readonly QuestCompletion[] _completionBlueprints;
    private readonly bool[] _infeasible;

    internal CompiledGuide(CompiledGuideData data)
    {
        _nodes = data.Nodes;
        _edges = data.Edges;

        _keyToId = new Dictionary<string, int>(_nodes.Length, StringComparer.Ordinal);
        for (int i = 0; i < _nodes.Length; i++)
        {
            _keyToId[_nodes[i].Key] = i;
        }

        _forwardAdj = data.ForwardAdjacency;
        _reverseAdj = data.ReverseAdjacency;
        _questNodeIds = data.QuestNodeIds;
        _itemNodeIds = data.ItemNodeIds;
        _topoOrder = data.TopoOrder;
        _zoneNodeIds = data.ZoneNodeIds;
        _zoneAdj = data.ZoneAdjacency;
        _itemToQuestIndices = data.ItemToQuestIndices;
        _questToDependentQuestIndices = data.QuestToDependentQuestIndices;

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
                    positions);
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
    }

    public int NodeCount => _nodes.Length;
    public int EdgeCount => _edges.Length;
    public int QuestCount => _questNodeIds.Length;
    public int ItemCount => _itemNodeIds.Length;

    public CompiledNodeData GetNode(int nodeId) => _nodes[nodeId];

    public bool TryGetNodeId(string key, out int nodeId) => _keyToId.TryGetValue(key, out nodeId);

    public string GetNodeKey(int nodeId) => _nodes[nodeId].Key;

    public string GetDisplayName(int nodeId) => _nodes[nodeId].DisplayName;

    public string? GetScene(int nodeId) => _nodes[nodeId].Scene;

    public string? GetDbName(int nodeId) => _nodes[nodeId].DbName;

    public ReadOnlySpan<int> ForwardEdgeIds(int nodeId) => _forwardAdj[nodeId];

    public ReadOnlySpan<int> ReverseEdgeIds(int nodeId) => _reverseAdj[nodeId];

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

    public int ItemNodeId(int itemIndex) => _itemNodeIds[itemIndex];

    public ReadOnlySpan<SourceSiteEntry> GetItemSources(int itemIndex) =>
        itemIndex >= 0 && itemIndex < _itemSources.Length
            ? _itemSources[itemIndex].AsSpan()
            : ReadOnlySpan<SourceSiteEntry>.Empty;

    public bool TryGetUnlockPredicate(int nodeId, out UnlockPredicateEntry predicate) =>
        _unlocks.TryGetValue(nodeId, out predicate);

    public ReadOnlySpan<int> TopologicalOrder => _topoOrder;

    public ReadOnlySpan<int> QuestsDependingOnItem(int itemIndex) => _itemToQuestIndices[itemIndex];

    public ReadOnlySpan<int> QuestsDependingOnQuest(int questIndex) => _questToDependentQuestIndices[questIndex];

    public ReadOnlySpan<int> ZoneNodeIds => _zoneNodeIds;

    public ReadOnlySpan<int> ZoneNeighbors(int zoneIndex) => _zoneAdj[zoneIndex];

    public ReadOnlySpan<QuestGiverEntry> GiverBlueprints => _giverBlueprints;

    public ReadOnlySpan<QuestCompletion> CompletionBlueprints => _completionBlueprints;
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
        SpawnPositionEntry[] positions)
    {
        SourceId = sourceId;
        SourceType = sourceType;
        EdgeType = edgeType;
        DirectItemId = directItemId;
        Scene = scene;
        Positions = positions;
    }

    public int SourceId { get; }
    public byte SourceType { get; }
    public byte EdgeType { get; }
    public int DirectItemId { get; }
    public string? Scene { get; }
    public SpawnPositionEntry[] Positions { get; }
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
