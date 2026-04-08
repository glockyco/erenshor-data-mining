using System.Text;

namespace AdventureGuide.CompiledGuide;

public sealed class CompiledGuide
{
    private readonly byte[] _stringTable;
    private readonly NodeRecord[] _nodes;
    private readonly Dictionary<string, int> _keyToId;
    private readonly EdgeRecord[] _edges;
    private readonly int[] _fwdOff;
    private readonly int[] _fwdVal;
    private readonly int[] _revOff;
    private readonly int[] _revVal;
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
    private readonly int[] _i2qOff;
    private readonly int[] _i2qVal;
    private readonly int[] _q2qOff;
    private readonly int[] _q2qVal;
    private readonly int[] _zoneNodeIds;
    private readonly int[] _zoneAdjOff;
    private readonly int[] _zoneAdjVal;
    private readonly QuestGiverEntry[] _giverBlueprints;
    private readonly QuestCompletion[] _completionBlueprints;
    private readonly bool[] _infeasible;

    internal CompiledGuide(
        byte[] stringTable,
        NodeRecord[] nodes,
        Dictionary<string, int> keyToId,
        EdgeRecord[] edges,
        int[] fwdOff,
        int[] fwdVal,
        int[] revOff,
        int[] revVal,
        int[] questNodeIds,
        int[][] prereqIds,
        ItemReq[][] requiredItems,
        StepEntry[] steps,
        int[] stepOff,
        int[][] giverIds,
        int[][] completerIds,
        int[][] chainsToIds,
        byte[] questFlags,
        int[] itemNodeIds,
        SourceSiteEntry[][] itemSources,
        Dictionary<int, UnlockPredicateEntry> unlocks,
        int[] topoOrder,
        int[] i2qOff,
        int[] i2qVal,
        int[] q2qOff,
        int[] q2qVal,
        int[] zoneNodeIds,
        int[] zoneAdjOff,
        int[] zoneAdjVal,
        QuestGiverEntry[] giverBlueprints,
        QuestCompletion[] completionBlueprints,
        bool[] infeasible)
    {
        _stringTable = stringTable;
        _nodes = nodes;
        _keyToId = keyToId;
        _edges = edges;
        _fwdOff = fwdOff;
        _fwdVal = fwdVal;
        _revOff = revOff;
        _revVal = revVal;
        _questNodeIds = questNodeIds;
        _prereqIds = prereqIds;
        _requiredItems = requiredItems;
        _steps = steps;
        _stepOff = stepOff;
        _giverIds = giverIds;
        _completerIds = completerIds;
        _chainsToIds = chainsToIds;
        _questFlags = questFlags;
        _itemNodeIds = itemNodeIds;
        _itemSources = itemSources;
        _unlocks = unlocks;
        _topoOrder = topoOrder;
        _i2qOff = i2qOff;
        _i2qVal = i2qVal;
        _q2qOff = q2qOff;
        _q2qVal = q2qVal;
        _zoneNodeIds = zoneNodeIds;
        _zoneAdjOff = zoneAdjOff;
        _zoneAdjVal = zoneAdjVal;
        _giverBlueprints = giverBlueprints;
        _completionBlueprints = completionBlueprints;
        _infeasible = infeasible;
    }

    public int NodeCount => _nodes.Length;
    public int EdgeCount => _edges.Length;
    public int QuestCount => _questNodeIds.Length;
    public int ItemCount => _itemNodeIds.Length;

    public string GetString(uint offset)
    {
        if (offset == 0)
        {
            return string.Empty;
        }

        int end = (int)offset;
        while (end < _stringTable.Length && _stringTable[end] != 0)
        {
            end++;
        }

        return Encoding.UTF8.GetString(_stringTable, (int)offset, end - (int)offset);
    }

    public ref readonly NodeRecord GetNode(int nodeId) => ref _nodes[nodeId];

    public bool TryGetNodeId(string key, out int nodeId) => _keyToId.TryGetValue(key, out nodeId);

    public string GetNodeKey(int nodeId) => GetString(_nodes[nodeId].KeyOffset);

    public string GetDisplayName(int nodeId) => GetString(_nodes[nodeId].DisplayNameOffset);

    public string? GetScene(int nodeId)
    {
        uint offset = _nodes[nodeId].SceneOffset;
        return offset == 0 ? null : GetString(offset);
    }

    public ref readonly EdgeRecord GetEdge(int edgeId) => ref _edges[edgeId];

    public ReadOnlySpan<int> ForwardEdgeIds(int nodeId) =>
        _fwdVal.AsSpan(_fwdOff[nodeId], _fwdOff[nodeId + 1] - _fwdOff[nodeId]);

    public ReadOnlySpan<int> ReverseEdgeIds(int nodeId) =>
        _revVal.AsSpan(_revOff[nodeId], _revOff[nodeId + 1] - _revOff[nodeId]);

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

    public ReadOnlySpan<int> QuestsDependingOnItem(int itemIndex) =>
        _i2qVal.AsSpan(_i2qOff[itemIndex], _i2qOff[itemIndex + 1] - _i2qOff[itemIndex]);

    public ReadOnlySpan<int> QuestsDependingOnQuest(int questIndex) =>
        _q2qVal.AsSpan(_q2qOff[questIndex], _q2qOff[questIndex + 1] - _q2qOff[questIndex]);

    public ReadOnlySpan<int> ZoneNodeIds => _zoneNodeIds;

    public ReadOnlySpan<int> ZoneNeighbors(int zoneIndex) =>
        _zoneAdjVal.AsSpan(_zoneAdjOff[zoneIndex], _zoneAdjOff[zoneIndex + 1] - _zoneAdjOff[zoneIndex]);

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
    public QuestCompletion(int questId, int characterId, int positionId)
    {
        QuestId = questId;
        CharacterId = characterId;
        PositionId = positionId;
    }

    public int QuestId { get; }
    public int CharacterId { get; }
    public int PositionId { get; }
}
